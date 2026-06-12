"""Unit tests for LiteLLMClient request construction.

The extra_body passthrough is Speak's latency guard: DeepSeek V4 selects
thinking vs non-thinking via `{"thinking": {"type": ...}}` in the request
body, and chain-of-thought on the conversational critical path would blow
the <=5s stop-to-voice budget. These tests pin that the knob actually
reaches the wire call.
"""

from __future__ import annotations

import pytest

from klara.config import Settings
from klara.llm.base import Message
from klara.llm.litellm_impl import LiteLLMClient


class _FakeMessage:
    content = "ok"


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]
    usage = None


@pytest.fixture
def captured(monkeypatch):
    calls: dict = {}

    async def fake_acompletion(**kwargs):
        calls.clear()
        calls.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr("klara.llm.litellm_impl.litellm.acompletion", fake_acompletion)
    return calls


def _msg() -> list[Message]:
    return [Message(role="user", content="hallo")]


@pytest.mark.asyncio
async def test_default_extra_body_reaches_the_request(captured):
    client = LiteLLMClient(
        Settings(),
        default_model="deepseek/deepseek-v4-flash",
        default_extra_body={"thinking": {"type": "disabled"}},
    )
    await client.complete(messages=_msg())
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


@pytest.mark.asyncio
async def test_per_call_extra_body_overrides_default(captured):
    client = LiteLLMClient(
        Settings(),
        default_model="deepseek/deepseek-v4-flash",
        default_extra_body={"thinking": {"type": "disabled"}},
    )
    await client.complete(messages=_msg(), extra_body={"thinking": {"type": "enabled"}})
    assert captured["extra_body"] == {"thinking": {"type": "enabled"}}


@pytest.mark.asyncio
async def test_no_extra_body_when_unset(captured):
    client = LiteLLMClient(Settings(), default_model="some/model")
    await client.complete(messages=_msg())
    assert "extra_body" not in captured


@pytest.mark.asyncio
async def test_per_call_timeout_and_retries_still_apply(captured):
    client = LiteLLMClient(Settings(), default_model="some/model")
    await client.complete(messages=_msg(), timeout_seconds=25.0, num_retries=0)
    assert captured["timeout"] == 25.0
    assert captured["num_retries"] == 0


def test_settings_parses_json_extra_body_from_env(monkeypatch):
    monkeypatch.setenv("LLM_CHAT_EXTRA_BODY", '{"thinking": {"type": "disabled"}}')
    assert Settings().llm_chat_extra_body == {"thinking": {"type": "disabled"}}


def test_settings_treats_blank_extra_body_as_none(monkeypatch):
    # docker-compose delivers ${LLM_CHAT_EXTRA_BODY:-} = "" when unset; an
    # empty string must not crash Settings() (it isn't valid JSON).
    monkeypatch.setenv("LLM_CHAT_EXTRA_BODY", "")
    assert Settings().llm_chat_extra_body is None
    monkeypatch.setenv("LLM_CHAT_EXTRA_BODY", "   ")
    assert Settings().llm_chat_extra_body is None
