"""管理端材料导入接口测试。"""

from __future__ import annotations

import os
import tempfile
import time
import unittest
import uuid

from fastapi.testclient import TestClient

import sys

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.schemas import MaterialImportRequest  # noqa: E402
from app.services.material_import_service import _ImportTask  # noqa: E402


class AdminImportsTestCase(unittest.TestCase):
    """验证导入任务接口行为。"""

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
        """清理测试环境。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)
        os.environ.pop("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", None)
        get_settings.cache_clear()

    def test_trigger_task_and_query_status(self) -> None:
        """验证触发任务后可查询状态。"""
        idem_key = str(uuid.uuid4())
        resp = self.client.post(
            "/api/v1/admin/imports/materials",
            json={"dry_run": True, "rebuild_mode": "incremental", "roles": ["java"]},
            headers={**self.admin_headers, "X-Idempotency-Key": idem_key},
        )
        self.assertEqual(202, resp.status_code, msg=resp.text)
        payload = resp.json()
        self.assertIn("task_id", payload)

        status_payload = payload
        for _ in range(40):
            status_resp = self.client.get(
                f"/api/v1/admin/imports/materials/{payload['task_id']}",
                headers=self.admin_headers,
            )
            self.assertEqual(200, status_resp.status_code, msg=status_resp.text)
            status_payload = status_resp.json()
            if status_payload["status"] in {"SUCCESS", "FAILED", "PARTIAL_SUCCESS"}:
                break
            time.sleep(0.1)
        self.assertIn(status_payload["status"], {"SUCCESS", "FAILED", "PARTIAL_SUCCESS"})

    def test_same_idempotency_key_returns_same_task(self) -> None:
        """验证同幂等键返回同一个任务。"""
        idem_key = str(uuid.uuid4())
        payload = {"dry_run": True, "rebuild_mode": "incremental", "roles": ["java"]}
        first = self.client.post(
            "/api/v1/admin/imports/materials",
            json=payload,
            headers={**self.admin_headers, "X-Idempotency-Key": idem_key},
        )
        second = self.client.post(
            "/api/v1/admin/imports/materials",
            json=payload,
            headers={**self.admin_headers, "X-Idempotency-Key": idem_key},
        )
        self.assertEqual(202, first.status_code, msg=first.text)
        self.assertEqual(202, second.status_code, msg=second.text)
        self.assertEqual(first.json()["task_id"], second.json()["task_id"])

    def test_reject_unsupported_models(self) -> None:
        """验证不支持模型时返回 400。"""
        resp = self.client.post(
            "/api/v1/admin/imports/materials",
            json={
                "dry_run": True,
                "rebuild_mode": "incremental",
                "roles": ["java"],
                "chunk_model": "other-model",
                "embedding_model": "nomic-embed-text",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(400, resp.status_code, msg=resp.text)
        self.assertEqual("KB_BUILD_400", resp.json()["error"]["code"])

    def test_full_rebuild_conflict(self) -> None:
        """验证全量任务并发冲突返回 409。"""
        service = self.client.app.state.material_import_service
        service._tasks["mock-running-full"] = _ImportTask(
            payload=MaterialImportRequest(
                rebuild_mode="full",
                roles=["java"],
                dry_run=False,
                chunk_model="qwen3.5-2b",
                embedding_model="nomic-embed-text",
            ),
            status="RUNNING",
            stage="embedding",
            progress=50,
            last_error="",
            report_path="",
            runner=None,
        )
        second = self.client.post(
            "/api/v1/admin/imports/materials",
            json={"dry_run": False, "rebuild_mode": "full", "roles": ["web"]},
            headers={**self.admin_headers, "X-Idempotency-Key": str(uuid.uuid4())},
        )
        self.assertEqual(409, second.status_code, msg=second.text)
        self.assertEqual("KB_BUILD_409", second.json()["error"]["code"])


if __name__ == "__main__":
    unittest.main()
