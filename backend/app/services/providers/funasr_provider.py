"""FunASR 本地 Provider 封装。"""

from __future__ import annotations

import os
import tempfile
import time
import wave
import errno
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import ApiError


# FunASRProviderClient 是本地 ASR SDK 适配器：
# 1. 模型采用惰性加载，只有真正收到语音识别请求时才初始化。
# 2. 识别前会把输入音频写入临时文件，适配 SDK 常见的文件路径接口。
# 3. 候选模型按配置优先、默认模型兜底的顺序尝试，提升本地环境兼容性。
# 4. 所有 SDK 初始化或推理失败都转换成 ApiError，便于 VoiceService 统一处理。
class FunASRProviderClient:
    """封装本地 FunASR 的语音识别调用。"""

    def __init__(self) -> None:
        """初始化 SDK 配置。"""
        settings = get_settings()
        self.settings = settings
        self._model: Any = None

    def _load_model(self) -> Any:
        """加载 FunASR SDK 模型实例。"""
        # 部分 macOS + Python 3.9 环境缺失 EREMOTEIO，ModelScope 下载流程会直接抛错。
        if not hasattr(errno, "EREMOTEIO"):
            errno.EREMOTEIO = errno.EIO  # type: ignore[attr-defined]
        try:
            from funasr import AutoModel  # type: ignore
        except Exception as exc:
            raise ApiError(
                code="ASR_UPSTREAM_FAILED",
                message=f"FunASR SDK 初始化失败：{exc}",
                status_code=502,
            ) from exc
        model_candidates = [
            self.settings.asr_model,
            "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        ]
        tried: list[str] = []
        for model_name in model_candidates:
            if model_name in tried:
                continue
            tried.append(model_name)
            try:
                # 逐个尝试候选模型，避免某个配置模型缺失时直接让整个 ASR 不可用。
                return AutoModel(model=model_name, device=self.settings.asr_device)
            except Exception:
                continue
        raise ApiError(
            code="ASR_UPSTREAM_FAILED",
            message=f"FunASR 模型加载失败，候选模型均不可用：{', '.join(tried)}",
            status_code=502,
        )

    def _get_model(self) -> Any:
        """惰性初始化模型实例。"""
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _write_temp_audio_file(self, audio_bytes: bytes, filename: str) -> str:
        """将音频二进制写入临时文件供 SDK 读取。"""
        suffix = Path(filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            return tmp_file.name

    def _extract_text(self, raw_result: Any) -> str:
        """从 SDK 推理结果中提取文本。"""
        if isinstance(raw_result, str):
            return raw_result.strip()
        if isinstance(raw_result, dict):
            return str(raw_result.get("text") or raw_result.get("sentence") or "").strip()
        if isinstance(raw_result, list) and raw_result:
            first = raw_result[0]
            if isinstance(first, dict):
                return str(first.get("text") or first.get("sentence") or "").strip()
            return str(first).strip()
        return ""

    def _run_inference(self, audio_path: str) -> Any:
        """调用 SDK 执行语音识别。"""
        model = self._get_model()
        if hasattr(model, "generate"):
            return model.generate(input=audio_path)
        if callable(model):
            return model(audio_path)
        raise ApiError(code="ASR_UPSTREAM_FAILED", message="FunASR 模型不支持当前调用方式", status_code=502)

    def _build_health_wav(self) -> bytes:
        """构建最小静音 WAV 样本用于健康检查。"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            with wave.open(tmp_file.name, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(b"\x00\x00" * 160)
            with open(tmp_file.name, "rb") as f:
                data = f.read()
            os.unlink(tmp_file.name)
            return data

    def transcribe_audio_bytes(self, audio_bytes: bytes, filename: str) -> dict[str, Any]:
        """通过 SDK 识别音频二进制并返回文本。"""
        started_at = time.perf_counter()
        audio_path = ""
        try:
            audio_path = self._write_temp_audio_file(audio_bytes, filename)
            raw_result = self._run_inference(audio_path)
            text = self._extract_text(raw_result)
            if not text:
                raise ApiError(code="ASR_UPSTREAM_FAILED", message="本地语音识别返回为空", status_code=502)
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return {
                "text": text,
                "confidence": 0.0,
                "provider": "funasr",
                "latency_ms": latency_ms,
            }
        except TimeoutError as exc:
            raise ApiError(code="UPSTREAM_TIMEOUT", message="本地语音识别超时", status_code=504) from exc
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(code="ASR_UPSTREAM_FAILED", message="本地语音识别失败", status_code=502) from exc
        finally:
            if audio_path and os.path.exists(audio_path):
                os.unlink(audio_path)

    def health(self) -> dict[str, Any]:
        """返回 FunASR 健康状态。"""
        started_at = time.perf_counter()
        try:
            self._get_model()
            # 健康检查使用静音样本时，模型可能返回空文本；只要推理过程不抛异常即视为可用。
            health_audio_path = self._write_temp_audio_file(self._build_health_wav(), "health.wav")
            try:
                self._run_inference(health_audio_path)
            finally:
                if os.path.exists(health_audio_path):
                    os.unlink(health_audio_path)
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            return {
                "status": "UP",
                "provider": "funasr",
                "model": self.settings.asr_model,
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
                "provider": "funasr",
                "model": self.settings.asr_model,
                "latency_ms": latency_ms,
                "error_message": message,
            }
