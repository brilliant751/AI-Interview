"""RAG 检索服务。"""

from __future__ import annotations

import json
import math
import re
import hashlib
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _tokenize(text: str) -> list[str]:
    """将文本切为中英文 token。"""
    return re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", text.lower())


def _embed_text(text: str, dim: int) -> list[float]:
    """使用 Hashing Trick 构建归一化向量。"""
    vector = [0.0] * dim
    for token in _tokenize(text):
        digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % dim
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [round(v / norm, 6) for v in vector]


class RAGService:
    """岗位化检索服务，优先 Chroma，失败时回退 JSONL。"""

    def __init__(self) -> None:
        """初始化配置与 Chroma 客户端。"""
        self.settings = get_settings()
        self.vector_dim = 64
        self._chroma_client = self._build_chroma_client()

    def _build_chroma_client(self):  # type: ignore[no-untyped-def]
        """构建 Chroma 客户端，失败时返回 None。"""
        try:
            import chromadb
        except Exception:
            return None
        try:
            return chromadb.PersistentClient(path=self.settings.chroma_dir)
        except Exception:
            return None

    def _retrieve_from_chroma(self, job_role: str, query: str, top_k: int) -> list[dict[str, Any]]:
        """从 Chroma collection 检索知识块。"""
        if self._chroma_client is None:
            return []
        collection_name = f"kb_{job_role}"
        try:
            collection = self._chroma_client.get_collection(collection_name)
            result = collection.query(
                query_embeddings=[_embed_text(query, self.vector_dim)],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            docs = result.get("documents") or [[]]
            metadatas = result.get("metadatas") or [[]]
            distances = result.get("distances") or [[]]
            rows: list[dict[str, Any]] = []
            for doc, metadata, distance in zip(docs[0], metadatas[0], distances[0]):
                rows.append(
                    {
                        "title": (metadata or {}).get("title", "知识片段"),
                        "content": doc,
                        "score": float(distance),
                        "source_path": (metadata or {}).get("source_path", ""),
                    }
                )
            return rows
        except Exception:
            return []

    def _retrieve_from_jsonl(self, job_role: str, query: str, top_k: int) -> list[dict[str, Any]]:
        """从本地 JSONL 索引回退检索。"""
        index_path = Path(self.settings.chroma_dir) / f"kb_{job_role}" / "knowledge_index.jsonl"
        if not index_path.exists():
            return []

        query_tokens = {t.lower() for t in query.split() if t.strip()}
        scored: list[tuple[int, dict[str, Any]]] = []
        with index_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                content = row.get("content", "").lower()
                score = sum(1 for token in query_tokens if token in content)
                if score > 0:
                    scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "title": item.get("title", "知识片段"),
                "content": item.get("content", ""),
                "score": score,
                "source_path": item.get("source_path", ""),
            }
            for score, item in scored[:top_k]
        ]

    def retrieve(self, job_role: str, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """统一检索入口。"""
        from_chroma = self._retrieve_from_chroma(job_role, query, top_k)
        if from_chroma:
            return from_chroma
        return self._retrieve_from_jsonl(job_role, query, top_k)
