"""鉴权与角色校验能力。"""

from __future__ import annotations

from typing import Literal

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.errors import ApiError

Role = Literal["user", "admin"]
bearer_scheme = HTTPBearer(auto_error=False)


def _parse_role(token: str) -> Role:
    """根据 token 解析角色。"""
    settings = get_settings()
    if token == settings.admin_token:
        return "admin"
    if token == settings.user_token:
        return "user"
    raise ApiError(code="AUTH_401", message="认证失败，请提供有效令牌", status_code=401)


def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> Role:
    """要求用户或管理员角色。"""
    if credentials is None or not credentials.credentials:
        raise ApiError(code="AUTH_401", message="未提供认证信息", status_code=401)
    return _parse_role(credentials.credentials)


def require_admin(role: Role = Depends(require_user)) -> Role:
    """要求管理员角色。"""
    if role != "admin":
        raise ApiError(code="AUTH_403", message="权限不足，仅管理员可访问", status_code=403)
    return role

