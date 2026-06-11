import os
from collections.abc import AsyncIterator
from typing import Any

import litellm
import structlog

from klara.config import Settings
from klara.llm.base import LLMResponse, Message

log = structlog.get_logger(__name__)


class LiteLLMClient:
    def __init__(self, settings: Settings, default_model: str) -> None:
        self.settings = settings
        self.default_model = default_model
        litellm.drop_params = True
        if settings.anthropic_api_key:
            os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
        if settings.openai_api_key:
            os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
        if settings.deepseek_api_key:
            os.environ.setdefault("DEEPSEEK_API_KEY", settings.deepseek_api_key)

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
    ) -> LLMResponse:
        target_model = model or self.default_model
        # Per-call overrides exist for latency-bound callers (a user is staring
        # at a "thinking" screen during /speak/turn — the settings-level 60s x
        # 2-retries budget is for background generation, not conversation).
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": (
                timeout_seconds
                if timeout_seconds is not None
                else self.settings.llm_request_timeout_seconds
            ),
            "num_retries": (
                num_retries if num_retries is not None else self.settings.llm_max_retries
            ),
        }
        if response_format is not None:
            payload["response_format"] = response_format

        log.debug("llm.request", model=target_model, max_tokens=max_tokens)
        resp = await litellm.acompletion(**payload)

        choice = resp.choices[0]
        content = choice.message.content or ""
        usage = getattr(resp, "usage", None)
        provider = target_model.split("/", 1)[0] if "/" in target_model else "unknown"

        cost: float | None = None
        try:
            cost = float(litellm.completion_cost(completion_response=resp))
        except Exception:
            cost = None

        return LLMResponse(
            content=content,
            model=target_model,
            provider=provider,
            input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            cost_usd=cost,
            raw=resp,
        )

    async def stream(
        self,
        *,
        messages: list[Message],
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        target_model = model or self.default_model
        resp = await litellm.acompletion(
            model=target_model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
            timeout=self.settings.llm_request_timeout_seconds,
        )
        async for chunk in resp:
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                yield text
