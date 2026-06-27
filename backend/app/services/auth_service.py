"""认证域服务实现。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.errors import auth_error
from app.repositories.interview_repository import InterviewRepository
from app.services.audit_service import AuditService


# AuthService 处理认证域核心规则：
# 1. 密码只保存哈希结果，比较时使用 hmac.compare_digest 降低时序攻击风险。
# 2. access/refresh/reset token 分开签发和校验，生命周期由配置集中控制。
# 3. 登录限流保存在进程内，适合课程项目和单进程部署，生产可替换为 Redis。
# 4. 所有关键认证事件都会写审计日志，便于排查暴力登录或异常重置。
# 5. 服务层不依赖 FastAPI Request，方便单元测试直接调用。
@dataclass
class _RateLimitWindow:
    """登录限流窗口状态。"""

    count: int
    expires_at: datetime


class AuthService:
    """认证核心服务。"""

    def __init__(self, repo: InterviewRepository, audit_service: AuditService):
        """初始化认证服务。"""
        self.repo = repo
        self.audit_service = audit_service
        self.settings = get_settings()
        self._rate_limit_state: dict[str, _RateLimitWindow] = {}

    def _now(self) -> datetime:
        """获取当前 UTC 时间。"""
        return datetime.now(timezone.utc)

    def _to_sqlite_dt(self, value: datetime) -> str:
        """将时间转换为 SQLite 可读字符串。"""
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def _issue_access_token(self, user_id: str, role: str) -> tuple[str, int]:
        """签发访问令牌。"""
        expires_at = self._now() + timedelta(minutes=self.settings.access_token_ttl_minutes)
        payload = {
            "sub": user_id,
            "role": role,
            "exp": expires_at,
            "iat": self._now(),
        }
        token = jwt.encode(payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm)
        return token, int(self.settings.access_token_ttl_minutes * 60)

    def _hash_token(self, token: str) -> str:
        """计算令牌哈希。"""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _hash_password(self, password: str) -> str:
        """生成密码哈希。"""
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            120000,
        ).hex()
        return f"pbkdf2_sha256$120000${salt}${digest}"

    def _verify_password(self, password: str, encoded: str) -> bool:
        """校验密码是否匹配。"""
        parts = encoded.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        _, iterations, salt, digest = parts
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(candidate, digest)

    def _build_user_profile(self, row: dict) -> dict:
        """构建用户响应模型。"""
        return {
            "user_id": row["user_id"],
            "email": row["email"],
            "display_name": row["display_name"],
            "role": row["role"],
            "status": row["status"],
        }

    def _enforce_password_policy(self, password: str) -> None:
        """执行密码复杂度校验。"""
        if len(password) < 8:
            raise auth_error("AUTH_400", "密码长度至少 8 位")
        if password.isalpha() or password.isdigit():
            raise auth_error("AUTH_400", "密码需包含字母和数字")

    def _consume_login_rate_limit(self, email: str, ip: str) -> None:
        """执行登录限流计数。"""
        key = f"{email.lower()}|{ip}"
        now = self._now()
        window = self._rate_limit_state.get(key)
        if not window or window.expires_at <= now:
            self._rate_limit_state[key] = _RateLimitWindow(
                count=1,
                expires_at=now + timedelta(seconds=self.settings.auth_login_limit_window_seconds),
            )
            return
        if window.count >= self.settings.auth_login_limit_threshold:
            raise auth_error("AUTH_429_LOGIN_RATE_LIMIT", "登录尝试过于频繁，请稍后重试")
        window.count += 1

    def register(self, email: str, password: str, display_name: str, ip: str, user_agent: str) -> dict:
        """注册新账号。"""
        self._enforce_password_policy(password)
        existing = self.repo.get_user_by_email(email)
        if existing:
            self.audit_service.log_auth_event("register", existing["user_id"], ip, user_agent, "failed", "邮箱已注册")
            raise auth_error("AUTH_409_EMAIL_EXISTS", "该邮箱已注册")
        user_id = f"usr_{uuid.uuid4().hex[:16]}"
        row = self.repo.create_user(
            user_id=user_id,
            email=email,
            password_hash=self._hash_password(password),
            display_name=display_name,
            role="user",
        )
        self.audit_service.log_auth_event("register", user_id, ip, user_agent, "success", "")
        return {"user": self._build_user_profile(row)}

    def login(self, email: str, password: str, ip: str, user_agent: str) -> dict:
        """账号密码登录并签发令牌。"""
        self._consume_login_rate_limit(email, ip)
        account = self.repo.get_user_by_email(email)
        if not account:
            self._verify_password(password, self._hash_password("dummy-password-123"))
            self.audit_service.log_auth_event("login", "", ip, user_agent, "failed", "账号不存在或密码错误")
            raise auth_error("AUTH_401_INVALID_CREDENTIALS", "账号或密码错误")
        if account["status"] != "active":
            self.audit_service.log_auth_event("login", account["user_id"], ip, user_agent, "failed", "账号已禁用")
            raise auth_error("AUTH_403_USER_DISABLED", "账号已被禁用")
        if not self._verify_password(password, account["password_hash"]):
            self.audit_service.log_auth_event("login", account["user_id"], ip, user_agent, "failed", "账号不存在或密码错误")
            raise auth_error("AUTH_401_INVALID_CREDENTIALS", "账号或密码错误")

        access_token, expires_in = self._issue_access_token(account["user_id"], account["role"])
        refresh_token = secrets.token_urlsafe(48)
        self.repo.insert_refresh_token(
            token_id=f"rt_{uuid.uuid4().hex[:16]}",
            user_id=account["user_id"],
            token_hash=self._hash_token(refresh_token),
            expires_at=self._to_sqlite_dt(self._now() + timedelta(days=self.settings.refresh_token_ttl_days)),
            ip=ip,
            user_agent=user_agent,
        )
        self.repo.update_user_last_login(account["user_id"])
        self.audit_service.log_auth_event("login", account["user_id"], ip, user_agent, "success", "")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "refresh_token": refresh_token,
            "user": self._build_user_profile(account),
        }

    def refresh(self, refresh_token: str, ip: str, user_agent: str) -> dict:
        """刷新访问令牌并轮换刷新令牌。"""
        row = self.repo.get_active_refresh_token_by_hash(self._hash_token(refresh_token))
        if not row:
            self.audit_service.log_auth_event("refresh", "", ip, user_agent, "failed", "refresh token 无效")
            raise auth_error("AUTH_401_REFRESH_TOKEN_INVALID", "刷新令牌无效")
        access_token, expires_in = self._issue_access_token(row["user_id"], row["role"])
        new_refresh_plain = secrets.token_urlsafe(48)
        new_token_id = f"rt_{uuid.uuid4().hex[:16]}"
        self.repo.rotate_refresh_token(
            old_token_id=row["token_id"],
            new_token_id=new_token_id,
            user_id=row["user_id"],
            new_token_hash=self._hash_token(new_refresh_plain),
            expires_at=self._to_sqlite_dt(self._now() + timedelta(days=self.settings.refresh_token_ttl_days)),
            ip=ip,
            user_agent=user_agent,
        )
        self.audit_service.log_auth_event("refresh", row["user_id"], ip, user_agent, "success", "")
        user = self.repo.get_user_by_id(row["user_id"])
        if not user:
            raise auth_error("AUTH_404_USER_NOT_FOUND", "用户不存在")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "refresh_token": new_refresh_plain,
            "user": self._build_user_profile(user),
        }

    def logout(self, refresh_token: str, ip: str, user_agent: str) -> None:
        """登出并撤销当前刷新令牌。"""
        row = self.repo.get_active_refresh_token_by_hash(self._hash_token(refresh_token))
        if row:
            self.repo.revoke_refresh_token(row["token_id"])
            self.audit_service.log_auth_event("logout", row["user_id"], ip, user_agent, "success", "")
            return
        self.audit_service.log_auth_event("logout", "", ip, user_agent, "success", "token 已失效")

    def forgot_password(self, email: str, ip: str, user_agent: str) -> None:
        """处理忘记密码请求（防枚举）。"""
        user = self.repo.get_user_by_email(email)
        if user:
            reset_plain = secrets.token_urlsafe(48)
            self.repo.insert_password_reset_token(
                reset_id=f"rst_{uuid.uuid4().hex[:16]}",
                user_id=user["user_id"],
                token_hash=self._hash_token(reset_plain),
                expires_at=self._to_sqlite_dt(self._now() + timedelta(minutes=self.settings.reset_token_ttl_minutes)),
            )
        self.audit_service.log_auth_event(
            "forgot_password",
            user["user_id"] if user else "",
            ip,
            user_agent,
            "accepted",
            "响应已脱敏",
        )

    def reset_password(self, reset_token: str, new_password: str, ip: str, user_agent: str) -> None:
        """重置密码并撤销历史刷新令牌。"""
        self._enforce_password_policy(new_password)
        row = self.repo.get_active_reset_token_by_hash(self._hash_token(reset_token))
        if not row:
            self.audit_service.log_auth_event("reset_password", "", ip, user_agent, "failed", "重置令牌无效")
            raise auth_error("AUTH_401_RESET_TOKEN_INVALID", "重置令牌无效")
        self.repo.reset_password_and_revoke_tokens(
            user_id=row["user_id"],
            password_hash=self._hash_password(new_password),
            reset_id=row["reset_id"],
        )
        self.audit_service.log_auth_event("reset_password", row["user_id"], ip, user_agent, "success", "")

    def get_me(self, user_id: str) -> dict:
        """查询当前登录用户。"""
        row = self.repo.get_user_by_id(user_id)
        if not row:
            raise auth_error("AUTH_404_USER_NOT_FOUND", "用户不存在")
        return {"user": self._build_user_profile(row)}
