"""管理端数据导入与健康检查接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, status

from app.core.security import require_admin
from app.models.schemas import (
    MaterialImportRequest,
    MaterialImportTaskResponse,
    MaterialImportTriggerResponse,
    ProviderHealthResponse,
)
from app.services.interview_service import InterviewService
from app.services.material_import_service import MaterialImportService

router = APIRouter(prefix="/admin", tags=["admin"])

# 管理端接口只面向管理员：
# 1. 材料导入通常耗时较长，因此返回 202 和 task_id，前端轮询任务状态。
# 2. provider health 用来展示 LLM/ASR/TTS/Embedding 等外部能力的可用性。
# 3. 这里不直接执行脚本细节，导入编排交给 MaterialImportService。
# 4. require_admin 是硬边界，普通用户不能触发全局材料重建。


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


@router.get(
    "/providers/health",
    response_model=ProviderHealthResponse,
    openapi_extra={"security": []},
)
async def provider_health(
    service: InterviewService = Depends(_get_interview_service),
) -> ProviderHealthResponse:
    """查询语音与 LLM provider 健康状态。"""
    return ProviderHealthResponse(**service.provider_health())
