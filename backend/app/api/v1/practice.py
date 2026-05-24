"""题库练习接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status

from app.core.security import AuthContext, require_admin, require_user
from app.models.schemas import (
    AdminQuestionBankCreateRequest,
    AdminQuestionBankListResponse,
    AdminQuestionBankUploadRequest,
    MaterialImportTaskResponse,
    MaterialImportTriggerResponse,
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeCreateRequest,
    PracticeOverviewResponse,
    PracticeRecordsResponse,
    PracticeSessionRecordsResponse,
    PracticeSessionResponse,
)
from app.services.material_import_service import MaterialImportService
from app.services.practice_service import PracticeService
from app.services.question_bank_service import QuestionBankService

router = APIRouter(prefix="/practice", tags=["practice"])


def get_service(request: Request) -> PracticeService:
    """从应用状态获取题库练习服务。"""
    return request.app.state.practice_service


def get_question_bank_service(request: Request) -> QuestionBankService:
    """从应用状态获取题库管理服务。"""
    return request.app.state.question_bank_service


def get_import_service(request: Request) -> MaterialImportService:
    """从应用状态获取导入任务服务。"""
    return request.app.state.material_import_service


@router.post("/sessions", response_model=PracticeSessionResponse)
async def create_practice_session(
    payload: PracticeCreateRequest,
    auth: AuthContext = Depends(require_user),
    service: PracticeService = Depends(get_service),
) -> PracticeSessionResponse:
    """创建新的题库练习会话。"""
    result = service.create_session(payload.model_dump(), user_id=auth.user_id)
    return PracticeSessionResponse(**result)


@router.get("/sessions/{practice_id}", response_model=PracticeSessionResponse)
async def get_practice_session(
    practice_id: str,
    auth: AuthContext = Depends(require_user),
    service: PracticeService = Depends(get_service),
) -> PracticeSessionResponse:
    """查询题库练习会话状态。"""
    result = service.get_session(practice_id, user_id=auth.user_id)
    return PracticeSessionResponse(**result)


@router.post("/sessions/{practice_id}/answers", response_model=PracticeAnswerResponse)
async def submit_practice_answer(
    practice_id: str,
    payload: PracticeAnswerRequest,
    auth: AuthContext = Depends(require_user),
    service: PracticeService = Depends(get_service),
) -> PracticeAnswerResponse:
    """提交题库练习答案。"""
    result = service.submit_answer(practice_id, payload.model_dump(), user_id=auth.user_id)
    return PracticeAnswerResponse(**result)


@router.post("/sessions/{practice_id}/finish", response_model=PracticeSessionResponse)
async def finish_practice_session(
    practice_id: str,
    auth: AuthContext = Depends(require_user),
    service: PracticeService = Depends(get_service),
) -> PracticeSessionResponse:
    """手动结束题库练习会话。"""
    result = service.finish_session(practice_id, user_id=auth.user_id)
    return PracticeSessionResponse(**result)


@router.get("/records", response_model=PracticeRecordsResponse)
async def get_practice_records(
    auth: AuthContext = Depends(require_user),
    service: PracticeService = Depends(get_service),
) -> PracticeRecordsResponse:
    """查询当前用户的题库练习记录。"""
    result = service.list_records(user_id=auth.user_id)
    return PracticeRecordsResponse(**result)


@router.get("/overview", response_model=PracticeOverviewResponse)
async def get_practice_overview(
    auth: AuthContext = Depends(require_user),
    service: PracticeService = Depends(get_service),
) -> PracticeOverviewResponse:
    """查询题库练习首页概览。"""
    result = service.get_overview(user_id=auth.user_id)
    return PracticeOverviewResponse(**result)


@router.get("/sessions/{practice_id}/records", response_model=PracticeSessionRecordsResponse)
async def get_practice_session_records(
    practice_id: str,
    auth: AuthContext = Depends(require_user),
    service: PracticeService = Depends(get_service),
) -> PracticeSessionRecordsResponse:
    """查询单场题库练习记录明细。"""
    result = service.get_session_records(practice_id=practice_id, user_id=auth.user_id)
    return PracticeSessionRecordsResponse(**result)


@router.get("/questions", response_model=AdminQuestionBankListResponse, tags=["practice-admin"])
@router.get("/admin/question-bank", response_model=AdminQuestionBankListResponse, tags=["practice-admin"])
async def list_question_bank(
    job_role: str,
    category: str | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    _: str = Depends(require_admin),
    service: QuestionBankService = Depends(get_question_bank_service),
) -> AdminQuestionBankListResponse:
    """分页查询管理员题库列表。"""
    result = service.list_questions(job_role=job_role, category=category, keyword=keyword, page=page, page_size=page_size)
    return AdminQuestionBankListResponse(**result)


@router.post(
    "/questions/upload",
    response_model=MaterialImportTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["practice-admin"],
)
async def upload_question_bank_markdown_file(
    job_role: str = Form(...),
    file: UploadFile = File(...),
    _: str = Depends(require_admin),
    service: QuestionBankService = Depends(get_question_bank_service),
) -> MaterialImportTriggerResponse:
    """通过 multipart 方式上传题库 Markdown 并触发导入任务。"""
    markdown = (await file.read()).decode("utf-8")
    return await service.upload_markdown(
        job_role=job_role,
        file_name=file.filename or "question-bank.md",
        markdown=markdown,
    )


@router.post(
    "/admin/question-bank/upload",
    response_model=MaterialImportTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["practice-admin"],
)
async def upload_question_bank_markdown(
    payload: AdminQuestionBankUploadRequest,
    _: str = Depends(require_admin),
    service: QuestionBankService = Depends(get_question_bank_service),
) -> MaterialImportTriggerResponse:
    """兼容旧调用方式的题库 Markdown 上传接口。"""
    return await service.upload_markdown(
        job_role=payload.job_role,
        file_name=payload.file_name,
        markdown=payload.markdown,
    )


@router.post(
    "/questions",
    response_model=MaterialImportTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["practice-admin"],
)
@router.post(
    "/admin/question-bank/questions",
    response_model=MaterialImportTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["practice-admin"],
)
async def create_question_bank_question(
    payload: AdminQuestionBankCreateRequest,
    _: str = Depends(require_admin),
    service: QuestionBankService = Depends(get_question_bank_service),
) -> MaterialImportTriggerResponse:
    """录入单题并触发题库导入任务。"""
    return await service.create_question(
        job_role=payload.job_role,
        category=payload.category,
        title=payload.title,
        question=payload.question,
        analysis=payload.analysis,
        source_note=payload.source_note,
    )


@router.get("/questions/import-tasks/{task_id}", response_model=MaterialImportTaskResponse, tags=["practice-admin"])
@router.get("/admin/import-tasks/{task_id}", response_model=MaterialImportTaskResponse, tags=["practice-admin"])
async def get_practice_admin_import_task(
    task_id: str,
    _: str = Depends(require_admin),
    service: MaterialImportService = Depends(get_import_service),
) -> MaterialImportTaskResponse:
    """查询题库管理导入任务状态。"""
    return service.get_task(task_id)
