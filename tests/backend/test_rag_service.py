"""RAG 服务降级策略测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import sys

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.core.errors import ApiError  # noqa: E402
from app.services.rag_service import RAGService  # noqa: E402


class RAGServiceTestCase(unittest.TestCase):
    """验证检索服务的显式降级行为。"""

    def setUp(self) -> None:
        """初始化隔离配置。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AI_INTERVIEW_CHROMA_DIR"] = self.tmpdir.name
        os.environ["AI_INTERVIEW_RETRIEVAL_FALLBACK_ENABLED"] = "false"
        get_settings.cache_clear()

    def tearDown(self) -> None:
        """清理测试环境。"""
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_CHROMA_DIR", None)
        os.environ.pop("AI_INTERVIEW_RETRIEVAL_FALLBACK_ENABLED", None)
        get_settings.cache_clear()

    def test_raise_error_when_chroma_unavailable_and_fallback_disabled(self) -> None:
        """验证默认模式下 Chroma 不可用会直接报错。"""
        service = RAGService()
        with patch.object(service, "_chroma_client", None):
            with self.assertRaises(ApiError) as exc:
                service.retrieve("java", "JVM 调优经验", top_k=2)
        self.assertEqual("KB_BUILD_424", exc.exception.code)

    def test_return_fallback_when_enabled(self) -> None:
        """验证显式打开降级后允许返回 fallback 结果。"""
        os.environ["AI_INTERVIEW_RETRIEVAL_FALLBACK_ENABLED"] = "true"
        get_settings.cache_clear()
        fallback_dir = Path(self.tmpdir.name) / "kb_java"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        (fallback_dir / "knowledge_index.jsonl").write_text(
            '{"title":"GC","content":"垃圾回收器和分代回收机制","source_path":"java-knowledge"}\n',
            encoding="utf-8",
        )
        service = RAGService()
        with patch.object(service, "_chroma_client", None):
            rows = service.retrieve("java", "垃圾回收", top_k=2)
        self.assertIsInstance(rows, list)
        self.assertTrue(rows)
        self.assertEqual("fallback", rows[0]["retrieval_mode"])


if __name__ == "__main__":
    unittest.main()
