"""简历接口。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, Request, UploadFile

from app.core.security import require_user
from app.models.schemas import ResumeUploadResponse
from app.repositories.interview_repository import InterviewRepository

router = APIRouter(prefix="/resumes", tags=["resumes"])


def get_repo(request: Request) -> InterviewRepository:
    """从应用状态获取仓储对象。"""
    return request.app.state.repo


@router.post("", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile,
    idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    _: str = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> ResumeUploadResponse:
    """上传简历并创建简历记录。"""
    endpoint = "POST:/resumes"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return ResumeUploadResponse(**json.loads(cached))
    result = repo.create_resume(filename=file.filename or "resume.pdf")
    response = ResumeUploadResponse(resume_id=result["resume_id"], parse_status="READY")
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, response.model_dump_json())
    return response
