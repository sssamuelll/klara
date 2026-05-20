"""Transcoding helper: any browser-recordable audio → WAV PCM 16 kHz mono.

Azure Pronunciation Assessment requires WAV; browsers tend to send webm/opus
or ogg. Subprocess-shells out to ffmpeg, which the backend image installs.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class TranscodeError(RuntimeError):
    """ffmpeg could not decode the audio."""


class FfmpegMissingError(RuntimeError):
    """ffmpeg binary is not available in the container's PATH."""


def transcode_to_wav(src_bytes: bytes, *, sample_rate: int = 16_000) -> Path:
    """Returns a path to a temp .wav file. Caller is responsible for unlinking."""
    src = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
    src.write(src_bytes)
    src.close()
    dst = Path(src.name).with_suffix(".wav")
    try:
        # -acodec pcm_s16le: Azure pronunciation assessment expects signed
        #   16-bit little-endian PCM. ffmpeg usually defaults to this for the
        #   wav muxer but the default depends on the build, so we pin it.
        # -af highpass=f=80: filter out sub-voice hum (fans, AC, 60Hz mains)
        #   without touching the human voice band (~85Hz and up). Cleaner
        #   signal → fewer phantom phonemes and better accuracy scores.
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                src.name,
                "-ar",
                str(sample_rate),
                "-ac",
                "1",
                "-acodec",
                "pcm_s16le",
                "-af",
                "highpass=f=80",
                "-f",
                "wav",
                str(dst),
            ],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as e:
        raise FfmpegMissingError("ffmpeg is not installed in the server PATH.") from e
    except subprocess.CalledProcessError as e:
        msg = e.stderr.decode(errors="ignore")[:300] if e.stderr else "ffmpeg error"
        raise TranscodeError(msg) from e
    finally:
        Path(src.name).unlink(missing_ok=True)
    return dst
