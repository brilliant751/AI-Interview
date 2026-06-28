"""轮次异步任务执行器。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.repositories.interview_repository import InterviewRepository


# TurnWorker 专门处理单轮回答任务：
# 1. API 收到回答后立即创建 job，真实处理逻辑在后台执行。
# 2. 成功时把 submit_turn 的结果写入 turn_jobs.result_json。
# 3. 失败时统一写 FAILED 和 error_message，前端轮询可以展示失败原因。
# 4. shutdown 等待所有未完成任务，减少测试或服务退出时的悬空任务。
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
