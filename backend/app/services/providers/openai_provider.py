"""OpenAI Provider 封装。"""

from __future__ import annotations

from io import BytesIO

from app.core.config import get_settings


class OpenAIProviderClient:
    """统一封装 OpenAI SDK 的 ASR/TTS/LLM 调用。"""

    def __init__(self) -> None:
        """初始化 OpenAI 客户端。"""
        import httpx
        settings = get_settings()
        from openai import OpenAI

        kwargs: dict = {
            "api_key": settings.openai_api_key,
            "timeout": settings.provider_timeout_seconds,
            "max_retries": settings.provider_max_retries,
            # 显式关闭系统代理继承，避免本地 SOCKS 代理导致 SDK 初始化失败。
            "http_client": httpx.Client(
                timeout=settings.provider_timeout_seconds,
                trust_env=settings.provider_trust_env,
            ),
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
        return self.transcribe_audio_bytes(response.content, audio_format=audio_format)

    def transcribe_audio_bytes(self, audio_bytes: bytes, audio_format: str = "wav") -> str:
        """通过音频二进制调用 ASR 获取文本。"""
        stream = BytesIO(audio_bytes)
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

    def _build_reference_context(self, references: list[dict], limit: int = 3) -> str:
        """构建用于提问的参考上下文（JD/简历/知识片段）。"""
        if not references:
            return "无"

        def _priority(reference: dict) -> int:
            source = str(reference.get("source_path") or "").lower()
            retrieval_mode = str(reference.get("retrieval_mode") or "").lower()
            if source == "jd" or retrieval_mode == "jd":
                return 0
            if source == "resume" or retrieval_mode == "resume":
                return 1
            return 2

        chunks: list[str] = []
        for ref in sorted(references, key=_priority)[:limit]:
            title = str(ref.get("title") or "参考片段").strip() or "参考片段"
            content = str(ref.get("content") or "").strip().replace("\n", " ")
            if content:
                chunks.append(f"- {title}：{content[:180]}")
            else:
                chunks.append(f"- {title}")
        return "\n".join(chunks) if chunks else "无"

    def generate_question(self, answer: str, references: list[dict]) -> str:
        """调用 LLM 生成下一题。"""
        ref_titles = "；".join(ref.get("title", "") for ref in references[:3] if ref.get("title"))
        ref_hint = ref_titles or "岗位基础能力"
        ref_context = self._build_reference_context(references=references)
        result = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一位资深中文技术面试官。"
                        "你的目标是基于候选人刚才的回答，提出一个具体、可追问、可验证的下一问。"
                        "优先围绕技术决策、实现细节、权衡取舍、排障过程、结果度量。"
                        "不要复述题干，不要泛泛而谈，不要同时问多个问题。"
                        "如候选人回答过短（如“不会”“不清楚”“no”），应先做澄清式追问。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "请生成下一轮技术追问。"
                        f"候选人回答：{answer}\n"
                        f"参考主题：{ref_hint}\n"
                        f"参考资料（含JD与简历）：\n{ref_context}\n"
                        "输出要求："
                        "1) 只输出一句中文问句；"
                        "2) 20-50字；"
                        "3) 必须与候选人回答或参考主题直接相关；"
                        "4) 优先验证候选人经历是否匹配JD要求；"
                        "5) 不要输出解释、前缀或编号。"
                    ),
                },
            ],
            # 通过 extra_body 透传 GLM 扩展字段，关闭思考模式，避免仅返回 reasoning_content。
            extra_body={"thinking": {"type": "disabled"}},
            max_tokens=256,
        )
        message = result.choices[0].message
        question = (message.content or "").strip()
        if not question:
            reasoning = str(getattr(message, "reasoning_content", "") or "").strip()
            if reasoning:
                # 兜底：若上游只返回 reasoning_content，则截取最后一行可读文本作为问题候选。
                question = reasoning.splitlines()[-1].strip()
        if not question:
            raise ValueError("LLM 返回空问题")
        return question

    def health(self) -> str:
        """返回 provider 健康状态。"""
        if not self.settings.openai_api_key.strip():
            return "DOWN"
        return "UP"
