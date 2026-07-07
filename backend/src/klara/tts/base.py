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
    def narration_model(self) -> str:
        """Model used when `synthesize(narration=True)`. Providers without a
        separate narration tier return `model` — the split only exists where
        the provider offers a more expressive (slower/pricier) model worth
        using for pre-cached story audio.
        """
        ...

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

    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        *,
        narration: bool = False,
        previous_text: str | None = None,
        next_text: str | None = None,
    ) -> TTSResult:
        """`narration=True` selects the expressive narration tier (where the
        provider has one). `previous_text`/`next_text` give the provider the
        neighboring sentences so a sentence synthesized in isolation is still
        intoned as part of the passage; providers without context conditioning
        ignore them.
        """
        ...
