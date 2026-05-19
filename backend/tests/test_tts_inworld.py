"""Unit tests for the Inworld TTS provider.

Patches httpx.AsyncClient.post so we never hit the real API. Verifies the
request shape (Basic auth without re-encoding the key, JSON body keys,
endpoint URL) and response handling (base64 decode, error mapping).
"""

from __future__ import annotations

import base64

import httpx
import pytest

from klara.config import Settings
from klara.tts.inworld_impl import InworldTTS, InworldTTSError


def _settings(**overrides) -> Settings:
    defaults: dict = {
        "inworld_api_key": "BASE64KEY==",
        "inworld_voice_id": "Aria",
        "inworld_voice_id_de": "",
        "inworld_voice_id_es": "",
        "inworld_voice_id_fr": "",
        "inworld_voice_id_ja": "",
        "inworld_voice_id_pt": "",
        "inworld_voice_id_en": "",
        "inworld_model": "inworld-tts-1.5-mini",
        "inworld_audio_encoding": "MP3",
        "inworld_sample_rate_hz": 24000,
        "tts_request_timeout_seconds": 30.0,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _patch_post(monkeypatch, response_factory):
    """Patch httpx.AsyncClient.post to call `response_factory(self, url, json, headers)`.

    The factory should return an httpx.Response. We also stash the captured
    args on the returned dict so tests can assert.
    """
    captured: dict = {}

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return response_factory()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    return captured


def _audio_response(audio: bytes = b"\x00\x01\x02fake-mp3") -> httpx.Response:
    body = {"audioContent": base64.b64encode(audio).decode("ascii")}
    return httpx.Response(200, json=body)


@pytest.mark.asyncio
async def test_synthesize_sends_basic_auth_without_reencoding(monkeypatch):
    captured = _patch_post(monkeypatch, _audio_response)
    tts = InworldTTS(_settings())
    await tts.synthesize("Guten Morgen")
    # The key arrives prefixed with "Basic " and NOT re-encoded — Inworld's key
    # is already base64. A failure here yields 401 in prod.
    assert captured["headers"]["Authorization"] == "Basic BASE64KEY=="
    assert captured["headers"]["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_synthesize_request_payload_shape(monkeypatch):
    captured = _patch_post(monkeypatch, _audio_response)
    tts = InworldTTS(_settings())
    await tts.synthesize("Hallo Welt")
    assert captured["url"] == "https://api.inworld.ai/tts/v1/voice"
    body = captured["json"]
    assert body["text"] == "Hallo Welt"
    assert body["voiceId"] == "Aria"
    assert body["modelId"] == "inworld-tts-1.5-mini"
    assert body["audioConfig"] == {"audioEncoding": "MP3", "sampleRateHertz": 24000}


@pytest.mark.asyncio
async def test_synthesize_uses_override_voice(monkeypatch):
    captured = _patch_post(monkeypatch, _audio_response)
    tts = InworldTTS(_settings())
    await tts.synthesize("Hallo", voice_id="Olivia")
    assert captured["json"]["voiceId"] == "Olivia"


@pytest.mark.asyncio
async def test_synthesize_decodes_base64_audio(monkeypatch):
    raw = b"actual-bytes-of-mp3\xff\xfe\xfd"
    _patch_post(monkeypatch, lambda: _audio_response(raw))
    tts = InworldTTS(_settings())
    result = await tts.synthesize("Guten Morgen")
    assert result.audio == raw
    assert result.mime_type == "audio/mpeg"
    assert result.provider == "inworld"
    assert result.model == "inworld-tts-1.5-mini"
    assert result.voice_id == "Aria"
    assert result.char_count == len("Guten Morgen")


@pytest.mark.asyncio
async def test_synthesize_strips_whitespace(monkeypatch):
    captured = _patch_post(monkeypatch, _audio_response)
    tts = InworldTTS(_settings())
    await tts.synthesize("   Hallo   ")
    assert captured["json"]["text"] == "Hallo"


@pytest.mark.asyncio
async def test_synthesize_empty_text_raises():
    tts = InworldTTS(_settings())
    with pytest.raises(InworldTTSError, match="empty"):
        await tts.synthesize("   ")


@pytest.mark.asyncio
async def test_synthesize_http_error_raises(monkeypatch):
    _patch_post(monkeypatch, lambda: httpx.Response(401, text="invalid api key"))
    tts = InworldTTS(_settings())
    with pytest.raises(InworldTTSError, match="401"):
        await tts.synthesize("Hallo")


@pytest.mark.asyncio
async def test_synthesize_missing_audio_content_raises(monkeypatch):
    _patch_post(monkeypatch, lambda: httpx.Response(200, json={"oops": "wrong shape"}))
    tts = InworldTTS(_settings())
    with pytest.raises(InworldTTSError, match="audioContent"):
        await tts.synthesize("Hallo")


@pytest.mark.asyncio
async def test_synthesize_invalid_base64_raises(monkeypatch):
    _patch_post(
        monkeypatch,
        lambda: httpx.Response(200, json={"audioContent": "!!!not-base64!!!"}),
    )
    tts = InworldTTS(_settings())
    with pytest.raises(InworldTTSError, match="base64"):
        await tts.synthesize("Hallo")


def test_init_requires_api_key():
    with pytest.raises(InworldTTSError, match="INWORLD_API_KEY"):
        InworldTTS(_settings(inworld_api_key=None))


def test_init_requires_at_least_one_voice():
    with pytest.raises(InworldTTSError, match="No Inworld voice"):
        InworldTTS(_settings(inworld_voice_id=""))


def test_init_accepts_per_lang_voice_only():
    """Having only per-lang voices (no generic fallback) is a valid setup."""
    tts = InworldTTS(_settings(inworld_voice_id="", inworld_voice_id_de="Aria"))
    assert tts.voice_for_lang("de") == "Aria"


def test_voice_for_lang_falls_back_to_default():
    tts = InworldTTS(_settings(inworld_voice_id_de="Aria"))
    assert tts.voice_for_lang("de") == "Aria"
    assert tts.voice_for_lang("es") == "Aria"  # fallback — no es-specific voice
    assert tts.voice_for_lang(None) == "Aria"  # no lang at all → fallback
    assert tts.voice_for_lang("xx") == "Aria"  # unknown lang → fallback


def test_voice_for_lang_case_insensitive():
    tts = InworldTTS(_settings(inworld_voice_id_de="Aria"))
    assert tts.voice_for_lang("DE") == "Aria"
    assert tts.voice_for_lang("De") == "Aria"


def test_voice_for_lang_picks_per_lang_over_fallback():
    tts = InworldTTS(_settings(inworld_voice_id="Aria", inworld_voice_id_es="Diego"))
    assert tts.voice_for_lang("es") == "Diego"
    assert tts.voice_for_lang("de") == "Aria"  # no de override → fallback


def test_provider_name_and_model_exposed():
    tts = InworldTTS(_settings(inworld_model="inworld-tts-1.5-max"))
    assert tts.name == "inworld"
    assert tts.model == "inworld-tts-1.5-max"
    assert tts.default_voice_id == "Aria"


@pytest.mark.asyncio
async def test_linear16_encoding_maps_to_wav(monkeypatch):
    _patch_post(monkeypatch, _audio_response)
    tts = InworldTTS(_settings(inworld_audio_encoding="LINEAR16"))
    result = await tts.synthesize("Hallo")
    assert result.mime_type == "audio/wav"
