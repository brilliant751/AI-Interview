"""认证域接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.core.security import AuthContext, require_user
from app.models.schemas import (
    AuthMeResponse,
    AuthTokenResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenRefreshRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_auth_service(request: Request) -> AuthService:
    """从应用状态获取认证服务。"""
    return request.app.state.auth_service


def _extract_ip(request: Request) -> str:
    """提取请求来源 IP。"""
    return request.client.host if request.client else "unknown"


def _extract_user_agent(user_agent: str | None) -> str:
    """提取请求 UA。"""
    return user_agent or "unknown"


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    user_agent: str | None = Header(default=None, alias="User-Agent"),
    service: AuthService = Depends(_get_auth_service),
) -> RegisterResponse:
    """注册账号。"""
    data = service.register(
        email=str(payload.email),
        password=payload.password,
        display_name=payload.display_name,
        ip=_extract_ip(request),
        user_agent=_extract_user_agent(user_agent),
    )
    return RegisterResponse(**data)


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    user_agent: str | None = Header(default=None, alias="User-Agent"),
    service: AuthService = Depends(_get_auth_service),
) -> AuthTokenResponse:
    """账号密码登录。"""
    data = service.login(
        email=str(payload.email),
        password=payload.password,
        ip=_extract_ip(request),
        user_agent=_extract_user_agent(user_agent),
    )
    return AuthTokenResponse(**data)


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_token(
    payload: TokenRefreshRequest,
    request: Request,
    user_agent: str | None = Header(default=None, alias="User-Agent"),
    service: AuthService = Depends(_get_auth_service),
) -> AuthTokenResponse:
    """刷新访问令牌。"""
    data = service.refresh(
        refresh_token=payload.refresh_token,
        ip=_extract_ip(request),
        user_agent=_extract_user_agent(user_agent),
    )
    return AuthTokenResponse(**data)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    request: Request,
    user_agent: str | None = Header(default=None, alias="User-Agent"),
    service: AuthService = Depends(_get_auth_service),
) -> Response:
    """登出并撤销刷新令牌。"""
    service.logout(
        refresh_token=payload.refresh_token,
        ip=_extract_ip(request),
        user_agent=_extract_user_agent(user_agent),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password", response_model=ForgotPasswordResponse, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    user_agent: str | None = Header(default=None, alias="User-Agent"),
    service: AuthService = Depends(_get_auth_service),
) -> ForgotPasswordResponse:
    """发起忘记密码流程。"""
    service.forgot_password(
        email=str(payload.email),
        ip=_extract_ip(request),
        user_agent=_extract_user_agent(user_agent),
    )
    return ForgotPasswordResponse()


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    user_agent: str | None = Header(default=None, alias="User-Agent"),
    service: AuthService = Depends(_get_auth_service),
) -> Response:
    """执行密码重置。"""
    service.reset_password(
        reset_token=payload.reset_token,
        new_password=payload.new_password,
        ip=_extract_ip(request),
        user_agent=_extract_user_agent(user_agent),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=AuthMeResponse)
async def me(
    auth: AuthContext = Depends(require_user),
    service: AuthService = Depends(_get_auth_service),
) -> AuthMeResponse:
    """获取当前登录用户信息。"""
    return AuthMeResponse(**service.get_me(auth.user_id))
