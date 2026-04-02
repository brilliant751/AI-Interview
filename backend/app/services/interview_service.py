"""面试流程编排服务。"""

from __future__ import annotations

from app.core.errors import ApiError
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

    def submit_turn(self, interview_id: str, payload: dict) -> dict:
        """处理单轮回答并产出下一题。"""
        session = self.repo.get_session(interview_id)
        if not session:
            raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
        if session["status"] == "FINISHED":
            raise ApiError(code="STATE_409", message="面试已结束，禁止继续提交", status_code=409)

        stage = payload["stage"]
        if stage != session["current_stage"]:
            raise ApiError(code="STATE_409", message="提交阶段与会话阶段不一致", status_code=409)

        answer = (payload.get("asr_text") or payload.get("answer_text") or "").strip()
        if not answer:
            raise ApiError(code="VALIDATE_400", message="回答内容不能为空", status_code=400)

        follow_up_count = int(session["follow_up_count"])
        technical_count = int(session.get("technical_count", 0))
        if stage == InterviewStage.BEHAVIORAL.value:
            follow_up_count += 1
            ensure_behavior_followup_limit(stage, follow_up_count)

        references = self.rag_service.retrieve(session["job_role"], answer, top_k=2)
        next_question = self.question_workflow.generate(answer=answer, references=references)
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

        self.repo.add_turn(interview_id, stage, answer, next_question, live_score)
        self.repo.update_session_stage(
            interview_id=interview_id,
            stage=next_stage,
            follow_up_count=follow_up_count,
            technical_count=technical_count,
        )

        output_mode = session["output_mode"]
        tts_audio_url = self.voice_service.tts(next_question) if output_mode == "voice" else None
        return {
            "interview_id": interview_id,
            "stage": next_stage,
            "next_question": next_question,
            "follow_up_count": follow_up_count,
            "live_score": live_score,
            "output_mode": output_mode,
            "tts_audio_url": tts_audio_url,
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
