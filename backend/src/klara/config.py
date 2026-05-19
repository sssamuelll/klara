from functools import lru_cache
from typing import Literal

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
    # ElevenLabs voices are technically multilingual but each has a native
    # tongue; the voice that nails German with no accent may butcher Spanish.
    # `elevenlabs_voice_id` is the fallback; per-language overrides win when
    # set. Pick voices at https://elevenlabs.io/app/voice-library.
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    elevenlabs_voice_id_de: str = ""
    elevenlabs_voice_id_es: str = ""
    elevenlabs_voice_id_fr: str = ""
    elevenlabs_voice_id_ja: str = ""
    elevenlabs_voice_id_pt: str = ""
    elevenlabs_voice_id_en: str = ""
    elevenlabs_model: str = "eleven_turbo_v2_5"
    # Inworld TTS — alternative provider. Flip TTS_PROVIDER=inworld to use.
    # The API key from Inworld Portal is already base64-encoded; paste as-is.
    # Inworld voices are language-locked (unlike ElevenLabs), so the per-lang
    # mapping matters even more here.
    inworld_api_key: str | None = None
    inworld_voice_id: str = ""
    inworld_voice_id_de: str = ""
    inworld_voice_id_es: str = ""
    inworld_voice_id_fr: str = ""
    inworld_voice_id_ja: str = ""
    inworld_voice_id_pt: str = ""
    inworld_voice_id_en: str = ""
    inworld_model: str = "inworld-tts-1.5-mini"
    inworld_audio_encoding: str = "MP3"
    inworld_sample_rate_hz: int = 24000
    tts_request_timeout_seconds: float = 30.0
    tts_max_text_chars: int = 4000

    @property
    def elevenlabs_voices_by_lang(self) -> dict[str, str]:
        return {
            "de": self.elevenlabs_voice_id_de,
            "es": self.elevenlabs_voice_id_es,
            "fr": self.elevenlabs_voice_id_fr,
            "ja": self.elevenlabs_voice_id_ja,
            "pt": self.elevenlabs_voice_id_pt,
            "en": self.elevenlabs_voice_id_en,
        }

    @property
    def inworld_voices_by_lang(self) -> dict[str, str]:
        return {
            "de": self.inworld_voice_id_de,
            "es": self.inworld_voice_id_es,
            "fr": self.inworld_voice_id_fr,
            "ja": self.inworld_voice_id_ja,
            "pt": self.inworld_voice_id_pt,
            "en": self.inworld_voice_id_en,
        }

    default_user_display_name: str = "Samuel"
    default_user_level: str = "A0"
    default_user_native_language: str = "es"
    default_user_target_language: str = "de"
    default_user_learning_context: str | None = None

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    auth_jwt_secret: str = "dev-secret-do-not-use-in-prod-change-me-32b"
    auth_cookie_name: str = "klara_session"
    auth_cookie_max_age: int = 60 * 60 * 24 * 30  # 30 days
    initial_owner_email: str | None = None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    resend_api_key: str | None = None
    email_from: str = "Klara <noreply@klara.app>"
    # Where the SPA lives — used in verify / reset email links.
    frontend_base_url: str = "http://localhost:5273"
    # Where the FastAPI app lives — used as the OAuth redirect_uri so Google
    # can POST the code back to /api/v1/auth/google/callback. MUST match what's
    # registered in the Google Cloud Console OAuth client.
    backend_base_url: str = "http://localhost:8000"

    # Azure AI Speech — powers POST /api/v1/pronunciation/score. Without a key
    # the endpoint returns 503 so the frontend can fall back gracefully.
    azure_speech_key: str | None = None
    azure_speech_region: str = "eastus"
    # Hard cap on uploaded audio (bytes). 25 MB ≈ ~5 min of 16kHz PCM — way
    # more than a single sentence needs, but protects against accidental
    # uploads of huge files.
    pronunciation_max_audio_bytes: int = 25 * 1024 * 1024

    @property
    def azure_speech_configured(self) -> bool:
        return bool(self.azure_speech_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def initial_owner_email_normalized(self) -> str | None:
        return self.initial_owner_email.strip().lower() if self.initial_owner_email else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
