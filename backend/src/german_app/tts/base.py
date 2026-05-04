from dataclasses import dataclass
from typing import Protocol


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

    async def synthesize(self, text: str, voice_id: str | None = None) -> TTSResult: ...
