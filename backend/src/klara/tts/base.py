from dataclasses import dataclass
from typing import Protocol


class TTSError(RuntimeError):
    """Common base for TTS provider errors so the router can catch one type."""


@dataclass(slots=True)
class TTSResult:
    audio: bytes
    mime_type: str
    provider: str
    model: str
    voice_id: str
    char_count: int


class TTSProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def default_voice_id(self) -> str: ...

    def voice_for_lang(self, lang: str | None) -> str:
        """Return the voice_id for `lang`, falling back to `default_voice_id`
        when the lang has no specific override (or lang is None).

        TTS voices have native languages — one voice that sounds great in
        German may sound non-native in Spanish. The mapping is configured
        per-provider in Settings (e.g. ELEVENLABS_VOICE_ID_ES).
        """
        ...

    async def synthesize(self, text: str, voice_id: str | None = None) -> TTSResult: ...
