"""RAG 检索服务。"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import kb_build_error
from app.services.providers import OllamaProviderClient


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
    """岗位化检索服务，默认仅走 Chroma。"""

    def __init__(self) -> None:
        """初始化配置与 Chroma 客户端。"""
        self.settings = get_settings()
        self._chroma_client = self._build_chroma_client()
        self._alias_map = self._load_alias_map()
        self._ollama_client: OllamaProviderClient | None = None
        self.vector_dim = 768

    def _resolve_collection_dim(self, collection: Any) -> int:
        """从 collection 探测向量维度，失败时回退默认维度。"""
        try:
            sample = collection.get(limit=1, include=["embeddings"])
            embeddings = sample.get("embeddings") if isinstance(sample, dict) else None
            if embeddings and embeddings[0]:
                return len(embeddings[0])
        except Exception:
            pass
        return self.vector_dim

    def _get_ollama_client(self) -> OllamaProviderClient:
        """惰性初始化 Ollama embedding 客户端。"""
        if self._ollama_client is None:
            self._ollama_client = OllamaProviderClient()
        return self._ollama_client

    def _embed_query(self, query: str) -> list[float]:
        """优先使用本地 embedding，失败回退 hashing 向量。"""
        if self.settings.llm_provider == "ollama":
            try:
                vector = self._get_ollama_client().embed_text(query)
                if vector:
                    return vector
            except Exception:
                pass
        return _embed_text(query, self.vector_dim)

    def _build_chroma_client(self):  # type: ignore[no-untyped-def]
        """构建 Chroma 客户端。"""
        try:
            import chromadb
        except Exception:
            return None
        try:
            return chromadb.PersistentClient(path=self.settings.chroma_dir)
        except Exception:
            return None

    def _load_alias_map(self) -> dict[str, str]:
        """读取 collection alias 映射。"""
        alias_file = Path(self.settings.kb_collection_alias_file)
        if not alias_file.exists():
            return {}
        try:
            return json.loads(alias_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _resolve_collection_name(self, job_role: str) -> str:
        """解析岗位对应的 collection 名称。"""
        return self._alias_map.get(job_role, f"kb_{job_role}")

    def _retrieve_from_chroma(self, job_role: str, query: str, top_k: int) -> list[dict[str, Any]]:
        """从 Chroma collection 检索知识块。"""
        if self._chroma_client is None:
            raise kb_build_error("KB_BUILD_424", "Chroma 依赖不可用，请先完成知识库构建")

        collection_name = self._resolve_collection_name(job_role)
        try:
            collection = self._chroma_client.get_collection(collection_name)
            self.vector_dim = self._resolve_collection_dim(collection)
            result = collection.query(
                query_embeddings=[self._embed_query(query)],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            docs = result.get("documents") or [[]]
            metadatas = result.get("metadatas") or [[]]
            distances = result.get("distances") or [[]]
            rows: list[dict[str, Any]] = []
            doc_list = docs[0] if docs and isinstance(docs[0], list) else []
            metadata_list = metadatas[0] if metadatas and isinstance(metadatas[0], list) else []
            distance_list = distances[0] if distances and isinstance(distances[0], list) else []
            for doc, metadata, distance in zip(doc_list, metadata_list, distance_list):
                metadata_map = metadata if isinstance(metadata, dict) else {}
                rows.append(
                    {
                        "title": metadata_map.get("title", "知识片段"),
                        "content": doc,
                        "score": float(distance),
                        "source_path": metadata_map.get("source_path", ""),
                        "retrieval_mode": "chroma",
                    }
                )
            return rows
        except Exception as exc:
            raise kb_build_error("KB_BUILD_500", f"Chroma 检索失败：{exc}") from exc

    def _retrieve_from_jsonl(self, job_role: str, query: str, top_k: int) -> list[dict[str, Any]]:
        """从本地 JSONL 索引回退检索。"""
        index_path = Path(self.settings.chroma_dir) / f"kb_{job_role}" / "knowledge_index.jsonl"
        if not index_path.exists():
            return []

        query_tokens = {t.lower() for t in query.split() if t.strip()}
        scored: list[tuple[int, dict[str, Any]]] = []
        with index_path.open("r", encoding="utf-8") as file_obj:
            for line in file_obj:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                content = row.get("content", "").lower()
                score = sum(1 for token in query_tokens if token in content)
                if score > 0:
                    scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "title": row.get("title", "知识片段"),
                "content": row.get("content", ""),
                "score": score,
                "source_path": row.get("source_path", ""),
                "retrieval_mode": "fallback",
            }
            for score, row in scored[:top_k]
        ]

    def retrieve(self, job_role: str, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """统一检索入口。"""
        try:
            return self._retrieve_from_chroma(job_role, query, top_k)
        except Exception:
            # 仅在显式开启降级时允许 fallback，默认保持错误可见性。
            if not self.settings.retrieval_fallback_enabled:
                raise
            # Chroma 异常时回退本地 JSONL；若无索引则返回空结果，避免阻断主面试流程。
            fallback = self._retrieve_from_jsonl(job_role, query, top_k)
            return fallback

    def health(self) -> dict[str, Any]:
        """返回 embedding 与向量库健康状态。"""
        if self.settings.llm_provider == "ollama":
            try:
                self._get_ollama_client().embed_text("health check")
                return {
                    "status": "UP",
                    "provider": "ollama-embedding",
                    "model": self.settings.embed_model,
                    "latency_ms": 0,
                    "error_message": "",
                }
            except Exception as exc:
                return {
                    "status": "DEGRADED",
                    "provider": "hash-embedding-fallback",
                    "model": self.settings.embed_model,
                    "latency_ms": 0,
                    "error_message": str(exc),
                }
        return {
            "status": "UP",
            "provider": "hash-embedding",
            "model": "hashing-trick",
            "latency_ms": 0,
            "error_message": "",
        }
