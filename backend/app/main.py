"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
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
from app.services.interview_service import InterviewService
from app.services.material_import_service import MaterialImportService
from app.services.practice_service import PracticeService
from app.services.question_bank_service import QuestionBankService
from app.services.report_worker import ReportWorker

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]


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
    report_worker = ReportWorker(repo=repo)
    material_import_service = MaterialImportService(repo_root=REPO_ROOT)
    audit_service = AuditService()
    auth_service = AuthService(repo=repo, audit_service=audit_service)
    question_bank_service = QuestionBankService(
        repo=repo,
        import_service=material_import_service,
        repo_root=REPO_ROOT,
    )
    app.state.repo = repo
    app.state.report_worker = report_worker
    app.state.material_import_service = material_import_service
    app.state.audit_service = audit_service
    app.state.auth_service = auth_service
    app.state.question_bank_service = question_bank_service
    app.state.interview_service = InterviewService(repo=repo, report_worker=report_worker)
    app.state.practice_service = PracticeService(repo=repo)
    logger.info("应用启动完成，数据库与服务已初始化")
    yield
    await material_import_service.shutdown()
    await report_worker.shutdown()
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
