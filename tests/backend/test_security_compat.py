"""鉴权兼容开关测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


class SecurityCompatTestCase(unittest.TestCase):
    """验证 dev 静态 token 兼容行为。"""

    def setUp(self) -> None:
        """初始化测试环境。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AI_INTERVIEW_DB_PATH"] = os.path.join(self.tmpdir.name, "test.db")

    def tearDown(self) -> None:
        """清理测试环境。"""
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)
        os.environ.pop("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", None)
        get_settings.cache_clear()

    def test_dev_static_token_enabled(self) -> None:
        """开关开启时应允许旧 token。"""
        os.environ["AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN"] = "true"
        get_settings.cache_clear()
        client = TestClient(create_app())
        with client:
            resp = client.get(
                "/api/v1/interviews/history",
                headers={"Authorization": "Bearer user-token"},
            )
        self.assertEqual(200, resp.status_code, msg=resp.text)

    def test_dev_static_token_disabled(self) -> None:
        """开关关闭时应拒绝旧 token。"""
        os.environ["AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN"] = "false"
        get_settings.cache_clear()
        client = TestClient(create_app())
        with client:
            resp = client.get(
                "/api/v1/interviews/history",
                headers={"Authorization": "Bearer user-token"},
            )
        self.assertEqual(401, resp.status_code, msg=resp.text)


if __name__ == "__main__":
    unittest.main()
