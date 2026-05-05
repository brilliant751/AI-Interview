"""本地模型 provider 单元测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.core.errors import ApiError  # noqa: E402
from app.services.providers import (  # noqa: E402
    FunASRProviderClient,
    OllamaProviderClient,
    PaddleSpeechProviderClient,
)


class LocalModelProviderTestCase(unittest.TestCase):
    """验证本地 provider 的成功与失败路径。"""

    def setUp(self) -> None:
        """初始化环境变量。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AI_INTERVIEW_DB_PATH"] = os.path.join(self.tmpdir.name, "test.db")
        get_settings.cache_clear()

    def tearDown(self) -> None:
        """清理测试环境。"""
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)

    @patch("app.services.providers.ollama_provider.httpx.Client.post")
    def test_ollama_generate_question_success(self, mock_post: Mock) -> None:
        """验证 Ollama 生成问题成功。"""
        mock_resp = Mock()
        mock_resp.json.return_value = {"message": {"content": "请说明你如何优化系统性能？"}}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        client = OllamaProviderClient()
        question = client.generate_question("hello")
        self.assertIn("优化", question)

    @patch("app.services.providers.funasr_provider.FunASRProviderClient._load_model")
    def test_funasr_transcribe_failed(self, mock_load_model: Mock) -> None:
        """验证 FunASR 失败时抛出可映射错误。"""
        model = Mock()
        model.generate.side_effect = RuntimeError("boom")
        mock_load_model.return_value = model

        client = FunASRProviderClient()
        with self.assertRaises(ApiError) as ctx:
            client.transcribe_audio_bytes(b"abc", "a.wav")
        self.assertEqual("ASR_UPSTREAM_FAILED", ctx.exception.code)

    @patch("app.services.providers.paddlespeech_provider.PaddleSpeechProviderClient._load_engine")
    def test_paddlespeech_synthesize_success(self, mock_load_engine: Mock) -> None:
        """验证 PaddleSpeech 合成成功。"""
        def _fake_engine(*args, **kwargs):
            output = kwargs.get("output")
            if output:
                with open(output, "wb") as f:
                    f.write(b"wav-bytes")

        mock_load_engine.return_value = _fake_engine

        client = PaddleSpeechProviderClient()
        audio = client.synthesize("你好")
        self.assertEqual(b"wav-bytes", audio)


if __name__ == "__main__":
    unittest.main()
