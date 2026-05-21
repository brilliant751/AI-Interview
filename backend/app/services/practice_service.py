"""题库练习流程编排服务。"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.core.errors import ApiError
from app.repositories.interview_repository import InterviewRepository


class PracticeService:
    """封装题库练习会话创建、答题推进和记录查询流程。"""

    def __init__(self, repo: InterviewRepository):
        """初始化服务依赖。"""
        self.repo = repo

    def create_session(self, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        """创建题库练习会话并返回首题。"""
        questions = self._list_question_bank_candidates(payload)
        question_count = int(payload["question_count"])
        if len(questions) < question_count:
            raise ApiError(code="VALIDATE_400", message="可用题量不足，请调整筛选条件后重试", status_code=400)

        selected = self._select_questions_for_mode(payload=payload, questions=questions)
        practice = self.repo.create_practice_session_with_snapshots(
            user_id=user_id,
            payload={
                "job_role": payload["job_role"],
                "mode": payload["mode"],
                "question_count": question_count,
            },
            question_snapshots=selected,
        )
        return self.get_session(practice["practice_id"], user_id=user_id)

    def get_session(self, practice_id: str, user_id: str) -> dict[str, Any]:
        """查询题库练习会话状态。"""
        session = self._require_owned_session(practice_id=practice_id, user_id=user_id)
        snapshots = self.repo.list_practice_question_snapshots(user_id=user_id, practice_id=practice_id)
        answers = self.repo.list_practice_answers(user_id=user_id, practice_id=practice_id)
        return self._build_session_response(session=session, snapshots=snapshots, answers=answers, user_id=user_id)

    def submit_answer(self, practice_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        """提交题库练习答案，并在顺序模式下推进到下一题。"""
        session = self._require_owned_session(practice_id=practice_id, user_id=user_id)
        if str(session.get("status") or "") == "FINISHED":
            raise ApiError(code="STATE_409", message="练习已结束，禁止继续提交", status_code=409)

        snapshots = self.repo.list_practice_question_snapshots(user_id=user_id, practice_id=practice_id)
        answers = self.repo.list_practice_answers(user_id=user_id, practice_id=practice_id)
        submitted_question_id = str(payload["session_question_id"])
        if any(str(answer["session_question_id"]) == submitted_question_id for answer in answers):
            raise ApiError(code="PRACTICE_409_DUPLICATE_ANSWER", message="当前题目已提交，请继续下一题", status_code=409)
        current_question = self._resolve_current_question(snapshots=snapshots, answers=answers)
        if current_question is None:
            self._update_session_status(practice_id=practice_id, user_id=user_id, status="FINISHED")
            raise ApiError(code="STATE_409", message="练习已结束，禁止继续提交", status_code=409)
        if submitted_question_id != str(current_question["session_question_id"]):
            raise ApiError(code="STATE_409", message="提交题目与当前题目不一致", status_code=409)

        try:
            self.repo.add_practice_answer(
                user_id=user_id,
                practice_id=practice_id,
                session_question_id=submitted_question_id,
                answer_text=str(payload["answer_text"]).strip(),
            )
        except sqlite3.IntegrityError as exc:
            raise ApiError(code="PRACTICE_409_DUPLICATE_ANSWER", message="当前题目已提交，请继续下一题", status_code=409) from exc
        updated_answers = self.repo.list_practice_answers(user_id=user_id, practice_id=practice_id)
        completed_count = len(updated_answers)
        finished = completed_count >= len(snapshots)
        next_question = None if finished else self._to_question_response(snapshots[completed_count])
        if finished:
            self._update_session_status(practice_id=practice_id, user_id=user_id, status="FINISHED")
        return {
            "practice_id": practice_id,
            "status": "FINISHED" if finished else "ACTIVE",
            "completed_count": completed_count,
            "finished": finished,
            "question_strategy": self._question_strategy(str(session["mode"])),
            "next_question": next_question,
        }

    def finish_session(self, practice_id: str, user_id: str) -> dict[str, Any]:
        """手动结束题库练习会话。"""
        self._require_owned_session(practice_id=practice_id, user_id=user_id)
        self._update_session_status(practice_id=practice_id, user_id=user_id, status="FINISHED")
        return self.get_session(practice_id, user_id=user_id)

    def list_records(self, user_id: str) -> dict[str, Any]:
        """查询当前用户的题库练习记录列表。"""
        rows = self.repo.list_practice_records(user_id=user_id)
        items = [
            {
                "practice_id": str(row["practice_id"]),
                "job_role": str(row["job_role"]),
                "mode": str(row["mode"]),
                "status": str(row["status"]),
                "total_questions": int(row["question_count"]),
                "answered_count": int(row["answered_count"] or 0),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]
        return {"items": items, "total": len(items)}

    def get_session_records(self, practice_id: str, user_id: str) -> dict[str, Any]:
        """查询单场题库练习的题目与答案明细。"""
        self._require_owned_session(practice_id=practice_id, user_id=user_id)
        detail = self.repo.get_practice_record_detail(user_id=user_id, practice_id=practice_id)
        if detail is None:
            raise ApiError(code="PRACTICE_404_NOT_FOUND", message="练习会话不存在", status_code=404)
        session = detail["session"]
        items = [
            {
                "session_question_id": str(item["session_question_id"]),
                "question_order": int(item["question_order"]),
                "category": item.get("category"),
                "stem": str(item["stem"]),
                "analysis": item.get("analysis"),
                "answer_text": item.get("answer_text"),
                "answered_at": item.get("answered_at"),
            }
            for item in detail["items"]
        ]
        completed_count = sum(1 for item in items if item["answer_text"])
        return {
            "practice_id": str(session["practice_id"]),
            "job_role": str(session["job_role"]),
            "mode": str(session["mode"]),
            "status": str(session["status"]),
            "total_questions": int(session["question_count"]),
            "completed_count": completed_count,
            "items": items,
            "created_at": session.get("created_at"),
            "finished_at": session.get("finished_at"),
        }

    def _select_questions_for_mode(self, payload: dict[str, Any], questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按练习模式选取题目列表。"""
        question_count = int(payload["question_count"])
        mode = str(payload["mode"])
        if mode == "followup":
            return self._build_followup_placeholder_questions(questions[:question_count])
        return questions[:question_count]

    def _list_question_bank_candidates(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """通过仓储读取岗位题库候选题。"""
        job_role = str(payload["job_role"])
        categories = [str(item) for item in payload.get("category_filters") or []]
        try:
            rows = self.repo.list_question_bank_items(job_role=job_role, categories=categories)
        except Exception as exc:
            message = str(exc).lower()
            if "no such table" not in message:
                raise
            raise ApiError(code="STATE_409", message="题库尚未准备完成，请稍后重试", status_code=409) from exc
        return [
            {
                "source_question_id": str(row["record_id"]),
                "category": row.get("category"),
                "stem": str(row["question"]),
                "analysis": row.get("analysis"),
            }
            for row in rows
        ]

    def _require_owned_session(self, practice_id: str, user_id: str) -> dict[str, Any]:
        """校验题库练习会话存在且归属当前用户。"""
        session = self.repo.get_practice_session(user_id=user_id, practice_id=practice_id)
        if session is not None:
            return session
        practice = self.repo.get_practice_session_by_id(practice_id=practice_id)
        if practice is None:
            raise ApiError(code="PRACTICE_404_NOT_FOUND", message="练习会话不存在", status_code=404)
        raise ApiError(code="PRACTICE_403_FORBIDDEN", message="无权访问该练习会话", status_code=403)

    def _update_session_status(self, practice_id: str, user_id: str, status: str) -> None:
        """通过仓储更新题库练习会话状态。"""
        updated = self.repo.update_practice_session_status(user_id=user_id, practice_id=practice_id, status=status)
        if not updated:
            raise ApiError(code="STATE_409", message="练习状态更新失败", status_code=409)

    def _build_session_response(
        self,
        session: dict[str, Any],
        snapshots: list[dict[str, Any]],
        answers: list[dict[str, Any]],
        user_id: str,
    ) -> dict[str, Any]:
        """构建题库练习会话响应。"""
        completed_count = len(answers)
        finished = str(session.get("status") or "") == "FINISHED" or completed_count >= len(snapshots)
        if finished and str(session.get("status") or "") != "FINISHED":
            self._update_session_status(practice_id=str(session["practice_id"]), user_id=user_id, status="FINISHED")
            session = {**session, "status": "FINISHED"}
        return {
            "practice_id": str(session["practice_id"]),
            "job_role": str(session["job_role"]),
            "mode": str(session["mode"]),
            "status": "FINISHED" if finished else "ACTIVE",
            "total_questions": len(snapshots),
            "completed_count": completed_count,
            "finished": finished,
            "question_strategy": self._question_strategy(str(session["mode"])),
            "current_question": None if finished else self._resolve_current_question(snapshots, answers),
            "created_at": session.get("created_at"),
        }

    def _build_followup_placeholder_questions(self, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """显式定义 followup 模式第一版的占位策略。"""
        return [
            {
                **question,
                "analysis": question.get("analysis"),
            }
            for question in questions
        ]

    def _question_strategy(self, mode: str) -> str:
        """返回当前模式对前端暴露的题目推进策略。"""
        if mode == "followup":
            return "followup_placeholder"
        return "sequence"

    def _resolve_current_question(
        self,
        snapshots: list[dict[str, Any]],
        answers: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """根据当前进度定位当前题目。"""
        next_index = len(answers)
        if next_index >= len(snapshots):
            return None
        return self._to_question_response(snapshots[next_index])

    def _to_question_response(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """将题目快照转换为接口响应结构。"""
        return {
            "session_question_id": str(snapshot["session_question_id"]),
            "question_order": int(snapshot["question_order"]),
            "source_question_id": snapshot.get("source_question_id"),
            "category": snapshot.get("category"),
            "stem": str(snapshot["stem"]),
            "analysis": snapshot.get("analysis"),
        }
