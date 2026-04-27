"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import ApiError, api_error_handler
from app.repositories.interview_repository import InterviewRepository
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.interview_service import InterviewService
from app.services.material_import_service import MaterialImportService
from app.services.report_worker import ReportWorker

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]


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
    app.state.repo = repo
    app.state.report_worker = report_worker
    app.state.material_import_service = material_import_service
    app.state.audit_service = audit_service
    app.state.auth_service = auth_service
    app.state.interview_service = InterviewService(repo=repo, report_worker=report_worker)
    logger.info("应用启动完成，数据库与服务已初始化")
    yield
    await material_import_service.shutdown()
    await report_worker.shutdown()
    logger.info("应用关闭完成，资源已释放")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="v1",
        lifespan=lifespan,
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(api_router)
    return app


app = create_app()
