"""简历接口。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse

from app.core.errors import ApiError
from app.core.security import AuthContext, require_user
from app.models.schemas import ResumeListItem, ResumeListResponse, ResumeUploadResponse
from app.repositories.interview_repository import InterviewRepository
from app.services.resume_parse_service import ResumeParseService

router = APIRouter(prefix="/resumes", tags=["resumes"])
RESUME_STORAGE_DIR = Path(__file__).resolve().parents[3] / "assets" / "data" / "resumes"
resume_parse_service = ResumeParseService()


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
    original_filename = file.filename or "resume.pdf"
    ext = Path(original_filename).suffix.lower()
    if ext not in {".pdf", ".doc", ".docx"}:
        raise ApiError(code="RESUME_400_UNSUPPORTED_TYPE", message="仅支持 pdf/doc/docx 文件", status_code=400)
    content = await file.read()
    if not content:
        raise ApiError(code="RESUME_400_EMPTY_FILE", message="简历文件为空", status_code=400)
    if len(content) > 10 * 1024 * 1024:
        raise ApiError(code="RESUME_400_TOO_LARGE", message="简历文件大小不能超过 10MB", status_code=400)
    RESUME_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = RESUME_STORAGE_DIR / stored_name
    stored_path.write_bytes(content)
    parse_status = "READY"
    parse_error = ""
    parsed_text = ""
    try:
        parsed_text = resume_parse_service.parse(original_filename, content)
        if not parsed_text:
            parse_status = "FAILED"
            parse_error = "简历解析结果为空，请检查文件内容或格式"
    except Exception as exc:
        parse_status = "FAILED"
        parse_error = f"简历解析失败：{exc}"
    result = repo.create_resume(
        user_id=auth.user_id,
        filename=original_filename,
        storage_path=str(stored_path),
        status=parse_status,
        parsed_text=parsed_text,
        parse_error=parse_error,
    )
    response = ResumeUploadResponse(resume_id=result["resume_id"], parse_status=result["status"])
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, response.model_dump_json())
    return response


@router.get("/{resume_id}/file")
async def get_resume_file(
    resume_id: str,
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> FileResponse:
    """获取当前用户简历文件内容。"""
    resume = repo.get_resume(resume_id)
    if not resume or int(resume.get("is_deleted") or 0) == 1:
        raise ApiError(code="RESUME_404_NOT_FOUND", message="简历不存在", status_code=404)
    if str(resume.get("user_id") or "") != auth.user_id:
        raise ApiError(code="RESUME_403_FORBIDDEN", message="无权限查看该简历", status_code=403)
    storage_path = str(resume.get("storage_path") or "").strip()
    if not storage_path:
        raise ApiError(code="RESUME_404_FILE_MISSING", message="简历文件不存在", status_code=404)
    file_path = Path(storage_path)
    if not file_path.exists() or not file_path.is_file():
        raise ApiError(code="RESUME_404_FILE_MISSING", message="简历文件不存在", status_code=404)
    suffix = file_path.suffix.lower()
    media_type = "application/pdf" if suffix == ".pdf" else "application/octet-stream"
    return FileResponse(path=file_path, filename=str(resume.get("filename") or file_path.name), media_type=media_type)


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
