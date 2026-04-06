"""链路日志工具。"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

logger = logging.getLogger("app.pipeline")


def build_trace_id() -> str:
    """生成链路追踪 ID。"""
    return f"trace_{uuid.uuid4().hex[:16]}"


def now_ms() -> int:
    """返回当前毫秒时间戳。"""
    return int(time.time() * 1000)


def log_pipeline_event(
    event: str,
    interview_id: str,
    turn_id: str | None,
    trace_id: str,
    providers: dict[str, str | None],
    degrade_flags: list[str],
    latency_ms: int,
    extra: dict[str, Any] | None = None,
) -> None:
    """输出结构化链路日志。"""
    payload = {
        "event": event,
        "trace_id": trace_id,
        "interview_id": interview_id,
        "turn_id": turn_id,
        "providers": providers,
        "degrade_flags": degrade_flags,
        "latency_ms": latency_ms,
    }
    if extra:
        payload.update(extra)
    logger.info("面试链路事件: %s", json.dumps(payload, ensure_ascii=False, sort_keys=True))
