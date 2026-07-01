"""链路日志工具。"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.pipeline")

# 链路日志工具用于把一次面试轮次串起来：
# 1. trace_id 贯穿回答解析、RAG、LLM、TTS 和最终写库。
# 2. providers 记录本轮实际命中的外部能力，degrade_flags 记录降级原因。
# 3. 日志采用 JSON 字符串，后续可以被 ELK、Loki 等系统直接解析。
# 4. 工具函数保持无业务依赖，InterviewService 可以在任意阶段调用。


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
    # provider 字段额外拼接一份字符串，是为了兼容只支持简单文本搜索的日志工具。
    # 完整结构仍保留在 providers 字典中，便于自动化分析。
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
