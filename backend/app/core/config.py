"""应用配置模块。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ASSETS_ROOT = BACKEND_ROOT / "assets"


class Settings(BaseSettings):
    """应用配置对象，统一管理环境变量读取。"""

    model_config = SettingsConfigDict(
        env_prefix="AI_INTERVIEW_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_env: str = "dev"
    app_name: str = "AI Interview API"
    db_path: str = str(ASSETS_ROOT / "data" / "sqlite" / "interview.db")
    chroma_dir: str = str(ASSETS_ROOT / "data" / "chroma")
    llm_provider: str = "mock"
    asr_provider: str = "mock"
    tts_provider: str = "mock"
    token_secret: str = "dev-token-secret"
    user_token: str = "user-token"
    admin_token: str = "admin-token"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局单例配置对象。"""
    return Settings()
