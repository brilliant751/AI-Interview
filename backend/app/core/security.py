"""鉴权与角色校验能力。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import get_settings
from app.core.errors import auth_error

Role = Literal["user", "admin"]
bearer_scheme = HTTPBearer(auto_error=False)

# 鉴权模块的边界：
# 1. 对外只暴露 require_user / require_admin 两个 FastAPI Depends。
# 2. 正式路径使用 JWT access token，dev_static 只作为开发兼容开关存在。
# 3. AuthContext 只包含 user_id、role、token_type，路由不直接解析 JWT payload。
# 4. 所有认证失败统一走 auth_error，保证错误码和 HTTP 状态一致。
# 5. require_admin 基于 require_user 叠加角色判断，避免重复写 token 解析逻辑。


@dataclass
class AuthContext:
    """认证上下文对象。"""

    user_id: str
    role: Role
    token_type: Literal["access", "dev_static"] = "access"


def decode_access_token(token: str) -> AuthContext:
    """解码并校验访问令牌。"""
    settings = get_settings()
    try:
        # 这里强制要求 sub、role、exp 三个字段。
        # sub 用于用户归属校验，role 用于权限分流，exp 用于避免长期有效 token。
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "role", "exp"]},
        )
    except ExpiredSignatureError as exc:
        raise auth_error("AUTH_401", "访问令牌已过期，请重新登录") from exc
    except InvalidTokenError as exc:
        raise auth_error("AUTH_401", "访问令牌无效，请重新登录") from exc

    user_id = str(payload.get("sub") or "").strip()
    role = str(payload.get("role") or "").strip()
    if not user_id or role not in {"user", "admin"}:
        raise auth_error("AUTH_401", "访问令牌无效，请重新登录")
    return AuthContext(user_id=user_id, role=role, token_type="access")


def _try_parse_dev_static_token(token: str) -> AuthContext | None:
    """在开发兼容模式下解析旧静态令牌。"""
    # 旧版前端或 Postman 集合可能仍使用静态 token。
    # 只有 dev 环境且显式打开 auth_enable_dev_static_token 时才允许该路径。
    # 生产环境必须走 JWT，避免固定 token 带来的安全风险。
    settings = get_settings()
    if settings.app_env != "dev" or not settings.auth_enable_dev_static_token:
        return None
    if token == settings.admin_token:
        return AuthContext(user_id="admin-default", role="admin", token_type="dev_static")
    if token == settings.user_token:
        return AuthContext(user_id="user-default", role="user", token_type="dev_static")
    return None


def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> AuthContext:
    """要求用户或管理员角色。"""
    if credentials is None or not credentials.credentials:
        raise auth_error("AUTH_401", "未提供认证信息")
    dev_ctx = _try_parse_dev_static_token(credentials.credentials)
    if dev_ctx is not None:
        return dev_ctx
    return decode_access_token(credentials.credentials)


def require_admin(auth: AuthContext = Depends(require_user)) -> AuthContext:
    """要求管理员角色。"""
    if auth.role != "admin":
        raise auth_error("AUTH_403", "权限不足，仅管理员可访问")
    return auth
