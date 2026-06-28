"""Ollama 本地 Provider 封装。"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import ApiError


# OllamaProviderClient 封装本地模型服务：
# 1. /api/chat 用于生成面试追问和报告辅助内容。
# 2. /api/embeddings 用于知识库检索或健康检查中的向量生成。
# 3. 本地服务不可用时统一转换为 ApiError，让上层按 provider 降级策略处理。
# 4. trust_env=False 避免本地代理影响 127.0.0.1/localhost 的访问。
class OllamaProviderClient:
    """封装本地 Ollama 的 LLM 与 Embedding 调用。"""

    def __init__(self) -> None:
        """初始化 HTTP 客户端与模型配置。"""
        settings = get_settings()
        self.settings = settings
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.client = httpx.Client(timeout=settings.provider_timeout_seconds, trust_env=False)

    def generate_question(self, prompt: str) -> str:
        """调用本地聊天模型生成下一题。"""
        started_at = time.perf_counter()
        try:
            # Ollama chat 接口返回 message.content。
            # 如果返回空字符串，按上游失败处理，避免空问题写入面试轮次。
            response = self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.settings.llm_model,
                    "stream": False,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = str(((payload.get("message") or {}).get("content") or "")).strip()
            if not content:
                raise ApiError(code="LLM_UPSTREAM_FAILED", message="本地大模型返回为空", status_code=502)
            return content
        except httpx.TimeoutException as exc:
            raise ApiError(code="UPSTREAM_TIMEOUT", message="本地大模型调用超时", status_code=504) from exc
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(code="LLM_UPSTREAM_FAILED", message="本地大模型调用失败", status_code=502) from exc
        finally:
            _ = started_at

    def embed_text(self, text: str) -> list[float]:
        """调用本地 embedding 模型生成向量。"""
        try:
            response = self.client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.settings.embed_model,
                    "prompt": text,
                },
            )
            response.raise_for_status()
            payload = response.json()
            vector = payload.get("embedding") or []
            return [float(v) for v in vector]
        except Exception as exc:
            raise ApiError(code="EMBED_UPSTREAM_FAILED", message="本地向量服务调用失败", status_code=502) from exc

    def health(self) -> dict[str, Any]:
        """返回 Ollama 可用性与模型信息。"""
        started_at = time.perf_counter()
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return {
                "status": "UP",
                "provider": "ollama",
                "model": self.settings.llm_model,
                "latency_ms": latency_ms,
                "error_message": "",
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return {
                "status": "DOWN",
                "provider": "ollama",
                "model": self.settings.llm_model,
                "latency_ms": latency_ms,
                "error_message": str(exc),
            }
