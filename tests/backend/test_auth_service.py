"""认证服务核心逻辑测试。"""

from __future__ import annotations

import os
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.core.errors import ApiError  # noqa: E402

if sys.version_info >= (3, 11):
    from app.services.auth_service import AuthService  # noqa: E402
else:
    AuthService = None

# AuthService 单元测试说明：
# 1. 直接测试服务层逻辑，不经过 FastAPI 路由，便于覆盖细粒度认证规则。
# 2. 使用审计桩记录 log_auth_event 调用，验证失败和成功路径都有审计记录。
# 3. 仓储对象在测试内构造，避免依赖真实用户数据。
# 4. 登录限流、密码哈希、token 签发和 reset token 都属于该文件关注范围。
# 5. Python 版本兼容分支用于规避旧解释器对依赖或类型语法的限制。
# 6. deepcopy 用于确保测试数据被服务层处理后不会污染后续断言。


class _AuditStub:
    """认证审计桩实现。"""

    def __init__(self) -> None:
        """初始化审计事件列表。"""
        self.events: list[dict] = []

    def log_auth_event(
        self,
        event: str,
        user_id: str,
        ip: str,
        user_agent: str,
        result: str,
        reason: str,
    ) -> None:
        """记录认证事件。"""
        self.events.append(
            {
                "event": event,
                "user_id": user_id,
                "ip": ip,
                "user_agent": user_agent,
                "result": result,
                "reason": reason,
            }
        )


class _RepoStub:
    """认证仓储桩实现。"""

    def __init__(self) -> None:
        """初始化内存状态。"""
        self.users_by_email: dict[str, dict] = {}
        self.users_by_id: dict[str, dict] = {}
        self.refresh_tokens_by_id: dict[str, dict] = {}
        self.reset_tokens_by_id: dict[str, dict] = {}

    def get_user_by_email(self, email: str) -> dict | None:
        """按邮箱查询用户。"""
        row = self.users_by_email.get(email.lower())
        return deepcopy(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        """按用户 ID 查询用户。"""
        row = self.users_by_id.get(user_id)
        return deepcopy(row) if row else None

    def create_user(self, user_id: str, email: str, password_hash: str, display_name: str, role: str) -> dict:
        """创建用户记录。"""
        row = {
            "user_id": user_id,
            "email": email.lower(),
            "password_hash": password_hash,
            "display_name": display_name,
            "role": role,
            "status": "active",
            "last_login_at": None,
        }
        self.users_by_email[email.lower()] = row
        self.users_by_id[user_id] = row
        return deepcopy(row)

    def update_user_last_login(self, user_id: str) -> None:
        """更新最近登录时间。"""
        if user_id in self.users_by_id:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            self.users_by_id[user_id]["last_login_at"] = now
            email = self.users_by_id[user_id]["email"]
            self.users_by_email[email]["last_login_at"] = now

    def insert_refresh_token(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        expires_at: str,
        ip: str,
        user_agent: str,
    ) -> None:
        """插入刷新令牌记录。"""
        self.refresh_tokens_by_id[token_id] = {
            "token_id": token_id,
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "revoked_at": None,
            "replaced_by_token_id": None,
            "ip": ip,
            "user_agent": user_agent,
        }

    def get_active_refresh_token_by_hash(self, token_hash: str) -> dict | None:
        """按哈希查询活跃刷新令牌。"""
        now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for row in self.refresh_tokens_by_id.values():
            if row["token_hash"] == token_hash and row["revoked_at"] is None and row["expires_at"] > now_text:
                user = self.users_by_id.get(row["user_id"])
                if user:
                    merged = deepcopy(row)
                    merged["role"] = user["role"]
                    return merged
        return None

    def rotate_refresh_token(
        self,
        old_token_id: str,
        new_token_id: str,
        user_id: str,
        new_token_hash: str,
        expires_at: str,
        ip: str,
        user_agent: str,
    ) -> None:
        """轮换刷新令牌。"""
        now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        old = self.refresh_tokens_by_id[old_token_id]
        old["revoked_at"] = now_text
        old["replaced_by_token_id"] = new_token_id
        self.insert_refresh_token(new_token_id, user_id, new_token_hash, expires_at, ip, user_agent)

    def revoke_refresh_token(self, token_id: str) -> None:
        """撤销单个刷新令牌。"""
        if token_id in self.refresh_tokens_by_id:
            self.refresh_tokens_by_id[token_id]["revoked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def insert_password_reset_token(self, reset_id: str, user_id: str, token_hash: str, expires_at: str) -> None:
        """插入重置令牌记录。"""
        self.reset_tokens_by_id[reset_id] = {
            "reset_id": reset_id,
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "used_at": None,
        }

    def get_active_reset_token_by_hash(self, token_hash: str) -> dict | None:
        """按哈希查询活跃重置令牌。"""
        now_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for row in self.reset_tokens_by_id.values():
            if row["token_hash"] == token_hash and row["used_at"] is None and row["expires_at"] > now_text:
                return deepcopy(row)
        return None

    def reset_password_and_revoke_tokens(self, user_id: str, password_hash: str, reset_id: str) -> None:
        """重置密码并撤销用户全部刷新令牌。"""
        if user_id in self.users_by_id:
            self.users_by_id[user_id]["password_hash"] = password_hash
            email = self.users_by_id[user_id]["email"]
            self.users_by_email[email]["password_hash"] = password_hash
        if reset_id in self.reset_tokens_by_id:
            self.reset_tokens_by_id[reset_id]["used_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for row in self.refresh_tokens_by_id.values():
            if row["user_id"] == user_id and row["revoked_at"] is None:
                row["revoked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@unittest.skipIf(AuthService is None, "当前环境需 Python 3.11+ 才能导入 AuthService")
class AuthServiceTestCase(unittest.TestCase):
    """验证认证服务关键业务路径。"""

    def setUp(self) -> None:
        """准备隔离环境与服务对象。"""
        os.environ["AI_INTERVIEW_JWT_SECRET"] = "unit-test-jwt-secret-with-32-chars!!"
        os.environ["AI_INTERVIEW_JWT_ALGORITHM"] = "HS256"
        os.environ["AI_INTERVIEW_ACCESS_TOKEN_TTL_MINUTES"] = "30"
        os.environ["AI_INTERVIEW_REFRESH_TOKEN_TTL_DAYS"] = "7"
        os.environ["AI_INTERVIEW_AUTH_LOGIN_LIMIT_WINDOW_SECONDS"] = "60"
        os.environ["AI_INTERVIEW_AUTH_LOGIN_LIMIT_THRESHOLD"] = "2"
        get_settings.cache_clear()
        self.repo = _RepoStub()
        self.audit = _AuditStub()
        self.service = AuthService(self.repo, self.audit)

    def tearDown(self) -> None:
        """清理环境变量。"""
        os.environ.pop("AI_INTERVIEW_JWT_SECRET", None)
        os.environ.pop("AI_INTERVIEW_JWT_ALGORITHM", None)
        os.environ.pop("AI_INTERVIEW_ACCESS_TOKEN_TTL_MINUTES", None)
        os.environ.pop("AI_INTERVIEW_REFRESH_TOKEN_TTL_DAYS", None)
        os.environ.pop("AI_INTERVIEW_AUTH_LOGIN_LIMIT_WINDOW_SECONDS", None)
        os.environ.pop("AI_INTERVIEW_AUTH_LOGIN_LIMIT_THRESHOLD", None)
        get_settings.cache_clear()

    def test_register_login_refresh_and_logout_flow(self) -> None:
        """验证注册、登录、刷新轮换与登出主路径。"""
        register_res = self.service.register(
            email="test@example.com",
            password="Passw0rd123",
            display_name="测试用户",
            ip="127.0.0.1",
            user_agent="pytest",
        )
        self.assertEqual("test@example.com", register_res["user"]["email"])

        login_res = self.service.login(
            email="test@example.com",
            password="Passw0rd123",
            ip="127.0.0.1",
            user_agent="pytest",
        )
        self.assertEqual("bearer", login_res["token_type"])
        old_refresh = login_res["refresh_token"]

        refresh_res = self.service.refresh(old_refresh, ip="127.0.0.1", user_agent="pytest")
        self.assertNotEqual(old_refresh, refresh_res["refresh_token"])

        with self.assertRaises(ApiError) as invalid_old:
            self.service.refresh(old_refresh, ip="127.0.0.1", user_agent="pytest")
        self.assertEqual("AUTH_401_REFRESH_TOKEN_INVALID", invalid_old.exception.code)

        self.service.logout(refresh_res["refresh_token"], ip="127.0.0.1", user_agent="pytest")
        with self.assertRaises(ApiError) as invalid_logout:
            self.service.refresh(refresh_res["refresh_token"], ip="127.0.0.1", user_agent="pytest")
        self.assertEqual("AUTH_401_REFRESH_TOKEN_INVALID", invalid_logout.exception.code)

    def test_forgot_password_masks_user_existence(self) -> None:
        """验证忘记密码不会暴露邮箱是否存在。"""
        self.service.forgot_password("missing@example.com", ip="127.0.0.1", user_agent="pytest")
        self.assertFalse(self.repo.reset_tokens_by_id)
        self.assertEqual("forgot_password", self.audit.events[-1]["event"])
        self.assertEqual("accepted", self.audit.events[-1]["result"])

    def test_reset_password_rejects_invalid_token(self) -> None:
        """验证无效重置令牌会被拒绝。"""
        with self.assertRaises(ApiError) as exc:
            self.service.reset_password(
                reset_token="invalid-reset-token",
                new_password="Passw0rd123",
                ip="127.0.0.1",
                user_agent="pytest",
            )
        self.assertEqual("AUTH_401_RESET_TOKEN_INVALID", exc.exception.code)

    def test_login_rate_limit_blocks_excessive_attempts(self) -> None:
        """验证连续失败登录会触发限流。"""
        for _ in range(2):
            with self.assertRaises(ApiError) as exc:
                self.service.login("none@example.com", "wrong-password", ip="127.0.0.1", user_agent="pytest")
            self.assertEqual("AUTH_401_INVALID_CREDENTIALS", exc.exception.code)

        with self.assertRaises(ApiError) as limited:
            self.service.login("none@example.com", "wrong-password", ip="127.0.0.1", user_agent="pytest")
        self.assertEqual("AUTH_429_LOGIN_RATE_LIMIT", limited.exception.code)

    def test_refresh_rejects_expired_token(self) -> None:
        """验证过期刷新令牌会被拒绝。"""
        user = self.repo.create_user(
            user_id="usr_expired",
            email="expired@example.com",
            password_hash="pbkdf2_sha256$120000$salt$hash",
            display_name="过期用户",
            role="user",
        )
        token_hash = self.service._hash_token("expired-token")
        self.repo.insert_refresh_token(
            token_id="rt_expired",
            user_id=user["user_id"],
            token_hash=token_hash,
            expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"),
            ip="127.0.0.1",
            user_agent="pytest",
        )
        with self.assertRaises(ApiError) as exc:
            self.service.refresh("expired-token", ip="127.0.0.1", user_agent="pytest")
        self.assertEqual("AUTH_401_REFRESH_TOKEN_INVALID", exc.exception.code)


if __name__ == "__main__":
    unittest.main()
