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

    def tearDown(self) -> None:
        """清理测试临时目录。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)
        os.environ.pop("AI_INTERVIEW_RETRIEVAL_FALLBACK_ENABLED", None)
        os.environ.pop("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", None)

    def _create_interview(self, output_mode: str = "text") -> str:
        """创建测试用会话并返回 interview_id。"""
        files = {"file": ("resume.pdf", b"mock-pdf-content", "application/pdf")}
        resume_resp = self.client.post("/api/v1/resumes", files=files, headers=self.user_headers)
        self.assertEqual(200, resume_resp.status_code)
        resume_id = resume_resp.json()["resume_id"]

        create_payload = {
            "resume_id": resume_id,
            "job_role": "java",
            "difficulty": "medium",
            "input_mode": "voice" if output_mode == "voice" else "text",
            "output_mode": output_mode,
        }
        create_resp = self.client.post("/api/v1/interviews", json=create_payload, headers=self.user_headers)
        self.assertEqual(200, create_resp.status_code)
        return create_resp.json()["interview_id"]

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
        self.assertEqual("PROJECT_DEEP_DIVE", turn_resp.json()["stage"])
        self.assertIn("pipeline_meta", turn_resp.json())
        self.assertIn("generation_mode", turn_resp.json()["pipeline_meta"])

        deep_dive_turn = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns",
            json={"stage": "PROJECT_DEEP_DIVE", "answer_text": "我在项目中负责了架构改造与核心模块落地。"},
            headers=self.user_headers,
        )
        self.assertEqual(200, deep_dive_turn.status_code)
        self.assertEqual("TECHNICAL", deep_dive_turn.json()["stage"])

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

    def test_list_turns_endpoint(self) -> None:
        """验证查询轮次列表接口返回有效数据。"""
        interview_id = self._create_interview()
        turn_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns",
            json={"stage": "SELF_INTRO", "answer_text": "这是首轮回答"},
            headers=self.user_headers,
        )
        self.assertEqual(200, turn_resp.status_code)
        list_resp = self.client.get(f"/api/v1/interviews/{interview_id}/turns", headers=self.user_headers)
        self.assertEqual(200, list_resp.status_code)
        self.assertEqual(interview_id, list_resp.json()["interview_id"])
        self.assertGreaterEqual(len(list_resp.json()["items"]), 1)
        self.assertEqual("SELF_INTRO", list_resp.json()["items"][0]["stage"])

    def test_input_priority_prefers_asr_text(self) -> None:
        """验证输入优先级为 asr_text > answer_text。"""
        interview_id = self._create_interview()
        turn_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns",
            json={
                "stage": "SELF_INTRO",
                "asr_text": "这是客户端 ASR 结果",
                "answer_text": "这是普通文本",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, turn_resp.status_code)
        pipeline_meta = turn_resp.json()["pipeline_meta"]
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

        turn_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns",
            json={"stage": "SELF_INTRO", "answer_text": "我负责过高并发服务优化"},
            headers=self.user_headers,
        )
        self.assertEqual(200, turn_resp.status_code)
        pipeline_meta = turn_resp.json()["pipeline_meta"]
        flags = pipeline_meta["degrade_flags"]
        self.assertIn("LLM_FALLBACK_TEMPLATE", flags)
        self.assertIn("TTS_FALLBACK_TEXT", flags)
        self.assertEqual("openai", pipeline_meta["providers"]["llm"])
        self.assertIn(pipeline_meta["provider_status"]["llm"], ["UP", "DOWN"])
        self.assertIsNone(turn_resp.json()["tts_audio_url"])

    def test_asr_failure_without_text_fallback(self) -> None:
        """验证仅音频输入且 ASR 失败时返回上游错误。"""
        interview_id = self._create_interview()
        service = self.client.app.state.interview_service

        def _raise_asr(*args, **kwargs):
            raise ApiError(code="ASR_UPSTREAM_FAILED", message="asr fail", status_code=502)

        service.voice_service.asr = _raise_asr

        turn_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns",
            json={
                "stage": "SELF_INTRO",
                "answer_audio_url": "https://example.com/a.mp3",
                "answer_audio_format": "mp3",
            },
            headers=self.user_headers,
        )
        self.assertEqual(502, turn_resp.status_code)
        self.assertEqual("ASR_UPSTREAM_FAILED", turn_resp.json()["error"]["code"])

    def test_audio_input_uses_server_asr_when_success(self) -> None:
        """验证音频输入成功时走服务端 ASR 路径并记录来源。"""
        interview_id = self._create_interview()
        service = self.client.app.state.interview_service
        service.voice_service.asr = lambda *_args, **_kwargs: "这是服务端语音识别文本"

        turn_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns",
            json={
                "stage": "SELF_INTRO",
                "answer_audio_url": "https://example.com/ok.mp3",
                "answer_audio_format": "mp3",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, turn_resp.status_code)
        pipeline_meta = turn_resp.json()["pipeline_meta"]
        self.assertEqual("ASR_SERVER", pipeline_meta["input_source"])
        self.assertEqual(service.voice_service.asr_provider, pipeline_meta["providers"]["asr"])

    def test_audio_upload_endpoint(self) -> None:
        """验证 multipart 音频上传接口可用。"""
        interview_id = self._create_interview(output_mode="text")
        service = self.client.app.state.interview_service
        service.voice_service.asr = lambda **_kwargs: "上传音频识别文本"

        turn_resp = self.client.post(
            f"/api/v1/interviews/{interview_id}/turns/audio",
            data={"stage": "SELF_INTRO"},
            files={"file": ("sample.wav", b"fake-audio", "audio/wav")},
            headers=self.user_headers,
        )
        self.assertEqual(200, turn_resp.status_code)
        self.assertEqual("PROJECT_DEEP_DIVE", turn_resp.json()["stage"])

    def test_admin_import_requires_admin_role(self) -> None:
        """验证管理接口权限控制生效。"""
        forbidden_resp = self.client.post(
            "/api/v1/admin/imports/materials",
            json={"dry_run": True, "roles": ["java"], "rebuild_mode": "incremental"},
            headers=self.user_headers,
        )
        self.assertEqual(403, forbidden_resp.status_code)


if __name__ == "__main__":
    unittest.main()
