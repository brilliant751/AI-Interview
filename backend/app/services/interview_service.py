"""面试流程编排服务。"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.core.errors import ApiError
from app.core.logging_utils import build_trace_id, log_pipeline_event, now_ms
from app.domain.interview_state import (
    InterviewStage,
    ensure_behavior_followup_limit,
    ensure_transition_allowed,
)
from app.repositories.interview_repository import InterviewRepository
from app.services.question_workflow import QuestionWorkflow
from app.services.rag_service import RAGService
from app.services.report_worker import ReportWorker
from app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)
INTERVIEW_END_MESSAGE = "本次面试已结束，正在生成报告。"


class InterviewService:
    """封装会话创建、轮次提交、报告生成等流程。"""

    def __init__(self, repo: InterviewRepository, report_worker: ReportWorker):
        """初始化服务依赖。"""
        self.repo = repo
        self.rag_service = RAGService()
        self.voice_service = VoiceService()
        self.report_worker = report_worker
        self.question_workflow = QuestionWorkflow()

    def create_session(self, payload: dict, user_id: str) -> dict:
        """创建会话并返回首题。"""
        resume = self.repo.get_resume(payload["resume_id"])
        if not resume or int(resume.get("is_deleted") or 0) == 1:
            raise ApiError(code="RESUME_404_NOT_FOUND", message="简历不存在", status_code=404)
        if str(resume.get("user_id") or "") != user_id:
            raise ApiError(code="RESUME_403_FORBIDDEN", message="无权使用该简历", status_code=403)
        session = self.repo.create_session(user_id=user_id, payload=payload)
        first_question = "请先做 1 分钟自我介绍，聚焦与你申请岗位最相关的经历。"
        output_mode = str(payload.get("output_mode") or "text")
        tts_audio_url: Optional[str] = None
        if output_mode == "voice":
            try:
                tts_audio_url = self.voice_service.tts(first_question)
            except ApiError as exc:
                logger.warning("首题语音合成失败，降级为文本输出：%s", exc.message)
        return {
            "interview_id": session["interview_id"],
            "current_stage": session["current_stage"],
            "first_question": first_question,
            "tts_audio_url": tts_audio_url,
        }

    def list_paused_interviews(self, user_id: str) -> list[dict]:
        """查询用户暂停中的面试会话。"""
        return self.repo.list_paused_sessions(user_id=user_id)

    def pause_interview(self, interview_id: str, user_id: str) -> dict:
        """暂停进行中的面试会话。"""
        session = self.repo.get_session(interview_id)
        if not session:
            raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
        if str(session.get("user_id") or "") != user_id:
            raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
        if str(session.get("status") or "") == "FINISHED":
            raise ApiError(code="STATE_409", message="面试已结束，无法暂停", status_code=409)
        if str(session.get("status") or "") == "PAUSED":
            return {"interview_id": interview_id, "status": "PAUSED"}
        paused = self.repo.pause_session(user_id=user_id, interview_id=interview_id)
        if not paused:
            raise ApiError(code="STATE_409", message="面试状态不允许暂停", status_code=409)
        return {"interview_id": interview_id, "status": "PAUSED"}

    def resume_interview(self, interview_id: str, user_id: str) -> dict:
        """恢复暂停的面试会话并返回当前题目。"""
        session = self.repo.get_session(interview_id)
        if not session:
            raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
        if str(session.get("user_id") or "") != user_id:
            raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
        if str(session.get("status") or "") == "FINISHED":
            raise ApiError(code="STATE_409", message="面试已结束，无法恢复", status_code=409)
        if str(session.get("status") or "") == "PAUSED":
            resumed = self.repo.resume_session(user_id=user_id, interview_id=interview_id)
            if not resumed:
                raise ApiError(code="STATE_409", message="面试状态不允许恢复", status_code=409)
        first_question = "请先做 1 分钟自我介绍，聚焦与你申请岗位最相关的经历。"
        question = self.repo.get_last_next_question(user_id=user_id, interview_id=interview_id) or first_question
        output_mode = str(session.get("output_mode") or "text")
        tts_audio_url: Optional[str] = None
        if output_mode == "voice":
            try:
                tts_audio_url = self.voice_service.tts(question)
            except ApiError:
                tts_audio_url = None
        return {
            "interview_id": interview_id,
            "stage": str(session.get("current_stage") or "SELF_INTRO"),
            "question": question,
            "job_role": str(session.get("job_role") or "java"),
            "difficulty": str(session.get("difficulty") or "medium"),
            "input_mode": str(session.get("input_mode") or "text"),
            "output_mode": output_mode,
            "tts_audio_url": tts_audio_url,
        }

    def _resolve_answer(self, payload: dict) -> tuple[str, str]:
        """解析回答输入优先级并返回文本与来源。"""
        asr_text = (payload.get("asr_text") or "").strip()
        answer_text = (payload.get("answer_text") or "").strip()
        answer_audio_url = (payload.get("answer_audio_url") or "").strip()
        answer_audio_format = (payload.get("answer_audio_format") or "mp3").strip() or "mp3"
        answer_audio_bytes = payload.get("answer_audio_bytes")
        answer_audio_filename = (payload.get("answer_audio_filename") or "answer.wav").strip() or "answer.wav"

        if asr_text:
            logger.info("ASR转写结果(客户端传入): %s", asr_text)
            print(f"[ASR] 客户端转写结果: {asr_text}")
            return asr_text, "ASR_CLIENT"
        if answer_text:
            return answer_text, "TEXT"
        if answer_audio_url or answer_audio_bytes:
            recognized_text = self.voice_service.asr(
                audio_url=answer_audio_url,
                audio_format=answer_audio_format,
                audio_bytes=answer_audio_bytes,
                audio_filename=answer_audio_filename,
            )
            logger.info("ASR转写结果(服务端识别): %s", recognized_text)
            print(f"[ASR] 服务端转写结果: {recognized_text}")
            return (
                recognized_text,
                "ASR_SERVER",
            )
        raise ApiError(code="VALIDATE_400", message="回答内容不能为空", status_code=400)

    def _build_resume_references(self, resume_text: str, answer: str, top_k: int = 2) -> list[dict[str, Any]]:
        """从简历文本中提取与当前回答相关的要点。"""
        source = (resume_text or "").strip()
        if not source:
            return []
        answer_tokens = {token for token in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", answer.lower()) if token}
        lines = [line.strip() for line in source.splitlines() if len(line.strip()) >= 6]
        scored: list[tuple[int, str]] = []
        for line in lines:
            line_lower = line.lower()
            score = sum(1 for token in answer_tokens if token in line_lower)
            if score > 0:
                scored.append((score, line))
        if not scored:
            picked = lines[:top_k]
        else:
            scored.sort(key=lambda item: item[0], reverse=True)
            picked = [line for _, line in scored[:top_k]]
        return [
            {
                "title": "简历要点",
                "content": text,
                "score": 0.0,
                "source_path": "resume",
                "retrieval_mode": "resume",
            }
            for text in picked
        ]

    def submit_turn_with_audio(self, interview_id: str, stage: str, audio_bytes: bytes, filename: str, user_id: str) -> dict:
        """处理 multipart 音频上传的轮次提交。"""
        payload = {
            "stage": stage,
            "answer_audio_bytes": audio_bytes,
            "answer_audio_filename": filename,
            "answer_audio_format": filename.split(".")[-1] if "." in filename else "wav",
        }
        return self.submit_turn(interview_id, payload, user_id=user_id)

    def submit_turn(self, interview_id: str, payload: dict, user_id: str) -> dict:
        """处理单轮回答并产出下一题。"""
        started_at = now_ms()
        trace_id = build_trace_id()
        providers = {
            "asr": None,
            "llm": None,
            "tts": None,
        }
        provider_status = {
            "asr": "UNKNOWN",
            "llm": "UNKNOWN",
            "tts": "UNKNOWN",
        }
        degrade_flags: list[str] = []

        session = self.repo.get_session(interview_id)
        if not session:
            raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
        if str(session.get("user_id") or "") != user_id:
            raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
        if session["status"] == "FINISHED":
            raise ApiError(code="STATE_409", message="面试已结束，禁止继续提交", status_code=409)
        if session["status"] == "PAUSED":
            raise ApiError(code="STATE_409", message="面试已暂停，请先恢复后再提交", status_code=409)

        stage = payload["stage"]
        if stage != session["current_stage"]:
            raise ApiError(code="STATE_409", message="提交阶段与会话阶段不一致", status_code=409)

        answer, input_source = self._resolve_answer(payload)
        resume = self.repo.get_resume(session["resume_id"]) or {}
        resume_references = self._build_resume_references(str(resume.get("parsed_text") or ""), answer)
        if input_source == "ASR_SERVER":
            providers["asr"] = self.voice_service.asr_provider
            provider_status["asr"] = self.voice_service.health().get("asr", "UNKNOWN")

        follow_up_count = int(session["follow_up_count"])
        technical_count = int(session.get("technical_count", 0))
        if stage == InterviewStage.BEHAVIORAL.value:
            follow_up_count += 1
            ensure_behavior_followup_limit(stage, follow_up_count)

        live_score = min(95, max(40, 60 + min(len(answer) // 10, 35)))
        if stage == InterviewStage.SELF_INTRO.value:
            next_stage = InterviewStage.PROJECT_DEEP_DIVE.value
            follow_up_count = 0
            technical_count = 0
        elif stage == InterviewStage.PROJECT_DEEP_DIVE.value:
            next_stage = InterviewStage.TECHNICAL.value
        elif stage == InterviewStage.TECHNICAL.value:
            technical_count += 1
            if technical_count < 3:
                next_stage = InterviewStage.TECHNICAL.value
            elif technical_count < 5 and len(answer) < 30:
                next_stage = InterviewStage.TECHNICAL.value
            else:
                next_stage = InterviewStage.BEHAVIORAL.value
        elif stage == InterviewStage.BEHAVIORAL.value:
            next_stage = InterviewStage.END.value if follow_up_count >= 3 else InterviewStage.BEHAVIORAL.value
        else:
            next_stage = stage

        if next_stage != stage:
            ensure_transition_allowed(stage, next_stage)
            follow_up_count = 0

        references = self.rag_service.retrieve(session["job_role"], answer, top_k=2)
        references = [*resume_references, *references][:4]
        generation_mode = "mock"
        if next_stage == InterviewStage.END.value:
            next_question = INTERVIEW_END_MESSAGE
            providers["llm"] = "finalizer"
            provider_status["llm"] = "UP"
        elif self.question_workflow.llm_provider in {"openai", "ollama"}:
            try:
                next_question = self.question_workflow.generate(
                    answer=answer,
                    references=references,
                    stage=stage,
                    technical_count=technical_count,
                    follow_up_count=follow_up_count,
                )
                providers["llm"] = self.question_workflow.llm_provider
                provider_status["llm"] = self.question_workflow.health().get("llm", "UNKNOWN")
                generation_mode = "local_ai"
            except Exception:
                next_question = self.question_workflow.generate_template(
                    answer=answer,
                    references=references,
                    stage=stage,
                    technical_count=technical_count,
                    follow_up_count=follow_up_count,
                )
                providers["llm"] = self.question_workflow.llm_provider
                provider_status["llm"] = "DOWN"
                degrade_flags.append("LLM_FALLBACK_TEMPLATE")
                generation_mode = "fallback_template"
        else:
            next_question = self.question_workflow.generate_template(
                answer=answer,
                references=references,
                stage=stage,
                technical_count=technical_count,
                follow_up_count=follow_up_count,
            )
            providers["llm"] = self.question_workflow.llm_provider
            provider_status["llm"] = "UP"

        output_mode = session["output_mode"]
        tts_audio_url = None
        if output_mode == "voice" and next_stage != InterviewStage.END.value:
            try:
                tts_audio_url = self.voice_service.tts(next_question)
                providers["tts"] = self.voice_service.tts_provider
                provider_status["tts"] = self.voice_service.health().get("tts", "UNKNOWN")
            except ApiError:
                degrade_flags.append("TTS_FALLBACK_TEXT")
                provider_status["tts"] = "DOWN"

        latency_ms = now_ms() - started_at
        turn_id = self.repo.add_turn(
            interview_id=interview_id,
            user_id=user_id,
            stage=stage,
            answer_text=answer,
            next_question=next_question,
            score=live_score,
            input_source=input_source,
            asr_provider=providers["asr"],
            llm_provider=providers["llm"],
            tts_provider=providers["tts"],
            degrade_flags=degrade_flags,
            trace_id=trace_id,
            latency_ms=latency_ms,
            generation_mode=generation_mode,
        )
        if next_stage == InterviewStage.END.value:
            self.repo.finish_session(interview_id)
            self.repo.upsert_report(
                interview_id,
                {
                    "status": "GENERATING",
                    "overall_score": None,
                    "strengths": "[]",
                    "weaknesses": "[]",
                    "suggestions": "[]",
                    "error_message": None,
                },
            )
            self.report_worker.enqueue(interview_id)
        else:
            self.repo.update_session_stage(
                interview_id=interview_id,
                stage=next_stage,
                follow_up_count=follow_up_count,
                technical_count=technical_count,
            )

        log_pipeline_event(
            event="submit_turn",
            interview_id=interview_id,
            turn_id=turn_id,
            trace_id=trace_id,
            providers=providers,
            degrade_flags=degrade_flags,
            latency_ms=latency_ms,
            extra={
                "input_source": input_source,
                "technical_count": technical_count,
                "next_question": next_question,
                "generation_mode": generation_mode,
            },
        )

        return {
            "interview_id": interview_id,
            "stage": next_stage,
            "next_question": next_question,
            "follow_up_count": follow_up_count,
            "live_score": live_score,
            "output_mode": output_mode,
            "tts_audio_url": tts_audio_url,
            "pipeline_meta": {
                "input_source": input_source,
                "providers": providers,
                "provider_status": provider_status,
                "degrade_flags": degrade_flags,
                "trace_id": trace_id,
                "latency_ms": latency_ms,
                "generation_mode": generation_mode,
            },
        }

    def finish_interview(self, interview_id: str, user_id: str) -> dict:
        """结束会话并同步生成报告。"""
        session = self.repo.get_session(interview_id)
        if not session:
            raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
        if str(session.get("user_id") or "") != user_id:
            raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
        self.repo.finish_session(interview_id)
        self.repo.upsert_report(
            interview_id,
            {
                "status": "GENERATING",
                "overall_score": None,
                "strengths": "[]",
                "weaknesses": "[]",
                "suggestions": "[]",
                "error_message": None,
            },
        )
        self.report_worker.enqueue(interview_id)
        return {"interview_id": interview_id, "report_status": "GENERATING"}

    def provider_health(self) -> dict:
        """聚合 provider 健康检查状态。"""
        voice = self.voice_service.health_details()
        llm = self.question_workflow.health_details()
        statuses = {
            "asr": voice["asr"]["status"],
            "tts": voice["tts"]["status"],
            "llm": llm["status"],
        }
        if all(status == "UP" for status in statuses.values()):
            overall = "UP"
        elif any(status == "UP" for status in statuses.values()):
            overall = "DEGRADED"
        else:
            overall = "DOWN"
        return {
            "overall": overall,
            "providers": {
                "asr": voice["asr"],
                "llm": llm,
                "tts": voice["tts"],
                "embed": self.rag_service.health(),
            },
        }
