"""Local audio quality gate for short learner utterances.

Ported from the speechtotext project's audio gate (audio/types.py,
audio/quality.py, audio/gate.py, audio/level.py), flattened into one module
and trimmed to what a 1-15s single-speaker clip needs. The
fingerprint/provenance machinery, the diarization-era transport counters
(dropped frames, discontinuities) and the SNR gate were NOT ported: Klara
clips are mostly all-voice, so there is often no usable noise floor to gate
on (SNR is still computed for logs). Kept reasons: silence, too_short,
level_too_low, clipping.

The gate runs AFTER ffmpeg transcode (WAV PCM 16kHz mono 16-bit) and BEFORE
the Azure call, so pathological audio is rejected locally instead of paying
for a recognition that was doomed from the start. Quiet-but-recoverable
audio gets a fixed gain boost (capped, peak-limited) rather than a rejection.
"""

from __future__ import annotations

import math
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import structlog
from fastapi import HTTPException, status

from klara.i18n import t
from klara.pronunciation.audio import transcode_to_wav

log = structlog.get_logger(__name__)

DBFS_FLOOR = -120.0
CLIP_LEVEL = 0.999

#: Gain staging for quiet-but-recoverable clips. speechtotext's pipeline
#: defaults (18dB cap, -1dBFS peak limit); -23dBFS RMS is a comfortable
#: speech level for Azure without pushing noise floors into audibility.
TARGET_RMS_DBFS = -23.0
MAX_GAIN_DB = 18.0
PEAK_LIMIT_DBFS = -1.0

#: Energy-VAD knobs for detect_speech_regions. 20ms frames match
#: speechtotext's noise-floor frame size. A frame counts as voice when it
#: sits 8dB above the clip's own noise floor (20th percentile) — but never
#: below -55dBFS, so a uniformly silent clip can't talk itself into speech.
VAD_FRAME_MS = 20
VAD_THRESHOLD_OFFSET_DB = 8.0
VAD_ABSOLUTE_FLOOR_DBFS = -55.0

QualityReason = Literal["silence", "too_short", "level_too_low", "clipping"]


@dataclass(frozen=True, order=True)
class SpeechRegion:
    start_s: float
    end_s: float

    def __post_init__(self) -> None:
        if self.start_s < 0.0 or self.end_s <= self.start_s:
            raise ValueError("speech region must satisfy 0 <= start_s < end_s")


@dataclass(frozen=True)
class AudioQualityReport:
    duration_ms: int
    effective_voice_ms: int
    input_rms_dbfs: float
    processed_rms_dbfs: float
    #: RMS of the detected speech only. This — not processed_rms_dbfs — is
    #: what "is this take loud enough" means: a whole-clip RMS is diluted by
    #: however much silence the recorder happened to capture, so gating or
    #: gain-staging on it makes the answer depend on how slowly the user
    #: tapped stop. None when no speech was detected at all.
    speech_rms_dbfs: float | None
    peak_dbfs: float
    #: Fraction of SPEECH samples at full scale (whole clip when no speech was
    #: found). Whole-clip would let a badly clipped word hide inside a long
    #: quiet take, and would reject a short all-voice take for mild clipping.
    clipping_ratio: float
    noise_floor_dbfs: float | None
    snr_db: float | None
    requested_gain_db: float
    applied_gain_db: float
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        if not 0 <= self.effective_voice_ms <= self.duration_ms:
            raise ValueError("effective_voice_ms must fit inside duration_ms")
        if not 0.0 <= self.clipping_ratio <= 1.0:
            raise ValueError("clipping_ratio must be between 0 and 1")

    @property
    def level_dbfs(self) -> float:
        """The level both the gate and the gain staging judge the take by.
        Speech when we found any, whole clip otherwise — one definition so the
        two can never drift apart."""
        return self.speech_rms_dbfs if self.speech_rms_dbfs is not None else self.processed_rms_dbfs


def _dbfs(samples: np.ndarray) -> float:
    if samples.size == 0:
        return DBFS_FLOOR
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    return DBFS_FLOOR if rms <= 1e-6 else max(DBFS_FLOOR, 20.0 * math.log10(rms))


def _region_samples(
    samples: np.ndarray,
    sample_rate: int,
    regions: Sequence[SpeechRegion],
) -> np.ndarray:
    chunks = [
        samples[round(region.start_s * sample_rate) : round(region.end_s * sample_rate)]
        for region in regions
    ]
    return np.concatenate(chunks) if chunks else np.empty(0, dtype=np.float32)


def _non_speech_samples(
    samples: np.ndarray,
    sample_rate: int,
    regions: Sequence[SpeechRegion],
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    cursor = 0
    for region in regions:
        start = round(region.start_s * sample_rate)
        end = round(region.end_s * sample_rate)
        chunks.append(samples[cursor:start])
        cursor = end
    chunks.append(samples[cursor:])
    nonempty = [chunk for chunk in chunks if chunk.size]
    return np.concatenate(nonempty) if nonempty else np.empty(0, dtype=np.float32)


def _frame_levels_dbfs(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Per-frame RMS in dBFS. Vectorized deliberately: this runs three times
    per gate call, and the per-frame Python loop it replaces cost ~4.7x more
    on a 15s clip (750 frames of pure call overhead)."""
    frame_size = max(1, round(sample_rate * VAD_FRAME_MS / 1000))
    complete = len(samples) // frame_size
    if complete == 0:
        return np.asarray([_dbfs(samples)], dtype=np.float64)
    frames = samples[: complete * frame_size].reshape(complete, frame_size)
    rms = np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1))
    # Same floor semantics as _dbfs: silence pins to DBFS_FLOOR instead of -inf.
    levels = 20.0 * np.log10(np.maximum(rms, 1e-12))
    return np.maximum(np.where(rms <= 1e-6, DBFS_FLOOR, levels), DBFS_FLOOR)


def _noise_floor(samples: np.ndarray, sample_rate: int) -> float:
    levels = _frame_levels_dbfs(samples, sample_rate)
    return float(np.percentile(levels, 20.0))


@dataclass(frozen=True)
class QualityThresholds:
    min_effective_voice_ms: int
    min_processed_rms_dbfs: float
    max_clipping_ratio: float

    def __post_init__(self) -> None:
        if self.min_effective_voice_ms <= 0:
            raise ValueError("min_effective_voice_ms must be positive")
        if not math.isfinite(self.min_processed_rms_dbfs):
            raise ValueError("min_processed_rms_dbfs must be finite")
        if not 0.0 <= self.max_clipping_ratio <= 1.0:
            raise ValueError("max_clipping_ratio must be between 0 and 1")


#: Gate defaults for short learner utterances. min_processed_rms_dbfs and
#: max_clipping_ratio match speechtotext's evaluation settings; 200ms of
#: effective voice is about one short syllable — MC voice-pick answers are
#: often a single word, so anything stricter would false-reject them.
DEFAULT_THRESHOLDS = QualityThresholds(
    min_effective_voice_ms=200,
    min_processed_rms_dbfs=-45.0,
    max_clipping_ratio=0.01,
)


def detect_speech_regions(
    samples: np.ndarray,
    sample_rate: int,
    *,
    thresholds: QualityThresholds = DEFAULT_THRESHOLDS,
) -> tuple[SpeechRegion, ...]:
    """Energy VAD for short clips — speechtotext got its regions from a
    human-labeled corpus manifest; Klara has no such thing, so we derive them
    from frame energy relative to the clip's own noise floor.

    Fallback: a steady signal (a held vowel, a constant tone) has no quiet
    frames, so the relative threshold finds nothing. If the whole clip is
    loud enough to be voice, treat it as one region instead of crying
    silence. That "loud enough" is the caller's own level floor — reading the
    module default here would silently ignore a widened threshold.
    """
    source = np.asarray(samples, dtype=np.float32)
    if source.size == 0:
        return ()
    levels = _frame_levels_dbfs(source, sample_rate)
    threshold = max(
        float(np.percentile(levels, 20.0)) + VAD_THRESHOLD_OFFSET_DB,
        VAD_ABSOLUTE_FLOOR_DBFS,
    )
    frame_s = VAD_FRAME_MS / 1000
    regions: list[SpeechRegion] = []
    start: int | None = None
    for idx, level in enumerate(levels):
        if level >= threshold and start is None:
            start = idx
        elif level < threshold and start is not None:
            regions.append(SpeechRegion(start * frame_s, idx * frame_s))
            start = None
    if start is not None:
        regions.append(SpeechRegion(start * frame_s, len(levels) * frame_s))
    if not regions and _dbfs(source) >= thresholds.min_processed_rms_dbfs:
        regions = [SpeechRegion(0.0, len(source) / sample_rate)]
    return tuple(regions)


def compute_audio_quality(
    capture: np.ndarray,
    processed: np.ndarray,
    sample_rate: int,
    speech_regions: Sequence[SpeechRegion],
    *,
    requested_gain_db: float,
    applied_gain_db: float,
) -> AudioQualityReport:
    raw = np.asarray(capture, dtype=np.float32)
    cooked = np.asarray(processed, dtype=np.float32)
    if raw.ndim != 1 or cooked.ndim != 1 or len(raw) != len(cooked):
        raise ValueError("capture and processed must be mono and equal-length")
    duration_s = len(raw) / sample_rate
    regions = tuple(sorted(speech_regions))
    speech = _region_samples(cooked, sample_rate, regions)
    noise = _non_speech_samples(cooked, sample_rate, regions)
    noise_floor = _noise_floor(noise, sample_rate) if noise.size else None
    speech_level = _dbfs(speech) if speech.size else None
    snr = (
        speech_level - noise_floor if speech_level is not None and noise_floor is not None else None
    )
    peak = float(np.max(np.abs(cooked))) if cooked.size else 0.0
    # Clipping is a property of the voice, not of the silence around it.
    clip_source = speech if speech.size else cooked
    warnings: list[str] = []
    if not regions:
        warnings.append("no_speech_regions")
    # ponytail: "gain was limited" lives on GainResult.limited, which is what
    # the log line reads. One predicate, one owner.
    return AudioQualityReport(
        duration_ms=round(duration_s * 1000),
        effective_voice_ms=round(sum(region.end_s - region.start_s for region in regions) * 1000),
        input_rms_dbfs=_dbfs(raw),
        processed_rms_dbfs=_dbfs(cooked),
        speech_rms_dbfs=speech_level,
        peak_dbfs=DBFS_FLOOR if peak <= 1e-6 else 20.0 * math.log10(peak),
        clipping_ratio=(
            float(np.mean(np.abs(clip_source) >= CLIP_LEVEL)) if clip_source.size else 0.0
        ),
        noise_floor_dbfs=noise_floor,
        snr_db=snr,
        requested_gain_db=requested_gain_db,
        applied_gain_db=applied_gain_db,
        warnings=tuple(warnings),
    )


@dataclass(frozen=True)
class GateDecision:
    eligible: bool
    reason_codes: tuple[QualityReason, ...]


def evaluate_gate(
    report: AudioQualityReport,
    thresholds: QualityThresholds,
) -> GateDecision:
    reasons: list[QualityReason] = []
    if report.effective_voice_ms == 0:
        reasons.append("silence")
    elif report.effective_voice_ms < thresholds.min_effective_voice_ms:
        reasons.append("too_short")
    if report.level_dbfs < thresholds.min_processed_rms_dbfs:
        reasons.append("level_too_low")
    if report.clipping_ratio > thresholds.max_clipping_ratio:
        reasons.append("clipping")
    return GateDecision(eligible=not reasons, reason_codes=tuple(reasons))


#: eq=False on purpose: the generated __eq__ would compare an ndarray field
#: and raise "truth value of an array is ambiguous", and frozen+eq would also
#: generate an __hash__ over that unhashable array. Identity comparison is all
#: any caller needs.
@dataclass(frozen=True, eq=False)
class GainResult:
    samples: np.ndarray
    requested_gain_db: float
    applied_gain_db: float
    limited: bool


def apply_fixed_gain(
    samples: np.ndarray,
    gain_db: float,
    *,
    max_gain_db: float = MAX_GAIN_DB,
    peak_limit_dbfs: float = PEAK_LIMIT_DBFS,
) -> GainResult:
    """Fixed dB gain, capped by max_gain_db and by peak headroom — boosting
    must never push the signal over peak_limit_dbfs (that would manufacture
    the very clipping the gate rejects)."""
    if gain_db > max_gain_db:
        raise ValueError("gain_db exceeds max_gain_db")
    if peak_limit_dbfs > 0.0:
        raise ValueError("peak_limit_dbfs must be <= 0")
    source = np.asarray(samples, dtype=np.float32)
    peak = float(np.max(np.abs(source))) if source.size else 0.0
    applied = gain_db
    if peak > 0.0:
        peak_limit = 10.0 ** (peak_limit_dbfs / 20.0)
        headroom_db = 20.0 * math.log10(peak_limit / peak)
        applied = min(gain_db, headroom_db)
    scale = 10.0 ** (applied / 20.0)
    output = np.array(source * scale, dtype=np.float32, order="C", copy=True)
    return GainResult(
        samples=output,
        requested_gain_db=gain_db,
        applied_gain_db=applied,
        limited=applied < gain_db - 1e-9,
    )


def load_wav_samples(wav_path: Path) -> tuple[np.ndarray, int]:
    """Read a PCM 16-bit mono WAV (exactly what transcode_to_wav produces)
    into float32 samples in [-1, 1]. Stdlib wave + numpy — no new audio dep."""
    with wave.open(str(wav_path), "rb") as handle:
        if handle.getsampwidth() != 2 or handle.getnchannels() != 1:
            raise ValueError("gate expects PCM 16-bit mono WAV")
        sample_rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return samples, sample_rate


def _write_wav_samples(wav_path: Path, samples: np.ndarray, sample_rate: int) -> None:
    pcm = np.clip(samples * 32768.0, -32768, 32767).astype("<i2")
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


#: User-facing message per rejection reason. Silence and level_too_low share
#: the "speak louder" copy — from the user's chair they're the same failure.
_REASON_MESSAGE_KEY: dict[QualityReason, str] = {
    "silence": "pron.no_speech_detected",
    "level_too_low": "pron.no_speech_detected",
    "too_short": "pron.audio_too_short",
    "clipping": "pron.audio_clipping",
}


def _round_opt(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _reject(reasons: tuple[QualityReason, ...], locale: str) -> HTTPException:
    primary = reasons[0]
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "audio_quality",
            "reason": primary,
            "reasons": list(reasons),
            "message": t(_REASON_MESSAGE_KEY[primary], locale),
        },
    )


def gate_wav_for_azure(
    wav_path: Path,
    *,
    locale: str,
    thresholds: QualityThresholds = DEFAULT_THRESHOLDS,
) -> Path:
    """Run the quality gate on a transcoded WAV before the Azure call.

    Returns the (possibly gain-normalized, rewritten in place) wav path.
    Raises HTTPException 422 with a machine-readable reason when the audio
    is not worth an Azure round-trip.

    Fails OPEN: a WAV this module cannot parse is handed to Azure untouched,
    exactly as it was before the gate existed. The gate is an optimization,
    so a parse failure must never turn a request that used to work into an
    error — and `wave` is stricter than ffmpeg's muxer (WAVE_FORMAT_EXTENSIBLE,
    an odd-length data chunk, a stereo file if the transcode args ever change).
    """
    try:
        samples, sample_rate = load_wav_samples(wav_path)
    except (wave.Error, EOFError, ValueError) as e:
        log.warning("pronunciation.audio_quality_unreadable", error=str(e))
        return wav_path
    if sample_rate <= 0 or samples.size == 0:
        log.warning("pronunciation.audio_quality_unreadable", error="empty or rateless wav")
        return wav_path

    regions = detect_speech_regions(samples, sample_rate, thresholds=thresholds)
    report = compute_audio_quality(
        samples,
        samples,
        sample_rate,
        regions,
        requested_gain_db=0.0,
        applied_gain_db=0.0,
    )
    decision = evaluate_gate(report, thresholds)

    # Gain can't manufacture voice, time, or un-clip a signal — reject those
    # outright. level_too_low is the one reason gain might fix.
    hard = tuple(reason for reason in decision.reason_codes if reason != "level_too_low")
    if hard:
        log.info(
            "pronunciation.audio_quality_rejected",
            reasons=list(hard),
            duration_ms=report.duration_ms,
            voice_ms=report.effective_voice_ms,
            speech_rms_dbfs=round(report.level_dbfs, 1),
            clip_rms_dbfs=round(report.processed_rms_dbfs, 1),
            noise_floor_dbfs=_round_opt(report.noise_floor_dbfs),
            snr_db=_round_opt(report.snr_db),
            clipping_ratio=round(report.clipping_ratio, 4),
        )
        raise _reject(hard, locale)

    # Gain staging targets the SPEECH level. Driving it from the whole-clip RMS
    # would make the boost a function of how much silence the recorder caught:
    # the same word at the same level asked for +1dB with a short tail and +8dB
    # with a long one, dragging the noise floor up with it.
    gain_db = TARGET_RMS_DBFS - report.level_dbfs
    if gain_db <= 0.0:
        return wav_path  # eligible and loud enough as-is

    gain = apply_fixed_gain(samples, min(gain_db, MAX_GAIN_DB))
    boosted = compute_audio_quality(
        samples,
        gain.samples,
        sample_rate,
        regions,
        requested_gain_db=gain.requested_gain_db,
        applied_gain_db=gain.applied_gain_db,
    )
    boosted_decision = evaluate_gate(boosted, thresholds)
    if not boosted_decision.eligible:
        log.info(
            "pronunciation.audio_quality_rejected",
            reasons=list(boosted_decision.reason_codes),
            duration_ms=boosted.duration_ms,
            voice_ms=boosted.effective_voice_ms,
            speech_rms_dbfs=round(boosted.level_dbfs, 1),
            noise_floor_dbfs=_round_opt(boosted.noise_floor_dbfs),
            snr_db=_round_opt(boosted.snr_db),
            applied_gain_db=round(gain.applied_gain_db, 1),
        )
        raise _reject(boosted_decision.reason_codes, locale)

    _write_wav_samples(wav_path, gain.samples, sample_rate)
    log.info(
        "pronunciation.audio_gain_applied",
        speech_rms_dbfs=round(report.level_dbfs, 1),
        noise_floor_dbfs=_round_opt(report.noise_floor_dbfs),
        snr_db=_round_opt(report.snr_db),
        applied_gain_db=round(gain.applied_gain_db, 1),
        limited=gain.limited,
    )
    return wav_path


def transcode_and_gate(
    src_bytes: bytes,
    *,
    locale: str,
    sample_rate: int = 16_000,
    thresholds: QualityThresholds = DEFAULT_THRESHOLDS,
) -> Path:
    """Transcode an upload and run the quality gate on it, as one step.

    The single entry point every audio endpoint should use. Both halves are
    blocking (ffmpeg subprocess, then WAV decode + analysis), so callers run
    this in a threadpool rather than on the event loop.

    Raises TranscodeError / FfmpegMissingError like transcode_to_wav, and
    HTTPException 422 from the gate. The caller owns the returned path; on any
    failure here the temp WAV is unlinked before the exception leaves, so a
    rejected take can't leak a file.
    """
    wav_path = transcode_to_wav(src_bytes, sample_rate=sample_rate)
    try:
        return gate_wav_for_azure(wav_path, locale=locale, thresholds=thresholds)
    except BaseException:
        wav_path.unlink(missing_ok=True)
        raise
