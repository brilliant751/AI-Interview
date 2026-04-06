"""管理端数据导入与健康检查接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, status

from app.core.security import require_admin
from app.models.schemas import (
    MaterialImportRequest,
    MaterialImportTaskResponse,
    MaterialImportTriggerResponse,
)
from app.services.interview_service import InterviewService
from app.services.material_import_service import MaterialImportService

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_import_service(request: Request) -> MaterialImportService:
    """获取应用级导入任务服务。"""
    return request.app.state.material_import_service


def _get_interview_service(request: Request) -> InterviewService:
    """从应用状态获取面试服务。"""
    return request.app.state.interview_service


@router.post(
    "/imports/materials",
    response_model=MaterialImportTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_materials(
    request: MaterialImportRequest,
    raw_request: Request,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    _: str = Depends(require_admin),
) -> MaterialImportTriggerResponse:
    """触发材料导入异步任务。"""
    service = _get_import_service(raw_request)
    return await service.trigger(payload=request, idempotency_key=x_idempotency_key)


@router.get(
    "/imports/materials/{task_id}",
    response_model=MaterialImportTaskResponse,
)
async def get_import_task(task_id: str, request: Request, _: str = Depends(require_admin)) -> MaterialImportTaskResponse:
    """查询材料导入任务状态。"""
    service = _get_import_service(request)
    return service.get_task(task_id)


@router.get("/providers/health")
async def provider_health(
    _: str = Depends(require_admin),
    service: InterviewService = Depends(_get_interview_service),
) -> dict:
    """查询语音与 LLM provider 健康状态。"""
    return service.provider_health()
