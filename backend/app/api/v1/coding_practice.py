"""在线编程练习接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.security import AuthContext, require_user
from app.models.schemas import (
    CodingPracticeCreateSessionRequest,
    CodingPracticeExecutionResponse,
    CodingPracticeQuestionListResponse,
    CodingPracticeRecordsResponse,
    CodingPracticeRunRequest,
    CodingPracticeSessionResponse,
)
from app.services.coding_practice_service import CodingPracticeService

router = APIRouter(prefix="/coding-practice", tags=["coding-practice"])

# 在线编程接口保持轻量：
# 1. 路由层只接收题目、会话、运行和提交请求。
# 2. 题目进度合并、会话归属校验、判题调用全部放在 CodingPracticeService。
# 3. 所有接口都需要登录用户，避免编程记录和草稿被匿名访问。
# 4. RUN 用于自测，SUBMIT 用于正式判题，二者响应结构保持一致。


def get_service(request: Request) -> CodingPracticeService:
    """从应用状态获取编程练习服务。"""
    return request.app.state.coding_practice_service


@router.get("/questions", response_model=CodingPracticeQuestionListResponse)
async def list_coding_practice_questions(
    auth: AuthContext = Depends(require_user),
    service: CodingPracticeService = Depends(get_service),
) -> CodingPracticeQuestionListResponse:
    """获取编程练习题列表。"""
    return CodingPracticeQuestionListResponse(**service.list_questions(user_id=auth.user_id))


@router.post("/sessions", response_model=CodingPracticeSessionResponse)
async def create_coding_practice_session(
    payload: CodingPracticeCreateSessionRequest,
    auth: AuthContext = Depends(require_user),
    service: CodingPracticeService = Depends(get_service),
) -> CodingPracticeSessionResponse:
    """创建或恢复编程练习会话。"""
    return CodingPracticeSessionResponse(**service.create_or_get_session(question_id=payload.question_id, user_id=auth.user_id))


@router.get("/sessions/{session_id}", response_model=CodingPracticeSessionResponse)
async def get_coding_practice_session(
    session_id: str,
    auth: AuthContext = Depends(require_user),
    service: CodingPracticeService = Depends(get_service),
) -> CodingPracticeSessionResponse:
    """读取编程练习会话详情。"""
    return CodingPracticeSessionResponse(**service.get_session(session_id=session_id, user_id=auth.user_id))


@router.post("/sessions/{session_id}/run", response_model=CodingPracticeExecutionResponse)
async def run_coding_practice_self_test(
    session_id: str,
    payload: CodingPracticeRunRequest,
    auth: AuthContext = Depends(require_user),
    service: CodingPracticeService = Depends(get_service),
) -> CodingPracticeExecutionResponse:
    """运行编程题自测。"""
    return CodingPracticeExecutionResponse(**service.run_self_test(session_id=session_id, payload=payload.model_dump(), user_id=auth.user_id))


@router.post("/sessions/{session_id}/submit", response_model=CodingPracticeExecutionResponse)
async def submit_coding_practice_solution(
    session_id: str,
    payload: CodingPracticeRunRequest,
    auth: AuthContext = Depends(require_user),
    service: CodingPracticeService = Depends(get_service),
) -> CodingPracticeExecutionResponse:
    """提交编程题解答并正式判题。"""
    return CodingPracticeExecutionResponse(**service.submit(session_id=session_id, payload=payload.model_dump(), user_id=auth.user_id))


@router.get("/records", response_model=CodingPracticeRecordsResponse)
async def list_coding_practice_records(
    auth: AuthContext = Depends(require_user),
    service: CodingPracticeService = Depends(get_service),
) -> CodingPracticeRecordsResponse:
    """获取当前用户的编程练习记录。"""
    return CodingPracticeRecordsResponse(**service.list_records(user_id=auth.user_id))
