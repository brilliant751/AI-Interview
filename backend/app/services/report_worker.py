"""异步报告任务执行器。"""

from __future__ import annotations

import asyncio

from app.repositories.interview_repository import InterviewRepository
from app.services.report_service import ReportService


class ReportWorker:
    """负责异步执行报告生成任务。"""

    def __init__(self, repo: InterviewRepository):
        """初始化执行器。"""
        self.repo = repo
        self.report_service = ReportService()
        self._tasks: set[asyncio.Task] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def enqueue(self, interview_id: str) -> None:
        """提交报告任务到事件循环。"""
        def _create_task() -> None:
            task = asyncio.create_task(self._run(interview_id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        try:
            loop = asyncio.get_running_loop()
            self._loop = loop
            _create_task()
        except RuntimeError:
            if self._loop is None:
                raise
            self._loop.call_soon_threadsafe(_create_task)

    async def _run(self, interview_id: str) -> None:
        """执行报告计算并落库。"""
        try:
            await asyncio.sleep(0)
            turns = self.repo.list_turns(interview_id)
            session = self.repo.get_session(interview_id) or {}
            resume_id = str(session.get("resume_id") or "")
            resume = self.repo.get_resume(resume_id) if resume_id else None
            resume_text = str((resume or {}).get("parsed_text") or "")
            report = self.report_service.build_report(turns, session=session, resume_text=resume_text)
            self.repo.upsert_report(interview_id, report)
        except Exception as exc:
            self.repo.upsert_report(
                interview_id,
                {
                    "status": "FAILED",
                    "overall_score": None,
                    "strengths": "[]",
                    "weaknesses": "[]",
                    "suggestions": "[]",
                    "dimension_scores": "[]",
                    "jd_resume_alignment": "[]",
                    "question_deep_dives": "[]",
                    "key_risks": "[]",
                    "final_recommendation": "",
                    "error_message": f"报告任务失败: {exc}",
                },
            )

    async def shutdown(self) -> None:
        """等待所有未完成任务结束。"""
        if not self._tasks:
            return
        await asyncio.gather(*self._tasks, return_exceptions=True)
