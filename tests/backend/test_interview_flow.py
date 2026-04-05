"""后端面试主流程集成测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import uuid

from fastapi.testclient import TestClient

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


class InterviewFlowTestCase(unittest.TestCase):
    """覆盖创建、提交、结束、查询报告与历史的主路径。"""

    def setUp(self) -> None:
        """初始化测试环境与客户端。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AI_INTERVIEW_DB_PATH"] = os.path.join(self.tmpdir.name, "test.db")
        get_settings.cache_clear()
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.user_headers = {"Authorization": "Bearer user-token"}
        self.admin_headers = {"Authorization": "Bearer admin-token"}

    def tearDown(self) -> None:
        """清理测试临时目录。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)

    def test_interview_flow(self) -> None:
        """验证主流程接口连通与状态可用。"""
        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        idem_key = str(uuid.uuid4())
        resume_resp = self.client.post(
            "/api/v1/resumes",
            files=files,
            headers={**self.user_headers, "X-Idempotency-Key": idem_key},
        )
        self.assertEqual(200, resume_resp.status_code)
        resume_id = resume_resp.json()["resume_id"]
        resume_retry_resp = self.client.post(
            "/api/v1/resumes",
            files=files,
            headers={**self.user_headers, "X-Idempotency-Key": idem_key},
        )
        self.assertEqual(200, resume_retry_resp.status_code)
        self.assertEqual(resume_id, resume_retry_resp.json()["resume_id"])

        create_payload = {
            "resume_id": resume_id,
            "job_role": "java",
            "difficulty": "medium",
            "input_mode": "text",
            "output_mode": "text",
        }
        create_resp = self.client.post(
            "/api/v1/interviews",
            json=create_payload,
            headers={**self.user_headers, "X-Idempotency-Key": str(uuid.uuid4())},
        )
        self.assertEqual(200, create_resp.status_code)
        interview_id = create_resp.json()["interview_id"]
        self.assertEqual("SELF_INTRO", create_resp.json()["current_stage"])

        turn_payload = {"stage": "SELF_INTRO", "answer_text": "我主要负责后端服务与性能优化。"}
        turn_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns",
            json=turn_payload,
            headers=self.user_headers,
        )
        self.assertEqual(200, turn_resp.status_code)
        self.assertIn("next_question", turn_resp.json())
        self.assertEqual("TECHNICAL", turn_resp.json()["stage"])

        for _ in range(2):
            tech_turn = self.client.post(
                f"/api/v1/interviews/{interview_id}/turns",
                json={"stage": "TECHNICAL", "answer_text": "我在项目中进行过 JVM 调优和 SQL 优化，定位过慢查询问题。"},
                headers=self.user_headers,
            )
            self.assertEqual(200, tech_turn.status_code)

        stage_after_tech = tech_turn.json()["stage"]
        self.assertIn(stage_after_tech, ["TECHNICAL", "BEHAVIORAL"])

        finish_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/finish",
            headers=self.user_headers,
        )
        self.assertEqual(202, finish_resp.status_code)
        self.assertEqual("GENERATING", finish_resp.json()["report_status"])

        report_resp = self.client.get(f"/api/v1/report/{interview_id}", headers=self.user_headers)
        self.assertEqual(200, report_resp.status_code)
        self.assertIn(report_resp.json()["status"], ["READY", "GENERATING"])

        history_resp = self.client.get("/api/v1/interviews/history", headers=self.user_headers)
        self.assertEqual(200, history_resp.status_code)
        self.assertGreaterEqual(history_resp.json()["total"], 1)

    def test_admin_import_requires_admin_role(self) -> None:
        """验证管理接口权限控制生效。"""
        forbidden_resp = self.client.post("/api/v1/admin/imports/materials", headers=self.user_headers)
        self.assertEqual(403, forbidden_resp.status_code)


if __name__ == "__main__":
    unittest.main()
