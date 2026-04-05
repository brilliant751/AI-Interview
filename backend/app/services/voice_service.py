"""语音能力封装（可插拔降级版）。"""

from __future__ import annotations

from app.core.config import get_settings


class VoiceService:
    """统一 ASR/TTS 接口，当前为 mock 实现。"""

    def __init__(self) -> None:
        """初始化语音提供方配置。"""
        settings = get_settings()
        self.asr_provider = settings.asr_provider
        self.tts_provider = settings.tts_provider

    def asr(self, audio_url: str) -> str:
        """将音频转为文本。"""
        if self.asr_provider == "funasr":
            return f"funasr-mock: {audio_url}"
        if self.asr_provider == "paddlespeech":
            return f"paddlespeech-mock: {audio_url}"
        return f"mock-asr: {audio_url}"

    def tts(self, text: str) -> str:
        """将文本转语音并返回音频 URL。"""
        if self.tts_provider == "paddlespeech":
            safe = text.replace(" ", "_")[:48]
            return f"https://paddlespeech-mock.local/{safe}.wav"
        safe = text.replace(" ", "_")[:48]
        return f"https://mock-tts.local/{safe}.mp3"
