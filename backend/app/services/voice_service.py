"""语音能力封装（可插拔降级版）。"""

from __future__ import annotations

import base64

from app.core.errors import ApiError
from app.services.providers import OpenAIProviderClient


class VoiceService:
    """统一 ASR/TTS 接口，支持 openai 与 mock 双模式。"""

    def __init__(self) -> None:
        """初始化语音提供方配置。"""
        from app.core.config import get_settings

        settings = get_settings()
        self.asr_provider = settings.asr_provider
        self.tts_provider = settings.tts_provider
        self._openai_client: OpenAIProviderClient | None = None

    def _get_openai_client(self) -> OpenAIProviderClient:
        """惰性初始化 OpenAI provider 客户端。"""
        if self._openai_client is None:
            self._openai_client = OpenAIProviderClient()
        return self._openai_client

    def asr(self, audio_url: str, audio_format: str = "mp3") -> str:
        """将音频转为文本。"""
        if self.asr_provider == "openai":
            try:
                return self._get_openai_client().transcribe_audio(audio_url=audio_url, audio_format=audio_format)
            except Exception as exc:
                import httpx

                if isinstance(exc, httpx.TimeoutException):
                    raise ApiError(code="UPSTREAM_TIMEOUT", message="上游语音识别超时", status_code=504) from exc
                raise ApiError(code="ASR_UPSTREAM_FAILED", message="上游语音识别失败", status_code=502) from exc
        if self.asr_provider == "funasr":
            return f"funasr-mock: {audio_url}"
        if self.asr_provider == "paddlespeech":
            return f"paddlespeech-mock: {audio_url}"
        return f"mock-asr: {audio_url}"

    def tts(self, text: str) -> str:
        """将文本转语音并返回音频 URL。"""
        safe = text.replace(" ", "_")[:48]
        if self.tts_provider == "openai":
            try:
                audio_bytes = self._get_openai_client().synthesize_speech(text)
                encoded = base64.b64encode(audio_bytes).decode("utf-8")
                return f"data:audio/mpeg;base64,{encoded}"
            except Exception as exc:
                raise ApiError(code="TTS_UPSTREAM_FAILED", message="上游语音合成失败", status_code=502) from exc
        if self.tts_provider == "paddlespeech":
            return f"https://paddlespeech-mock.local/{safe}.wav"
        return f"https://mock-tts.local/{safe}.mp3"

    def health(self) -> dict[str, str]:
        """返回语音 provider 健康状态。"""
        try:
            asr_health = "UP" if self.asr_provider != "openai" else self._get_openai_client().health()
        except Exception:
            asr_health = "DOWN"
        try:
            tts_health = "UP" if self.tts_provider != "openai" else self._get_openai_client().health()
        except Exception:
            tts_health = "DOWN"
        return {
            "asr": asr_health,
            "tts": tts_health,
        }
