"""Provider 健康检查接口测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

from fastapi.testclient import TestClient

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


class ProviderHealthTestCase(unittest.TestCase):
    """验证 provider health 接口聚合逻辑。"""

    def setUp(self) -> None:
        """初始化测试环境与客户端。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AI_INTERVIEW_DB_PATH"] = os.path.join(self.tmpdir.name, "test.db")
        os.environ["AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN"] = "true"
        get_settings.cache_clear()
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.admin_headers = {"Authorization": "Bearer admin-token"}

    def tearDown(self) -> None:
        """清理测试临时目录。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)
        os.environ.pop("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", None)

    def test_provider_health_up(self) -> None:
        """默认 mock provider 返回 UP。"""
        resp = self.client.get("/api/v1/admin/providers/health", headers=self.admin_headers)
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertIn(body["overall"], ["UP", "DEGRADED", "DOWN"])
        self.assertIn("llm", body["providers"])
        self.assertIn("status", body["providers"]["llm"])

    def test_provider_health_without_auth(self) -> None:
        """provider health 接口无需认证信息。"""
        resp = self.client.get("/api/v1/admin/providers/health")
        self.assertEqual(200, resp.status_code)

    def test_provider_health_degraded(self) -> None:
        """存在部分 provider 异常时返回 DEGRADED。"""
        service = self.client.app.state.interview_service
        service.voice_service.health_details = lambda: {
            "asr": {
                "status": "DOWN",
                "provider": "funasr",
                "model": "paraformer-zh",
                "latency_ms": 1,
                "error_message": "down",
            },
            "tts": {
                "status": "UP",
                "provider": "paddlespeech",
                "model": "fastspeech2_csmsc",
                "latency_ms": 1,
                "error_message": "",
            },
        }
        service.question_workflow.health_details = lambda: {
            "status": "UP",
            "provider": "ollama",
            "model": "deepseek-r1:8b",
            "latency_ms": 1,
            "error_message": "",
        }
        service.rag_service.health = lambda: {
            "status": "UP",
            "provider": "ollama-embedding",
            "model": "nomic-embed-text",
            "latency_ms": 1,
            "error_message": "",
        }

        resp = self.client.get("/api/v1/admin/providers/health", headers=self.admin_headers)
        self.assertEqual(200, resp.status_code)
        self.assertEqual("DEGRADED", resp.json()["overall"])


if __name__ == "__main__":
    unittest.main()
