"""Tests for the local audio quality gate (pronunciation/audio_quality.py).

Synthetic WAVs built with numpy + stdlib wave — the same PCM 16kHz mono
16-bit shape transcode_to_wav produces, so the gate sees exactly what it
would in production.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest
from fastapi import HTTPException

from klara.pronunciation.audio_quality import (
    DEFAULT_THRESHOLDS,
    AudioQualityReport,
    apply_fixed_gain,
    evaluate_gate,
    gate_wav_for_azure,
    load_wav_samples,
)

RATE = 16_000


def _tone(seconds: float, amplitude: float, freq: float = 200.0) -> np.ndarray:
    t = np.arange(round(seconds * RATE)) / RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _silence(seconds: float) -> np.ndarray:
    return np.zeros(round(seconds * RATE), dtype=np.float32)


def _write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = np.clip(samples * 32768.0, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(pcm.tobytes())


def _rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))


def _gate_error(path: Path) -> HTTPException:
    with pytest.raises(HTTPException) as exc_info:
        gate_wav_for_azure(path, locale="en")
    return exc_info.value


def test_silence_is_rejected_with_silence_reason(tmp_path):
    wav = tmp_path / "silence.wav"
    _write_wav(wav, _silence(2.0))

    err = _gate_error(wav)

    assert err.status_code == 422
    assert err.detail["error"] == "audio_quality"
    assert err.detail["reason"] == "silence"
    assert "silence" in err.detail["reasons"]
    assert err.detail["message"]  # localized user-facing copy


def test_clean_tone_passes_untouched(tmp_path):
    samples = np.concatenate([_silence(0.3), _tone(1.2, 0.3), _silence(0.3)])
    wav = tmp_path / "clean.wav"
    _write_wav(wav, samples)
    before = wav.read_bytes()

    out = gate_wav_for_azure(wav, locale="en")

    assert out == wav
    assert wav.read_bytes() == before  # loud enough as-is: no gain rewrite


def test_steady_tone_without_pauses_passes(tmp_path):
    """A constant signal has no quiet frames for the relative VAD threshold;
    the steady-signal fallback must not misread it as silence."""
    wav = tmp_path / "steady.wav"
    _write_wav(wav, _tone(1.5, 0.3))

    out = gate_wav_for_azure(wav, locale="en")

    assert out == wav


def test_quiet_but_recoverable_tone_gets_gain(tmp_path):
    samples = np.concatenate([_silence(0.3), _tone(1.2, 0.02), _silence(0.3)])
    wav = tmp_path / "quiet.wav"
    _write_wav(wav, samples)
    original_rms = _rms(load_wav_samples(wav)[0])

    out = gate_wav_for_azure(wav, locale="en")

    assert out == wav
    gained_rms = _rms(load_wav_samples(wav)[0])
    assert gained_rms > original_rms * 2  # ~16dB boost toward the target level


def test_very_quiet_tone_is_rejected(tmp_path):
    """Below the VAD floor there is no voice to recover — rejected locally
    instead of paying Azure for a mic-off take."""
    wav = tmp_path / "faint.wav"
    _write_wav(wav, np.concatenate([_silence(0.3), _tone(1.2, 0.0005), _silence(0.3)]))

    err = _gate_error(wav)

    assert err.status_code == 422
    assert err.detail["reason"] == "silence"


def test_clipped_signal_is_rejected(tmp_path):
    t = np.arange(round(1.2 * RATE)) / RATE
    square = (np.sign(np.sin(2 * np.pi * 200 * t)) * 0.9999).astype(np.float32)
    wav = tmp_path / "clipped.wav"
    _write_wav(wav, np.concatenate([_silence(0.3), square, _silence(0.3)]))

    err = _gate_error(wav)

    assert err.status_code == 422
    assert err.detail["reason"] == "clipping"


def test_too_short_clip_is_rejected(tmp_path):
    samples = np.concatenate([_silence(0.3), _tone(0.1, 0.3), _silence(0.3)])
    wav = tmp_path / "short.wav"
    _write_wav(wav, samples)

    err = _gate_error(wav)

    assert err.status_code == 422
    assert err.detail["reason"] == "too_short"


def test_gate_flags_level_too_low_when_gain_cannot_recover():
    """Unit-level: a report below the RMS floor whose only problem is level
    is ineligible with level_too_low (the helper only reaches this when peak
    headroom caps the gain below what recovery needs)."""
    report = AudioQualityReport(
        duration_ms=2000,
        effective_voice_ms=1500,
        input_rms_dbfs=-60.0,
        processed_rms_dbfs=-60.0,
        speech_rms_dbfs=-60.0,
        peak_dbfs=-40.0,
        clipping_ratio=0.0,
        noise_floor_dbfs=None,
        snr_db=None,
        requested_gain_db=0.0,
        applied_gain_db=0.0,
        warnings=(),
    )

    decision = evaluate_gate(report, DEFAULT_THRESHOLDS)

    assert not decision.eligible
    assert decision.reason_codes == ("level_too_low",)


def test_apply_fixed_gain_is_peak_limited():
    samples = np.full(1000, 0.5, dtype=np.float32)  # peak 0.5 ≈ -6dBFS

    result = apply_fixed_gain(samples, 12.0)

    assert result.limited
    assert result.applied_gain_db < 12.0
    assert float(np.max(np.abs(result.samples))) <= 10.0 ** (-1.0 / 20.0) + 1e-6


def test_apply_fixed_gain_refuses_more_than_max_gain():
    with pytest.raises(ValueError, match="max_gain_db"):
        apply_fixed_gain(np.zeros(100, dtype=np.float32), 20.0)


# --- regressions -------------------------------------------------------------


def _voiced(seconds: float, level_dbfs: float = -20.0) -> np.ndarray:
    """Speech-shaped: harmonic stack under a syllabic envelope. Every threshold
    in the gate is tuned for voice, so a pure tone is not a fair stand-in."""
    t = np.arange(round(seconds * RATE)) / RATE
    sig = sum(np.sin(2 * np.pi * 150.0 * k * t) / k for k in range(1, 12))
    sig = sig * (1.0 + 0.35 * np.sin(2 * np.pi * 4.0 * t))
    sig = sig / np.max(np.abs(sig))
    return (sig * (10.0 ** (level_dbfs / 20.0) / _rms(sig))).astype(np.float32)


def _room_tone(seconds: float, level_dbfs: float = -58.0) -> np.ndarray:
    rng = np.random.default_rng(11)
    noise = rng.standard_normal(round(seconds * RATE)).astype(np.float32)
    return (noise * (10.0 ** (level_dbfs / 20.0) / _rms(noise))).astype(np.float32)


def _applied_gain_db(before: np.ndarray, after: np.ndarray) -> float:
    return 20.0 * np.log10(_rms(after) / _rms(before))


def test_gain_does_not_depend_on_how_long_the_user_took_to_stop(tmp_path):
    """The same word at the same level must get the same boost regardless of
    trailing silence. Driving gain off the whole-clip RMS made the boost a
    function of the recorder tail (+1dB at 300ms, +8dB at 4s) and dragged the
    noise floor up with it."""
    word = _voiced(0.5)
    gains = []
    for tail_s in (0.3, 1.5, 4.0):
        clip = np.concatenate([_room_tone(0.25), word, _room_tone(tail_s)])
        wav = tmp_path / f"tail{tail_s}.wav"
        _write_wav(wav, clip)

        gate_wav_for_azure(wav, locale="en")

        after, _ = load_wav_samples(wav)
        gains.append(_applied_gain_db(clip, after))

    assert max(gains) - min(gains) < 1.0, f"gain tracked the silence tail: {gains}"


def test_quiet_speech_is_still_boosted_toward_the_target(tmp_path):
    """The counterpart: gain must still fire when the SPEECH is genuinely quiet."""
    clip = np.concatenate([_room_tone(0.25, -75.0), _voiced(0.8, -38.0), _room_tone(0.3, -75.0)])
    wav = tmp_path / "quiet.wav"
    _write_wav(wav, clip)

    gate_wav_for_azure(wav, locale="en")

    after, _ = load_wav_samples(wav)
    assert _applied_gain_db(clip, after) > 6.0


def test_unparseable_wav_fails_open_instead_of_erroring(tmp_path):
    """The gate is an optimization: audio it cannot read goes to Azure
    untouched, exactly as before the gate existed. `wave` is stricter than
    ffmpeg's muxer, and a 500 here would be worse than a missed saving."""
    wav = tmp_path / "broken.wav"
    wav.write_bytes(b"RIFFnope")

    assert gate_wav_for_azure(wav, locale="en") == wav
    assert wav.read_bytes() == b"RIFFnope"


def test_stereo_wav_fails_open(tmp_path):
    """Same contract for a shape the gate refuses to analyse."""
    wav = tmp_path / "stereo.wav"
    pcm = np.zeros(RATE * 2, dtype="<i2")
    with wave.open(str(wav), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(pcm.tobytes())

    assert gate_wav_for_azure(wav, locale="en") == wav


def test_clipping_is_judged_on_the_speech_not_the_silence(tmp_path):
    """A badly clipped word must be rejected even when a long quiet tail
    dilutes it below the whole-clip 1% threshold."""
    clipped_word = np.clip(_voiced(0.4, -6.0) * 6.0, -1.0, 1.0)
    clip = np.concatenate([clipped_word, _room_tone(6.0)])
    wav = tmp_path / "clipped_word.wav"
    _write_wav(wav, clip)

    err = _gate_error(wav)

    assert err.status_code == 422
    assert err.detail["reason"] == "clipping"


def test_rejection_detail_carries_the_shape_the_frontend_parses(tmp_path):
    """client.ts reads body.detail.reason / .message. Keep the contract pinned:
    a plain-string detail (the old shape) would silently regress the UI to a
    generic error."""
    wav = tmp_path / "silence.wav"
    _write_wav(wav, _silence(1.5))

    err = _gate_error(wav)

    assert err.detail["error"] == "audio_quality"
    assert err.detail["reason"] in {"silence", "too_short", "clipping", "level_too_low"}
    assert isinstance(err.detail["reasons"], list)
    assert isinstance(err.detail["message"], str) and err.detail["message"]


CAMPOS_MEDICION = (
    "duration_ms",
    "voice_ms",
    "speech_rms_dbfs",
    "clip_rms_dbfs",
    "peak_dbfs",
    "noise_floor_dbfs",
    "snr_db",
    "clipping_ratio",
)


def test_toda_toma_aceptada_deja_su_medicion(tmp_path):
    """El gate mide para decidir; esas mediciones son el único material con el
    que se pueden calibrar sus umbrales contra audio real (issue #120, punto 4).
    Si sólo se registran los rechazos, la muestra queda sesgada hacia lo malo y
    la próxima calibración vuelve a hacerse con señales sintéticas.

    caplog no sirve acá: structlog escribe por su cuenta, no por el logging de
    la stdlib. capture_logs además deja assertar los campos estructurados en
    vez del texto renderizado.
    """
    from structlog.testing import capture_logs

    clip = np.concatenate([_room_tone(0.25), _voiced(0.8), _room_tone(0.3)])
    wav = tmp_path / "buena.wav"
    _write_wav(wav, clip)

    with capture_logs() as logs:
        gate_wav_for_azure(wav, locale="en")

    medidas = [ln for ln in logs if ln.get("event") == "pronunciation.audio_quality_ok"]
    assert medidas, f"una toma aceptada no dejó medición: {[ln.get('event') for ln in logs]}"
    for campo in CAMPOS_MEDICION:
        assert campo in medidas[0], f"falta {campo} en la medición"


def test_la_toma_rechazada_tambien_deja_su_medicion(tmp_path):
    """El otro lado de la muestra: sin los mismos campos en el rechazo, no se
    puede comparar la cola contra la distribución sana."""
    from structlog.testing import capture_logs

    wav = tmp_path / "silencio.wav"
    _write_wav(wav, _silence(1.5))

    with capture_logs() as logs:
        with pytest.raises(HTTPException):
            gate_wav_for_azure(wav, locale="en")

    medidas = [ln for ln in logs if ln.get("event") == "pronunciation.audio_quality_rejected"]
    assert medidas
    for campo in CAMPOS_MEDICION:
        assert campo in medidas[0], f"falta {campo} en la medición del rechazo"
