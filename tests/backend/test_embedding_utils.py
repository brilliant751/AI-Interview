"""离线 embedding 工具补充测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_ROOT = Path(__file__).resolve().parents[2] / "scripts" / "data"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from embeddings import create_embedding_client, hash_embed_text, tokenize  # noqa: E402


# embedding 工具是离线构建和在线检索兜底的共同基础。
# 这里不依赖本地 Ollama 服务，只验证 token、hash 向量和异常 fallback 行为。


def test_tokenize_keeps_chinese_and_english_tokens() -> None:
    """分词应同时识别中文片段和英文技术词。"""
    tokens = tokenize("Java 后端 Redis_cache 与 高并发")

    assert "java" in tokens
    assert "redis_cache" in tokens
    assert "后端" in tokens
    assert "高并发" in tokens


def test_hash_embed_text_is_stable_and_normalized() -> None:
    """hash embedding 对相同文本应稳定，且非空文本向量应归一化。"""
    first = hash_embed_text("Java Redis Java", 16)
    second = hash_embed_text("Java Redis Java", 16)

    assert first == second
    assert len(first) == 16
    assert any(value > 0 for value in first)
    assert max(first) <= 1


def test_hash_embed_text_returns_zero_vector_for_empty_text() -> None:
    """空文本应返回指定维度的零向量。"""
    assert hash_embed_text("", 8) == [0.0] * 8


def test_embedding_client_falls_back_to_hash_when_ollama_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama 不可用时 embedding client 应返回 hash_fallback。"""

    class _FailingClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def post(self, *args, **kwargs):
            raise RuntimeError("ollama down")

    monkeypatch.setattr("embeddings.httpx.Client", _FailingClient)

    embed_text = create_embedding_client(model="mock", base_url="http://127.0.0.1:1")
    vector, provider = embed_text("Java Redis", 12)

    assert provider == "hash_fallback"
    assert len(vector) == 12
