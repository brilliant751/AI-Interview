"""历史记录接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.core.security import require_user
from app.models.schemas import HistoryItem, HistoryResponse
from app.repositories.interview_repository import InterviewRepository

router = APIRouter(prefix="/interviews/history", tags=["history"])


def get_repo(request: Request) -> InterviewRepository:
    """从应用状态获取仓储对象。"""
    return request.app.state.repo


@router.get("", response_model=HistoryResponse)
async def list_history(
    job_role: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    _: str = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> HistoryResponse:
    """按分页查询历史会话列表。"""
    offset = (page - 1) * page_size
    rows, total = repo.list_history(job_role=job_role, offset=offset, limit=page_size)
    items = [
        HistoryItem(
            interview_id=row["interview_id"],
            job_role=row["job_role"],
            overall_score=row.get("overall_score"),
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return HistoryResponse(items=items, total=total)
