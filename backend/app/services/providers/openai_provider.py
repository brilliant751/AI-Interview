"""OpenAI Provider 封装。"""

from __future__ import annotations

import logging
from io import BytesIO

from app.core.config import get_settings

logger = logging.getLogger(__name__)
resume_context_logger = logging.getLogger("app.resume_context")


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

    def generate_question(
        self,
        answer: str,
        references: list[dict],
        stage: str,
        difficulty: str,
        history_messages: list[dict[str, str]],
        job_role: str,
        jd_content: str,
        resume_content: str,
        trace_id: str,
        interview_id: str,
    ) -> str:
        """调用 LLM 生成下一题。"""
        ref_context = self._build_reference_context(references=references)
        role_or_jd = (jd_content or "").strip() or f"岗位方向：{job_role or '未提供'}"
        difficulty_hint_map = {
            "easy": "基础难度：优先核验基础概念与真实参与度，避免一次追问过深。",
            "medium": "标准难度：平衡实现细节、取舍理由与结果验证。",
            "hard": "高难度：重点追问边界条件、故障排查、性能优化与反例分析。",
        }
        difficulty_hint = difficulty_hint_map.get(difficulty, difficulty_hint_map["medium"])
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "你是一位资深中文技术面试官。"
                    "你的回答就是面试官现场说出的下一句提问。"
                    "请像真人面试官一样自然说话，口语化、简洁、直接。"
                    "优先围绕技术决策、实现细节、权衡取舍、排障过程、结果度量。"
                    "不要复述题干，不要泛泛而谈，不要一次问多个问题，不要写成说明文。"
                    "禁止输出“追问意图”、括号解释、分点、Markdown 标题或加粗。"
                    "只返回一句可直接说出口的中文问句。"
                ),
            }
        ]
        if stage == "PROJECT_DEEP_DIVE" and (resume_content or "").strip():
            sent_resume_content = resume_content[:2400]
            logger.info(
                "发送给大模型的简历内容（项目经历轮）：总长度=%s，发送长度=%s，内容预览=%s",
                len(resume_content),
                len(sent_resume_content),
                sent_resume_content[:400].replace("\n", " "),
            )
            resume_context_logger.info(
                "发送给大模型的简历内容（项目经历轮）：trace_id=%s interview_id=%s 总长度=%s 发送长度=%s 内容预览=%s",
                trace_id,
                interview_id,
                len(resume_content),
                len(sent_resume_content),
                sent_resume_content[:400].replace("\n", " "),
            )
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "【简历内容（仅项目经历轮使用）】\n"
                        f"{sent_resume_content}\n"
                        "请围绕候选人简历中的项目经历进行追问。"
                    ),
                }
            )
        messages.append(
            {
                "role": "system",
                "content": (
                    f"岗位方向或岗位描述：{role_or_jd}\n"
                    f"当前阶段：{stage}\n"
                    f"面试难度：{difficulty}（{difficulty_hint}）\n"
                    f"参考资料（含JD与简历）：\n{ref_context}"
                ),
            }
        )
        for message in history_messages:
            role = str(message.get("role") or "").strip().lower()
            content = str(message.get("content") or "").strip()
            if role in {"assistant", "user"} and content:
                messages.append({"role": role, "content": content})
        if not history_messages:
            messages.append({"role": "user", "content": answer})
        result = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages,
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

    def generate_report_json(
        self,
        prompt_messages: list[dict[str, str]],
        schema: dict,
        max_tokens: int = 2200,
    ) -> dict:
        """调用 LLM 按 JSON Schema 生成结构化面试报告。"""
        result = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=prompt_messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "interview_report_schema",
                    "strict": True,
                    "schema": schema,
                },
            },
            extra_body={"thinking": {"type": "disabled"}},
            max_tokens=max_tokens,
        )
        message = result.choices[0].message
        content = (message.content or "").strip()
        if not content:
            raise ValueError("LLM 未返回结构化报告内容")
        import json

        return json.loads(content)

    def health(self) -> str:
        """返回 provider 健康状态。"""
        if not self.settings.openai_api_key.strip():
            return "DOWN"
        return "UP"
