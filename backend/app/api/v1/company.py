"""公司接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.security import AuthContext, require_user
from app.models.schemas import CompanyListItem, CompanyListResponse
from app.repositories.interview_repository import InterviewRepository

router = APIRouter(prefix="/companies", tags=["companies"])

# 公司接口目前是轻量基础资料查询：
# 1. 需要登录后访问，保持和 JD、面试等用户功能的权限模型一致。
# 2. 路由层只做模型包装，实际数据来自仓储层维护的公司表。
# 3. 返回 status/created_at/updated_at，便于后续管理端扩展启停或编辑能力。


def get_repo(request: Request) -> InterviewRepository:
    """从应用状态获取仓储对象。"""
    return request.app.state.repo


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    _: AuthContext = Depends(require_user),
    repo: InterviewRepository = Depends(get_repo),
) -> CompanyListResponse:
    """查询公司列表。"""
    rows = repo.list_companies()
    return CompanyListResponse(
        items=[
            CompanyListItem(
                company_id=row["company_id"],
                name=row["name"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
    )
