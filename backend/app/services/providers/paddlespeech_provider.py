"""PaddleSpeech 本地 Provider 封装。"""

from __future__ import annotations

import os
import tempfile
import time
from typing import Any

from app.core.config import get_settings
from app.core.errors import ApiError


class PaddleSpeechProviderClient:
    """封装本地 PaddleSpeech 的语音合成调用。"""

    def __init__(self) -> None:
        """初始化 SDK 配置。"""
        settings = get_settings()
        self.settings = settings
        self._engine: Any = None

    def _load_engine(self) -> Any:
        """加载 PaddleSpeech SDK 引擎。"""
        self._patch_aistudio_sdk_download()
        try:
            from paddlespeech.cli.tts.infer import TTSExecutor  # type: ignore
        except Exception as exc:
            raise ApiError(
                code="TTS_UPSTREAM_FAILED",
                message=f"PaddleSpeech SDK 初始化失败：{exc}",
                status_code=502,
            ) from exc
        return TTSExecutor()

    def _patch_aistudio_sdk_download(self) -> None:
        """兼容 aistudio_sdk 新版本缺失 download 符号的问题。"""
        try:
            import aistudio_sdk.hub as aistudio_hub  # type: ignore
        except Exception:
            return
        if hasattr(aistudio_hub, "download"):
            return
        try:
            from aistudio_sdk import file_download as aistudio_file_download  # type: ignore
        except Exception:
            return

        def _download(*args: Any, **kwargs: Any) -> Any:
            """兼容导出 download 接口，转发到 file_download。"""
            return aistudio_file_download(*args, **kwargs)

        setattr(aistudio_hub, "download", _download)

    def _get_engine(self) -> Any:
        """惰性初始化 TTS 引擎。"""
        if self._engine is None:
            self._engine = self._load_engine()
        return self._engine

    def _synthesize_to_file(self, text: str, output_path: str) -> None:
        """调用 SDK 合成音频到文件。"""
        engine = self._get_engine()
        try:
            engine(
                text=text,
                output=output_path,
                am=self.settings.tts_model,
                lang="zh",
                spk_id=0,
                use_onnx=True,
            )
            return
        except TypeError:
            engine(text=text, output=output_path)

    def synthesize(self, text: str) -> bytes:
        """通过 SDK 合成语音并返回音频二进制。"""
        output_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                output_path = tmp_file.name
            self._synthesize_to_file(text, output_path)
            with open(output_path, "rb") as f:
                return f.read()
        except TimeoutError as exc:
            raise ApiError(code="UPSTREAM_TIMEOUT", message="本地语音合成超时", status_code=504) from exc
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(code="TTS_UPSTREAM_FAILED", message="本地语音合成失败", status_code=502) from exc
        finally:
            if output_path and os.path.exists(output_path):
                os.unlink(output_path)

    def health(self) -> dict[str, Any]:
        """返回 PaddleSpeech 健康状态。"""
        started_at = time.perf_counter()
        try:
            self._get_engine()
            self.synthesize("健康检查")
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return {
                "status": "UP",
                "provider": "paddlespeech",
                "model": self.settings.tts_model,
                "latency_ms": latency_ms,
                "error_message": "",
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            message = str(exc)
            if isinstance(exc, ApiError):
                message = exc.message or exc.code
            return {
                "status": "DOWN",
                "provider": "paddlespeech",
                "model": self.settings.tts_model,
                "latency_ms": latency_ms,
                "error_message": message,
            }
