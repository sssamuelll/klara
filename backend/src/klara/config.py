from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "staging", "production"] = "development"
    app_log_level: str = "INFO"

    # DB credentials are split so the password never rides inside the DSN
    # string (issue #81). A cleartext credential in a connection string leaks
    # via repr(engine), tracebacks that interpolate the URL, or any direct log
    # of settings.database_url; keeping it out of the DSN closes that vector
    # (engine.url.password is then None). The password is a SecretStr injected
    # out-of-band — see `db_connect_args`. A full DSN with an embedded password
    # still works (the in-URL credential is respected, never overridden).
    # The default is EMPTY: a passwordless DSN with no DB_PASSWORD fails closed
    # rather than falling back to a baked-in dev credential. Supply it via
    # .env / docker-compose (DB_PASSWORD=${POSTGRES_PASSWORD}).
    database_url: str = "postgresql+asyncpg://german@localhost:5432/german_app"
    db_password: SecretStr = SecretStr("")
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True

    llm_provider: str = "anthropic"
    llm_story_model: str = "anthropic/claude-haiku-4-5-20251001"
    llm_chat_model: str = "anthropic/claude-sonnet-4-6"
    llm_correction_model: str = "anthropic/claude-haiku-4-5-20251001"
    llm_request_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    # Provider-specific request-body extras for the CHAT model (JSON in env).
    # Speak's latency budget depends on it: with DeepSeek V4 set
    #   LLM_CHAT_EXTRA_BODY={"thinking": {"type": "disabled"}}
    # so a provider-side default flip can never put chain-of-thought on the
    # conversational critical path.
    llm_chat_extra_body: dict | None = None
    # Same mechanism for the STORY model (JSON in env). DeepSeek V4 defaults to
    # *thinking* mode, which spends the token budget on reasoning and truncates
    # the JSON story mid-object (finish_reason=length → malformed JSON). Set
    #   LLM_STORY_EXTRA_BODY={"thinking": {"type": "disabled"}}
    # so structured story generation returns clean, complete JSON.
    llm_story_extra_body: dict | None = None

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
    # Two ElevenLabs models: `elevenlabs_model` serves latency-sensitive audio
    # (Speak replies), `elevenlabs_narration_model` serves pre-cached story
    # narration where latency is irrelevant and expressiveness wins. Turbo is
    # deprecated by ElevenLabs; Flash is its official drop-in replacement.
    elevenlabs_model: str = "eleven_flash_v2_5"
    elevenlabs_narration_model: str = "eleven_multilingual_v2"
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

    @field_validator("llm_chat_extra_body", "llm_story_extra_body", mode="before")
    @classmethod
    def _blank_extra_body_is_none(cls, v: object) -> object:
        # docker-compose delivers these as ${LLM_*_EXTRA_BODY:-}, i.e. an
        # EMPTY string whenever unset (local dev, anthropic path). An empty
        # string is not valid JSON and would crash Settings(); treat blank as
        # "unset". A real value is JSON-decoded to a dict upstream.
        if isinstance(v, str) and not v.strip():
            return None
        return v

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

    # --- #22 live pronunciation streaming (WS /pronunciation/stream) ---
    # Sole drain-health signal: a ws.send slower than this means the client
    # can't keep up -> tear down -> client falls back to batch.
    pron_stream_send_timeout_s: float = 5.0
    # Offloaded stop_continuous_recognition() is uncancellable; cap the wait,
    # then release the cap slot regardless so a wedged Azure stop can't leak it.
    pron_stream_stop_timeout_s: float = 3.0
    # Memory bound on the never-dropped accumulator (unscripted has no word
    # ceiling) and the backstop if the client never sends end-of-speech.
    pron_stream_max_session_s: float = 90.0
    # Global cap bounds native SDK threads; per-user cap stops one user
    # monopolising all slots and pushing everyone else to batch.
    pron_stream_global_cap: int = 8
    pron_stream_per_user_cap: int = 2

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
    def db_connect_args(self) -> dict[str, str]:
        # Inject the password out-of-band ONLY when the DSN doesn't already
        # carry a usable one. A full DSN (e.g. a CI job that sets
        # DATABASE_URL=user:pass@host) keeps its own credential — we never
        # override it, so the migration-roundtrip path keeps working unchanged.
        # An empty in-URL password (a stray trailing colon) counts as "no
        # usable password", so the configured DB_PASSWORD wins.
        pw = self.db_password.get_secret_value()
        if not make_url(self.database_url).password and pw:
            return {"password": pw}
        return {}

    @property
    def initial_owner_email_normalized(self) -> str | None:
        return self.initial_owner_email.strip().lower() if self.initial_owner_email else None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
