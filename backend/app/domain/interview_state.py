"""面试状态机与规则约束。"""

from __future__ import annotations

from enum import Enum

from app.core.errors import ApiError


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
    current = InterviewStage(current_stage)
    target = InterviewStage(next_stage)
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ApiError(code="STATE_409", message="面试阶段迁移非法", status_code=409)


def ensure_behavior_followup_limit(stage: str, followup_count: int, max_count: int = 3) -> None:
    """校验行为题追问次数是否超过上限。"""
    if stage == InterviewStage.BEHAVIORAL.value and followup_count > max_count:
        raise ApiError(code="STATE_409", message="行为题追问次数已达上限", status_code=409)

