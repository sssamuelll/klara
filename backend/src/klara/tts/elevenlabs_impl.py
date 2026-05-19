import httpx
import structlog

from klara.config import Settings
from klara.tts.base import TTSError, TTSResult

log = structlog.get_logger(__name__)


class ElevenLabsTTSError(TTSError):
    pass


class ElevenLabsTTS:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, settings: Settings) -> None:
        if not settings.elevenlabs_api_key:
            raise ElevenLabsTTSError("ELEVENLABS_API_KEY is not configured")
        self._api_key = settings.elevenlabs_api_key
        self._timeout = settings.tts_request_timeout_seconds
        self._model = settings.elevenlabs_model
        self._default_voice = settings.elevenlabs_voice_id
        # Only keep entries with a configured voice; an empty string would
        # masquerade as a real voice_id and 404 against the API.
        self._voices_by_lang = {k: v for k, v in settings.elevenlabs_voices_by_lang.items() if v}

    @property
    def name(self) -> str:
        return "elevenlabs"

    @property
    def model(self) -> str:
        return self._model

    @property
    def default_voice_id(self) -> str:
        return self._default_voice

    def voice_for_lang(self, lang: str | None) -> str:
        if lang:
            specific = self._voices_by_lang.get(lang.lower())
            if specific:
                return specific
        return self._default_voice

    async def synthesize(self, text: str, voice_id: str | None = None) -> TTSResult:
        text = text.strip()
        if not text:
            raise ElevenLabsTTSError("text is empty")
        voice = voice_id or self._default_voice
        url = f"{self.BASE_URL}/text-to-speech/{voice}"
        payload = {
            "text": text,
            "model_id": self._model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        log.debug("tts.elevenlabs.request", voice=voice, model=self._model, chars=len(text))
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            detail = resp.text[:500]
            raise ElevenLabsTTSError(f"ElevenLabs API {resp.status_code}: {detail}")

        return TTSResult(
            audio=resp.content,
            mime_type="audio/mpeg",
            provider=self.name,
            model=self._model,
            voice_id=voice,
            char_count=len(text),
        )
