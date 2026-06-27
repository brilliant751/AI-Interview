"""报告服务规则评分补充测试。"""

from __future__ import annotations

from app.services.report_service import ReportService


# 报告服务有 LLM 和规则回退两条路径。
# 这里专门覆盖规则计算和归一化逻辑，避免依赖真实模型服务。
# 这些测试能在报告结构重构时提醒维护者保留 12 维评分、置信度和回退报告字段。


def _turn(stage: str, answer: str, score: int = 76, next_question: str = "下一题") -> dict:
    """构造最小轮次对象。"""
    return {
        "stage": stage,
        "answer_text": answer,
        "live_score": score,
        "next_question": next_question,
    }


def test_extract_tokens_keeps_chinese_words_and_technical_terms() -> None:
    """关键词提取应同时保留中文词和常见技术符号。"""
    service = ReportService()

    tokens = service._extract_tokens("熟悉 Spring-Boot、Redis、C++，参与高并发系统")

    assert "spring-boot" in tokens
    assert "redis" in tokens
    assert "c++" in tokens
    assert "熟悉" in tokens


def test_confidence_level_depends_on_turn_count() -> None:
    """报告置信度应随有效轮次数量递增。"""
    service = ReportService()

    assert service._confidence_level([]) == "低"
    assert service._confidence_level([{}, {}, {}]) == "中"
    assert service._confidence_level([{}, {}, {}, {}, {}, {}]) == "高"


def test_calc_12d_scores_always_returns_all_dimensions_with_bounded_values() -> None:
    """12 维评分必须完整且限制在 1 到 5。"""
    service = ReportService()
    turns = [
        _turn("SELF_INTRO", "我负责过 Java 后端服务和 Redis 缓存治理", 82),
        _turn("PROJECT_DEEP_DIVE", "项目中我设计了异步任务和失败重试，并跟踪上线指标" * 3, 88),
        _turn("TECHNICAL", "我会从索引、缓存、限流和降级几个方向分析性能问题" * 3, 90),
        _turn("BEHAVIORAL", "我会先同步目标，再拆解风险，并推动团队复盘" * 3, 78),
    ]

    scores = service._calc_12d_scores(turns)

    assert len(scores) == 12
    assert set(scores).issuperset({"技术深度", "沟通表达", "岗位匹配度"})
    assert all(1 <= value <= 5 for value in scores.values())


def test_normalize_dimension_scores_fills_missing_llm_dimensions() -> None:
    """LLM 漏维度时应由规则分数补齐。"""
    service = ReportService()
    turns = [_turn("TECHNICAL", "回答较长" * 60, 85)]
    llm_scores = [
        {
            "dimension": "技术深度",
            "capability_score": 9,
            "match_score": 0,
            "confidence": "人工指定",
            "evidence": "模型证据",
        }
    ]

    normalized = service._normalize_dimension_scores(llm_scores, turns)
    by_name = {item["dimension"]: item for item in normalized}

    assert len(normalized) == 12
    assert by_name["技术深度"]["capability_score"] == 5
    assert by_name["技术深度"]["match_score"] == 1
    assert by_name["技术深度"]["evidence"] == "模型证据"
    assert "沟通表达" in by_name


def test_fallback_report_returns_ready_structured_payload() -> None:
    """规则回退报告应返回 READY 且包含结构化字段。"""
    service = ReportService()
    turns = [
        _turn("SELF_INTRO", "我主要做 Java 后端和接口性能优化", 75),
        _turn("PROJECT_DEEP_DIVE", "项目里我负责缓存、限流和发布回滚方案" * 4, 82),
        _turn("TECHNICAL", "我会用慢查询、线程池指标和链路日志定位问题" * 4, 86),
    ]
    session = {"job_role": "java", "difficulty": "medium", "jd_snapshot_content": "Java Redis 性能优化"}

    report = service._fallback_report(turns=turns, session=session, resume_text="Java Redis 项目经历")

    assert report["status"] == "READY"
    assert isinstance(report["overall_score"], int)
    assert len(report["dimension_scores"]) == 12
    assert report["question_deep_dives"]
    assert report["jd_resume_alignment"]
