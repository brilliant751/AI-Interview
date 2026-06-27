"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import ApiError, api_error_handler
from app.core.logging_setup import setup_resume_context_logger
from app.repositories.interview_repository import InterviewRepository
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.code_execution_service import CodeExecutionService
from app.services.coding_practice_service import CodingPracticeService
from app.services.interview_service import InterviewService
from app.services.interview_schedule_service import InterviewScheduleService
from app.services.material_import_service import MaterialImportService
from app.services.practice_service import PracticeService
from app.services.question_bank_service import QuestionBankService
from app.services.report_worker import ReportWorker
from app.services.turn_worker import TurnWorker

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]

# 启动入口承担“依赖装配层”的职责：
# 1. 只在这里创建数据库仓储和各类服务，避免路由层重复初始化。
# 2. 将实例挂到 app.state，FastAPI 的 Depends 再从 request.app.state 取用。
# 3. 启动时同步内置题库，关闭时统一释放后台 worker 和导入服务资源。
# 4. 这里不写具体业务流程，业务规则继续下沉到 service/repository 中。
# 5. 这样可以让测试直接替换 app.state 上的对象，减少对真实外部服务的依赖。


def _bootstrap_coding_questions(repo: InterviewRepository, repo_root: Path) -> None:
    """启动时幂等同步内置编程题到数据库。"""
    material_path = repo_root / "backend" / "assets" / "material" / "coding" / "programming_practice_questions.json"
    if not material_path.exists():
        logger.warning("编程题材料文件不存在，跳过启动同步: path=%s", material_path)
        return
    try:
        # 这里使用 upsert 而不是简单 insert，是为了允许题库文件反复导入。
        # 本地开发、CI 初始化、生产重启都会走同一段逻辑，幂等能避免重复题目。
        # 题库文件仍然是来源事实，数据库只保存接口查询和做题流程需要的结构化副本。
        rows = json.loads(material_path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("编程题材料文件格式错误")
        for row in rows:
            repo.upsert_coding_question(row)
        logger.info("编程题材料同步完成，count=%s", len(rows))
    except Exception as exc:
        logger.exception("编程题材料同步失败: %s", exc)
        raise


def _find_allowed_methods(app: FastAPI, path: str) -> list[str]:
    """根据请求路径匹配可用方法列表。"""
    methods: set[str] = set()
    for route in app.router.routes:
        route_methods = getattr(route, "methods", None)
        route_regex = getattr(route, "path_regex", None)
        if not route_methods or not route_regex:
            continue
        if route_regex.match(path):
            methods.update(route_methods)
    methods.discard("HEAD")
    methods.discard("OPTIONS")
    return sorted(methods)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：初始化仓储与服务。"""
    settings = get_settings()
    repo = InterviewRepository(db_path=settings.db_path)
    repo.init_schema()
    _bootstrap_coding_questions(repo=repo, repo_root=REPO_ROOT)

    # 后台 worker 放在应用级生命周期中管理，保证一个进程内只有一套队列消费。
    # ReportWorker 负责面试结束后的报告生成，TurnWorker 负责单轮回答的异步处理。
    # 两者都依赖同一个仓储实例，避免不同连接之间读写时序不一致。
    report_worker = ReportWorker(repo=repo)
    turn_worker = TurnWorker(repo=repo)
    material_import_service = MaterialImportService(repo_root=REPO_ROOT)
    audit_service = AuditService()
    auth_service = AuthService(repo=repo, audit_service=audit_service)
    question_bank_service = QuestionBankService(
        repo=repo,
        import_service=material_import_service,
        repo_root=REPO_ROOT,
    )
    code_execution_service = CodeExecutionService()

    # app.state 是本项目的轻量依赖容器。
    # 路由层只负责协议转换，真正的鉴权、状态推进、题目生成都委托给这些服务。
    # 这种写法比在每个接口里 new Service 更容易保证缓存、worker 和数据库连接复用。
    app.state.repo = repo
    app.state.report_worker = report_worker
    app.state.turn_worker = turn_worker
    app.state.material_import_service = material_import_service
    app.state.audit_service = audit_service
    app.state.auth_service = auth_service
    app.state.question_bank_service = question_bank_service
    app.state.code_execution_service = code_execution_service
    interview_service = InterviewService(repo=repo, report_worker=report_worker, turn_worker=turn_worker)
    app.state.interview_service = interview_service
    app.state.interview_schedule_service = InterviewScheduleService(
        repo=repo,
        interview_service=interview_service,
        settings=settings,
    )
    app.state.practice_service = PracticeService(repo=repo)
    app.state.coding_practice_service = CodingPracticeService(repo=repo, execution_service=code_execution_service)
    logger.info("应用启动完成，数据库与服务已初始化")
    yield
    await material_import_service.shutdown()
    await report_worker.shutdown()
    await turn_worker.shutdown()
    logger.info("应用关闭完成，资源已释放")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    settings = get_settings()
    resume_log_file = setup_resume_context_logger(REPO_ROOT)
    logger.info("简历上下文日志已初始化: path=%s", resume_log_file)
    app = FastAPI(
        title=settings.app_name,
        version="v1",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Idempotency-Key"],
    )
    app.add_exception_handler(ApiError, api_error_handler)

    @app.middleware("http")
    async def log_api_requests(request: Request, call_next):
        """记录 API 请求日志，并在 405 时输出路由方法提示。"""
        # 中间件只记录可观测信息，不改写请求和响应。
        # 405 时额外输出同一路径支持的方法，便于前端定位“路径正确但方法错了”的问题。
        # 对非 /api/ 路径保持安静，避免静态资源或健康检查把日志刷满。
        started_at = time.perf_counter()
        response = await call_next(request)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        path = request.url.path
        if path.startswith("/api/"):
            client = request.client.host if request.client else "-"
            logger.info(
                "接口访问日志: method=%s path=%s status=%s latency_ms=%s client=%s",
                request.method,
                path,
                response.status_code,
                latency_ms,
                client,
            )
            if response.status_code == 405:
                allowed_methods = _find_allowed_methods(app, path)
                logger.warning(
                    "接口方法不支持: method=%s path=%s status=%s 支持方法=%s",
                    request.method,
                    path,
                    response.status_code,
                    ",".join(allowed_methods) if allowed_methods else "未知",
                )
        return response

    app.include_router(api_router)
    return app


app = create_app()
