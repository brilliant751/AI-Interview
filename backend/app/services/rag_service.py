"""RAG 检索服务。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import kb_build_error


class RAGService:
    """岗位化检索服务，默认仅走 Chroma。"""

    def __init__(self) -> None:
        """初始化配置与 Chroma 客户端。"""
        self.settings = get_settings()
        self._chroma_client = self._build_chroma_client()
        self._alias_map = self._load_alias_map()

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
            result = collection.query(
                query_texts=[query],
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
        except Exception as exc:
            if not self.settings.retrieval_fallback_enabled:
                if isinstance(exc, Exception):
                    raise
            fallback = self._retrieve_from_jsonl(job_role, query, top_k)
            return fallback
