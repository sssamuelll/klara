import httpx
import structlog

from klara.config import Settings
from klara.tts.base import TTSError, TTSResult

log = structlog.get_logger(__name__)


class ElevenLabsTTSError(TTSError):
    pass


# Realtime keeps ElevenLabs' defaults. Narration lowers stability and raises
# style — both documented liveliness knobs; style 0.0 is the flattest possible
# delivery and is why cached story audio sounded monotone. Values are the
# documented starting point for expressive narration; retune by ear, not here.
_REALTIME_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
}
_NARRATION_VOICE_SETTINGS = {
    "stability": 0.4,
    "similarity_boost": 0.75,
    "style": 0.3,
    "use_speaker_boost": True,
}


class ElevenLabsTTS:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, settings: Settings) -> None:
        if not settings.elevenlabs_api_key:
            raise ElevenLabsTTSError("ELEVENLABS_API_KEY is not configured")
        self._api_key = settings.elevenlabs_api_key
        self._timeout = settings.tts_request_timeout_seconds
        self._model = settings.elevenlabs_model
        self._narration_model = settings.elevenlabs_narration_model
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
    def narration_model(self) -> str:
        return self._narration_model

    @property
    def default_voice_id(self) -> str:
        return self._default_voice

    def voice_for_lang(self, lang: str | None) -> str:
        if lang:
            specific = self._voices_by_lang.get(lang.lower())
            if specific:
                return specific
        return self._default_voice

    def _build_payload(
        self,
        text: str,
        *,
        narration: bool,
        previous_text: str | None,
        next_text: str | None,
    ) -> dict:
        payload = {
            "text": text,
            "model_id": self._narration_model if narration else self._model,
            "voice_settings": dict(
                _NARRATION_VOICE_SETTINGS if narration else _REALTIME_VOICE_SETTINGS
            ),
        }
        if previous_text:
            payload["previous_text"] = previous_text
        if next_text:
            payload["next_text"] = next_text
        return payload

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        *,
        narration: bool = False,
        previous_text: str | None = None,
        next_text: str | None = None,
    ) -> TTSResult:
        text = text.strip()
        if not text:
            raise ElevenLabsTTSError("text is empty")
        voice = voice_id or self._default_voice
        url = f"{self.BASE_URL}/text-to-speech/{voice}"
        payload = self._build_payload(
            text, narration=narration, previous_text=previous_text, next_text=next_text
        )
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        log.debug("tts.elevenlabs.request", voice=voice, model=payload["model_id"], chars=len(text))
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            detail = resp.text[:500]
            raise ElevenLabsTTSError(f"ElevenLabs API {resp.status_code}: {detail}")

        return TTSResult(
            audio=resp.content,
            mime_type="audio/mpeg",
            provider=self.name,
            model=payload["model_id"],
            voice_id=voice,
            char_count=len(text),
        )
