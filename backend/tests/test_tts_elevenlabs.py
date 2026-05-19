"""Unit tests for ElevenLabs per-language voice resolution.

ElevenLabs voices are technically multilingual but quality varies by native
language (Bella nails German, butchers Spanish). The per-lang mapping lets
you pick a native voice per target_language; this verifies the lookup falls
back gracefully when a language has no override.
"""

from __future__ import annotations

import pytest

from klara.config import Settings
from klara.tts.elevenlabs_impl import ElevenLabsTTS, ElevenLabsTTSError


def _settings(**overrides) -> Settings:
    defaults: dict = {
        "elevenlabs_api_key": "test-key",
        "elevenlabs_voice_id": "FALLBACK",
        "elevenlabs_voice_id_de": "",
        "elevenlabs_voice_id_es": "",
        "elevenlabs_voice_id_fr": "",
        "elevenlabs_voice_id_ja": "",
        "elevenlabs_voice_id_pt": "",
        "elevenlabs_voice_id_en": "",
        "elevenlabs_model": "eleven_turbo_v2_5",
        "tts_request_timeout_seconds": 30.0,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_init_requires_api_key():
    with pytest.raises(ElevenLabsTTSError, match="ELEVENLABS_API_KEY"):
        ElevenLabsTTS(_settings(elevenlabs_api_key=None))


def test_voice_for_lang_falls_back_when_no_override():
    tts = ElevenLabsTTS(_settings())
    assert tts.voice_for_lang("de") == "FALLBACK"
    assert tts.voice_for_lang("es") == "FALLBACK"
    assert tts.voice_for_lang(None) == "FALLBACK"
    assert tts.voice_for_lang("xx") == "FALLBACK"


def test_voice_for_lang_picks_specific_when_configured():
    tts = ElevenLabsTTS(
        _settings(
            elevenlabs_voice_id_de="GERMAN_VOICE",
            elevenlabs_voice_id_es="SPANISH_VOICE",
        )
    )
    assert tts.voice_for_lang("de") == "GERMAN_VOICE"
    assert tts.voice_for_lang("es") == "SPANISH_VOICE"
    assert tts.voice_for_lang("fr") == "FALLBACK"  # no fr → fallback


def test_voice_for_lang_case_insensitive():
    tts = ElevenLabsTTS(_settings(elevenlabs_voice_id_de="GERMAN_VOICE"))
    assert tts.voice_for_lang("DE") == "GERMAN_VOICE"
    assert tts.voice_for_lang("De") == "GERMAN_VOICE"


def test_empty_string_override_is_ignored():
    """Empty env-var values must NOT mask the fallback — an empty voice_id
    would 404 against ElevenLabs."""
    tts = ElevenLabsTTS(
        _settings(elevenlabs_voice_id="FALLBACK", elevenlabs_voice_id_de="")
    )
    assert tts.voice_for_lang("de") == "FALLBACK"


def test_default_voice_id_property_returns_fallback():
    tts = ElevenLabsTTS(_settings())
    assert tts.default_voice_id == "FALLBACK"
    assert tts.name == "elevenlabs"
    assert tts.model == "eleven_turbo_v2_5"
