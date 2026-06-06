"""面试预约主流程集成测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


class InterviewScheduleFlowTestCase(unittest.TestCase):
    """覆盖预约创建、查询、取消、开始与完成回写。"""

    def setUp(self) -> None:
        """初始化测试环境与客户端。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AI_INTERVIEW_DB_PATH"] = os.path.join(self.tmpdir.name, "test.db")
        os.environ["AI_INTERVIEW_RETRIEVAL_FALLBACK_ENABLED"] = "true"
        os.environ["AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN"] = "true"
        get_settings.cache_clear()
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.user_headers = {"Authorization": "Bearer user-token"}
        self.admin_headers = {"Authorization": "Bearer admin-token"}
        self.repo = self.client.app.state.repo
        self.default_java_jd_id = self._upload_jd(job_role="java", title="预约测试 JD", headers=self.user_headers)

    def tearDown(self) -> None:
        """清理测试环境。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)
        os.environ.pop("AI_INTERVIEW_RETRIEVAL_FALLBACK_ENABLED", None)
        os.environ.pop("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", None)
        get_settings.cache_clear()

    def _upload_jd(self, job_role: str, title: str, headers: dict[str, str]) -> str:
        """上传测试用 JD。"""
        jd_upload = self.client.post(
            "/api/v1/jds",
            data={"job_role": job_role, "title": title},
            files={"file": ("jd.txt", f"{title} 内容".encode("utf-8"), "text/plain")},
            headers=headers,
        )
        self.assertEqual(200, jd_upload.status_code)
        return jd_upload.json()["jd_id"]

    def _create_resume(self) -> str:
        """创建测试简历。"""
        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        resume_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertIn(resume_resp.status_code, [200, 201])
        return resume_resp.json()["resume_id"]

    def _build_schedule_payload(self, resume_id: str, start_offset_minutes: int = 30) -> dict:
        """构造预约请求体。"""
        scheduled_at = datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(minutes=start_offset_minutes)
        return {
            "title": "预约 Java 模拟面试",
            "scheduled_start_at": scheduled_at.isoformat(),
            "duration_minutes": 45,
            "resume_id": resume_id,
            "jd_id": self.default_java_jd_id,
            "difficulty": "medium",
            "input_mode": "text",
            "output_mode": "text",
            "session_name": "预约 Java 模拟面试",
            "question_types": ["project", "technical", "scenario"],
        }

    def test_create_list_detail_and_calendar(self) -> None:
        """验证预约可创建、查询详情并导出日历文件。"""
        resume_id = self._create_resume()
        create_resp = self.client.post(
            "/api/v1/interview-schedules",
            json=self._build_schedule_payload(resume_id),
            headers=self.user_headers,
        )
        self.assertEqual(201, create_resp.status_code)
        schedule_id = create_resp.json()["schedule_id"]
        self.assertIn("calendar.google.com", create_resp.json()["google_calendar_url"])
        self.assertIn("outlook.office.com", create_resp.json()["outlook_calendar_url"])

        list_resp = self.client.get("/api/v1/interview-schedules", headers=self.user_headers)
        self.assertEqual(200, list_resp.status_code)
        self.assertEqual(1, list_resp.json()["total"])
        self.assertEqual(schedule_id, list_resp.json()["items"][0]["schedule_id"])
        self.assertIn("calendar.google.com", list_resp.json()["items"][0]["google_calendar_url"])

        detail_resp = self.client.get(f"/api/v1/interview-schedules/{schedule_id}", headers=self.user_headers)
        self.assertEqual(200, detail_resp.status_code)
        self.assertEqual("scheduled", detail_resp.json()["status"])
        self.assertEqual(resume_id, detail_resp.json()["resume_id"])
        self.assertIn("calendar.google.com", detail_resp.json()["google_calendar_url"])
        self.assertIn("outlook.office.com", detail_resp.json()["outlook_calendar_url"])

        calendar_resp = self.client.get(
            f"/api/v1/interview-schedules/{schedule_id}/calendar.ics",
            headers=self.user_headers,
        )
        self.assertEqual(200, calendar_resp.status_code)
        self.assertEqual("text/calendar; charset=utf-8", calendar_resp.headers["content-type"])
        self.assertIn("BEGIN:VCALENDAR", calendar_resp.text)
        self.assertIn("BEGIN:VALARM", calendar_resp.text)

    def test_cancel_schedule(self) -> None:
        """验证可取消未开始预约。"""
        resume_id = self._create_resume()
        create_resp = self.client.post(
            "/api/v1/interview-schedules",
            json=self._build_schedule_payload(resume_id),
            headers=self.user_headers,
        )
        schedule_id = create_resp.json()["schedule_id"]

        cancel_resp = self.client.post(
            f"/api/v1/interview-schedules/{schedule_id}/cancel",
            json={"reason": "临时有事"},
            headers=self.user_headers,
        )
        self.assertEqual(200, cancel_resp.status_code)
        self.assertEqual("cancelled", cancel_resp.json()["status"])

    def test_start_schedule_and_finish_backfill(self) -> None:
        """验证预约开始后创建真实会话，并在结束后回写完成状态。"""
        resume_id = self._create_resume()
        create_resp = self.client.post(
            "/api/v1/interview-schedules",
            json=self._build_schedule_payload(resume_id),
            headers=self.user_headers,
        )
        schedule_id = create_resp.json()["schedule_id"]
        self.assertTrue(self.repo.update_schedule_status(schedule_id, "user-default", "ready"))

        start_resp = self.client.post(
            f"/api/v1/interview-schedules/{schedule_id}/start",
            headers=self.user_headers,
        )
        self.assertEqual(200, start_resp.status_code)
        interview_id = start_resp.json()["interview_id"]
        self.assertTrue(interview_id.startswith("int_"))

        finish_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/finish",
            headers=self.user_headers,
        )
        self.assertEqual(202, finish_resp.status_code)

        detail_resp = self.client.get(f"/api/v1/interview-schedules/{schedule_id}", headers=self.user_headers)
        self.assertEqual(200, detail_resp.status_code)
        self.assertEqual("completed", detail_resp.json()["status"])
        self.assertEqual(interview_id, detail_resp.json()["interview_id"])

    def test_schedule_forbidden_for_other_user(self) -> None:
        """验证其他账号不可访问当前用户预约。"""
        resume_id = self._create_resume()
        create_resp = self.client.post(
            "/api/v1/interview-schedules",
            json=self._build_schedule_payload(resume_id),
            headers=self.user_headers,
        )
        schedule_id = create_resp.json()["schedule_id"]

        detail_resp = self.client.get(f"/api/v1/interview-schedules/{schedule_id}", headers=self.admin_headers)
        self.assertEqual(403, detail_resp.status_code)
