"""v1 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.company import router as company_router
from app.api.v1.history import router as history_router
from app.api.v1.interview import router as interview_router
from app.api.v1.jd import router as jd_router
from app.api.v1.report import router as report_router
from app.api.v1.resume import router as resume_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(company_router)
api_router.include_router(resume_router)
api_router.include_router(jd_router)
api_router.include_router(interview_router)
api_router.include_router(report_router)
api_router.include_router(history_router)
api_router.include_router(admin_router)
