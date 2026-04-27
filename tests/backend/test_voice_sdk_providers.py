"""语音 SDK provider 单元测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.core.errors import ApiError  # noqa: E402
from app.services.providers import FunASRProviderClient, PaddleSpeechProviderClient  # noqa: E402


class VoiceSDKProviderTestCase(unittest.TestCase):
    """覆盖 SDK provider 的惰性初始化与异常映射。"""

    def setUp(self) -> None:
        """初始化测试环境。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AI_INTERVIEW_DB_PATH"] = os.path.join(self.tmpdir.name, "test.db")
        get_settings.cache_clear()

    def tearDown(self) -> None:
        """清理测试环境。"""
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)

    @patch("app.services.providers.funasr_provider.FunASRProviderClient._load_model")
    def test_funasr_lazy_init_and_success(self, mock_load_model: Mock) -> None:
        """验证 FunASR 惰性初始化与成功识别。"""
        model = Mock()
        model.generate.return_value = [{"text": "识别成功"}]
        mock_load_model.return_value = model

        client = FunASRProviderClient()
        result = client.transcribe_audio_bytes(b"audio", "demo.wav")
        self.assertEqual("识别成功", result["text"])
        self.assertEqual(1, mock_load_model.call_count)

    @patch("app.services.providers.funasr_provider.FunASRProviderClient._load_model")
    def test_funasr_timeout_mapping(self, mock_load_model: Mock) -> None:
        """验证 FunASR 超时映射。"""
        model = Mock()
        model.generate.side_effect = TimeoutError("timeout")
        mock_load_model.return_value = model

        client = FunASRProviderClient()
        with self.assertRaises(ApiError) as ctx:
            client.transcribe_audio_bytes(b"audio", "demo.wav")
        self.assertEqual("UPSTREAM_TIMEOUT", ctx.exception.code)

    @patch("app.services.providers.paddlespeech_provider.PaddleSpeechProviderClient._load_engine")
    def test_paddlespeech_health_down_when_engine_failed(self, mock_load_engine: Mock) -> None:
        """验证 PaddleSpeech 初始化失败时健康检查为 DOWN。"""
        mock_load_engine.side_effect = RuntimeError("engine fail")

        client = PaddleSpeechProviderClient()
        health = client.health()
        self.assertEqual("DOWN", health["status"])
        self.assertIn("engine fail", health["error_message"])


if __name__ == "__main__":
    unittest.main()
