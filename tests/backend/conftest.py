"""后端测试公共隔离配置。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

# 后端测试公共夹具说明：
# 1. 每个测试默认使用临时 SQLite 数据库，避免污染真实开发数据。
# 2. LLM/ASR/TTS provider 默认固定为 mock，测试不依赖外部模型服务。
# 3. Chroma 目录也指向 tmp_path，保证向量检索相关测试彼此隔离。
# 4. dev static token 默认打开，旧接口测试可以直接使用 user-token/admin-token。
# 5. 每个测试前后清理 get_settings 缓存，确保环境变量变更立即生效。
# 6. 这里的 autouse fixture 是测试稳定性的基础，不需要各用例重复声明。


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
