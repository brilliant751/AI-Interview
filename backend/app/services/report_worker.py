"""异步报告任务执行器。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.repositories.interview_repository import InterviewRepository
from app.services.report_service import ReportService


class ReportWorker:
    """负责异步执行报告生成任务。"""

    def __init__(self, repo: InterviewRepository):
        """初始化执行器。"""
        self.repo = repo
        self.report_service = ReportService()
        self._tasks: set[asyncio.Task] = set()

    def enqueue(self, interview_id: str) -> None:
        """提交报告任务到事件循环。"""
        task = asyncio.create_task(self._run(interview_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, interview_id: str) -> None:
        """执行报告计算并落库。"""
        try:
            await asyncio.sleep(0)
            turns = self.repo.list_turns(interview_id)
            report = self.report_service.build_report(turns)
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
                    "error_message": f"报告任务失败: {exc}",
                },
            )

    async def shutdown(self) -> None:
        """等待所有未完成任务结束。"""
        if not self._tasks:
            return
        await asyncio.gather(*self._tasks, return_exceptions=True)
