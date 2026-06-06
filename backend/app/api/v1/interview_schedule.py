"""面试预约接口。"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.core.security import AuthContext, require_user
from app.models.schemas import (
    InterviewScheduleCancelRequest,
    InterviewScheduleCancelResponse,
    InterviewScheduleCreateRequest,
    InterviewScheduleCreateResponse,
    InterviewScheduleDetailResponse,
    InterviewScheduleListItem,
    InterviewScheduleListResponse,
    InterviewScheduleStartResponse,
)
from app.repositories.interview_repository import InterviewRepository
from app.services.interview_schedule_service import InterviewScheduleService

router = APIRouter(prefix="/interview-schedules", tags=["interview-schedules"])


def get_repo(request: Request) -> InterviewRepository:
    """从应用状态获取仓储对象。"""
    return request.app.state.repo


def get_service(request: Request) -> InterviewScheduleService:
    """从应用状态获取预约服务。"""
    return request.app.state.interview_schedule_service


@router.post("", response_model=InterviewScheduleCreateResponse, status_code=201)
async def create_interview_schedule(
    payload: InterviewScheduleCreateRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    auth: AuthContext = Depends(require_user),
    service: InterviewScheduleService = Depends(get_service),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewScheduleCreateResponse:
    """创建单次模拟面试预约。"""
    endpoint = "POST:/interview-schedules"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return InterviewScheduleCreateResponse(**json.loads(cached))
    result = service.create_schedule(payload.model_dump(), user_id=auth.user_id)
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, json.dumps(result, ensure_ascii=False))
    return InterviewScheduleCreateResponse(**result)


@router.get("", response_model=InterviewScheduleListResponse)
async def list_interview_schedules(
    status: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    auth: AuthContext = Depends(require_user),
    service: InterviewScheduleService = Depends(get_service),
) -> InterviewScheduleListResponse:
    """查询当前用户预约列表。"""
    result = service.list_schedules(
        user_id=auth.user_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return InterviewScheduleListResponse(
        items=[InterviewScheduleListItem(**item) for item in result["items"]],
        page=result["page"],
        page_size=result["page_size"],
        total=result["total"],
    )


@router.get("/{schedule_id}", response_model=InterviewScheduleDetailResponse)
async def get_interview_schedule_detail(
    schedule_id: str,
    auth: AuthContext = Depends(require_user),
    service: InterviewScheduleService = Depends(get_service),
) -> InterviewScheduleDetailResponse:
    """查询单个预约详情。"""
    return InterviewScheduleDetailResponse(**service.get_schedule_detail(schedule_id, user_id=auth.user_id))


@router.post("/{schedule_id}/cancel", response_model=InterviewScheduleCancelResponse)
async def cancel_interview_schedule(
    schedule_id: str,
    payload: InterviewScheduleCancelRequest,
    auth: AuthContext = Depends(require_user),
    service: InterviewScheduleService = Depends(get_service),
) -> InterviewScheduleCancelResponse:
    """取消预约。"""
    return InterviewScheduleCancelResponse(**service.cancel_schedule(schedule_id, user_id=auth.user_id, reason=payload.reason))


@router.post("/{schedule_id}/start", response_model=InterviewScheduleStartResponse)
async def start_interview_schedule(
    schedule_id: str,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    auth: AuthContext = Depends(require_user),
    service: InterviewScheduleService = Depends(get_service),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewScheduleStartResponse:
    """开始预约面试。"""
    endpoint = f"POST:/interview-schedules/{schedule_id}/start"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return InterviewScheduleStartResponse(**json.loads(cached))
    result = service.start_schedule(schedule_id, user_id=auth.user_id)
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, json.dumps(result, ensure_ascii=False))
    return InterviewScheduleStartResponse(**result)


@router.get("/{schedule_id}/calendar.ics")
async def download_interview_schedule_calendar(
    schedule_id: str,
    auth: AuthContext = Depends(require_user),
    service: InterviewScheduleService = Depends(get_service),
) -> Response:
    """下载预约日历文件。"""
    content = service.build_calendar_content(schedule_id, user_id=auth.user_id)
    return Response(
        content=content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{schedule_id}.ics"'},
    )
