"""仓储 JSON 解码辅助逻辑测试。"""

from __future__ import annotations

from app.repositories.interview_repository import InterviewRepository


# 仓储中有不少字段以 JSON 字符串形式保存在 SQLite。
# 这些测试只调用纯解码方法，不打开数据库连接，保证执行稳定且不影响生产数据。


def test_safe_json_loads_returns_default_for_invalid_json() -> None:
    """非法 JSON 应返回调用方提供的默认值。"""
    repo = InterviewRepository(":memory:")

    assert repo._safe_json_loads("{bad json", []) == []
    assert repo._safe_json_loads(None, {}) == {}


def test_safe_json_loads_accepts_already_decoded_values() -> None:
    """已经是 list/dict 的值应原样返回。"""
    repo = InterviewRepository(":memory:")
    payload = [{"key": "A"}]

    assert repo._safe_json_loads(payload, []) is payload


def test_safe_json_loads_handles_double_encoded_json() -> None:
    """历史重复编码的 JSON 字符串应被二次解析。"""
    repo = InterviewRepository(":memory:")

    assert repo._safe_json_loads('"[{\\"key\\": \\"A\\"}]"', []) == [{"key": "A"}]


def test_safe_json_loads_respects_default_container_type() -> None:
    """解析结果类型和默认值类型不一致时应返回默认值。"""
    repo = InterviewRepository(":memory:")

    assert repo._safe_json_loads('{"a": 1}', []) == []
    assert repo._safe_json_loads("[1, 2]", {}) == {}


def test_decode_coding_question_expands_all_json_fields() -> None:
    """编程题 JSON 字段应被统一解码为前端需要的结构。"""
    repo = InterviewRepository(":memory:")
    decoded = repo._decode_coding_question(
        {
            "topic_tags": '["数组", "模拟"]',
            "sample_cases": '[{"input": "1 2", "output": "3"}]',
            "judge_cases": '[{"input": "2 3", "output": "5"}]',
            "self_test_case": '{"input": "1 1", "output": "2"}',
            "starter_codes": '{"cpp": "int main(){}"}',
            "source": '{"type": "seed"}',
        }
    )

    assert decoded["topic_tags"] == ["数组", "模拟"]
    assert decoded["sample_cases"][0]["output"] == "3"
    assert decoded["self_test_case"]["output"] == "2"
    assert decoded["starter_codes"]["cpp"].startswith("int main")
    assert decoded["source"]["type"] == "seed"
