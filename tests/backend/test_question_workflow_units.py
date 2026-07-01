"""问题生成工作流纯逻辑补充测试。"""

from __future__ import annotations

from app.services.question_workflow import QuestionWorkflow


# QuestionWorkflow 的真实 provider 调用已由 provider 测试覆盖。
# 这里测试不访问外部模型的辅助逻辑，包括参考资料优先级、模板问题轮换和输出清理。


def test_reference_context_prioritizes_jd_then_resume_then_knowledge() -> None:
    """参考上下文应按 JD、简历、知识库顺序进入 prompt。"""
    workflow = QuestionWorkflow()
    references = [
        {"title": "知识片段", "content": "通用知识", "source_path": "kb", "retrieval_mode": "vector"},
        {"title": "简历要点", "content": "候选人项目", "source_path": "resume", "retrieval_mode": "resume"},
        {"title": "JD要求", "content": "岗位要求", "source_path": "jd", "retrieval_mode": "jd"},
    ]

    context = workflow._build_reference_context(references)

    assert context.splitlines()[0].startswith("- JD要求")
    assert context.splitlines()[1].startswith("- 简历要点")
    assert context.splitlines()[2].startswith("- 知识片段")


def test_reference_context_returns_none_marker_when_empty() -> None:
    """没有参考资料时应返回稳定的“无”标记。"""
    workflow = QuestionWorkflow()

    assert workflow._build_reference_context([]) == "无"


def test_sanitize_spoken_question_removes_markdown_and_intent_lines() -> None:
    """模型输出清理应移除 Markdown 和追问意图说明。"""
    workflow = QuestionWorkflow()
    raw_text = """
**请解释你如何设计缓存失效策略？**
追问意图：验证缓存一致性
```extra```
"""

    cleaned = workflow._sanitize_spoken_question(raw_text)

    assert "**" not in cleaned
    assert "```" not in cleaned
    assert "追问意图" not in cleaned
    assert "缓存失效策略" in cleaned


def test_template_generation_rotates_technical_prompts_by_count() -> None:
    """技术题模板应根据 technical_count 轮换。"""
    workflow = QuestionWorkflow()
    references = [{"title": "Redis 缓存", "content": "缓存雪崩"}]

    first = workflow.generate_template("我做过缓存治理", references, "TECHNICAL", technical_count=0)
    second = workflow.generate_template("我做过缓存治理", references, "TECHNICAL", technical_count=1)

    assert first != second
    assert "缓存" in first
    assert "缓存" in second


def test_template_generation_uses_behavior_followup_count() -> None:
    """行为题模板应根据 follow_up_count 轮换。"""
    workflow = QuestionWorkflow()
    references = [{"title": "团队协作", "content": "推进项目"}]

    question = workflow.generate_template("我协调过跨团队项目", references, "BEHAVIORAL", follow_up_count=2)

    assert "关键" in question or "回顾" in question


def test_pick_reference_hint_ignores_generic_title() -> None:
    """参考标题应跳过泛化的“知识片段”。"""
    workflow = QuestionWorkflow()

    hint = workflow._pick_reference_hint([
        {"title": "知识片段"},
        {"title": "线程池治理"},
    ])

    assert hint == "线程池治理"
