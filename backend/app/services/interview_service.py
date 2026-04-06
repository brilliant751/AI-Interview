"""面试流程编排服务。"""

from __future__ import annotations

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


class InterviewService:
    """封装会话创建、轮次提交、报告生成等流程。"""

    def __init__(self, repo: InterviewRepository, report_worker: ReportWorker):
        """初始化服务依赖。"""
        self.repo = repo
        self.rag_service = RAGService()
        self.voice_service = VoiceService()
        self.report_worker = report_worker
        self.question_workflow = QuestionWorkflow()

    def create_session(self, payload: dict) -> dict:
        """创建会话并返回首题。"""
        session = self.repo.create_session(payload)
        first_question = "请先做 1 分钟自我介绍，聚焦与你申请岗位最相关的经历。"
        return {
            "interview_id": session["interview_id"],
            "current_stage": session["current_stage"],
            "first_question": first_question,
        }

    def _resolve_answer(self, payload: dict) -> tuple[str, str]:
        """解析回答输入优先级并返回文本与来源。"""
        asr_text = (payload.get("asr_text") or "").strip()
        answer_text = (payload.get("answer_text") or "").strip()
        answer_audio_url = (payload.get("answer_audio_url") or "").strip()
        answer_audio_format = (payload.get("answer_audio_format") or "mp3").strip() or "mp3"

        if asr_text:
            return asr_text, "ASR_CLIENT"
        if answer_text:
            return answer_text, "TEXT"
        if answer_audio_url:
            return self.voice_service.asr(answer_audio_url, answer_audio_format), "ASR_SERVER"
        raise ApiError(code="VALIDATE_400", message="回答内容不能为空", status_code=400)

    def submit_turn(self, interview_id: str, payload: dict) -> dict:
        """处理单轮回答并产出下一题。"""
        started_at = now_ms()
        trace_id = build_trace_id()
        providers = {
            "asr": None,
            "llm": None,
            "tts": None,
        }
        degrade_flags: list[str] = []

        session = self.repo.get_session(interview_id)
        if not session:
            raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
        if session["status"] == "FINISHED":
            raise ApiError(code="STATE_409", message="面试已结束，禁止继续提交", status_code=409)

        stage = payload["stage"]
        if stage != session["current_stage"]:
            raise ApiError(code="STATE_409", message="提交阶段与会话阶段不一致", status_code=409)

        answer, input_source = self._resolve_answer(payload)
        if input_source == "ASR_SERVER":
            providers["asr"] = self.voice_service.asr_provider

        follow_up_count = int(session["follow_up_count"])
        technical_count = int(session.get("technical_count", 0))
        if stage == InterviewStage.BEHAVIORAL.value:
            follow_up_count += 1
            ensure_behavior_followup_limit(stage, follow_up_count)

        references = self.rag_service.retrieve(session["job_role"], answer, top_k=2)
        if self.question_workflow.llm_provider == "openai":
            try:
                next_question = self.question_workflow.generate_by_llm(answer=answer, references=references)
                providers["llm"] = self.question_workflow.llm_provider
            except Exception:
                next_question = self.question_workflow.generate_template(answer=answer, references=references)
                degrade_flags.append("LLM_FALLBACK_TEMPLATE")
        else:
            next_question = self.question_workflow.generate_template(answer=answer, references=references)
            providers["llm"] = self.question_workflow.llm_provider

        live_score = min(95, max(40, 60 + min(len(answer) // 10, 35)))
        if stage == InterviewStage.SELF_INTRO.value:
            next_stage = InterviewStage.TECHNICAL.value
            follow_up_count = 0
            technical_count = 0
        elif stage == InterviewStage.TECHNICAL.value:
            technical_count += 1
            if technical_count < 3:
                next_stage = InterviewStage.TECHNICAL.value
            elif technical_count < 5 and len(answer) < 30:
                next_stage = InterviewStage.TECHNICAL.value
            else:
                next_stage = InterviewStage.BEHAVIORAL.value
        else:
            next_stage = stage

        if next_stage != stage:
            ensure_transition_allowed(stage, next_stage)
            follow_up_count = 0

        output_mode = session["output_mode"]
        tts_audio_url = None
        if output_mode == "voice":
            try:
                tts_audio_url = self.voice_service.tts(next_question)
                providers["tts"] = self.voice_service.tts_provider
            except ApiError:
                degrade_flags.append("TTS_FALLBACK_TEXT")

        latency_ms = now_ms() - started_at
        turn_id = self.repo.add_turn(
            interview_id=interview_id,
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
        )
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
            extra={"input_source": input_source},
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
                "degrade_flags": degrade_flags,
                "trace_id": trace_id,
                "latency_ms": latency_ms,
            },
        }

    def finish_interview(self, interview_id: str) -> dict:
        """结束会话并同步生成报告。"""
        session = self.repo.get_session(interview_id)
        if not session:
            raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
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
        voice = self.voice_service.health()
        llm = self.question_workflow.health()
        statuses = {
            "asr": voice["asr"],
            "tts": voice["tts"],
            "llm": llm["llm"],
        }
        if all(status == "UP" for status in statuses.values()):
            overall = "UP"
        elif any(status == "UP" for status in statuses.values()):
            overall = "DEGRADED"
        else:
            overall = "DOWN"
        return {
            "overall": overall,
            "providers": statuses,
        }
