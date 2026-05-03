"""离线构建与在线检索共享的 embedding 工具。"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Callable

import httpx


def tokenize(text: str) -> list[str]:
    """将文本切分为中英文 token。"""
    return re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text.lower())


def hash_embed_text(text: str, dim: int) -> list[float]:
    """使用 hashing trick 生成归一化向量。"""
    vector = [0.0] * dim
    for token in tokenize(text):
        digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % dim
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [round(v / norm, 6) for v in vector]


def create_embedding_client(
    model: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 20.0,
) -> Callable[[str, int], tuple[list[float], str]]:
    """创建 embedding 函数，优先走 Ollama，失败回退 hash。"""
    resolved_model = model or os.getenv("AI_INTERVIEW_EMBED_MODEL", "nomic-embed-text")
    resolved_base_url = (base_url or os.getenv("AI_INTERVIEW_OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    # 仅访问本地 Ollama，禁用环境代理，避免 SOCKS 代理缺少依赖导致初始化失败。
    client = httpx.Client(timeout=timeout_seconds, trust_env=False)

    def embed_text(text: str, dim: int) -> tuple[list[float], str]:
        """生成向量并返回 provider 标识。"""
        try:
            response = client.post(
                f"{resolved_base_url}/api/embeddings",
                json={"model": resolved_model, "prompt": text},
            )
            response.raise_for_status()
            payload = response.json()
            vector = [float(v) for v in (payload.get("embedding") or [])]
            if vector:
                return vector, "ollama"
        except Exception:
            pass
        return hash_embed_text(text, dim), "hash_fallback"

    return embed_text
