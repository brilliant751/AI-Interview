"""离线构建与在线检索共享的 embedding 工具。"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Callable

import httpx


# embedding 工具同时服务离线构建和在线兜底：
# 1. tokenize 对中文连续字符和英文 token 采用同一套规则，和 RAGService 保持一致。
# 2. hash_embed_text 是无模型兜底，保证没有 Ollama 时也能生成稳定向量。
# 3. create_embedding_client 优先访问本地 Ollama，失败后返回 hash_fallback provider 标识。
# 4. trust_env=False 避免系统代理影响 localhost 的 embedding 请求。
# 5. 调用方可以统计 provider，判断本次索引主要由模型还是 hash fallback 构建。

def tokenize(text: str) -> list[str]:
    """将文本切分为中英文 token。"""
    return re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text.lower())


def hash_embed_text(text: str, dim: int) -> list[float]:
    """使用 hashing trick 生成归一化向量。"""
    # Hashing Trick 不需要训练模型，适合作为离线脚本的最后兜底。
    # 同一个 token 永远映射到同一个维度，因此重复构建结果稳定。
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
            # 优先调用本地 Ollama embedding；只要返回非空向量就认为成功。
            # 任何异常都会回退 hash，避免单条材料导致整个构建失败。
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
