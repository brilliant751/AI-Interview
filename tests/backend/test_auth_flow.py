"""认证主流程集成测试。"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


class AuthFlowTestCase(unittest.TestCase):
    """验证注册、登录、刷新、登出与重置流程。"""

    def setUp(self) -> None:
        """初始化测试环境。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AI_INTERVIEW_DB_PATH"] = os.path.join(self.tmpdir.name, "test.db")
        os.environ["AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN"] = "false"
        get_settings.cache_clear()
        self.client = TestClient(create_app())
        self.client.__enter__()

    def tearDown(self) -> None:
        """清理测试环境。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)
        os.environ.pop("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", None)
        get_settings.cache_clear()

    def test_register_login_refresh_logout(self) -> None:
        """验证注册、登录、刷新轮换、登出全链路。"""
        email = f"u_{uuid.uuid4().hex[:8]}@example.com"
        register_resp = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Passw0rd123",
                "display_name": "测试用户",
            },
        )
        self.assertEqual(201, register_resp.status_code, msg=register_resp.text)

        login_resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Passw0rd123"},
        )
        self.assertEqual(200, login_resp.status_code, msg=login_resp.text)
        token_payload = login_resp.json()

        me_resp = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token_payload['access_token']}"},
        )
        self.assertEqual(200, me_resp.status_code, msg=me_resp.text)
        self.assertEqual(email, me_resp.json()["user"]["email"])

        refresh_resp = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token_payload["refresh_token"]},
        )
        self.assertEqual(200, refresh_resp.status_code, msg=refresh_resp.text)
        refreshed = refresh_resp.json()
        self.assertNotEqual(token_payload["refresh_token"], refreshed["refresh_token"])

        old_refresh_resp = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token_payload["refresh_token"]},
        )
        self.assertEqual(401, old_refresh_resp.status_code)

        logout_resp = self.client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {refreshed['access_token']}"},
            json={"refresh_token": refreshed["refresh_token"]},
        )
        self.assertEqual(204, logout_resp.status_code, msg=logout_resp.text)

        refresh_after_logout = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refreshed["refresh_token"]},
        )
        self.assertEqual(401, refresh_after_logout.status_code)

    def test_reset_password_should_revoke_refresh_tokens(self) -> None:
        """验证重置密码后旧 refresh token 失效。"""
        email = f"u_{uuid.uuid4().hex[:8]}@example.com"
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "Passw0rd123",
                "display_name": "测试用户",
            },
        )
        login_resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "Passw0rd123"},
        )
        self.assertEqual(200, login_resp.status_code, msg=login_resp.text)
        old_refresh = login_resp.json()["refresh_token"]

        repo = self.client.app.state.repo
        user = repo.get_user_by_email(email)
        self.assertIsNotNone(user)
        reset_plain = f"rst_{uuid.uuid4().hex}"
        repo.insert_password_reset_token(
            reset_id=f"rst_id_{uuid.uuid4().hex[:12]}",
            user_id=user["user_id"],
            token_hash=hashlib.sha256(reset_plain.encode("utf-8")).hexdigest(),
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
        )

        reset_resp = self.client.post(
            "/api/v1/auth/reset-password",
            json={"reset_token": reset_plain, "new_password": "NewPassw0rd123"},
        )
        self.assertEqual(204, reset_resp.status_code, msg=reset_resp.text)

        refresh_resp = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        self.assertEqual(401, refresh_resp.status_code)


if __name__ == "__main__":
    unittest.main()
