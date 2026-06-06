"""面试预约服务。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.core.errors import ApiError
from app.repositories.interview_repository import InterviewRepository
from app.services.interview_service import InterviewService


class InterviewScheduleService:
    """封装单次模拟面试预约能力。"""

    def __init__(self, repo: InterviewRepository, interview_service: InterviewService, settings: Settings):
        """初始化预约服务依赖。"""
        self.repo = repo
        self.interview_service = interview_service
        self.settings = settings

    def _now(self) -> datetime:
        """获取当前北京时间。"""
        return datetime.now(ZoneInfo("Asia/Shanghai"))

    def _parse_dt(self, value: str) -> datetime:
        """解析 ISO 时间字符串。"""
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ApiError(code="SCHEDULE_400_INVALID_START_TIME", message="预约时间格式不正确", status_code=400) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        return parsed

    def _serialize_dt(self, value: datetime) -> str:
        """将时间序列化为 ISO 字符串。"""
        return value.isoformat()

    def _build_schedule_entry_url(self) -> str:
        """构建预约页入口地址。"""
        return f"{self.settings.frontend_base_url.rstrip('/')}/schedules"

    def _ensure_resume(self, resume_id: str, user_id: str) -> None:
        """校验简历存在且归属当前用户。"""
        resume = self.repo.get_resume(resume_id)
        if not resume or int(resume.get("is_deleted") or 0) == 1:
            raise ApiError(code="SCHEDULE_404_RESUME_NOT_FOUND", message="简历不存在", status_code=404)
        if str(resume.get("user_id") or "") != user_id:
            raise ApiError(code="RESUME_403_FORBIDDEN", message="无权使用该简历", status_code=403)

    def _normalize_role_and_jd(self, payload: dict, user_id: str) -> tuple[str, str, str]:
        """校验岗位方向与 JD 并返回归一化信息。"""
        jd_id = str(payload.get("jd_id") or "").strip()
        normalized_role = str(payload.get("job_role") or "").strip()
        jd_title = ""
        if not jd_id and not normalized_role:
            raise ApiError(code="SCHEDULE_400_ROLE_OR_JD_REQUIRED", message="岗位方向与岗位描述至少选择一个", status_code=400)
        if jd_id:
            jd = self.repo.get_jd(jd_id)
            if not jd or int(jd.get("is_deleted") or 0) == 1:
                raise ApiError(code="SCHEDULE_404_JD_NOT_FOUND", message="JD 不存在", status_code=404)
            is_system = str(jd.get("source_type") or "") == "SYSTEM_PRESET"
            if (not is_system) and str(jd.get("user_id") or "") != user_id:
                raise ApiError(code="JD_403_FORBIDDEN", message="无权访问该 JD", status_code=403)
            jd_role = str(jd.get("job_role") or "").strip()
            if normalized_role and jd_role != normalized_role:
                raise ApiError(code="JD_409_ROLE_MISMATCH", message="JD 岗位方向与面试方向不匹配", status_code=409)
            if not normalized_role:
                normalized_role = jd_role
            jd_title = str(jd.get("title") or "")
        return normalized_role, jd_id, jd_title

    def _ensure_voice_tone(self, payload: dict) -> str:
        """校验语气配置。"""
        if str(payload.get("output_mode") or "text") != "voice":
            return ""
        tone_id = str(payload.get("voice_tone_id") or "").strip()
        if not tone_id:
            return ""
        tone = self.repo.get_voice_tone(tone_id)
        if not tone:
            raise ApiError(code="VOICE_TONE_404_NOT_FOUND", message="语气配置不存在", status_code=404)
        if int(tone.get("is_active") or 0) != 1:
            raise ApiError(code="VOICE_TONE_409_INACTIVE", message="语气配置已停用", status_code=409)
        return tone_id

    def _refresh_status_for_row(self, row: dict) -> dict:
        """根据当前时间懒刷新预约状态。"""
        status = str(row.get("status") or "")
        if status in {"completed", "cancelled", "in_progress", "missed"}:
            return row
        start_at = self._parse_dt(str(row.get("scheduled_start_at") or ""))
        end_at = self._parse_dt(str(row.get("scheduled_end_at") or ""))
        now = self._now()
        schedule_id = str(row.get("schedule_id") or "")
        if status == "scheduled" and now >= start_at - timedelta(minutes=10) and now <= end_at:
            self.repo.update_schedule_status(schedule_id=schedule_id, user_id=str(row.get("user_id") or ""), status="ready")
            refreshed = self.repo.get_schedule(schedule_id)
            return refreshed or row
        if status in {"scheduled", "ready"} and now > end_at:
            self.repo.update_schedule_status(schedule_id=schedule_id, user_id=str(row.get("user_id") or ""), status="missed")
            refreshed = self.repo.get_schedule(schedule_id)
            return refreshed or row
        return row

    def _build_schedule_title(self, row: dict) -> str:
        """构建预约标题。"""
        return str(row.get("title") or row.get("session_name") or "AI 模拟面试预约")

    def _build_schedule_description(self, row: dict) -> str:
        """构建统一的日历描述文案。"""
        return (
            "请提前 5 分钟进入系统并检查麦克风。\n"
            f"面试入口：{self._build_schedule_entry_url()}\n"
            f"岗位方向：{str(row.get('job_role') or '--')}\n"
            f"难度：{str(row.get('difficulty') or '--')}"
        )

    def _build_calendar_links(self, row: dict) -> dict[str, str]:
        """生成 Google Calendar 与 Outlook Web 直达链接。"""
        start_at = self._parse_dt(str(row.get("scheduled_start_at") or ""))
        end_at = self._parse_dt(str(row.get("scheduled_end_at") or ""))
        title = self._build_schedule_title(row)
        description = self._build_schedule_description(row)
        google_dates = (
            f"{start_at.astimezone(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')}"
            f"/{end_at.astimezone(ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ')}"
        )
        google_query = urlencode(
            {
                "action": "TEMPLATE",
                "text": title,
                "dates": google_dates,
                "details": description,
            }
        )
        outlook_query = urlencode(
            {
                "subject": title,
                "startdt": start_at.isoformat(),
                "enddt": end_at.isoformat(),
                "body": description,
            }
        )
        return {
            "google_calendar_url": f"https://calendar.google.com/calendar/render?{google_query}",
            "outlook_calendar_url": f"https://outlook.office.com/calendar/0/deeplink/compose?{outlook_query}",
        }

    def _to_list_item(self, row: dict) -> dict:
        """将仓储对象转换为列表响应字典。"""
        refreshed = self._refresh_status_for_row(row)
        return {
            "schedule_id": str(refreshed.get("schedule_id") or ""),
            "title": str(refreshed.get("title") or ""),
            "status": str(refreshed.get("status") or "scheduled"),
            "source_type": str(refreshed.get("source_type") or "single"),
            "scheduled_start_at": str(refreshed.get("scheduled_start_at") or ""),
            "scheduled_end_at": str(refreshed.get("scheduled_end_at") or ""),
            "duration_minutes": int(refreshed.get("duration_minutes") or 0),
            "job_role": str(refreshed.get("job_role") or ""),
            "difficulty": str(refreshed.get("difficulty") or "medium"),
            "resume_id": str(refreshed.get("resume_id") or ""),
            "jd_id": str(refreshed.get("jd_id") or ""),
            "interview_id": str(refreshed.get("interview_id") or ""),
            "resume_file_name": str(refreshed.get("resume_file_name") or ""),
            **self._build_calendar_links(refreshed),
            "created_at": str(refreshed.get("created_at") or ""),
        }

    def _to_detail(self, row: dict) -> dict:
        """将仓储对象转换为详情响应字典。"""
        refreshed = self._refresh_status_for_row(row)
        raw_question_types = str(refreshed.get("question_types") or "[]")
        try:
            question_types = json.loads(raw_question_types)
        except Exception:
            question_types = []
        schedule_id = str(refreshed.get("schedule_id") or "")
        status = str(refreshed.get("status") or "scheduled")
        return {
            "schedule_id": schedule_id,
            "status": status,
            "source_type": str(refreshed.get("source_type") or "single"),
            "sequence_no": refreshed.get("sequence_no"),
            "plan_id": refreshed.get("plan_id"),
            "title": str(refreshed.get("title") or ""),
            "scheduled_start_at": str(refreshed.get("scheduled_start_at") or ""),
            "scheduled_end_at": str(refreshed.get("scheduled_end_at") or ""),
            "duration_minutes": int(refreshed.get("duration_minutes") or 0),
            "timezone": str(refreshed.get("timezone") or "Asia/Shanghai"),
            "resume_id": str(refreshed.get("resume_id") or ""),
            "resume_file_name": str(refreshed.get("resume_file_name") or ""),
            "job_role": str(refreshed.get("job_role") or ""),
            "jd_id": str(refreshed.get("jd_id") or ""),
            "jd_title": str(refreshed.get("jd_title") or ""),
            "difficulty": str(refreshed.get("difficulty") or "medium"),
            "input_mode": str(refreshed.get("input_mode") or "text"),
            "output_mode": str(refreshed.get("output_mode") or "text"),
            "session_name": str(refreshed.get("session_name") or ""),
            "question_types": [str(item) for item in question_types] if isinstance(question_types, list) else [],
            "voice_tone_id": str(refreshed.get("voice_tone_id") or ""),
            "interview_id": str(refreshed.get("interview_id") or ""),
            "calendar_download_url": f"/api/v1/interview-schedules/{schedule_id}/calendar.ics",
            **self._build_calendar_links(refreshed),
            "can_start": status == "ready",
            "can_cancel": status in {"scheduled", "ready"},
            "created_at": str(refreshed.get("created_at") or ""),
            "updated_at": str(refreshed.get("updated_at") or ""),
        }

    def create_schedule(self, payload: dict, user_id: str) -> dict:
        """创建单次面试预约。"""
        start_at = self._parse_dt(str(payload.get("scheduled_start_at") or ""))
        if start_at < self._now() + timedelta(minutes=5):
            raise ApiError(code="SCHEDULE_400_INVALID_START_TIME", message="预约时间需晚于当前时间至少 5 分钟", status_code=400)
        duration_minutes = int(payload.get("duration_minutes") or 0)
        if duration_minutes not in {20, 45, 60}:
            raise ApiError(code="SCHEDULE_400_INVALID_DURATION", message="预约时长仅支持 20/45/60 分钟", status_code=400)
        resume_id = str(payload.get("resume_id") or "").strip()
        if not resume_id:
            raise ApiError(code="SCHEDULE_400_RESUME_REQUIRED", message="请先选择简历", status_code=400)
        self._ensure_resume(resume_id, user_id)
        normalized_role, jd_id, _ = self._normalize_role_and_jd(payload, user_id)
        tone_id = self._ensure_voice_tone(payload)
        end_at = start_at + timedelta(minutes=duration_minutes)
        schedule_payload = {
            **payload,
            "job_role": normalized_role,
            "jd_id": jd_id,
            "voice_tone_id": tone_id,
            "scheduled_start_at": self._serialize_dt(start_at),
            "scheduled_end_at": self._serialize_dt(end_at),
            "timezone": str(start_at.tzinfo or "Asia/Shanghai"),
            "source_type": "single",
        }
        row = self.repo.create_schedule(user_id=user_id, payload=schedule_payload)
        return {
            "schedule_id": str(row.get("schedule_id") or ""),
            "status": str(row.get("status") or "scheduled"),
            "source_type": "single",
            "title": str(row.get("title") or ""),
            "scheduled_start_at": str(row.get("scheduled_start_at") or ""),
            "scheduled_end_at": str(row.get("scheduled_end_at") or ""),
            "duration_minutes": int(row.get("duration_minutes") or duration_minutes),
            "timezone": str(row.get("timezone") or "Asia/Shanghai"),
            "interview_id": str(row.get("interview_id") or ""),
            "calendar_download_url": f"/api/v1/interview-schedules/{row['schedule_id']}/calendar.ics",
            **self._build_calendar_links(row),
            "created_at": str(row.get("created_at") or ""),
        }

    def list_schedules(
        self,
        user_id: str,
        status: str | None,
        date_from: str | None,
        date_to: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        """分页查询预约列表。"""
        normalized_status = status.strip().lower() if status else None
        if normalized_status and normalized_status not in {"scheduled", "ready", "in_progress", "completed", "missed", "cancelled"}:
            raise ApiError(code="VALIDATE_400", message="status 参数不合法", status_code=400)
        offset = (page - 1) * page_size
        rows, total = self.repo.list_schedules(
            user_id=user_id,
            status=normalized_status,
            date_from=(date_from or "").strip() or None,
            date_to=(date_to or "").strip() or None,
            offset=offset,
            limit=page_size,
        )
        items = [self._to_list_item(row) for row in rows]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    def get_schedule_detail(self, schedule_id: str, user_id: str) -> dict:
        """查询预约详情。"""
        row = self.repo.get_schedule(schedule_id)
        if not row:
            raise ApiError(code="SCHEDULE_404_NOT_FOUND", message="预约不存在", status_code=404)
        if str(row.get("user_id") or "") != user_id:
            raise ApiError(code="SCHEDULE_403_FORBIDDEN", message="无权访问该预约", status_code=403)
        return self._to_detail(row)

    def cancel_schedule(self, schedule_id: str, user_id: str, reason: str) -> dict:
        """取消预约。"""
        detail = self.get_schedule_detail(schedule_id, user_id)
        if detail["status"] not in {"scheduled", "ready"}:
            raise ApiError(code="SCHEDULE_409_CANNOT_CANCEL", message="当前状态不可取消该预约", status_code=409)
        cancelled_at = self.repo.cancel_schedule(schedule_id=schedule_id, user_id=user_id, reason=reason)
        if not cancelled_at:
            raise ApiError(code="SCHEDULE_409_CANNOT_CANCEL", message="当前状态不可取消该预约", status_code=409)
        return {"schedule_id": schedule_id, "status": "cancelled", "cancelled_at": cancelled_at}

    def start_schedule(self, schedule_id: str, user_id: str) -> dict:
        """开始预约面试。"""
        detail = self.get_schedule_detail(schedule_id, user_id)
        if detail["status"] != "ready":
            raise ApiError(code="SCHEDULE_409_NOT_READY", message="尚未到可进入时间，请稍后再试", status_code=409)
        if detail["interview_id"]:
            session = self.repo.get_session(detail["interview_id"])
            if not session:
                raise ApiError(code="INTERVIEW_500_CREATE_FAILED", message="预约会话状态异常", status_code=500)
            self.repo.mark_schedule_in_progress(schedule_id=schedule_id, user_id=user_id)
            question = self.repo.get_last_next_question(user_id=user_id, interview_id=detail["interview_id"]) or "请先做 1 分钟自我介绍，聚焦与你申请岗位最相关的经历。"
            tts_audio_url = None
            if str(session.get("output_mode") or "") == "voice":
                try:
                    tts_style = self.interview_service._build_tts_style(
                        stage=str(session.get("current_stage") or "SELF_INTRO"),
                        question=question,
                        session=session,
                    )
                    tts_audio_url = self.interview_service.voice_service.tts(
                        question,
                        instructions=tts_style["instructions"],
                        speed=tts_style["speed"],
                    )
                except ApiError:
                    tts_audio_url = None
            return {
                "schedule_id": schedule_id,
                "status": "in_progress",
                "interview_id": detail["interview_id"],
                "current_stage": str(session.get("current_stage") or "SELF_INTRO"),
                "first_question": question,
                "tts_audio_url": tts_audio_url,
            }
        create_payload = {
            "resume_id": detail["resume_id"],
            "job_role": detail["job_role"],
            "difficulty": detail["difficulty"],
            "input_mode": detail["input_mode"],
            "output_mode": detail["output_mode"],
            "session_name": detail["session_name"] or detail["title"],
            "question_types": detail["question_types"],
            "jd_id": detail["jd_id"],
            "voice_tone_id": detail["voice_tone_id"],
            "schedule_id": schedule_id,
            "source_type": "scheduled",
        }
        created = self.interview_service.create_session(create_payload, user_id=user_id)
        interview_id = str(created.get("interview_id") or "")
        self.repo.bind_schedule_to_interview(schedule_id=schedule_id, user_id=user_id, interview_id=interview_id)
        self.repo.mark_schedule_in_progress(schedule_id=schedule_id, user_id=user_id)
        return {
            "schedule_id": schedule_id,
            "status": "in_progress",
            "interview_id": interview_id,
            "current_stage": str(created.get("current_stage") or "SELF_INTRO"),
            "first_question": str(created.get("first_question") or ""),
            "tts_audio_url": created.get("tts_audio_url"),
        }

    def build_calendar_content(self, schedule_id: str, user_id: str) -> str:
        """生成 ICS 文本。"""
        detail = self.get_schedule_detail(schedule_id, user_id)
        start_at = self._parse_dt(detail["scheduled_start_at"])
        end_at = self._parse_dt(detail["scheduled_end_at"])
        uid = f"{schedule_id}@ai-interview"
        stamp = self._now().astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
        dt_start = start_at.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
        dt_end = end_at.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
        title = self._build_schedule_title(detail)
        description = self._build_schedule_description(detail)
        escaped_title = title.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")
        escaped_description = description.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//AI Interview//Interview Schedule//CN",
            "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{dt_start}",
            f"DTEND:{dt_end}",
            f"SUMMARY:{escaped_title}",
            f"DESCRIPTION:{escaped_description}",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:AI 模拟面试即将开始",
            "TRIGGER:-PT10M",
            "END:VALARM",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        return "\r\n".join(lines) + "\r\n"
