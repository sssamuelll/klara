"""Inworld AI TTS provider.

POST https://api.inworld.ai/tts/v1/voice with `Authorization: Basic <key>`,
JSON body {text, voiceId, modelId, audioConfig}. Response is JSON wrapping
base64-encoded audio in `audioContent` — we decode and ship the raw bytes,
matching the ElevenLabs path so the cache + router stay provider-agnostic.

The API key from Inworld Portal is already base64-encoded — do NOT re-encode
when building the `Authorization: Basic` header (re-encoding yields 401).
"""

import base64

import httpx
import structlog

from klara.config import Settings
from klara.tts.base import TTSError, TTSResult

log = structlog.get_logger(__name__)


class InworldTTSError(TTSError):
    pass


_AUDIO_ENCODING_TO_MIME = {
    "MP3": "audio/mpeg",
    "LINEAR16": "audio/wav",
    "WAV": "audio/wav",
    "OGG_OPUS": "audio/ogg",
    "FLAC": "audio/flac",
}


class InworldTTS:
    URL = "https://api.inworld.ai/tts/v1/voice"

    def __init__(self, settings: Settings) -> None:
        if not settings.inworld_api_key:
            raise InworldTTSError("INWORLD_API_KEY is not configured")
        self._api_key = settings.inworld_api_key
        self._timeout = settings.tts_request_timeout_seconds
        self._model = settings.inworld_model
        self._default_voice = settings.inworld_voice_id
        self._voices_by_lang = {k: v for k, v in settings.inworld_voices_by_lang.items() if v}
        # Inworld voices are language-locked, so requiring at least *some*
        # voice up-front catches "I forgot to configure anything" failures
        # at startup instead of at the first synthesize call.
        if not self._default_voice and not self._voices_by_lang:
            raise InworldTTSError(
                "No Inworld voice configured. Set INWORLD_VOICE_ID or at least "
                "one INWORLD_VOICE_ID_<lang>."
            )
        self._audio_encoding = settings.inworld_audio_encoding
        self._sample_rate = settings.inworld_sample_rate_hz

    @property
    def name(self) -> str:
        return "inworld"

    @property
    def model(self) -> str:
        return self._model

    @property
    def narration_model(self) -> str:
        # Inworld has no separate expressive tier we target; one model serves
        # both narration and realtime.
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

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        *,
        narration: bool = False,
        previous_text: str | None = None,
        next_text: str | None = None,
    ) -> TTSResult:
        # narration/context accepted for protocol parity; Inworld's 1.5 API
        # has no cross-request conditioning (and its markups are English-only),
        # so they are deliberately unused.
        del narration, previous_text, next_text
        text = text.strip()
        if not text:
            raise InworldTTSError("text is empty")
        voice = voice_id or self._default_voice
        if not voice:
            raise InworldTTSError(
                "No Inworld voice resolved. Configure INWORLD_VOICE_ID or "
                "INWORLD_VOICE_ID_<lang> for the requested language."
            )
        payload = {
            "text": text,
            "voiceId": voice,
            "modelId": self._model,
            "audioConfig": {
                "audioEncoding": self._audio_encoding,
                "sampleRateHertz": self._sample_rate,
            },
        }
        headers = {
            "Authorization": f"Basic {self._api_key}",
            "Content-Type": "application/json",
        }

        log.debug("tts.inworld.request", voice=voice, model=self._model, chars=len(text))
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self.URL, json=payload, headers=headers)
        if resp.status_code != 200:
            raise InworldTTSError(f"Inworld API {resp.status_code}: {resp.text[:500]}")

        try:
            audio_b64 = resp.json()["audioContent"]
        except (ValueError, KeyError) as e:
            raise InworldTTSError(
                f"Inworld response missing audioContent: {resp.text[:200]}"
            ) from e
        try:
            audio = base64.b64decode(audio_b64)
        except (ValueError, TypeError) as e:
            raise InworldTTSError("Inworld returned non-base64 audioContent") from e

        return TTSResult(
            audio=audio,
            mime_type=_AUDIO_ENCODING_TO_MIME.get(self._audio_encoding, "audio/mpeg"),
            provider=self.name,
            model=self._model,
            voice_id=voice,
            char_count=len(text),
        )
