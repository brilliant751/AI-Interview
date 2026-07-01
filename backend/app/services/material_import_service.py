"""材料导入任务编排服务。"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import kb_build_error
from app.models.schemas import (
    MaterialImportRequest,
    MaterialImportTaskResponse,
    MaterialImportTriggerResponse,
)

logger = logging.getLogger(__name__)


# 材料导入服务负责把管理员请求转换成后台脚本任务：
# 1. 任务状态保存在进程内，前端通过 task_id 查询进度。
# 2. 导入脚本仍然复用 scripts/data 下的离线处理能力，避免线上逻辑重复实现。
# 3. idempotency_key 用于防止管理员重复点击触发多次重建。
# 4. 失败时保留 last_error 和 report_path，便于在管理页展示诊断信息。
# 5. shutdown 会等待未完成任务，避免应用关闭时中断正在写报告的导入流程。
@dataclass
class _ImportTask:
    """导入任务运行时状态。"""

    payload: MaterialImportRequest
    status: str
    stage: str
    progress: int
    last_error: str
    report_path: str
    task_type: str
    runner: asyncio.Task[None] | None = None


class MaterialImportService:
    """管理材料导入异步任务生命周期。"""

    def __init__(self, repo_root: Path) -> None:
        """初始化任务存储。"""
        self.repo_root = repo_root
        self.settings = get_settings()
        self._tasks: dict[str, _ImportTask] = {}
        self._idempotency_map: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def trigger(
        self,
        payload: MaterialImportRequest,
        idempotency_key: str | None,
    ) -> MaterialImportTriggerResponse:
        """创建异步任务，命中幂等键时直接返回历史任务。"""
        self._validate_payload(payload)
        async with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_map:
                task_id = self._idempotency_map[idempotency_key]
                task = self._tasks.get(task_id)
                if task is not None:
                    logger.info("命中幂等键，直接返回历史任务，task_id=%s", task_id)
                    return MaterialImportTriggerResponse(
                        task_id=task_id,
                        status=task.status,
                        stage=task.stage,
                        progress=task.progress,
                        task_type=task.task_type,  # type: ignore[arg-type]
                        idempotency_hit=True,
                    )

            if payload.rebuild_mode == "full" and self._has_running_full_task():
                raise kb_build_error("KB_BUILD_409", "当前已有全量重建任务在运行，请稍后重试")

            task_id = f"kb-build-{uuid.uuid4().hex[:16]}"
            task = _ImportTask(
                payload=payload,
                status="PENDING",
                stage="init",
                progress=0,
                last_error="",
                report_path=self._build_report_path(payload.task_type),
                task_type=payload.task_type,
            )
            self._tasks[task_id] = task
            if idempotency_key:
                self._idempotency_map[idempotency_key] = task_id

            logger.info("创建导入任务成功，task_id=%s，模式=%s，岗位=%s", task_id, payload.rebuild_mode, payload.roles)
            task.runner = asyncio.create_task(self._run_task(task_id), name=f"material-import-{task_id}")
            return MaterialImportTriggerResponse(
                task_id=task_id,
                status=task.status,
                stage=task.stage,
                progress=task.progress,
                task_type=task.task_type,  # type: ignore[arg-type]
                idempotency_hit=False,
            )

    def get_task(self, task_id: str) -> MaterialImportTaskResponse:
        """查询任务状态详情。"""
        task = self._tasks.get(task_id)
        if task is None:
            raise kb_build_error("KB_BUILD_400", "任务不存在，请检查 task_id")
        return MaterialImportTaskResponse(
            task_id=task_id,
            status=task.status,  # type: ignore[arg-type]
            stage=task.stage,
            progress=task.progress,
            rebuild_mode=task.payload.rebuild_mode,
            roles=task.payload.roles,
            dry_run=task.payload.dry_run,
            task_type=task.task_type,  # type: ignore[arg-type]
            last_error=task.last_error,
            report_path=task.report_path,
        )

    async def shutdown(self) -> None:
        """应用关闭时终止未完成任务。"""
        tasks = [item.runner for item in self._tasks.values() if item.runner and not item.runner.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _has_running_full_task(self) -> bool:
        """判断是否已有运行中的全量任务。"""
        for task in self._tasks.values():
            if task.payload.rebuild_mode != "full":
                continue
            if task.status in {"PENDING", "RUNNING"}:
                return True
        return False

    async def _run_task(self, task_id: str) -> None:
        """执行导入任务流水线。"""
        task = self._tasks[task_id]
        try:
            task.status = "RUNNING"
            task.stage = "validate"
            task.progress = 5

            commands = self._build_commands(task.payload)
            total = len(commands)
            for index, step in enumerate(commands, start=1):
                task.stage = step["stage"]
                task.progress = min(95, int(index / total * 90))
                logger.info("开始执行导入阶段，task_id=%s，stage=%s", task_id, task.stage)
                await self._run_command(step["cmd"])
                logger.info("导入阶段执行成功，task_id=%s，stage=%s", task_id, task.stage)

            task.status = "SUCCESS"
            task.stage = "report"
            task.progress = 100
            logger.info("导入任务完成，task_id=%s", task_id)
        except Exception as exc:
            task.status = "FAILED"
            task.stage = "failed"
            task.progress = 100
            task.last_error = str(exc)
            logger.error("导入任务失败，task_id=%s，错误=%s", task_id, task.last_error)

    def _build_commands(self, payload: MaterialImportRequest) -> list[dict[str, Any]]:
        """构建导入脚本命令列表。"""
        python_cmd = sys.executable
        dry_run_args = ["--dry-run"] if payload.dry_run else []
        roles_args = [*payload.roles]
        commands: list[dict[str, Any]] = [
            {
                "stage": "validate",
                "cmd": [python_cmd, "backend/assets/scripts/data/validate_materials.py", "--strict"],
            },
            {
                "stage": "normalize",
                "cmd": [python_cmd, "backend/assets/scripts/data/normalize_materials.py", *dry_run_args],
            },
        ]
        if payload.task_type == "question_bank":
            commands.append(
                {
                    "stage": "question_bank",
                    "cmd": [python_cmd, "backend/assets/scripts/data/build_question_bank.py", *dry_run_args],
                }
            )
            return commands
        for role in payload.roles:
            commands.append(
                {
                    "stage": "chunking",
                    "cmd": [
                        python_cmd,
                        "backend/assets/scripts/data/chunk_with_ollama.py",
                        "--input",
                        f"backend/assets/data/normalized/{role}_knowledge.jsonl",
                        "--output",
                        f"backend/assets/data/normalized/chunk_preview_{role}.jsonl",
                        "--model",
                        payload.chunk_model,
                    ],
                }
            )
        commands.extend(
            [
                {
                    "stage": "question_bank",
                    "cmd": [python_cmd, "backend/assets/scripts/data/build_question_bank.py", *dry_run_args],
                },
                {
                    "stage": "embedding",
                    "cmd": [
                        python_cmd,
                        "backend/assets/scripts/data/build_knowledge_vectorstore.py",
                        "--rebuild-mode",
                        payload.rebuild_mode,
                        "--embed-model",
                        payload.embedding_model,
                        "--embed-batch-size",
                        str(self.settings.embed_batch_size),
                        "--roles",
                        *roles_args,
                        *dry_run_args,
                    ],
                },
                {
                    "stage": "evaluating",
                    "cmd": [python_cmd, "backend/assets/scripts/data/evaluate_retrieval.py"],
                },
            ]
        )
        return commands

    def _build_report_path(self, task_type: str) -> str:
        """根据任务类型返回对应报告路径。"""
        if task_type == "question_bank":
            return "backend/assets/data/reports/question_bank_build_report.json"
        return "backend/assets/data/reports/knowledge_vectorstore_build_report.json"

    def _validate_payload(self, payload: MaterialImportRequest) -> None:
        """校验导入请求参数。"""
        if not payload.roles:
            raise kb_build_error("KB_BUILD_400", "roles 不能为空")
        if payload.chunk_model != self.settings.chunk_model:
            raise kb_build_error("KB_BUILD_400", f"仅支持分块模型 {self.settings.chunk_model}")
        if payload.embedding_model != self.settings.embedding_model:
            raise kb_build_error("KB_BUILD_400", f"仅支持嵌入模型 {self.settings.embedding_model}")
        if payload.task_type == "question_bank" and payload.rebuild_mode != "incremental":
            raise kb_build_error("KB_BUILD_400", "题库任务仅支持 incremental 模式")

    async def _run_command(self, cmd: list[str]) -> None:
        """异步执行脚本命令并在失败时抛出统一错误。"""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(self.repo_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            return

        message = stderr.decode("utf-8", errors="ignore").strip()[-500:]
        if "ollama" in message.lower():
            raise kb_build_error("KB_BUILD_502", f"Ollama 调用失败：{message or '未知错误'}")
        if "chroma" in message.lower():
            raise kb_build_error("KB_BUILD_424", f"Chroma 依赖异常：{message or '未知错误'}")
        raise kb_build_error("KB_BUILD_500", f"导入脚本执行失败：{message or '未知错误'}")
