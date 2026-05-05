"""面试流程接口。"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile

from app.core.security import require_user
from app.core.errors import ApiError
from app.core.security import AuthContext
from app.models.schemas import (
    InterviewCreateRequest,
    InterviewCreateResponse,
    InterviewFinishResponse,
    InterviewPlaybackMeta,
    InterviewPlaybackResponse,
    InterviewPlaybackResume,
    InterviewPlaybackTurn,
    InterviewStatusResponse,
    InterviewTurnRequest,
    InterviewTurnItemResponse,
    InterviewTurnResponse,
    InterviewTurnsResponse,
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
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    auth: AuthContext = Depends(require_user),
    service: InterviewService = Depends(get_service),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewCreateResponse:
    """创建新的面试会话。"""
    endpoint = "POST:/interviews"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return InterviewCreateResponse(**json.loads(cached))
    result = service.create_session(payload.model_dump(), user_id=auth.user_id)
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, json.dumps(result, ensure_ascii=False))
    return InterviewCreateResponse(**result)


@router.post("/{interview_id}/turns", response_model=InterviewTurnResponse)
async def submit_turn(
    interview_id: str,
    payload: InterviewTurnRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    auth: AuthContext = Depends(require_user),
    service: InterviewService = Depends(get_service),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewTurnResponse:
    """提交单轮回答并获取下一题。"""
    endpoint = f"POST:/interviews/{interview_id}/turns"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return InterviewTurnResponse(**json.loads(cached))
    result = service.submit_turn(interview_id, payload.model_dump(), user_id=auth.user_id)
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, json.dumps(result, ensure_ascii=False))
    return InterviewTurnResponse(**result)


@router.get("/{interview_id}/turns", response_model=InterviewTurnsResponse)
async def list_turns(
    interview_id: str,
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewTurnsResponse:
    """查询会话已提交轮次列表。"""
    session = repo.get_session(interview_id)
    if not session:
        raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
    if str(session.get("user_id") or "") != auth.user_id:
        raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
    turns = repo.list_turns(interview_id)
    items: list[InterviewTurnItemResponse] = []
    for turn in turns:
        degrade_flags: list[str] = []
        raw_flags = turn.get("degrade_flags")
        if isinstance(raw_flags, str) and raw_flags.strip():
            try:
                parsed_flags = json.loads(raw_flags)
                if isinstance(parsed_flags, list):
                    degrade_flags = [str(flag) for flag in parsed_flags]
            except Exception:
                degrade_flags = []
        elif isinstance(raw_flags, list):
            degrade_flags = [str(flag) for flag in raw_flags]
        items.append(
            InterviewTurnItemResponse(
                turn_id=turn["turn_id"],
                interview_id=turn["interview_id"],
                stage=turn["stage"],
                answer_text=turn["answer_text"],
                next_question=turn["next_question"],
                live_score=int(turn["live_score"]),
                generation_mode=str(turn.get("generation_mode") or "mock"),
                input_source=turn.get("input_source"),
                asr_provider=turn.get("asr_provider"),
                llm_provider=turn.get("llm_provider"),
                tts_provider=turn.get("tts_provider"),
                degrade_flags=degrade_flags,
                trace_id=turn.get("trace_id"),
                latency_ms=int(turn.get("latency_ms") or 0),
                created_at=str(turn["created_at"]),
            )
        )
    return InterviewTurnsResponse(interview_id=interview_id, items=items)


@router.post("/{interview_id}/turns/audio", response_model=InterviewTurnResponse)
async def submit_turn_audio(
    interview_id: str,
    stage: str = Form(...),
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    auth: AuthContext = Depends(require_user),
    service: InterviewService = Depends(get_service),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewTurnResponse:
    """上传音频并提交轮次。"""
    endpoint = f"POST:/interviews/{interview_id}/turns/audio"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return InterviewTurnResponse(**json.loads(cached))
    content = await file.read()
    result = service.submit_turn_with_audio(
        interview_id,
        stage=stage,
        audio_bytes=content,
        filename=file.filename or "answer.wav",
        user_id=auth.user_id,
    )
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, json.dumps(result, ensure_ascii=False))
    return InterviewTurnResponse(**result)


@router.post("/{interview_id}/finish", response_model=InterviewFinishResponse, status_code=202)
async def finish_interview(
    interview_id: str,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    auth: AuthContext = Depends(require_user),
    service: InterviewService = Depends(get_service),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewFinishResponse:
    """结束面试并触发报告生成。"""
    endpoint = f"POST:/interviews/{interview_id}/finish"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return InterviewFinishResponse(**json.loads(cached))
    result = service.finish_interview(interview_id, user_id=auth.user_id)
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, json.dumps(result, ensure_ascii=False))
    return InterviewFinishResponse(**result)


@router.get("/{interview_id}/status", response_model=InterviewStatusResponse)
async def get_interview_status(
    interview_id: str,
    status: Optional[str] = None,
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
    service: InterviewService = Depends(get_service),
) -> InterviewStatusResponse:
    """查询会话当前状态，可通过 status=PAUSED|ACTIVE 更新状态。"""
    session = repo.get_session(interview_id)
    if not session:
        raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
    if str(session.get("user_id") or "") != auth.user_id:
        raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
    if status:
        target = status.strip().upper()
        if target not in {"ACTIVE", "PAUSED"}:
            raise ApiError(code="VALIDATE_400", message="status 仅支持 ACTIVE 或 PAUSED", status_code=400)
        current = str(session.get("status") or "")
        if current == "FINISHED":
            raise ApiError(code="STATE_409", message="面试已结束，无法更新状态", status_code=409)
        if current != target:
            changed = repo.set_session_status(user_id=auth.user_id, interview_id=interview_id, status=target)
            if not changed:
                raise ApiError(code="STATE_409", message="面试状态更新失败", status_code=409)
            session = repo.get_session(interview_id) or session
    current_question = repo.get_last_next_question(user_id=auth.user_id, interview_id=interview_id)
    if not current_question:
        current_question = "请先做 1 分钟自我介绍，聚焦与你申请岗位最相关的经历。"
    tts_audio_url = None
    if str(session.get("output_mode") or "") == "voice":
        try:
            tts_audio_url = service.voice_service.tts(current_question)
        except ApiError:
            tts_audio_url = None
    return InterviewStatusResponse(
        interview_id=interview_id,
        status=session["status"],
        current_stage=session["current_stage"],
        follow_up_count=int(session["follow_up_count"]),
        technical_count=int(session.get("technical_count", 0)),
        job_role=str(session.get("job_role") or "java"),
        difficulty=str(session.get("difficulty") or "medium"),
        input_mode=str(session.get("input_mode") or "text"),
        output_mode=str(session.get("output_mode") or "text"),
        current_question=current_question,
        tts_audio_url=tts_audio_url,
        duration_seconds=int(session.get("duration_seconds") or 0),
        duration_updated_at=session.get("duration_updated_at"),
    )


@router.get("/{interview_id}/playback", response_model=InterviewPlaybackResponse)
async def get_interview_playback(
    interview_id: str,
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> InterviewPlaybackResponse:
    """查询面试回放详情。"""
    playback = repo.get_playback(user_id=auth.user_id, interview_id=interview_id)
    if not playback:
        raise ApiError(code="INTERVIEW_404_NOT_FOUND", message="面试会话不存在", status_code=404)
    if playback.get("forbidden"):
        raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
    session = playback["session"]
    resume = playback.get("resume") or {"resume_id": session["resume_id"], "filename": "已删除简历"}
    turns = playback.get("turns", [])
    return InterviewPlaybackResponse(
        interview_id=session["interview_id"],
        resume=InterviewPlaybackResume(resume_id=resume["resume_id"], file_name=resume["filename"]),
        meta=InterviewPlaybackMeta(
            job_role=session["job_role"],
            difficulty=session["difficulty"],
            status=session["status"],
            started_at=session["started_at"] or "",
            finished_at=session.get("finished_at"),
            duration_seconds=int(session.get("duration_seconds") or 0),
            duration_updated_at=session.get("duration_updated_at"),
        ),
        turns=[
            InterviewPlaybackTurn(
                turn_id=t["turn_id"],
                sequence=int(t["sequence"]),
                question=t["question"],
                answer=t["answer"],
                question_ts=t["question_ts"],
                answer_ts=t.get("answer_ts"),
            )
            for t in turns
        ],
    )
