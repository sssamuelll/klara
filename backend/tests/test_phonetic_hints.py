"""Unit tests for the phonetic-hints service.

The LLM is patched; we only verify input shaping, JSON parsing tolerance,
and the case-mismatch mapping (LLM may lowercase keys).
"""

from __future__ import annotations

import pytest

from klara.llm.base import LLMResponse
from klara.services.phonetic_hints import generate_phonetic_hints


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.last_messages = None

    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        self.last_messages = messages
        return LLMResponse(content=self.content, model="fake", provider="fake")

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_happy_path_parses_json():
    llm = FakeLLM('{"hints": {"autobús": "au-to-BÚS", "voy": "voy"}}')
    out = await generate_phonetic_hints(llm, words=["autobús", "voy"], language="es")
    assert out == {"autobús": "au-to-BÚS", "voy": "voy"}


@pytest.mark.asyncio
async def test_strips_json_code_fence():
    llm = FakeLLM('```json\n{"hints": {"hund": "HUND"}}\n```')
    out = await generate_phonetic_hints(llm, words=["Hund"], language="de")
    # Case-insensitive key matching → maps back to the original "Hund".
    assert out == {"Hund": "HUND"}


@pytest.mark.asyncio
async def test_dedupes_and_strips_input():
    llm = FakeLLM('{"hints": {"autobús": "au-to-BÚS"}}')
    out = await generate_phonetic_hints(
        llm, words=["  autobús  ", "AUTOBÚS", "autobús"], language="es"
    )
    # The LLM gets a single deduped entry; output keys match the original spelling.
    assert out == {"autobús": "au-to-BÚS"}
    # Verify only one word reached the prompt
    user_msg = llm.last_messages[-1].content
    assert user_msg.count("autobús") == 1


@pytest.mark.asyncio
async def test_empty_input_skips_llm():
    llm = FakeLLM("never called")
    out = await generate_phonetic_hints(llm, words=["", "   "], language="es")
    assert out == {}
    assert llm.last_messages is None


@pytest.mark.asyncio
async def test_malformed_json_returns_empty():
    llm = FakeLLM("not json at all, just a chatty response")
    out = await generate_phonetic_hints(llm, words=["autobús"], language="es")
    assert out == {}


@pytest.mark.asyncio
async def test_wrong_shape_returns_empty():
    llm = FakeLLM('{"hints": ["wrong", "shape"]}')
    out = await generate_phonetic_hints(llm, words=["autobús"], language="es")
    assert out == {}


@pytest.mark.asyncio
async def test_empty_hint_value_filtered():
    llm = FakeLLM('{"hints": {"voy": "", "autobús": "au-to-BÚS"}}')
    out = await generate_phonetic_hints(llm, words=["voy", "autobús"], language="es")
    assert out == {"autobús": "au-to-BÚS"}


@pytest.mark.asyncio
async def test_extra_keys_not_in_input_dropped():
    """LLM hallucinated a word that wasn't asked → ignore."""
    llm = FakeLLM('{"hints": {"autobús": "au-to-BÚS", "tren": "TREN"}}')
    out = await generate_phonetic_hints(llm, words=["autobús"], language="es")
    assert out == {"autobús": "au-to-BÚS"}
