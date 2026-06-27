"""v1 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.company import router as company_router
from app.api.v1.coding_practice import router as coding_practice_router
from app.api.v1.history import router as history_router
from app.api.v1.interview import router as interview_router
from app.api.v1.interview_schedule import router as interview_schedule_router
from app.api.v1.practice import router as practice_router
from app.api.v1.jd import router as jd_router
from app.api.v1.report import router as report_router
from app.api.v1.resume import router as resume_router

api_router = APIRouter(prefix="/api/v1")

# v1 版本所有业务路由都在这里集中注册：
# 1. 前端只需要记住统一前缀 /api/v1，后续模块扩展不会影响基础地址。
# 2. 各模块仍然在自己的文件里维护 prefix 和 tag，便于生成 OpenAPI 文档。
# 3. 注册顺序保持“账户/基础资料/业务流程/管理接口”的阅读顺序。
# 4. 这里不做鉴权和业务判断，鉴权统一在具体路由的 Depends 中声明。
api_router.include_router(auth_router)
api_router.include_router(company_router)
api_router.include_router(coding_practice_router)
api_router.include_router(resume_router)
api_router.include_router(jd_router)
api_router.include_router(interview_router)
api_router.include_router(interview_schedule_router)
api_router.include_router(practice_router)
api_router.include_router(report_router)
api_router.include_router(history_router)
api_router.include_router(admin_router)
