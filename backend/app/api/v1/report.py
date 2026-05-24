"""报告查询接口。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request

from app.core.errors import ApiError
from app.core.security import AuthContext, require_user
from app.models.schemas import ReportResponse
from app.repositories.interview_repository import InterviewRepository
from app.services.report_worker import ReportWorker

router = APIRouter(prefix="/report", tags=["report"])


def get_repo(request: Request) -> InterviewRepository:
    """从应用状态获取仓储对象。"""
    return request.app.state.repo


def get_worker(request: Request) -> ReportWorker:
    """从应用状态获取报告任务执行器。"""
    return request.app.state.report_worker


@router.get("/{interview_id}", response_model=ReportResponse)
async def get_report(
    interview_id: str,
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> ReportResponse:
    """查询面试报告状态与结果。"""
    session = repo.get_session(interview_id)
    if session and str(session.get("user_id") or "") != auth.user_id:
        raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
    row = repo.get_report(interview_id)
    if not row:
        return ReportResponse(interview_id=interview_id, status="GENERATING")

    return ReportResponse(
        interview_id=interview_id,
        status=row["status"],
        overall_score=row.get("overall_score"),
        strengths=json.loads(row.get("strengths") or "[]"),
        weaknesses=json.loads(row.get("weaknesses") or "[]"),
        suggestions=json.loads(row.get("suggestions") or "[]"),
        dimension_scores=json.loads(row.get("dimension_scores") or "[]"),
        jd_resume_alignment=json.loads(row.get("jd_resume_alignment") or "[]"),
        question_deep_dives=json.loads(row.get("question_deep_dives") or "[]"),
        key_risks=json.loads(row.get("key_risks") or "[]"),
        final_recommendation=str(row.get("final_recommendation") or ""),
        error_message=row.get("error_message"),
    )


@router.post("/{interview_id}/retry")
async def retry_report(
    interview_id: str,
    auth: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
    worker: ReportWorker = Depends(get_worker),
) -> dict:
    """重试报告生成任务。"""
    session = repo.get_session(interview_id)
    if session and str(session.get("user_id") or "") != auth.user_id:
        raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
    row = repo.get_report(interview_id)
    if not row:
        repo.upsert_report(
            interview_id,
            {
                "status": "GENERATING",
                "overall_score": None,
                "strengths": "[]",
                "weaknesses": "[]",
                "suggestions": "[]",
                "dimension_scores": "[]",
                "jd_resume_alignment": "[]",
                "question_deep_dives": "[]",
                "key_risks": "[]",
                "final_recommendation": "",
                "error_message": None,
            },
        )
    else:
        repo.upsert_report(
            interview_id,
            {
                "status": "GENERATING",
                "overall_score": row.get("overall_score"),
                "strengths": row.get("strengths", "[]"),
                "weaknesses": row.get("weaknesses", "[]"),
                "suggestions": row.get("suggestions", "[]"),
                "dimension_scores": row.get("dimension_scores", "[]"),
                "jd_resume_alignment": row.get("jd_resume_alignment", "[]"),
                "question_deep_dives": row.get("question_deep_dives", "[]"),
                "key_risks": row.get("key_risks", "[]"),
                "final_recommendation": row.get("final_recommendation", ""),
                "error_message": None,
            },
        )
    worker.enqueue(interview_id)
    return {"interview_id": interview_id, "status": "GENERATING"}
