"""轮次异步任务执行器。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.repositories.interview_repository import InterviewRepository


class TurnWorker:
    """负责异步执行轮次提交任务。"""

    def __init__(self, repo: InterviewRepository):
        """初始化执行器。"""
        self.repo = repo
        self._tasks: set[asyncio.Task] = set()

    def enqueue(self, job_id: str, task_factory: Callable[[], Awaitable[dict]]) -> None:
        """提交轮次任务到事件循环。"""
        task = asyncio.create_task(self._run(job_id, task_factory))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, job_id: str, task_factory: Callable[[], Awaitable[dict]]) -> None:
        """执行轮次任务并更新任务状态。"""
        try:
            result = await task_factory()
            self.repo.update_turn_job_status(job_id=job_id, status="READY", result=result, error_message="")
        except Exception as exc:
            self.repo.update_turn_job_status(
                job_id=job_id,
                status="FAILED",
                result={},
                error_message=f"轮次任务失败: {exc}",
            )

    async def shutdown(self) -> None:
        """等待所有未完成任务结束。"""
        if not self._tasks:
            return
        await asyncio.gather(*self._tasks, return_exceptions=True)
