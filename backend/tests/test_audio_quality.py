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
        peak_dbfs=-40.0,
        clipping_ratio=0.0,
        noise_floor_dbfs=None,
        snr_db=None,
        requested_gain_db=0.0,
        applied_gain_db=0.0,
        warnings=(),
    )
    from klara.pronunciation.audio_quality import DEFAULT_THRESHOLDS

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
