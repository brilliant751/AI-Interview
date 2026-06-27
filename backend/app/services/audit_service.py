"""认证审计日志服务。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# 审计服务目前使用应用日志作为落点：
# 1. 认证成功、失败、登出、重置等事件都可以记录统一字段。
# 2. user_id、ip、ua、result、reason 便于后续做安全排查。
# 3. 如果未来接入数据库或外部审计系统，只需要替换这个服务实现。
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
