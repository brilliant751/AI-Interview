"""面试状态机规则补充测试。"""

from __future__ import annotations

import pytest

from app.core.errors import ApiError
from app.domain.interview_state import (
    InterviewStage,
    ensure_behavior_followup_limit,
    ensure_transition_allowed,
)


# 该文件补充纯状态机测试：
# 1. 不启动 FastAPI 应用，不访问数据库，执行速度很快。
# 2. 验证允许迁移和禁止迁移，防止后续阶段规则被误改。
# 3. 验证行为题追问上限，避免无限追问导致面试无法结束。
# 4. 状态机是服务层之前的规则防线，单元测试能快速定位流程回归。


@pytest.mark.parametrize(
    ("current_stage", "next_stage"),
    [
        (InterviewStage.SELF_INTRO.value, InterviewStage.PROJECT_DEEP_DIVE.value),
        (InterviewStage.PROJECT_DEEP_DIVE.value, InterviewStage.TECHNICAL.value),
        (InterviewStage.TECHNICAL.value, InterviewStage.TECHNICAL.value),
        (InterviewStage.TECHNICAL.value, InterviewStage.BEHAVIORAL.value),
        (InterviewStage.TECHNICAL.value, InterviewStage.END.value),
        (InterviewStage.BEHAVIORAL.value, InterviewStage.BEHAVIORAL.value),
        (InterviewStage.BEHAVIORAL.value, InterviewStage.END.value),
    ],
)
def test_allowed_stage_transitions_do_not_raise(current_stage: str, next_stage: str) -> None:
    """所有显式允许的阶段迁移都应通过校验。"""
    ensure_transition_allowed(current_stage, next_stage)


@pytest.mark.parametrize(
    ("current_stage", "next_stage"),
    [
        (InterviewStage.SELF_INTRO.value, InterviewStage.TECHNICAL.value),
        (InterviewStage.PROJECT_DEEP_DIVE.value, InterviewStage.BEHAVIORAL.value),
        (InterviewStage.BEHAVIORAL.value, InterviewStage.TECHNICAL.value),
        (InterviewStage.END.value, InterviewStage.SELF_INTRO.value),
    ],
)
def test_forbidden_stage_transitions_raise_state_conflict(current_stage: str, next_stage: str) -> None:
    """非法阶段跳转应统一转换为 STATE_409。"""
    with pytest.raises(ApiError) as exc_info:
        ensure_transition_allowed(current_stage, next_stage)

    assert exc_info.value.code == "STATE_409"
    assert exc_info.value.status_code == 409


def test_unknown_stage_value_is_rejected_by_enum_validation() -> None:
    """未知阶段值不能绕过枚举校验。"""
    with pytest.raises(ValueError):
        ensure_transition_allowed("UNKNOWN_STAGE", InterviewStage.END.value)


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_behavior_followup_limit_allows_counts_within_boundary(count: int) -> None:
    """行为题追问次数在上限内不应抛错。"""
    ensure_behavior_followup_limit(InterviewStage.BEHAVIORAL.value, count, max_count=3)


def test_behavior_followup_limit_rejects_count_above_boundary() -> None:
    """行为题追问超过上限时应返回状态冲突。"""
    with pytest.raises(ApiError) as exc_info:
        ensure_behavior_followup_limit(InterviewStage.BEHAVIORAL.value, 4, max_count=3)

    assert exc_info.value.code == "STATE_409"
    assert "追问次数" in exc_info.value.message


def test_behavior_followup_limit_ignores_non_behavior_stage() -> None:
    """非行为题阶段不应被行为题追问上限限制。"""
    ensure_behavior_followup_limit(InterviewStage.TECHNICAL.value, 99, max_count=3)
