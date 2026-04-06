"""OpenAI Provider 封装。"""

from __future__ import annotations

from io import BytesIO

from app.core.config import get_settings


class OpenAIProviderClient:
    """统一封装 OpenAI SDK 的 ASR/TTS/LLM 调用。"""

    def __init__(self) -> None:
        """初始化 OpenAI 客户端。"""
        settings = get_settings()
        from openai import OpenAI

        kwargs: dict = {
            "api_key": settings.openai_api_key,
            "timeout": settings.provider_timeout_seconds,
            "max_retries": settings.provider_max_retries,
        }
        if settings.provider_base_url.strip():
            kwargs["base_url"] = settings.provider_base_url.strip()
        self.client = OpenAI(**kwargs)
        self.settings = settings

    def transcribe_audio(self, audio_url: str, audio_format: str = "mp3") -> str:
        """通过音频 URL 调用 ASR 获取文本。"""
        import httpx

        response = httpx.get(audio_url, timeout=self.settings.provider_timeout_seconds)
        response.raise_for_status()
        stream = BytesIO(response.content)
        stream.name = f"answer.{audio_format}"
        transcript = self.client.audio.transcriptions.create(
            model=self.settings.asr_model,
            file=stream,
            response_format="text",
        )
        return str(transcript).strip()

    def synthesize_speech(self, text: str) -> bytes:
        """调用 TTS 生成语音二进制数据。"""
        response = self.client.audio.speech.create(
            model=self.settings.tts_model,
            voice=self.settings.tts_voice,
            input=text,
            response_format="mp3",
        )
        return response.read()

    def generate_question(self, answer: str, references: list[dict]) -> str:
        """调用 LLM 生成下一题。"""
        ref_titles = "；".join(ref.get("title", "") for ref in references[:3] if ref.get("title"))
        ref_hint = ref_titles or "岗位基础能力"
        result = self.client.responses.create(
            model=self.settings.llm_model,
            input=(
                "你是面试官，请基于候选人回答生成一个追问问题。"
                f"候选人回答：{answer}\n"
                f"参考主题：{ref_hint}\n"
                "要求：只输出一句中文问题。"
            ),
            max_output_tokens=120,
        )
        question = (result.output_text or "").strip()
        if not question:
            raise ValueError("LLM 返回空问题")
        return question

    def health(self) -> str:
        """返回 provider 健康状态。"""
        if not self.settings.openai_api_key.strip():
            return "DOWN"
        return "UP"
