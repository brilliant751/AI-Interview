"""语音能力封装（可插拔降级版）。"""

from __future__ import annotations

import base64
import logging
from typing import Any, Optional

import httpx

from app.core.errors import ApiError
from app.services.providers import (
    FunASRProviderClient,
    OpenAIProviderClient,
    PaddleSpeechProviderClient,
)

logger = logging.getLogger(__name__)


class VoiceService:
    """统一 ASR/TTS 接口，支持 openai 与 mock 双模式。"""

    def __init__(self) -> None:
        """初始化语音提供方配置。"""
        from app.core.config import get_settings

        settings = get_settings()
        self.settings = settings
        self.asr_provider = settings.asr_provider
        self.tts_provider = settings.tts_provider
        self._openai_client: Optional[OpenAIProviderClient] = None
        self._funasr_client: Optional[FunASRProviderClient] = None
        self._paddlespeech_client: Optional[PaddleSpeechProviderClient] = None

    def _get_openai_client(self) -> OpenAIProviderClient:
        """惰性初始化 OpenAI provider 客户端。"""
        if self._openai_client is None:
            self._openai_client = OpenAIProviderClient()
        return self._openai_client

    def _get_funasr_client(self) -> FunASRProviderClient:
        """惰性初始化 FunASR provider 客户端。"""
        if self._funasr_client is None:
            self._funasr_client = FunASRProviderClient()
        return self._funasr_client

    def _get_paddlespeech_client(self) -> PaddleSpeechProviderClient:
        """惰性初始化 PaddleSpeech provider 客户端。"""
        if self._paddlespeech_client is None:
            self._paddlespeech_client = PaddleSpeechProviderClient()
        return self._paddlespeech_client

    def _download_audio(self, audio_url: str) -> bytes:
        """下载远端音频为二进制。"""
        response = httpx.get(audio_url, timeout=self.settings.provider_timeout_seconds)
        response.raise_for_status()
        return response.content

    def asr(
        self,
        audio_url: str = "",
        audio_format: str = "mp3",
        audio_bytes: Optional[bytes] = None,
        audio_filename: str = "answer.wav",
    ) -> str:
        """将音频转为文本。"""
        resolved_bytes = audio_bytes
        if resolved_bytes is None and audio_url.strip():
            try:
                resolved_bytes = self._download_audio(audio_url.strip())
            except Exception as exc:
                raise ApiError(code="ASR_UPSTREAM_FAILED", message="音频下载失败", status_code=502) from exc

        if self.asr_provider == "openai":
            try:
                if resolved_bytes:
                    recognized_text = self._get_openai_client().transcribe_audio_bytes(
                        audio_bytes=resolved_bytes,
                        audio_format=audio_format,
                    )
                    logger.info("ASR转写结果(VoiceService/OpenAI): %s", recognized_text)
                    print(f"[ASR] VoiceService/OpenAI 转写结果: {recognized_text}", flush=True)
                    return recognized_text
                if not audio_url.strip():
                    raise ApiError(code="VALIDATE_400", message="缺少音频内容，无法识别", status_code=400)
                recognized_text = self._get_openai_client().transcribe_audio(audio_url=audio_url, audio_format=audio_format)
                logger.info("ASR转写结果(VoiceService/OpenAI): %s", recognized_text)
                print(f"[ASR] VoiceService/OpenAI 转写结果: {recognized_text}", flush=True)
                return recognized_text
            except Exception as exc:
                if isinstance(exc, httpx.TimeoutException):
                    raise ApiError(code="UPSTREAM_TIMEOUT", message="上游语音识别超时", status_code=504) from exc
                if isinstance(exc, ApiError):
                    raise exc
                raise ApiError(code="ASR_UPSTREAM_FAILED", message="上游语音识别失败", status_code=502) from exc
        if self.asr_provider == "funasr":
            if not resolved_bytes:
                raise ApiError(code="VALIDATE_400", message="缺少音频内容，无法识别", status_code=400)
            result = self._get_funasr_client().transcribe_audio_bytes(
                audio_bytes=resolved_bytes,
                filename=audio_filename,
            )
            recognized_text = str(result["text"])
            logger.info("ASR转写结果(VoiceService/FunASR): %s", recognized_text)
            print(f"[ASR] VoiceService/FunASR 转写结果: {recognized_text}", flush=True)
            return recognized_text
        if self.asr_provider == "paddlespeech":
            recognized_text = f"paddlespeech-mock: {audio_url}"
            logger.info("ASR转写结果(VoiceService/PaddleSpeech): %s", recognized_text)
            print(f"[ASR] VoiceService/PaddleSpeech 转写结果: {recognized_text}", flush=True)
            return recognized_text
        recognized_text = f"mock-asr: {audio_url or audio_filename}"
        logger.info("ASR转写结果(VoiceService/Mock): %s", recognized_text)
        print(f"[ASR] VoiceService/Mock 转写结果: {recognized_text}", flush=True)
        return recognized_text

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
            audio_bytes = self._get_paddlespeech_client().synthesize(text)
            encoded = base64.b64encode(audio_bytes).decode("utf-8")
            return f"data:audio/wav;base64,{encoded}"
        return f"https://mock-tts.local/{safe}.mp3"

    def health(self) -> dict[str, str]:
        """返回语音 provider 健康状态。"""
        details = self.health_details()
        asr_health = details["asr"]["status"]
        tts_health = details["tts"]["status"]
        return {
            "asr": asr_health,
            "tts": tts_health,
        }

    def health_details(self) -> dict[str, dict[str, Any]]:
        """返回语音 provider 详细健康信息。"""
        asr_detail: dict[str, Any]
        tts_detail: dict[str, Any]

        if self.asr_provider == "funasr":
            asr_detail = self._get_funasr_client().health()
        elif self.asr_provider == "openai":
            asr_status = self._get_openai_client().health()
            asr_detail = {
                "status": asr_status,
                "provider": "openai",
                "model": self.settings.asr_model,
                "latency_ms": 0,
                "error_message": "" if asr_status == "UP" else "缺少 OpenAI 密钥",
            }
        else:
            asr_detail = {
                "status": "UP",
                "provider": self.asr_provider,
                "model": self.settings.asr_model,
                "latency_ms": 0,
                "error_message": "",
            }

        if self.tts_provider == "paddlespeech":
            tts_detail = self._get_paddlespeech_client().health()
        elif self.tts_provider == "openai":
            tts_status = self._get_openai_client().health()
            tts_detail = {
                "status": tts_status,
                "provider": "openai",
                "model": self.settings.tts_model,
                "latency_ms": 0,
                "error_message": "" if tts_status == "UP" else "缺少 OpenAI 密钥",
            }
        else:
            tts_detail = {
                "status": "UP",
                "provider": self.tts_provider,
                "model": self.settings.tts_model,
                "latency_ms": 0,
                "error_message": "",
            }

        return {"asr": asr_detail, "tts": tts_detail}
