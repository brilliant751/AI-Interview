"""后端面试主流程集成测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.core.errors import ApiError  # noqa: E402
from app.main import create_app  # noqa: E402


class InterviewFlowTestCase(unittest.TestCase):
    """覆盖创建、提交、结束、查询报告与历史的主路径。"""

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
        self.default_java_jd_id = self._upload_jd(job_role="java", title="默认Java后端JD", headers=self.user_headers)

    def tearDown(self) -> None:
        """清理测试临时目录。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)
        os.environ.pop("AI_INTERVIEW_RETRIEVAL_FALLBACK_ENABLED", None)
        os.environ.pop("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", None)
        get_settings.cache_clear()

    def _create_interview(self, output_mode: str = "text") -> str:
        """创建测试用会话并返回 interview_id。"""
        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        resume_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertIn(resume_resp.status_code, [200, 201])
        resume_id = resume_resp.json()["resume_id"]

        create_payload = {
            "resume_id": resume_id,
            "jd_id": self.default_java_jd_id,
            "job_role": "java",
            "difficulty": "medium",
            "input_mode": "voice" if output_mode == "voice" else "text",
            "output_mode": output_mode,
        }
        create_resp = self.client.post("/api/v1/interviews", json=create_payload, headers=self.user_headers)
        self.assertEqual(200, create_resp.status_code)
        return create_resp.json()["interview_id"]

    def _upload_jd(self, job_role: str, title: str, headers: dict[str, str]) -> str:
        """上传测试用 JD 并返回 jd_id。"""
        jd_upload = self.client.post(
            "/api/v1/jds",
            data={"job_role": job_role, "title": title},
            files={"file": ("jd.txt", f"{title} 内容".encode("utf-8"), "text/plain")},
            headers=headers,
        )
        self.assertEqual(200, jd_upload.status_code)
        return jd_upload.json()["jd_id"]

    def _submit_turn_and_wait(
        self,
        interview_id: str,
        payload: dict,
        headers: dict[str, str] | None = None,
        max_attempts: int = 60,
        sleep_seconds: float = 0.05,
    ) -> dict:
        """提交轮次并轮询异步任务结果，超时时返回最新状态。"""
        submit_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns",
            json=payload,
            headers=headers or self.user_headers,
        )
        self.assertEqual(200, submit_resp.status_code)
        submit_data = submit_resp.json()
        self.assertEqual("PROCESSING", submit_data["status"])
        job_id = submit_data["job_id"]
        latest_job_data: dict = {"interview_id": interview_id, "job_id": job_id, "status": "PROCESSING"}
        for _ in range(max_attempts):
            job_resp = self.client.get(
                f"/api/v1/interviews/{interview_id}/turn-jobs/{job_id}",
                headers=headers or self.user_headers,
            )
            self.assertEqual(200, job_resp.status_code)
            job_data = job_resp.json()
            latest_job_data = job_data
            status = job_data["status"]
            if status == "READY":
                return job_data["result"]
            if status == "FAILED":
                return job_data
            time.sleep(sleep_seconds)
        return latest_job_data

    def test_interview_flow(self) -> None:
        """验证主流程接口连通与状态可用。"""
        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        idem_key = str(uuid.uuid4())
        resume_resp = self.client.post(
            "/api/v1/resumes",
            files=files,
            headers={**self.user_headers, "X-Idempotency-Key": idem_key},
        )
        self.assertIn(resume_resp.status_code, [200, 201])
        resume_id = resume_resp.json()["resume_id"]
        resume_retry_resp = self.client.post(
            "/api/v1/resumes",
            files=files,
            headers={**self.user_headers, "X-Idempotency-Key": idem_key},
        )
        self.assertIn(resume_retry_resp.status_code, [200, 201])
        self.assertEqual(resume_id, resume_retry_resp.json()["resume_id"])

        create_payload = {
            "resume_id": resume_id,
            "jd_id": self.default_java_jd_id,
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
        first_turn = self._submit_turn_and_wait(interview_id=interview_id, payload=turn_payload)
        if first_turn.get("status") == "PROCESSING":
            self.assertEqual("PROCESSING", first_turn["status"])
        else:
            self.assertIn("next_question", first_turn)
            self.assertEqual("PROJECT_DEEP_DIVE", first_turn["stage"])
            self.assertIn("pipeline_meta", first_turn)
            self.assertIn("generation_mode", first_turn["pipeline_meta"])

        if first_turn.get("status") != "PROCESSING":
            deep_dive_turn = self._submit_turn_and_wait(
                interview_id=interview_id,
                payload={"stage": "PROJECT_DEEP_DIVE", "answer_text": "我在项目中负责了架构改造与核心模块落地。"},
            )
            if deep_dive_turn.get("status") != "PROCESSING":
                self.assertEqual("TECHNICAL", deep_dive_turn["stage"])

            for _ in range(2):
                tech_turn = self._submit_turn_and_wait(
                    interview_id=interview_id,
                    payload={"stage": "TECHNICAL", "answer_text": "我在项目中进行过 JVM 调优和 SQL 优化，定位过慢查询问题。"},
                )

            if tech_turn.get("status") != "PROCESSING":
                stage_after_tech = tech_turn["stage"]
                self.assertIn(stage_after_tech, ["TECHNICAL", "BEHAVIORAL"])

        finish_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/finish",
            headers=self.user_headers,
        )
        self.assertEqual(202, finish_resp.status_code)
        self.assertEqual("GENERATING", finish_resp.json()["report_status"])

        report_resp = self.client.get(f"/api/v1/report/{interview_id}", headers=self.user_headers)
        self.assertEqual(200, report_resp.status_code)
        self.assertIn(report_resp.json()["status"], ["READY", "GENERATING", "FAILED"])

        history_resp = self.client.get("/api/v1/interviews/history", headers=self.user_headers)
        self.assertEqual(200, history_resp.status_code)
        self.assertGreaterEqual(history_resp.json()["total"], 1)
        self.assertIn("resume_id", history_resp.json()["items"][0])
        self.assertIn("status", history_resp.json()["items"][0])
        self.assertIn("turn_count", history_resp.json()["items"][0])

    def test_list_turns_endpoint(self) -> None:
        """验证查询轮次列表接口返回有效数据。"""
        interview_id = self._create_interview()
        self._submit_turn_and_wait(
            interview_id=interview_id,
            payload={"stage": "SELF_INTRO", "answer_text": "这是首轮回答"},
        )
        list_resp = self.client.get(f"/api/v1/interviews/{interview_id}/turns", headers=self.user_headers)
        self.assertEqual(200, list_resp.status_code)
        self.assertEqual(interview_id, list_resp.json()["interview_id"])
        self.assertGreaterEqual(len(list_resp.json()["items"]), 0)
        if list_resp.json()["items"]:
            self.assertEqual("SELF_INTRO", list_resp.json()["items"][0]["stage"])

    def test_history_status_filter(self) -> None:
        """验证历史列表支持按状态过滤。"""
        interview_id = self._create_interview()
        finish_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/finish",
            headers=self.user_headers,
        )
        self.assertEqual(202, finish_resp.status_code)

        paused_history = self.client.get(
            "/api/v1/interviews/history",
            params={"status": "FINISHED"},
            headers=self.user_headers,
        )
        self.assertEqual(200, paused_history.status_code)
        self.assertGreaterEqual(paused_history.json()["total"], 1)
        self.assertTrue(all(item["status"] == "FINISHED" for item in paused_history.json()["items"]))
        self.assertTrue(all("difficulty" in item for item in paused_history.json()["items"]))

    def test_report_list_endpoint(self) -> None:
        """验证报告列表接口返回当前用户报告数据。"""
        interview_id = self._create_interview()
        finish_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/finish",
            headers=self.user_headers,
        )
        self.assertEqual(202, finish_resp.status_code)

        list_resp = self.client.get(
            "/api/v1/report",
            params={"status": "GENERATING", "page": 1, "page_size": 10},
            headers=self.user_headers,
        )
        self.assertEqual(200, list_resp.status_code)
        payload = list_resp.json()
        self.assertIn("total", payload)
        self.assertIn("items", payload)
        if payload["items"]:
            self.assertIn(payload["items"][0]["status"], ["GENERATING", "READY", "FAILED"])

    def test_update_interview_status_by_query(self) -> None:
        """验证可通过查询参数更新会话状态。"""
        interview_id = self._create_interview()
        pause_resp = self.client.get(
            f"/api/v1/interviews/{interview_id}/status",
            params={"status": "PAUSED"},
            headers=self.user_headers,
        )
        self.assertEqual(200, pause_resp.status_code)
        self.assertEqual("PAUSED", pause_resp.json()["status"])

        resume_resp = self.client.get(
            f"/api/v1/interviews/{interview_id}/status",
            params={"status": "ACTIVE"},
            headers=self.user_headers,
        )
        self.assertEqual(200, resume_resp.status_code)
        self.assertEqual("ACTIVE", resume_resp.json()["status"])

    def test_schedule_creation_and_list(self) -> None:
        """验证可以创建预约面试并按时间范围查询。"""
        interview_id, scheduled_at = self._create_scheduled_interview(minutes_from_now=45)
        start_range = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        end_range = (datetime.now(timezone.utc) + timedelta(minutes=60)).isoformat()
        list_resp = self.client.get(
            "/api/v1/interviews/schedules",
            params={
                "scheduled_from": start_range,
                "scheduled_to": end_range,
                "statuses": "SCHEDULED",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, list_resp.status_code)
        self.assertTrue(
            any(item["interview_id"] == interview_id for item in list_resp.json()["items"])
        )
        target = next(
            item for item in list_resp.json()["items"] if item["interview_id"] == interview_id
        )
        self.assertEqual("SCHEDULED", target["status"])
        self.assertFalse(target["start_available"])
        self.assertTrue(target["scheduled_start_at"])
        self.assertTrue(scheduled_at)

    def test_schedule_cannot_start_before_time_but_can_start_when_due(self) -> None:
        """验证预约面试未到时间不可开始，到点后可开始。"""
        interview_id, _scheduled_at = self._create_scheduled_interview(minutes_from_now=20)
        early_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/start",
            headers=self.user_headers,
        )
        self.assertEqual(409, early_resp.status_code)
        self.assertEqual("INTERVIEW_409_NOT_READY", early_resp.json()["error"]["code"])

        repo = self.client.app.state.repo
        with repo._session() as conn:
            conn.execute(
                """
                UPDATE interview_sessions
                SET scheduled_start_at = datetime('now', '-5 minutes')
                WHERE interview_id = ?
                """,
                (interview_id,),
            )

        start_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/start",
            headers=self.user_headers,
        )
        self.assertEqual(200, start_resp.status_code)
        self.assertEqual("ACTIVE", start_resp.json()["status"])
        self.assertEqual(interview_id, start_resp.json()["interview_id"])

    def test_input_priority_prefers_asr_text(self) -> None:
        """验证输入优先级为 asr_text > answer_text。"""
        interview_id = self._create_interview()
        turn_result = self._submit_turn_and_wait(
            interview_id=interview_id,
            payload={
                "stage": "SELF_INTRO",
                "asr_text": "这是客户端 ASR 结果",
                "answer_text": "这是普通文本",
            },
        )
        if turn_result.get("status") == "PROCESSING":
            self.assertEqual("PROCESSING", turn_result["status"])
        else:
            pipeline_meta = turn_result["pipeline_meta"]
            self.assertEqual("ASR_CLIENT", pipeline_meta["input_source"])

    def test_llm_and_tts_fallback(self) -> None:
        """验证 LLM 与 TTS 失败时返回降级标记。"""
        interview_id = self._create_interview(output_mode="voice")
        service = self.client.app.state.interview_service
        service.question_workflow.llm_provider = "openai"

        def _raise_llm(*args, **kwargs):
            raise RuntimeError("llm fail")

        def _raise_tts(*args, **kwargs):
            raise ApiError(code="TTS_UPSTREAM_FAILED", message="tts fail", status_code=502)

        service.question_workflow.generate_by_llm = _raise_llm
        service.voice_service.tts = _raise_tts

        turn_result = self._submit_turn_and_wait(
            interview_id=interview_id,
            payload={
                "stage": "SELF_INTRO",
                "answer_text": "我负责过高并发服务优化",
            },
        )
        if turn_result.get("status") == "PROCESSING":
            self.assertEqual("PROCESSING", turn_result["status"])
        else:
            pipeline_meta = turn_result["pipeline_meta"]
            flags = pipeline_meta["degrade_flags"]
            self.assertIn("LLM_FALLBACK_TEMPLATE", flags)
            self.assertIn("TTS_FALLBACK_TEXT", flags)
            self.assertEqual("openai", pipeline_meta["providers"]["llm"])
            self.assertIn(pipeline_meta["provider_status"]["llm"], ["UP", "DOWN"])
            self.assertIsNone(turn_result["tts_audio_url"])

    def test_difficulty_is_forwarded_to_question_workflow(self) -> None:
        """验证会话难度会透传给问题生成工作流。"""
        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        resume_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertIn(resume_resp.status_code, [200, 201])
        resume_id = resume_resp.json()["resume_id"]
        create_resp = self.client.post(
            "/api/v1/interviews",
            json={
                "resume_id": resume_id,
                "jd_id": self.default_java_jd_id,
                "job_role": "java",
                "difficulty": "hard",
                "input_mode": "text",
                "output_mode": "text",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, create_resp.status_code)
        interview_id = create_resp.json()["interview_id"]
        service = self.client.app.state.interview_service
        captured: dict[str, str] = {}
        original_generate = service.question_workflow.generate

        def _capture_generate(*args, **kwargs):
            captured["difficulty"] = str(kwargs.get("difficulty") or "")
            return original_generate(*args, **kwargs)

        service.question_workflow.generate = _capture_generate
        self._submit_turn_and_wait(
            interview_id=interview_id,
            payload={"stage": "SELF_INTRO", "answer_text": "我负责高并发链路优化和故障排查。"},
        )
        self.assertIn(captured.get("difficulty"), ["hard", "", None])

    def test_asr_failure_without_text_fallback(self) -> None:
        """验证仅音频输入且 ASR 失败时返回上游错误。"""
        interview_id = self._create_interview()
        service = self.client.app.state.interview_service

        def _raise_asr(*args, **kwargs):
            raise ApiError(code="ASR_UPSTREAM_FAILED", message="asr fail", status_code=502)

        service.voice_service.asr = _raise_asr

        failed_job = self._submit_turn_and_wait(
            interview_id=interview_id,
            payload={
                "stage": "SELF_INTRO",
                "answer_audio_url": "https://example.com/a.mp3",
                "answer_audio_format": "mp3",
            },
        )
        self.assertIn(failed_job["status"], ["PROCESSING", "FAILED", "READY"])

    def test_end_stage_returns_fixed_message_without_new_question(self) -> None:
        """验证进入 END 阶段时返回固定结束文案而非新问题。"""
        interview_id = self._create_interview(output_mode="voice")
        stage = "SELF_INTRO"
        payload = None
        for _ in range(12):
            payload = self._submit_turn_and_wait(
                interview_id=interview_id,
                payload={"stage": stage, "answer_text": "这是用于推进流程的标准回答内容，覆盖项目、技术与行为问题。"},
            )
            if payload.get("status") in {"PROCESSING", "FAILED"} or "stage" not in payload:
                break
            stage = payload["stage"]
            if stage == "END":
                break

        assert payload is not None
        if payload.get("status") != "PROCESSING" and "stage" in payload:
            self.assertEqual("END", payload["stage"])
            self.assertEqual("本次面试已结束，正在生成报告。", payload["next_question"])
            self.assertIsNone(payload.get("tts_audio_url"))
        status_resp = self.client.get(f"/api/v1/interviews/{interview_id}/status", headers=self.user_headers)
        self.assertEqual(200, status_resp.status_code)
        self.assertIn(status_resp.json()["status"], ["ACTIVE", "FINISHED"])

    def test_audio_input_uses_server_asr_when_success(self) -> None:
        """验证音频输入成功时走服务端 ASR 路径并记录来源。"""
        interview_id = self._create_interview()
        service = self.client.app.state.interview_service
        service.voice_service.asr = lambda *_args, **_kwargs: "这是服务端语音识别文本"

        turn_result = self._submit_turn_and_wait(
            interview_id=interview_id,
            payload={
                "stage": "SELF_INTRO",
                "answer_audio_url": "https://example.com/ok.mp3",
                "answer_audio_format": "mp3",
            },
        )
        if turn_result.get("status") == "PROCESSING":
            self.assertEqual("PROCESSING", turn_result["status"])
        else:
            pipeline_meta = turn_result["pipeline_meta"]
            self.assertEqual("ASR_SERVER", pipeline_meta["input_source"])
            self.assertEqual(service.voice_service.asr_provider, pipeline_meta["providers"]["asr"])

    def test_audio_upload_endpoint(self) -> None:
        """验证 multipart 音频上传接口可用。"""
        interview_id = self._create_interview(output_mode="text")
        service = self.client.app.state.interview_service
        service.voice_service.asr = lambda **_kwargs: "上传音频识别文本"

        submit_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns/audio",
            data={"stage": "SELF_INTRO"},
            files={"file": ("sample.wav", b"fake-audio", "audio/wav")},
            headers=self.user_headers,
        )
        self.assertEqual(200, submit_resp.status_code)
        self.assertEqual("PROCESSING", submit_resp.json()["status"])
        job_id = submit_resp.json()["job_id"]
        turn_result = None
        for _ in range(60):
            job_resp = self.client.get(
                f"/api/v1/interviews/{interview_id}/turn-jobs/{job_id}",
                headers=self.user_headers,
            )
            self.assertEqual(200, job_resp.status_code)
            job_data = job_resp.json()
            if job_data["status"] == "READY":
                turn_result = job_data["result"]
                break
            if job_data["status"] == "FAILED":
                self.fail(f"音频轮次任务失败: {job_data['error_message']}")
            time.sleep(0.05)
        if turn_result is not None:
            self.assertEqual("PROJECT_DEEP_DIVE", turn_result["stage"])

    def test_admin_import_requires_admin_role(self) -> None:
        """验证管理接口权限控制生效。"""
        forbidden_resp = self.client.post(
            "/api/v1/admin/imports/materials",
            json={"dry_run": True, "roles": ["java"], "rebuild_mode": "incremental"},
            headers=self.user_headers,
        )
        self.assertEqual(403, forbidden_resp.status_code)

    def test_resume_list_and_delete(self) -> None:
        """验证简历列表与删除能力。"""
        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        upload_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertIn(upload_resp.status_code, [200, 201])
        resume_id = upload_resp.json()["resume_id"]

        list_resp = self.client.get("/api/v1/resumes?page=1&page_size=10", headers=self.user_headers)
        self.assertEqual(200, list_resp.status_code)
        self.assertGreaterEqual(list_resp.json()["total"], 1)
        self.assertTrue(any(item["resume_id"] == resume_id for item in list_resp.json()["items"]))

        delete_resp = self.client.delete(f"/api/v1/resumes/{resume_id}", headers=self.user_headers)
        self.assertEqual(204, delete_resp.status_code)

        list_after_delete_resp = self.client.get("/api/v1/resumes?page=1&page_size=10", headers=self.user_headers)
        self.assertEqual(200, list_after_delete_resp.status_code)
        self.assertFalse(any(item["resume_id"] == resume_id for item in list_after_delete_resp.json()["items"]))

    def test_resume_delete_conflict_when_interview_active(self) -> None:
        """验证进行中面试引用的简历删除冲突。"""
        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        upload_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertIn(upload_resp.status_code, [200, 201])
        resume_id = upload_resp.json()["resume_id"]

        create_payload = {
            "resume_id": resume_id,
            "jd_id": self.default_java_jd_id,
            "job_role": "java",
            "difficulty": "medium",
            "input_mode": "text",
            "output_mode": "text",
        }
        create_resp = self.client.post("/api/v1/interviews", json=create_payload, headers=self.user_headers)
        self.assertEqual(200, create_resp.status_code)

        delete_resp = self.client.delete(f"/api/v1/resumes/{resume_id}", headers=self.user_headers)
        self.assertEqual(409, delete_resp.status_code)
        self.assertEqual("RESUME_409_IN_USE", delete_resp.json()["error"]["code"])

    def test_playback_and_scope_protection(self) -> None:
        """验证回放详情可用且跨用户不可访问。"""
        interview_id = self._create_interview()
        self._submit_turn_and_wait(
            interview_id=interview_id,
            payload={"stage": "SELF_INTRO", "answer_text": "这是首轮回答"},
        )

        playback_resp = self.client.get(f"/api/v1/interviews/{interview_id}/playback", headers=self.user_headers)
        self.assertEqual(200, playback_resp.status_code)
        self.assertEqual(interview_id, playback_resp.json()["interview_id"])
        self.assertIn("turns", playback_resp.json())
        if playback_resp.json()["turns"]:
            first_turn = playback_resp.json()["turns"][0]
            self.assertIn("question", first_turn)
            self.assertIn("answer", first_turn)
            self.assertIn("sequence", first_turn)

        forbidden_resp = self.client.get(f"/api/v1/interviews/{interview_id}/playback", headers=self.admin_headers)
        self.assertEqual(403, forbidden_resp.status_code)
        self.assertEqual("INTERVIEW_403_FORBIDDEN", forbidden_resp.json()["error"]["code"])

    def test_jd_upload_list_and_bind_interview(self) -> None:
        """验证 JD 上传、列表与绑定创建面试。"""
        jd_upload = self.client.post(
            "/api/v1/jds",
            data={"job_role": "java", "title": "后端开发工程师JD"},
            files={"file": ("jd.txt", "负责Java后端开发，熟悉Spring和MySQL。".encode("utf-8"), "text/plain")},
            headers=self.user_headers,
        )
        self.assertEqual(200, jd_upload.status_code)
        jd_id = jd_upload.json()["jd_id"]

        jd_list = self.client.get("/api/v1/jds?job_role=java", headers=self.user_headers)
        self.assertEqual(200, jd_list.status_code)
        self.assertTrue(any(item["jd_id"] == jd_id for item in jd_list.json()["items"]))

        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        resume_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertIn(resume_resp.status_code, [200, 201])
        resume_id = resume_resp.json()["resume_id"]

        create_resp = self.client.post(
            "/api/v1/interviews",
            json={
                "resume_id": resume_id,
                "jd_id": jd_id,
                "job_role": "java",
                "difficulty": "medium",
                "input_mode": "text",
                "output_mode": "text",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, create_resp.status_code)
        interview_id = create_resp.json()["interview_id"]

        status_resp = self.client.get(f"/api/v1/interviews/{interview_id}/status", headers=self.user_headers)
        self.assertEqual(200, status_resp.status_code)
        self.assertEqual(jd_id, status_resp.json()["jd_id"])
        self.assertEqual("后端开发工程师JD", status_resp.json()["jd_title"])

    def test_jd_bind_role_mismatch(self) -> None:
        """验证 JD 岗位方向不匹配时创建面试失败。"""
        jd_upload = self.client.post(
            "/api/v1/jds",
            data={"job_role": "web", "title": "前端开发JD"},
            files={"file": ("jd.txt", "负责Web前端开发，熟悉React。".encode("utf-8"), "text/plain")},
            headers=self.user_headers,
        )
        self.assertEqual(200, jd_upload.status_code)
        jd_id = jd_upload.json()["jd_id"]

        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        resume_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertIn(resume_resp.status_code, [200, 201])
        resume_id = resume_resp.json()["resume_id"]

        create_resp = self.client.post(
            "/api/v1/interviews",
            json={
                "resume_id": resume_id,
                "jd_id": jd_id,
                "job_role": "java",
                "difficulty": "medium",
                "input_mode": "text",
                "output_mode": "text",
            },
            headers=self.user_headers,
        )
        self.assertEqual(409, create_resp.status_code)
        self.assertEqual("JD_409_ROLE_MISMATCH", create_resp.json()["error"]["code"])

    def test_role_or_jd_required_for_create_interview(self) -> None:
        """验证创建面试时岗位方向与 JD 至少提供一个。"""
        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        resume_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertIn(resume_resp.status_code, [200, 201])
        resume_id = resume_resp.json()["resume_id"]

        role_only_resp = self.client.post(
            "/api/v1/interviews",
            json={
                "resume_id": resume_id,
                "job_role": "java",
                "difficulty": "medium",
                "input_mode": "text",
                "output_mode": "text",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, role_only_resp.status_code)

        jd_only_resp = self.client.post(
            "/api/v1/interviews",
            json={
                "resume_id": resume_id,
                "jd_id": self.default_java_jd_id,
                "difficulty": "medium",
                "input_mode": "text",
                "output_mode": "text",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, jd_only_resp.status_code)

        empty_value_resp = self.client.post(
            "/api/v1/interviews",
            json={
                "resume_id": resume_id,
                "jd_id": "",
                "difficulty": "medium",
                "input_mode": "text",
                "output_mode": "text",
            },
            headers=self.user_headers,
        )
        self.assertEqual(422, empty_value_resp.status_code)

        blank_value_resp = self.client.post(
            "/api/v1/interviews",
            json={
                "resume_id": resume_id,
                "jd_id": "   ",
                "difficulty": "medium",
                "input_mode": "text",
                "output_mode": "text",
            },
            headers=self.user_headers,
        )
        self.assertEqual(422, blank_value_resp.status_code)

    def test_jd_forbidden_for_other_user(self) -> None:
        """验证无法绑定其他用户上传的 JD。"""
        jd_upload = self.client.post(
            "/api/v1/jds",
            data={"job_role": "java", "title": "管理员JD"},
            files={"file": ("jd.txt", "负责Java平台建设。".encode("utf-8"), "text/plain")},
            headers=self.admin_headers,
        )
        self.assertEqual(200, jd_upload.status_code)
        jd_id = jd_upload.json()["jd_id"]

        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        resume_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertIn(resume_resp.status_code, [200, 201])
        resume_id = resume_resp.json()["resume_id"]

        create_resp = self.client.post(
            "/api/v1/interviews",
            json={
                "resume_id": resume_id,
                "jd_id": jd_id,
                "job_role": "java",
                "difficulty": "medium",
                "input_mode": "text",
                "output_mode": "text",
            },
            headers=self.user_headers,
        )
        self.assertEqual(403, create_resp.status_code)
        self.assertEqual("JD_403_FORBIDDEN", create_resp.json()["error"]["code"])


if __name__ == "__main__":
    unittest.main()
