"""面试状态机与规则约束。"""

from __future__ import annotations

from enum import Enum

from app.core.errors import ApiError


# 面试状态机是流程一致性的最后防线：
# 1. Service 层可以计算 next_stage，但必须通过这里校验是否合法。
# 2. END 是终态，不允许再迁移到其他阶段。
# 3. TECHNICAL 和 BEHAVIORAL 支持原阶段追问，但追问次数另行限制。
# 4. 这里不读取数据库，只校验纯状态规则，便于单元测试覆盖。
class InterviewStage(str, Enum):
    """面试阶段枚举。"""

    SELF_INTRO = "SELF_INTRO"
    PROJECT_DEEP_DIVE = "PROJECT_DEEP_DIVE"
    TECHNICAL = "TECHNICAL"
    BEHAVIORAL = "BEHAVIORAL"
    END = "END"


ALLOWED_TRANSITIONS: dict[InterviewStage, set[InterviewStage]] = {
    InterviewStage.SELF_INTRO: {InterviewStage.PROJECT_DEEP_DIVE},
    InterviewStage.PROJECT_DEEP_DIVE: {InterviewStage.TECHNICAL},
    InterviewStage.TECHNICAL: {InterviewStage.TECHNICAL, InterviewStage.BEHAVIORAL, InterviewStage.END},
    InterviewStage.BEHAVIORAL: {InterviewStage.BEHAVIORAL, InterviewStage.END},
    InterviewStage.END: set(),
}


def ensure_transition_allowed(current_stage: str, next_stage: str) -> None:
    """校验状态迁移是否合法。"""
    # 使用枚举构造可以顺便校验非法字符串，非法值会直接触发异常。
    # 如果目标阶段不在允许集合内，返回统一 STATE_409 业务错误。
    current = InterviewStage(current_stage)
    target = InterviewStage(next_stage)
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ApiError(code="STATE_409", message="面试阶段迁移非法", status_code=409)


def ensure_behavior_followup_limit(stage: str, followup_count: int, max_count: int = 3) -> None:
    """校验行为题追问次数是否超过上限。"""
    if stage == InterviewStage.BEHAVIORAL.value and followup_count > max_count:
        raise ApiError(code="STATE_409", message="行为题追问次数已达上限", status_code=409)
