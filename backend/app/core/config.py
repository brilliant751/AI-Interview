"""应用配置模块。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    db_path: str = "assets/data/sqlite/interview.db"
    chroma_dir: str = "assets/data/chroma"
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
