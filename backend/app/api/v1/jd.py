"""岗位描述（JD）接口。"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile

from app.core.errors import ApiError
from app.core.security import AuthContext, require_user
from app.models.schemas import JobDescriptionListItem, JobDescriptionListResponse, JobDescriptionUploadResponse
from app.repositories.interview_repository import InterviewRepository
from app.services.resume_parse_service import ResumeParseService

router = APIRouter(prefix="/jds", tags=["jds"])
JD_STORAGE_DIR = Path(__file__).resolve().parents[3] / "assets" / "data" / "jds"
jd_parse_service = ResumeParseService()


def get_repo(request: Request) -> InterviewRepository:
    """从应用状态获取仓储对象。"""
    return request.app.state.repo


@router.post("", response_model=JobDescriptionUploadResponse)
async def upload_jd(
    file: UploadFile | None = File(default=None),
    job_role: str = Form(default=""),
    title: str = Form(default=""),
    content_text: str = Form(default=""),
    company_id: str = Form(default=""),
    idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> JobDescriptionUploadResponse:
    """上传用户 JD。"""
    endpoint = "POST:/jds"
    if idempotency_key:
        cached = repo.get_idempotent_response(endpoint, idempotency_key)
        if cached:
            return JobDescriptionUploadResponse(**json.loads(cached))
    normalized_role = (job_role or "").strip() or "other"
    if len(normalized_role) > 64:
        raise ApiError(code="JD_400_INVALID_ROLE", message="job_role 长度不能超过 64", status_code=400)
    parsed_text = (content_text or "").strip()
    stored_path: str | None = None
    if file is None and not parsed_text:
        raise ApiError(code="JD_400_EMPTY_FILE", message="请上传文件或填写岗位描述文本", status_code=400)
    if file is not None:
        original_filename = file.filename or "jd.txt"
        ext = Path(original_filename).suffix.lower()
        if ext not in {".pdf", ".doc", ".docx", ".txt", ".md"}:
            raise ApiError(code="JD_400_INVALID_FILE", message="仅支持 pdf/doc/docx/txt/md 文件", status_code=400)
        content = await file.read()
        if not content:
            raise ApiError(code="JD_400_EMPTY_FILE", message="JD 文件为空", status_code=400)
        if len(content) > 5 * 1024 * 1024:
            raise ApiError(code="JD_400_INVALID_FILE", message="JD 文件大小不能超过 5MB", status_code=400)
        if ext in {".txt", ".md"}:
            parsed_text = content.decode("utf-8", errors="ignore").strip() or parsed_text
        else:
            parsed_text = jd_parse_service.parse(original_filename, content).strip() or parsed_text
        JD_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{ext}"
        local_path = JD_STORAGE_DIR / stored_name
        local_path.write_bytes(content)
        stored_path = str(local_path)
    if not parsed_text:
        raise ApiError(code="JD_400_INVALID_FILE", message="JD 文本内容为空，请检查输入", status_code=400)
    normalized_company_id = (company_id or "").strip()
    company_name = ""
    if normalized_company_id:
        company = repo.get_company(normalized_company_id)
        if not company:
            raise ApiError(code="COMPANY_404_NOT_FOUND", message="公司不存在", status_code=404)
        company_name = str(company.get("name") or "")
    row = repo.create_jd(
        user_id=auth.user_id,
        source_type="USER_UPLOAD",
        company_id=normalized_company_id or None,
        title=(title or "").strip() or f"{normalized_role.upper()}岗位描述",
        job_role=normalized_role,
        content_text=parsed_text,
        storage_path=stored_path,
        status="READY",
    )
    response = JobDescriptionUploadResponse(
        jd_id=str(row.get("jd_id") or ""),
        source_type=str(row.get("source_type") or "USER_UPLOAD"),
        company_id=str(row.get("company_id") or ""),
        company_name=company_name,
        title=str(row.get("title") or ""),
        job_role=str(row.get("job_role") or normalized_role),
        status=str(row.get("status") or "READY"),
        created_at=str(row.get("created_at") or ""),
    )
    if idempotency_key:
        repo.save_idempotent_response(endpoint, idempotency_key, response.model_dump_json())
    return response


@router.get("", response_model=JobDescriptionListResponse)
async def list_jds(
    job_role: Optional[str] = Query(default=None),
    source_type: Optional[str] = Query(default=None),
    title: Optional[str] = Query(default=None),
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> JobDescriptionListResponse:
    """查询 JD 列表。"""
    normalized_role = (job_role or "").strip() or None
    if normalized_role is not None and len(normalized_role) > 64:
        raise ApiError(code="JD_400_INVALID_ROLE", message="job_role 长度不能超过 64", status_code=400)
    normalized_source = (source_type or "").strip().upper() or None
    if normalized_source is not None and normalized_source not in {"USER_UPLOAD", "SYSTEM_PRESET"}:
        raise ApiError(
            code="JD_400_INVALID_SOURCE",
            message="source_type 仅支持 USER_UPLOAD 或 SYSTEM_PRESET",
            status_code=400,
        )
    normalized_title = (title or "").strip() or None
    rows = repo.list_jds(
        user_id=auth.user_id,
        job_role=normalized_role,
        source_type=normalized_source,
        title=normalized_title,
    )
    return JobDescriptionListResponse(
        items=[
            JobDescriptionListItem(
                jd_id=row["jd_id"],
                source_type=row["source_type"],
                company_id=str(row.get("company_id") or ""),
                company_name=str(row.get("company_name") or ""),
                title=row["title"],
                job_role=row["job_role"],
                status=row["status"],
                content_text=str(row.get("content_text") or ""),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
    )


@router.delete("/{jd_id}", status_code=204)
async def delete_jd(
    jd_id: str,
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> Response:
    """删除用户上传 JD。"""
    jd = repo.get_jd(jd_id)
    if not jd or int(jd.get("is_deleted") or 0) == 1:
        raise ApiError(code="JD_404_NOT_FOUND", message="JD 不存在", status_code=404)
    if str(jd.get("source_type") or "") == "SYSTEM_PRESET":
        raise ApiError(code="JD_403_FORBIDDEN", message="系统预置 JD 不允许删除", status_code=403)
    if str(jd.get("user_id") or "") != auth.user_id:
        raise ApiError(code="JD_403_FORBIDDEN", message="无权操作该 JD", status_code=403)
    repo.soft_delete_jd(user_id=auth.user_id, jd_id=jd_id)
    return Response(status_code=204)
