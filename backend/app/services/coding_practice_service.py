"""在线编程练习业务服务。"""

from __future__ import annotations

from typing import Any

from app.core.errors import ApiError
from app.repositories.interview_repository import InterviewRepository
from app.services.code_execution_service import CodeExecutionService


class CodingPracticeService:
    """负责编程题列表、会话与判题流程。"""

    def __init__(self, repo: InterviewRepository, execution_service: CodeExecutionService):
        """初始化依赖。"""
        self.repo = repo
        self.execution_service = execution_service

    def list_questions(self, user_id: str) -> dict[str, Any]:
        """读取编程题列表并补充用户进度。"""
        questions = self.repo.list_coding_questions()
        records = {str(item["question_id"]): item for item in self.repo.list_coding_records(user_id=user_id)}
        items = []
        for question in questions:
            record = records.get(str(question["question_id"]))
            items.append(
                {
                    "question_id": str(question["question_id"]),
                    "slug": str(question["slug"]),
                    "title": str(question["title"]),
                    "difficulty": str(question["difficulty"]),
                    "topic_tags": list(question.get("topic_tags") or []),
                    "status": str(record.get("status") if record else "NOT_STARTED"),
                    "last_language": str(record.get("last_language") or "cpp") if record else "cpp",
                    "latest_submission_status": record.get("latest_submission_status") if record else None,
                    "session_id": record.get("session_id") if record else None,
                    "updated_at": record.get("last_opened_at") if record else question.get("updated_at"),
                }
            )
        return {"items": items, "total": len(items)}

    def create_or_get_session(self, question_id: str, user_id: str) -> dict[str, Any]:
        """为当前用户创建或恢复题目练习会话。"""
        question = self._require_question(question_id)
        session = self.repo.create_or_get_coding_session(user_id=user_id, question_id=question_id)
        return self._build_session_response(session=session, question=question, user_id=user_id)

    def get_session(self, session_id: str, user_id: str) -> dict[str, Any]:
        """读取当前用户的练习会话。"""
        session = self.repo.get_coding_session(user_id=user_id, session_id=session_id)
        if session is None:
            foreign = self.repo.get_coding_session_by_id(session_id)
            if foreign is None:
                raise ApiError(code="CODING_404_NOT_FOUND", message="编程练习会话不存在", status_code=404)
            raise ApiError(code="CODING_403_FORBIDDEN", message="无权访问该编程练习会话", status_code=403)
        question = self._require_question(str(session["question_id"]))
        return self._build_session_response(session=session, question=question, user_id=user_id)

    def run_self_test(self, session_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        """运行单题自测。"""
        session = self._require_session(session_id=session_id, user_id=user_id)
        question = self._require_question(str(session["question_id"]))
        language = str(payload["language"])
        source_code = self._resolve_source_code(
            user_id=user_id,
            session_id=session_id,
            question=question,
            language=language,
            inline_source_code=payload.get("source_code"),
        )
        result = self.execution_service.execute_cases(
            language=language,
            source_code=source_code,
            cases=[question["self_test_case"]],
            submit_type="RUN",
        )
        submission = self.repo.add_coding_submission(
            user_id=user_id,
            session_id=session_id,
            question_id=str(question["question_id"]),
            language=language,
            source_code="",
            submit_type="RUN",
            result_payload=result,
        )
        return {"session_id": session_id, "result": result, "submission_id": submission["submission_id"]}

    def submit(self, session_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        """执行正式判题。"""
        session = self._require_session(session_id=session_id, user_id=user_id)
        question = self._require_question(str(session["question_id"]))
        language = str(payload["language"])
        source_code = self._resolve_source_code(
            user_id=user_id,
            session_id=session_id,
            question=question,
            language=language,
            inline_source_code=payload.get("source_code"),
        )
        result = self.execution_service.execute_cases(
            language=language,
            source_code=source_code,
            cases=list(question.get("judge_cases") or []),
            submit_type="SUBMIT",
        )
        submission = self.repo.add_coding_submission(
            user_id=user_id,
            session_id=session_id,
            question_id=str(question["question_id"]),
            language=language,
            source_code="",
            submit_type="SUBMIT",
            result_payload=result,
        )
        return {"session_id": session_id, "result": result, "submission_id": submission["submission_id"]}

    def list_records(self, user_id: str) -> dict[str, Any]:
        """读取当前用户的编程练习记录。"""
        rows = self.repo.list_coding_records(user_id=user_id)
        items = [
            {
                "session_id": str(row["session_id"]),
                "question_id": str(row["question_id"]),
                "title": str(row["title"]),
                "difficulty": str(row["difficulty"]),
                "status": str(row["status"]),
                "last_language": str(row["last_language"]),
                "latest_submission_status": row.get("latest_submission_status"),
                "last_opened_at": row.get("last_opened_at"),
                "created_at": row.get("created_at"),
            }
            for row in rows
        ]
        return {"items": items, "total": len(items)}

    def _require_question(self, question_id: str) -> dict[str, Any]:
        """读取题目，不存在时抛错。"""
        question = self.repo.get_coding_question(question_id)
        if question is None:
            raise ApiError(code="CODING_404_NOT_FOUND", message="编程题不存在", status_code=404)
        return question

    def _require_session(self, session_id: str, user_id: str) -> dict[str, Any]:
        """读取会话，不存在时抛错。"""
        session = self.repo.get_coding_session(user_id=user_id, session_id=session_id)
        if session is None:
            foreign = self.repo.get_coding_session_by_id(session_id)
            if foreign is None:
                raise ApiError(code="CODING_404_NOT_FOUND", message="编程练习会话不存在", status_code=404)
            raise ApiError(code="CODING_403_FORBIDDEN", message="无权访问该编程练习会话", status_code=403)
        return session

    def _resolve_source_code(
        self,
        user_id: str,
        session_id: str,
        question: dict[str, Any],
        language: str,
        inline_source_code: object | None,
    ) -> str:
        """从请求或题目示例代码中解析本次运行代码。"""
        if isinstance(inline_source_code, str) and inline_source_code.strip():
            return inline_source_code
        starter_codes = question.get("starter_codes") or {}
        source_code = str(starter_codes.get(language) or "").strip()
        if not source_code:
            raise ApiError(code="VALIDATE_400", message="当前语言缺少可执行代码", status_code=400)
        return source_code

    def _build_session_response(self, session: dict[str, Any], question: dict[str, Any], user_id: str) -> dict[str, Any]:
        """组装会话响应。"""
        active_language = str(session.get("last_language") or "cpp")
        if active_language not in {"cpp", "java", "javascript"}:
            active_language = "cpp"
        question_payload = dict(question)
        question_payload.pop("starter_codes", None)
        return {
            "session_id": str(session["session_id"]),
            "question": question_payload,
            "status": str(session["status"]),
            "active_language": active_language,
            "last_opened_at": session.get("last_opened_at"),
            "created_at": session.get("created_at"),
        }
