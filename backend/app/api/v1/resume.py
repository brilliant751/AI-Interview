"""简历接口。"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, Response, UploadFile

from app.core.errors import ApiError
from app.core.security import AuthContext, require_user
from app.models.schemas import ResumeListItem, ResumeListResponse, ResumeUploadResponse
from app.repositories.interview_repository import InterviewRepository

router = APIRouter(prefix="/resumes", tags=["resumes"])


def get_repo(request: Request) -> InterviewRepository:
    """从应用状态获取仓储对象。"""
    return request.app.state.repo


@router.post("", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile,
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> ResumeUploadResponse:
    """上传简历并创建简历记录。"""
    endpoint = "POST:/resumes"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return ResumeUploadResponse(**json.loads(cached))
    result = repo.create_resume(user_id=auth.user_id, filename=file.filename or "resume.pdf")
    response = ResumeUploadResponse(resume_id=result["resume_id"], parse_status="READY")
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, response.model_dump_json())
    return response


@router.get("", response_model=ResumeListResponse)
async def list_resumes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> ResumeListResponse:
    """分页查询当前用户简历。"""
    offset = (page - 1) * page_size
    rows, total = repo.list_resumes(user_id=auth.user_id, offset=offset, limit=page_size)
    items = [
        ResumeListItem(
            resume_id=row["resume_id"],
            file_name=row["filename"],
            parse_status=row["status"],
            created_at=row["created_at"],
            last_used_at=row.get("last_used_at"),
        )
        for row in rows
    ]
    return ResumeListResponse(items=items, page=page, page_size=page_size, total=total)


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: str,
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> Response:
    """删除当前用户简历。"""
    resume = repo.get_resume(resume_id)
    if not resume or int(resume.get("is_deleted") or 0) == 1:
        raise ApiError(code="RESUME_404_NOT_FOUND", message="简历不存在", status_code=404)
    if str(resume.get("user_id") or "") != auth.user_id:
        raise ApiError(code="RESUME_403_FORBIDDEN", message="无权限操作该简历", status_code=403)
    if repo.has_active_session_ref(user_id=auth.user_id, resume_id=resume_id):
        raise ApiError(code="RESUME_409_IN_USE", message="简历存在进行中的面试，暂不可删除", status_code=409)
    repo.soft_delete_resume(user_id=auth.user_id, resume_id=resume_id)
    return Response(status_code=204)
