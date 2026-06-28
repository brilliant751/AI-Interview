"""面试流程编排服务。"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from starlette.concurrency import run_in_threadpool

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
from app.services.turn_worker import TurnWorker
from app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)
resume_context_logger = logging.getLogger("app.resume_context")
INTERVIEW_END_MESSAGE = "本次面试已结束，正在生成报告。"
INTERVIEW_FIRST_QUESTION = "请先做 1 分钟自我介绍，聚焦与你申请岗位最相关的经历。"

# InterviewService 是面试主流程的编排中心：
# 1. API 层负责收发请求，这里负责会话状态、阶段转换和 provider 降级。
# 2. Repository 只做数据读写，这里决定哪些数据可以被写入以及何时写入。
# 3. QuestionWorkflow/RAG/VoiceService 是可替换能力，服务层负责把它们串成稳定流程。
# 4. 所有返回给前端的字段都在这里组装，便于和 Pydantic 响应模型保持一致。
# 5. 异步入口和同步 submit_turn 共用同一套校验，避免两条路径出现状态差异。


class InterviewService:
    """封装会话创建、轮次提交、报告生成等流程。"""

    def __init__(self, repo: InterviewRepository, report_worker: ReportWorker, turn_worker: TurnWorker):
        """初始化服务依赖。"""
        self.repo = repo
        self.rag_service = RAGService()
        self.voice_service = VoiceService()
        self.report_worker = report_worker
        self.turn_worker = turn_worker
        self.question_workflow = QuestionWorkflow()

    async def enqueue_turn_submission(self, interview_id: str, payload: dict, user_id: str) -> str:
        """创建轮次异步任务并入队后台处理。"""
        session = self.repo.get_session(interview_id)
        if not session:
            raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
        if str(session.get("user_id") or "") != user_id:
            raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
        if session["status"] == "FINISHED":
            raise ApiError(code="STATE_409", message="面试已结束，禁止继续提交", status_code=409)
        if session["status"] == "PAUSED":
            raise ApiError(code="STATE_409", message="面试已暂停，请先恢复后再提交", status_code=409)
        if session["status"] == "SCHEDULED":
            raise ApiError(code="INTERVIEW_409_NOT_READY", message="未到预约开始时间，请先开始面试", status_code=409)
        stage = str(payload.get("stage") or "")
        if stage != str(session.get("current_stage") or ""):
            raise ApiError(code="STATE_409", message="提交阶段与会话阶段不一致", status_code=409)

        # 先落库创建任务，再把真正的 submit_turn 丢给后台 worker。
        # 这样即使 LLM 或 TTS 很慢，前端也能立即拿到 job_id 并展示处理中状态。
        # run_in_threadpool 用来复用同步业务实现，避免维护两份几乎相同的轮次逻辑。
        job_id = self.repo.create_turn_job(interview_id=interview_id, user_id=user_id, stage=stage, payload=payload)

        async def _task() -> dict:
            return await run_in_threadpool(self.submit_turn, interview_id, payload, user_id)

        self.turn_worker.enqueue(job_id=job_id, task_factory=_task)
        return job_id

    def get_turn_job_result(self, job_id: str, user_id: str) -> dict:
        """查询轮次异步任务结果。"""
        row = self.repo.get_turn_job(job_id)
        if not row:
            raise ApiError(code="TURN_JOB_404_NOT_FOUND", message="轮次任务不存在", status_code=404)
        if str(row.get("user_id") or "") != user_id:
            raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该轮次任务", status_code=403)
        result = {}
        raw_result = str(row.get("result_json") or "{}")
        try:
            import json

            parsed = json.loads(raw_result)
            if isinstance(parsed, dict):
                result = parsed
        except Exception:
            result = {}
        return {
            "job_id": str(row["job_id"]),
            "interview_id": str(row["interview_id"]),
            "status": str(row["status"]),
            "result": result,
            "error_message": str(row.get("error_message") or ""),
        }

    def _parse_schedule_time(self, value: str) -> datetime:
        """解析前端传入的预约时间。"""
        normalized = value.strip()
        if not normalized:
            raise ApiError(code="INTERVIEW_400_SCHEDULE_TIME_INVALID", message="预约开始时间不能为空", status_code=400)
        normalized = normalized.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ApiError(code="INTERVIEW_400_SCHEDULE_TIME_INVALID", message="预约开始时间格式不正确", status_code=400) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _to_sqlite_datetime(self, value: datetime) -> str:
        """将 UTC 时间转换为 SQLite 可读格式。"""
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def _get_start_available(self, session: dict) -> bool:
        """判断预约面试是否已经到达可开始时间。"""
        if str(session.get("status") or "") != "SCHEDULED":
            return False
        scheduled_start_at = str(session.get("scheduled_start_at") or "").strip()
        if not scheduled_start_at:
            return False
        scheduled_at = self._parse_schedule_time(scheduled_start_at.replace(" ", "T"))
        return scheduled_at <= datetime.now(timezone.utc)

    def create_session(self, payload: dict, user_id: str) -> dict:
        """创建会话并返回首题。"""
        resume = self.repo.get_resume(payload["resume_id"])
        if not resume or int(resume.get("is_deleted") or 0) == 1:
            raise ApiError(code="RESUME_404_NOT_FOUND", message="简历不存在", status_code=404)
        if str(resume.get("user_id") or "") != user_id:
            raise ApiError(code="RESUME_403_FORBIDDEN", message="无权使用该简历", status_code=403)
        jd_id = str(payload.get("jd_id") or "").strip()
        normalized_role = str(payload.get("job_role") or "").strip()
        if not jd_id and not normalized_role:
            raise ApiError(code="INTERVIEW_400_ROLE_OR_JD_REQUIRED", message="岗位方向与岗位描述至少选择一个", status_code=400)
        jd_snapshot: dict[str, str] = {}
        if jd_id:
            # 创建会话时保存 JD 快照，而不是后续每轮都读取最新 JD。
            # 这样用户在面试过程中修改或删除 JD，不会影响已经开始的会话上下文。
            # 系统预置 JD 不要求 user_id 匹配，用户自建 JD 必须做归属校验。
            jd = self.repo.get_jd(jd_id)
            if not jd or int(jd.get("is_deleted") or 0) == 1:
                raise ApiError(code="JD_404_NOT_FOUND", message="JD 不存在", status_code=404)
            is_system = str(jd.get("source_type") or "") == "SYSTEM_PRESET"
            if (not is_system) and str(jd.get("user_id") or "") != user_id:
                raise ApiError(code="JD_403_FORBIDDEN", message="无权访问该 JD", status_code=403)
            jd_role = str(jd.get("job_role") or "").strip()
            if normalized_role and jd_role != normalized_role:
                raise ApiError(code="JD_409_ROLE_MISMATCH", message="JD 岗位方向与面试方向不匹配", status_code=409)
            if not normalized_role:
                normalized_role = jd_role
            jd_snapshot = {
                "jd_id": jd_id,
                "jd_snapshot_title": str(jd.get("title") or ""),
                "jd_snapshot_content": str(jd.get("content_text") or "")[:2000],
            }
        payload["job_role"] = normalized_role
        scheduled_start_at_raw = str(payload.get("scheduled_start_at") or "").strip()
        status = "ACTIVE"
        if scheduled_start_at_raw:
            scheduled_start_at = self._parse_schedule_time(scheduled_start_at_raw)
            if scheduled_start_at <= datetime.now(timezone.utc):
                raise ApiError(code="INTERVIEW_400_SCHEDULE_TIME_INVALID", message="预约时间必须晚于当前时间", status_code=400)
            payload["scheduled_start_at"] = self._to_sqlite_datetime(scheduled_start_at)
            status = "SCHEDULED"
        else:
            payload["scheduled_start_at"] = ""
        payload["status"] = status
        requested_tone_id = str(payload.get("voice_tone_id") or "").strip()
        tone = None
        if requested_tone_id:
            # 语气配置只允许选择启用中的记录，避免前端缓存了已下线 tone 后继续使用。
            tone = self.repo.get_voice_tone(requested_tone_id)
            if not tone:
                raise ApiError(code="VOICE_TONE_404_NOT_FOUND", message="语气配置不存在", status_code=404)
            if int(tone.get("is_active") or 0) != 1:
                raise ApiError(code="VOICE_TONE_409_INACTIVE", message="语气配置已停用", status_code=409)
        else:
            tone_list = self.repo.list_active_voice_tones()
            tone = tone_list[0] if tone_list else None
        payload["voice_tone_id"] = str((tone or {}).get("tone_id") or "")
        payload["voice_tone_name"] = str((tone or {}).get("tone_name") or "")
        payload["voice_tone_instructions"] = str((tone or {}).get("base_instructions") or "")
        payload["voice_tone_speed"] = float((tone or {}).get("speed") or 1.0)
        session = self.repo.create_session(user_id=user_id, payload=payload, jd_snapshot=jd_snapshot)
        first_question = INTERVIEW_FIRST_QUESTION
        output_mode = str(payload.get("output_mode") or "text")
        tts_audio_url: Optional[str] = None
        if output_mode == "voice" and status == "ACTIVE":
            try:
                # 首题语音合成失败不阻断会话创建，文本问题仍然可以继续面试。
                # 语音能力属于增强体验，因此降级策略是“能播则播，失败回文本”。
                tts_style = self._build_tts_style(
                    stage=InterviewStage.SELF_INTRO.value,
                    question=first_question,
                    session={
                        "voice_tone_instructions": payload.get("voice_tone_instructions"),
                        "voice_tone_speed": payload.get("voice_tone_speed"),
                    },
                )
                tts_audio_url = self.voice_service.tts(
                    first_question,
                    instructions=tts_style["instructions"],
                    speed=tts_style["speed"],
                )
            except ApiError as exc:
                logger.warning("首题语音合成失败，降级为文本输出：%s", exc.message)
        return {
            "interview_id": session["interview_id"],
            "status": status,
            "current_stage": session["current_stage"],
            "first_question": first_question,
            "scheduled_start_at": payload["scheduled_start_at"] or None,
            "tts_audio_url": tts_audio_url,
            "voice_tone_id": str(payload.get("voice_tone_id") or ""),
            "voice_tone_name": str(payload.get("voice_tone_name") or ""),
        }

    def _build_tts_style(self, stage: str, question: str, session: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """根据阶段生成语气指令与语速。"""
        normalized_stage = str(stage or "").strip().upper()
        concise_hint = "使用简洁口语化表达，句间有自然停顿，避免播报腔。"
        tone_instructions = str((session or {}).get("voice_tone_instructions") or "").strip()
        tone_speed = float((session or {}).get("voice_tone_speed") or 1.0)

        def _merge_instructions(stage_instructions: str) -> str:
            if tone_instructions:
                return f"{tone_instructions} {stage_instructions}".strip()
            return stage_instructions

        if normalized_stage == InterviewStage.SELF_INTRO.value:
            return {
                "instructions": _merge_instructions(f"语气友好且专业，先鼓励再提问，语速略慢，语调自然。{concise_hint}"),
                "speed": round(tone_speed * 0.95, 2),
            }
        if normalized_stage == InterviewStage.PROJECT_DEEP_DIVE.value:
            return {
                "instructions": _merge_instructions(f"语气专注且有探究感，重点词汇轻微重读，保持清晰节奏。{concise_hint}"),
                "speed": round(tone_speed * 1.0, 2),
            }
        if normalized_stage == InterviewStage.TECHNICAL.value:
            return {
                "instructions": _merge_instructions(f"语气冷静客观，提问明确，停顿干净，不要过度情绪化。{concise_hint}"),
                "speed": round(tone_speed * 1.02, 2),
            }
        if normalized_stage == InterviewStage.BEHAVIORAL.value:
            return {
                "instructions": _merge_instructions(f"语气共情且有引导感，听起来耐心、温和、不过分热情。{concise_hint}"),
                "speed": round(tone_speed * 0.96, 2),
            }
        if normalized_stage == InterviewStage.END.value or "结束" in question:
            return {
                "instructions": _merge_instructions(f"语气肯定且收束，简短有礼貌，留有结束停顿。{concise_hint}"),
                "speed": round(tone_speed * 0.94, 2),
            }
        return {
            "instructions": _merge_instructions(f"语气自然专业，发音清晰，保留正常停顿。{concise_hint}"),
            "speed": round(tone_speed, 2),
        }

    def list_voice_tones(self) -> list[dict[str, Any]]:
        """查询可用语气配置列表。"""
        return self.repo.list_active_voice_tones()

    def list_paused_interviews(self, user_id: str) -> list[dict]:
        """查询用户暂停中的面试会话。"""
        return self.repo.list_paused_sessions(user_id=user_id)

    def list_scheduled_interviews(
        self,
        user_id: str,
        scheduled_from: str | None,
        scheduled_to: str | None,
        statuses: list[str] | None = None,
    ) -> list[dict]:
        """查询用户的预约面试列表。"""
        normalized_from = self._to_sqlite_datetime(self._parse_schedule_time(scheduled_from)) if scheduled_from else None
        normalized_to = self._to_sqlite_datetime(self._parse_schedule_time(scheduled_to)) if scheduled_to else None
        rows = self.repo.list_scheduled_sessions(
            user_id=user_id,
            scheduled_from=normalized_from,
            scheduled_to=normalized_to,
            statuses=statuses,
        )
        for row in rows:
            row["start_available"] = self._get_start_available(row)
        return rows

    def start_scheduled_interview(self, interview_id: str, user_id: str) -> dict:
        """开始已到预约时间的面试会话。"""
        session = self.repo.get_session(interview_id)
        if not session:
            raise ApiError(code="NOT_FOUND", message="面试会话不存在", status_code=404)
        if str(session.get("user_id") or "") != user_id:
            raise ApiError(code="INTERVIEW_403_FORBIDDEN", message="无权访问该面试会话", status_code=403)
        status = str(session.get("status") or "")
        if status == "FINISHED":
            raise ApiError(code="STATE_409", message="面试已结束，无法开始", status_code=409)
        if status == "PAUSED":
            result = self.resume_interview(interview_id=interview_id, user_id=user_id)
            result["status"] = "ACTIVE"
            result["scheduled_start_at"] = session.get("scheduled_start_at")
            return result
        if status == "ACTIVE":
            result = self.resume_interview(interview_id=interview_id, user_id=user_id)
            result["status"] = "ACTIVE"
            result["scheduled_start_at"] = session.get("scheduled_start_at")
            return result
        if status != "SCHEDULED":
            raise ApiError(code="STATE_409", message="当前会话不处于预约状态", status_code=409)
        if not self._get_start_available(session):
            raise ApiError(code="INTERVIEW_409_NOT_READY", message="未到预约开始时间，暂时无法开始面试", status_code=409)
        started = self.repo.start_scheduled_session(user_id=user_id, interview_id=interview_id)
        if not started:
            raise ApiError(code="STATE_409", message="预约面试开始失败，请刷新后重试", status_code=409)
        result = self.resume_interview(interview_id=interview_id, user_id=user_id)
        result["status"] = "ACTIVE"
        result["scheduled_start_at"] = session.get("scheduled_start_at")
        return result

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
        first_question = INTERVIEW_FIRST_QUESTION
        question = self.repo.get_last_next_question(user_id=user_id, interview_id=interview_id) or first_question
        output_mode = str(session.get("output_mode") or "text")
        tts_audio_url: Optional[str] = None
        if output_mode == "voice":
            try:
                tts_style = self._build_tts_style(
                    stage=str(session.get("current_stage") or "SELF_INTRO"),
                    question=question,
                    session=session,
                )
                tts_audio_url = self.voice_service.tts(
                    question,
                    instructions=tts_style["instructions"],
                    speed=tts_style["speed"],
                )
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

        # 输入优先级从“已经识别好的文本”到“原始音频”递减：
        # 1. 客户端 ASR 文本可信度最高，也能减少后端重复识别成本。
        # 2. 普通文本回答是最稳定路径，适合手动输入和测试。
        # 3. 音频 URL/字节流最后交给服务端 ASR，失败时由 VoiceService 抛出可控错误。
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
        # 这里做一个轻量关键词匹配，不依赖向量库。
        # 目的不是精确检索，而是在 LLM 提问时补充“候选人简历中的可追问事实”。
        # 如果回答里没有命中任何简历片段，就退回前 top_k 行，至少给模型一点简历上下文。
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

    def _build_conversation_history(self, previous_turns: list[dict[str, Any]], current_answer: str) -> list[dict[str, str]]:
        """按固定 role 格式构建历史消息：assistant -> user 交替。"""
        history: list[dict[str, str]] = []
        assistant_question = INTERVIEW_FIRST_QUESTION
        for turn in previous_turns:
            answer_text = str(turn.get("answer_text") or "").strip()
            if answer_text:
                history.append({"role": "assistant", "content": assistant_question})
                history.append({"role": "user", "content": answer_text})
            next_question = str(turn.get("next_question") or "").strip()
            if next_question:
                assistant_question = next_question
        normalized_answer = (current_answer or "").strip()
        if normalized_answer:
            history.append({"role": "assistant", "content": assistant_question})
            history.append({"role": "user", "content": normalized_answer})
        return history

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
        # providers/provider_status/degrade_flags 会随本轮链路逐步填充。
        # 前端报告和排障日志都依赖这些字段判断本轮是否走了降级路径。
        # trace_id 用来把 API 日志、简历上下文日志和 provider 日志串起来。
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
        if session["status"] == "SCHEDULED":
            raise ApiError(code="INTERVIEW_409_NOT_READY", message="未到预约开始时间，请先开始面试", status_code=409)

        stage = payload["stage"]
        if stage != session["current_stage"]:
            raise ApiError(code="STATE_409", message="提交阶段与会话阶段不一致", status_code=409)

        # 从这里开始进入本轮业务处理：解析回答、补充上下文、推进状态、生成下一题。
        # 前面的校验确保用户、会话状态和当前阶段都匹配，后续写库才是安全的。
        answer, input_source = self._resolve_answer(payload)
        resume = self.repo.get_resume(session["resume_id"]) or {}
        resume_text = str(resume.get("parsed_text") or "").strip()
        if resume_text:
            logger.info(
                "简历解析内容已加载：resume_id=%s，总长度=%s，预览=%s",
                str(session.get("resume_id") or ""),
                len(resume_text),
                resume_text[:300].replace("\n", " "),
            )
            resume_context_logger.info(
                "简历解析内容已加载：trace_id=%s interview_id=%s resume_id=%s 总长度=%s 预览=%s",
                trace_id,
                interview_id,
                str(session.get("resume_id") or ""),
                len(resume_text),
                resume_text[:300].replace("\n", " "),
            )
        else:
            logger.info("简历解析内容为空：resume_id=%s", str(session.get("resume_id") or ""))
            resume_context_logger.info(
                "简历解析内容为空：trace_id=%s interview_id=%s resume_id=%s",
                trace_id,
                interview_id,
                str(session.get("resume_id") or ""),
            )
        resume_references = self._build_resume_references(resume_text, answer)
        if resume_references:
            logger.info(
                "简历命中要点（将参与本轮提问）：%s",
                " | ".join(str(item.get("content") or "")[:120].replace("\n", " ") for item in resume_references),
            )
            resume_context_logger.info(
                "简历命中要点（将参与本轮提问）：trace_id=%s interview_id=%s 内容=%s",
                trace_id,
                interview_id,
                " | ".join(str(item.get("content") or "")[:120].replace("\n", " ") for item in resume_references),
            )
        else:
            logger.info("本轮未命中简历要点，继续使用岗位/JD/知识库上下文。")
            resume_context_logger.info(
                "本轮未命中简历要点：trace_id=%s interview_id=%s，继续使用岗位/JD/知识库上下文。",
                trace_id,
                interview_id,
            )
        if input_source == "ASR_SERVER":
            providers["asr"] = self.voice_service.asr_provider
            provider_status["asr"] = self.voice_service.health().get("asr", "UNKNOWN")

        follow_up_count = int(session["follow_up_count"])
        technical_count = int(session.get("technical_count", 0))
        if stage == InterviewStage.BEHAVIORAL.value:
            follow_up_count += 1
            ensure_behavior_followup_limit(stage, follow_up_count)

        live_score = min(95, max(40, 60 + min(len(answer) // 10, 35)))
        # 阶段推进规则保持确定性：
        # 自我介绍 -> 项目深挖 -> 多轮技术题 -> 行为题 -> 结束。
        # 技术题根据回答长度和计数决定是否继续追问，行为题使用 follow_up_count 控制上限。
        # 每次跨阶段都要经过 ensure_transition_allowed，防止非法跳转污染会话状态。
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
        jd_snapshot_content = str(session.get("jd_snapshot_content") or "").strip()
        jd_snapshot_title = str(session.get("jd_snapshot_title") or "").strip()
        jd_references: list[dict[str, Any]] = []
        if jd_snapshot_content:
            # JD 快照优先级高于知识库材料，因为它代表本次面试的具体岗位要求。
            # 最终 references 限制在 4 条以内，避免 prompt 过长导致生成质量下降。
            jd_references.append(
                {
                    "title": f"JD要求：{jd_snapshot_title or '岗位描述'}",
                    "content": jd_snapshot_content[:400],
                    "score": 0.0,
                    "source_path": "jd",
                    "retrieval_mode": "jd",
                }
            )
        references = [*jd_references, *resume_references, *references][:4]
        previous_turns = self.repo.list_turns(interview_id)
        history_messages = self._build_conversation_history(previous_turns=previous_turns, current_answer=answer)
        generation_mode = "mock"
        if next_stage == InterviewStage.END.value:
            # 结束阶段不再调用 LLM 生成问题，直接返回固定收束语并触发报告生成。
            next_question = INTERVIEW_END_MESSAGE
            providers["llm"] = "finalizer"
            provider_status["llm"] = "UP"
        elif self.question_workflow.llm_provider in {"openai", "ollama"}:
            try:
                # LLM 路径失败时只降级为模板问题，不让 provider 故障中断整场面试。
                # degrade_flags 会记录这次降级，便于报告和运维排查。
                next_question = self.question_workflow.generate(
                    answer=answer,
                    references=references,
                    stage=stage,
                    difficulty=str(session.get("difficulty") or "medium"),
                    technical_count=technical_count,
                    follow_up_count=follow_up_count,
                    history_messages=history_messages,
                    job_role=str(session.get("job_role") or ""),
                    jd_content=jd_snapshot_content,
                    resume_content=resume_text,
                    trace_id=trace_id,
                    interview_id=interview_id,
                )
                providers["llm"] = self.question_workflow.llm_provider
                provider_status["llm"] = self.question_workflow.health().get("llm", "UNKNOWN")
                generation_mode = "local_ai"
            except Exception:
                next_question = self.question_workflow.generate_template(
                    answer=answer,
                    references=references,
                    stage=stage,
                    difficulty=str(session.get("difficulty") or "medium"),
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
                difficulty=str(session.get("difficulty") or "medium"),
                technical_count=technical_count,
                follow_up_count=follow_up_count,
            )
            providers["llm"] = self.question_workflow.llm_provider
            provider_status["llm"] = "UP"

        output_mode = session["output_mode"]
        tts_audio_url = None
        if output_mode == "voice" and next_stage != InterviewStage.END.value:
            try:
                # TTS 只影响下一题的语音播放，不影响题目文本本身。
                # 因此 TTS 失败时记录降级标记并继续返回 next_question。
                tts_style = self._build_tts_style(stage=next_stage, question=next_question, session=session)
                tts_audio_url = self.voice_service.tts(
                    next_question,
                    instructions=tts_style["instructions"],
                    speed=tts_style["speed"],
                )
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
        resume_context_logger.info(
            "轮次已写入：trace_id=%s interview_id=%s turn_id=%s stage=%s generation_mode=%s",
            trace_id,
            interview_id,
            turn_id,
            stage,
            generation_mode,
        )
        if next_stage == InterviewStage.END.value:
            # 到达 END 后立即写入 GENERATING 报告占位记录。
            # 前端可以据此进入报告等待页，后台 ReportWorker 再异步补齐评分和建议。
            self.repo.finish_session(interview_id)
            self.repo.upsert_report(
                interview_id,
                {
                    "status": "GENERATING",
                    "overall_score": None,
                    "strengths": "[]",
                    "weaknesses": "[]",
                    "suggestions": "[]",
                    "dimension_scores": "[]",
                    "jd_resume_alignment": "[]",
                    "question_deep_dives": "[]",
                    "key_risks": "[]",
                    "final_recommendation": "",
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
                "dimension_scores": "[]",
                "jd_resume_alignment": "[]",
                "question_deep_dives": "[]",
                "key_risks": "[]",
                "final_recommendation": "",
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
