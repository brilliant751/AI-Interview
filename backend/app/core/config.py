"""应用配置模块。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ASSETS_ROOT = BACKEND_ROOT / "assets"

# 配置读取的约定：
# 1. 所有环境变量统一使用 AI_INTERVIEW_ 前缀，避免与系统变量或其他项目冲突。
# 2. 默认值尽量指向本地可运行的 mock/SQLite 环境，方便新人拉仓库后直接启动。
# 3. provider 相关配置集中在这里，服务层只读取 settings，不直接碰 os.environ。
# 4. 路径默认放在 backend/assets 下，使测试和本地开发都能复用同一套目录结构。
# 5. 兼容性字段保留默认值，避免历史 .env 在升级时导致应用无法启动。


class Settings(BaseSettings):
    """应用配置对象，统一管理环境变量读取。"""

    model_config = SettingsConfigDict(
        env_prefix="AI_INTERVIEW_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "dev"
    app_name: str = "AI Interview API"
    db_path: str = str(ASSETS_ROOT / "data" / "sqlite" / "interview.db")
    chroma_dir: str = str(ASSETS_ROOT / "data" / "chroma")
    cors_allow_origin_regex: str = r"http://localhost:5173"
    llm_provider: str = "mock"
    asr_provider: str = "mock"
    tts_provider: str = "mock"
    token_secret: str = "dev-token-secret"
    user_token: str = "user-token"
    admin_token: str = "admin-token"
    jwt_secret: str = "dev-jwt-secret"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 7
    reset_token_ttl_minutes: int = 30
    auth_enable_dev_static_token: bool = False
    auth_login_limit_window_seconds: int = 300
    auth_login_limit_threshold: int = 10
    ollama_base_url: str = "http://127.0.0.1:11434"
    chunk_model: str = "qwen2.5:7b"
    embedding_model: str = "nomic-embed-text"
    embed_batch_size: int = 32
    retrieval_fallback_enabled: bool = False
    kb_collection_alias_file: str = str(ASSETS_ROOT / "data" / "chroma" / "aliases.json")
    cors_allow_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    frontend_base_url: str = "http://localhost:5173"

    openai_api_key: str = ""
    asr_model: str = "paraformer-zh"
    asr_device: str = "cpu"
    tts_model: str = "fastspeech2_csmsc"
    tts_device: str = "cpu"
    tts_sample_rate: int = 24000
    tts_voice: str = "alloy"
    llm_model: str = "deepseek-r1:8b"
    embed_model: str = "nomic-embed-text"
    split_model: str = "qwen3.5-2b"
    provider_timeout_seconds: float = 20.0
    provider_max_retries: int = 2
    provider_base_url: str = ""
    provider_trust_env: bool = True
    ollama_base_url: str = "http://localhost:11434"
    # 兼容期配置：SDK 模式默认不依赖 URL，可用于灰度或历史配置兼容。
    funasr_base_url: str = "http://localhost:10095"
    # 兼容期配置：SDK 模式默认不依赖 URL，可用于灰度或历史配置兼容。
    paddlespeech_base_url: str = "http://localhost:8888"

    @model_validator(mode="after")
    def validate_openai_key_for_dev(self) -> Settings:
        """在 dev 环境使用 openai provider 时校验密钥是否存在。"""
        # dev 环境下如果显式启用 openai provider，就提前校验密钥。
        # 这样可以把“启动配置错误”暴露在应用启动阶段，而不是等到用户面试中途才失败。
        # mock/ollama 等本地模式不需要密钥，因此不进入这个强校验分支。
        need_key = any(
            provider == "openai"
            for provider in [self.llm_provider, self.asr_provider, self.tts_provider]
        )
        if self.app_env == "dev" and need_key and not self.openai_api_key.strip():
            raise ValueError(
                "dev 环境使用 openai provider 时必须配置 AI_INTERVIEW_OPENAI_API_KEY（支持兼容 OpenAI API 的第三方密钥）"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局单例配置对象。"""
    return Settings()
