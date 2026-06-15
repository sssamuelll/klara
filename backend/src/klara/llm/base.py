from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class Message:
    role: Role
    content: str


@dataclass(slots=True)
class LLMResponse:
    content: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    raw: Any = None


class LLMClient(Protocol):
    async def complete(
        self,
        *,
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: dict | None = None,
        timeout_seconds: float | None = None,
        num_retries: int | None = None,
        extra_body: dict | None = None,
    ) -> LLMResponse: ...

    async def stream(
        self,
        *,
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]: ...
