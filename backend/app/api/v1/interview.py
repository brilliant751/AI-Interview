"""面试流程接口。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, Request

from app.core.security import require_user
from app.core.errors import ApiError
from app.models.schemas import (
    InterviewCreateRequest,
    InterviewCreateResponse,
    InterviewFinishResponse,
    InterviewStatusResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
)
from app.services.interview_service import InterviewService
from app.repositories.interview_repository import InterviewRepository

router = APIRouter(prefix="/interviews", tags=["interviews"])


def get_service(request: Request) -> InterviewService:
    """从应用状态获取面试服务。"""
    return request.app.state.interview_service


def get_repo(request: Request) -> InterviewRepository:
    """从应用状态获取仓储对象。"""
    return request.app.state.repo


@router.post("", response_model=InterviewCreateResponse)
async def create_interview(
    payload: InterviewCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    _: str = Depends(require_user),
    service: InterviewService = Depends(get_service),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewCreateResponse:
    """创建新的面试会话。"""
    endpoint = "POST:/interviews"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return InterviewCreateResponse(**json.loads(cached))
    result = service.create_session(payload.model_dump())
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, json.dumps(result, ensure_ascii=False))
    return InterviewCreateResponse(**result)


@router.post("/{interview_id}/turns", response_model=InterviewTurnResponse)
async def submit_turn(
    interview_id: str,
    payload: InterviewTurnRequest,
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    _: str = Depends(require_user),
    service: InterviewService = Depends(get_service),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewTurnResponse:
    """提交单轮回答并获取下一题。"""
    endpoint = f"POST:/interviews/{interview_id}/turns"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return InterviewTurnResponse(**json.loads(cached))
    result = service.submit_turn(interview_id, payload.model_dump())
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, json.dumps(result, ensure_ascii=False))
    return InterviewTurnResponse(**result)


@router.post("/{interview_id}/finish", response_model=InterviewFinishResponse, status_code=202)
async def finish_interview(
    interview_id: str,
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    _: str = Depends(require_user),
    service: InterviewService = Depends(get_service),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewFinishResponse:
    """结束面试并触发报告生成。"""
    endpoint = f"POST:/interviews/{interview_id}/finish"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return InterviewFinishResponse(**json.loads(cached))
    result = service.finish_interview(interview_id)
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, json.dumps(result, ensure_ascii=False))
    return InterviewFinishResponse(**result)


@router.get("/{interview_id}/status", response_model=InterviewStatusResponse)
async def get_interview_status(
    interview_id: str,
    _: str = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewStatusResponse:
    """查询会话当前状态。"""
    session = repo.get_session(interview_id)
    if not session:
        raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
    return InterviewStatusResponse(
        interview_id=interview_id,
        status=session["status"],
        current_stage=session["current_stage"],
        follow_up_count=int(session["follow_up_count"]),
        technical_count=int(session.get("technical_count", 0)),
    )
