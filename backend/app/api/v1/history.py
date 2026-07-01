"""历史记录接口。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.core.errors import ApiError
from app.core.security import AuthContext, require_user
from app.models.schemas import HistoryItem, HistoryResponse
from app.repositories.interview_repository import InterviewRepository

router = APIRouter(prefix="/interviews/history", tags=["history"])

# 历史记录接口只读取当前用户的面试会话：
# 1. 支持 job_role 和 status 过滤，方便前端按岗位或状态筛选。
# 2. status 在路由层先归一化为大写枚举，避免仓储层处理自由文本。
# 3. 分页参数在 Query 中限制范围，防止一次查询过多历史数据。
# 4. 返回项只暴露列表展示所需字段，不返回完整简历/JD/轮次内容。


def get_repo(request: Request) -> InterviewRepository:
    """从应用状态获取仓储对象。"""
    return request.app.state.repo


@router.get("", response_model=HistoryResponse)
async def list_history(
    job_role: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> HistoryResponse:
    """按分页查询历史会话列表。"""
    normalized_status: Optional[str] = None
    if status is not None:
        normalized_status = status.strip().upper()
        if normalized_status not in {"ACTIVE", "PAUSED", "FINISHED"}:
            raise ApiError(code="VALIDATE_400", message="status 仅支持 ACTIVE、PAUSED 或 FINISHED", status_code=400)
    offset = (page - 1) * page_size
    rows, total = repo.list_history(
        user_id=auth.user_id,
        job_role=job_role,
        status=normalized_status,
        offset=offset,
        limit=page_size,
    )
    items = [
        HistoryItem(
            interview_id=row["interview_id"],
            session_name=str(row.get("session_name") or ""),
            resume_id=row["resume_id"],
            resume_file_name=str(row.get("resume_file_name") or ""),
            job_role=row["job_role"],
            difficulty=str(row.get("difficulty") or "medium"),
            status=row["status"],
            jd_id=str(row.get("jd_id") or ""),
            jd_title=str(row.get("jd_snapshot_title") or ""),
            jd_source_type=str(row.get("jd_source_type") or ""),
            started_at=row["started_at"] or row["created_at"],
            finished_at=row.get("finished_at"),
            turn_count=int(row.get("turn_count") or 0),
            overall_score=row.get("overall_score"),
            created_at=row["created_at"],
            duration_seconds=int(row.get("duration_seconds") or 0),
            duration_updated_at=row.get("duration_updated_at"),
        )
        for row in rows
    ]
    return HistoryResponse(items=items, total=total)


@router.delete("/{interview_id}")
async def delete_history_interview(
    interview_id: str,
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> dict:
    """删除指定历史面试会话。"""
    deleted = repo.delete_interview(user_id=auth.user_id, interview_id=interview_id)
    if not deleted:
        raise ApiError(code="INTERVIEW_404_NOT_FOUND", message="面试会话不存在", status_code=404)
    return {"interview_id": interview_id, "deleted": True}
