"""Tests for POST /api/v1/pronunciation/score.

The Azure SDK call is monkeypatched everywhere — we never hit the real
service. Tests cover the gating logic, error mapping, and that an
authenticated successful path returns the schema as designed.
"""
from __future__ import annotations

from pathlib import Path

import pytest


async def _register_and_login(client, app_settings, seed_invite) -> str:
    app_settings(ALLOWED_SIGNUP_EMAILS="", INITIAL_OWNER_EMAIL="", AZURE_SPEECH_KEY="dummy-key")
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "pron@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "pron@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204
    return r2.headers["set-cookie"].split(";")[0]


def _fake_score_response(reference: str = "Hello world", lang: str = "en-US"):
    from klara.pronunciation.schemas import (
        PhonemeScore,
        PronunciationScores,
        ScoreResponse,
        WordScore,
    )

    return ScoreResponse(
        recognized_text=reference,
        reference_text=reference,
        language=lang,
        scores=PronunciationScores(
            accuracy=92.0, fluency=88.0, completeness=100.0, pronunciation=90.0
        ),
        words=[
            WordScore(
                word="Hello",
                accuracy_score=95.0,
                error_type="None",
                phonemes=[PhonemeScore(phoneme="h", accuracy_score=98.0)],
            ),
            WordScore(
                word="world",
                accuracy_score=85.0,
                error_type="None",
                phonemes=[PhonemeScore(phoneme="w", accuracy_score=82.0)],
            ),
        ],
    )


@pytest.fixture
def patched_pronunciation(monkeypatch, tmp_path: Path):
    """Stubs transcode + Azure so no ffmpeg/Azure is touched."""

    def fake_transcode(audio_bytes: bytes, *, sample_rate: int = 16_000) -> Path:
        out = tmp_path / "fake.wav"
        out.write_bytes(b"RIFFfake")
        return out

    monkeypatch.setattr(
        "klara.routers.pronunciation.transcode_to_wav", fake_transcode
    )

    def fake_score(wav_path, reference_text, language, *, azure_key, azure_region):
        return _fake_score_response(reference_text, language)

    monkeypatch.setattr(
        "klara.routers.pronunciation.score_pronunciation", fake_score
    )
    return {"transcode": fake_transcode, "score": fake_score}


@pytest.mark.asyncio
async def test_score_requires_auth(client, app_settings):
    app_settings(AZURE_SPEECH_KEY="dummy-key")
    r = await client.post(
        "/api/v1/pronunciation/score",
        data={"reference_text": "hi", "language": "en-US"},
        files={"audio": ("a.webm", b"\x00\x01\x02", "audio/webm")},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_score_503_when_key_missing(client, app_settings, seed_invite):
    """Without AZURE_SPEECH_KEY the endpoint must respond 503, not 500."""
    cookie = await _register_and_login(client, app_settings, seed_invite)
    # Strip the key now that we're past the login step.
    app_settings(AZURE_SPEECH_KEY="")
    r = await client.post(
        "/api/v1/pronunciation/score",
        headers={"Cookie": cookie},
        data={"reference_text": "hi", "language": "en-US"},
        files={"audio": ("a.webm", b"\x00\x01\x02", "audio/webm")},
    )
    assert r.status_code == 503
    assert "pronunciaci" in r.json()["detail"].lower() or "pronunciation" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_score_400_on_empty_audio(client, app_settings, seed_invite):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    r = await client.post(
        "/api/v1/pronunciation/score",
        headers={"Cookie": cookie},
        data={"reference_text": "hi", "language": "en-US"},
        files={"audio": ("a.webm", b"", "audio/webm")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_score_413_when_audio_too_large(
    client, app_settings, seed_invite, monkeypatch
):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    # Force the cap to a tiny value so the test doesn't have to upload 25 MB.
    from klara.config import get_settings

    get_settings.cache_clear()
    import os

    os.environ["PRONUNCIATION_MAX_AUDIO_BYTES"] = "8"
    try:
        r = await client.post(
            "/api/v1/pronunciation/score",
            headers={"Cookie": cookie},
            data={"reference_text": "hi", "language": "en-US"},
            files={"audio": ("a.webm", b"\x00" * 128, "audio/webm")},
        )
        assert r.status_code == 413
    finally:
        os.environ.pop("PRONUNCIATION_MAX_AUDIO_BYTES", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_score_happy_path(
    client, app_settings, seed_invite, patched_pronunciation
):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    r = await client.post(
        "/api/v1/pronunciation/score",
        headers={"Cookie": cookie},
        data={"reference_text": "Hello world", "language": "en-US"},
        files={"audio": ("a.webm", b"\x00\x01\x02\x03", "audio/webm")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["recognized_text"] == "Hello world"
    assert body["language"] == "en-US"
    assert body["scores"]["pronunciation"] == 90.0
    assert len(body["words"]) == 2
    assert body["words"][0]["word"] == "Hello"
    assert body["words"][0]["phonemes"][0]["phoneme"] == "h"


@pytest.mark.asyncio
async def test_score_422_when_no_speech_detected(
    client, app_settings, seed_invite, monkeypatch, tmp_path: Path
):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    from klara.pronunciation.azure_client import AzureSpeechError

    def stub_transcode(b, *, sample_rate=16_000):
        out = tmp_path / "x.wav"
        out.write_bytes(b"x")
        return out

    monkeypatch.setattr(
        "klara.routers.pronunciation.transcode_to_wav", stub_transcode
    )

    def raise_no_match(*a, **k):
        raise AzureSpeechError("No speech", recoverable=True)

    monkeypatch.setattr(
        "klara.routers.pronunciation.score_pronunciation", raise_no_match
    )

    r = await client.post(
        "/api/v1/pronunciation/score",
        headers={"Cookie": cookie},
        data={"reference_text": "hi", "language": "en-US"},
        files={"audio": ("a.webm", b"\x00\x01\x02\x03", "audio/webm")},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_score_502_when_azure_fails(
    client, app_settings, seed_invite, monkeypatch, tmp_path: Path
):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    from klara.pronunciation.azure_client import AzureSpeechError

    def stub_transcode(b, *, sample_rate=16_000):
        out = tmp_path / "x.wav"
        out.write_bytes(b"x")
        return out

    monkeypatch.setattr(
        "klara.routers.pronunciation.transcode_to_wav", stub_transcode
    )

    def raise_fatal(*a, **k):
        raise AzureSpeechError("Quota exceeded", recoverable=False)

    monkeypatch.setattr(
        "klara.routers.pronunciation.score_pronunciation", raise_fatal
    )

    r = await client.post(
        "/api/v1/pronunciation/score",
        headers={"Cookie": cookie},
        data={"reference_text": "hi", "language": "en-US"},
        files={"audio": ("a.webm", b"\x00\x01\x02\x03", "audio/webm")},
    )
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_score_400_when_audio_undecodable(
    client, app_settings, seed_invite, monkeypatch
):
    cookie = await _register_and_login(client, app_settings, seed_invite)
    from klara.pronunciation.audio import TranscodeError

    def raise_transcode(b, *, sample_rate=16_000):
        raise TranscodeError("ffmpeg: invalid container")

    monkeypatch.setattr(
        "klara.routers.pronunciation.transcode_to_wav", raise_transcode
    )

    r = await client.post(
        "/api/v1/pronunciation/score",
        headers={"Cookie": cookie},
        data={"reference_text": "hi", "language": "en-US"},
        files={"audio": ("a.bin", b"\x00garbage", "application/octet-stream")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_short_language_code_resolves_to_bcp47(
    client, app_settings, seed_invite, monkeypatch, tmp_path: Path
):
    """The endpoint should accept short codes ('en', 'de') as a convenience."""
    cookie = await _register_and_login(client, app_settings, seed_invite)

    captured = {}

    def stub_transcode(b, *, sample_rate=16_000):
        out = tmp_path / "x.wav"
        out.write_bytes(b"x")
        return out

    monkeypatch.setattr(
        "klara.routers.pronunciation.transcode_to_wav", stub_transcode
    )

    def fake_score(wav_path, reference_text, language, *, azure_key, azure_region):
        captured["language"] = language
        return _fake_score_response(reference_text, language)

    monkeypatch.setattr(
        "klara.routers.pronunciation.score_pronunciation", fake_score
    )

    r = await client.post(
        "/api/v1/pronunciation/score",
        headers={"Cookie": cookie},
        data={"reference_text": "Hallo", "language": "de"},
        files={"audio": ("a.webm", b"\x00\x01", "audio/webm")},
    )
    assert r.status_code == 200, r.text
    assert captured["language"] == "de-DE"
