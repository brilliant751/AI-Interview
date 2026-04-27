"""认证审计日志服务。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class AuditService:
    """认证审计服务。"""

    def log_auth_event(
        self,
        event: str,
        user_id: str,
        ip: str,
        user_agent: str,
        result: str,
        reason: str,
    ) -> None:
        """记录认证事件审计日志。"""
        logger.info(
            "认证审计 event=%s user_id=%s ip=%s ua=%s result=%s reason=%s",
            event,
            user_id,
            ip,
            user_agent,
            result,
            reason,
        )
