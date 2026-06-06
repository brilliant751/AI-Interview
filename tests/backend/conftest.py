"""后端测试公共隔离配置。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


@pytest.fixture(autouse=True)
def default_mock_provider_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """为每个测试提供默认 mock provider，避免真实模型和外部 API。"""
    monkeypatch.setenv("AI_INTERVIEW_APP_ENV", "dev")
    monkeypatch.setenv("AI_INTERVIEW_LLM_PROVIDER", "mock")
    monkeypatch.setenv("AI_INTERVIEW_ASR_PROVIDER", "mock")
    monkeypatch.setenv("AI_INTERVIEW_TTS_PROVIDER", "mock")
    monkeypatch.setenv("AI_INTERVIEW_OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_INTERVIEW_PROVIDER_TRUST_ENV", "false")
    monkeypatch.setenv("AI_INTERVIEW_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("AI_INTERVIEW_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
