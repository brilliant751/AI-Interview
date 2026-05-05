"""链路日志工具。"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

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
    turn_id: Optional[str],
    trace_id: str,
    providers: Dict[str, Optional[str]],
    degrade_flags: List[str],
    latency_ms: int,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """输出结构化链路日志。"""
    provider_list = [name for name in [providers.get("asr"), providers.get("llm"), providers.get("tts")] if name]
    payload = {
        "event": event,
        "trace_id": trace_id,
        "interview_id": interview_id,
        "turn_id": turn_id,
        "providers": providers,
        "provider": ",".join(provider_list) if provider_list else "unknown",
        "degrade_flags": degrade_flags,
        "latency_ms": latency_ms,
    }
    if extra:
        payload.update(extra)
    logger.info("面试链路事件: %s", json.dumps(payload, ensure_ascii=False, sort_keys=True))
