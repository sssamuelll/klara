from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "staging", "production"] = "development"
    app_log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://german:german_dev_pw@localhost:5432/german_app"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True

    llm_provider: str = "anthropic"
    llm_story_model: str = "anthropic/claude-haiku-4-5-20251001"
    llm_chat_model: str = "anthropic/claude-sonnet-4-6"
    llm_correction_model: str = "anthropic/claude-haiku-4-5-20251001"
    llm_request_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

    anthropic_api_key: str | None = None
    deepseek_api_key: str | None = None
    openai_api_key: str | None = None

    tts_provider: str = "elevenlabs"
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    elevenlabs_model: str = "eleven_turbo_v2_5"
    tts_request_timeout_seconds: float = 30.0
    tts_max_text_chars: int = 4000

    default_user_display_name: str = "Samuel"
    default_user_level: str = "A0"
    default_user_native_language: str = "es"
    default_user_target_language: str = "de"
    default_user_learning_context: str | None = None

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
