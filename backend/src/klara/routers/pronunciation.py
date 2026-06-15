"""POST /api/v1/pronunciation/score — wraps Azure Pronunciation Assessment.

Auth-gated. Audio comes in as multipart (any browser-encoded format),
gets transcoded to WAV via ffmpeg, then evaluated against `reference_text`.
Response carries per-word and per-phoneme scores so the UI can highlight
mispronounced parts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from klara.dependencies import ChatLLM, CurrentUser, LocaleDep, SettingsDep
from klara.i18n import t
from klara.i18n.languages import SUPPORTED_LANGUAGES, speech_locale
from klara.pronunciation.audio import (
    FfmpegMissingError,
    TranscodeError,
    transcode_to_wav,
)
from klara.pronunciation.azure_client import AzureSpeechError, score_pronunciation
from klara.pronunciation.schemas import (
    PhoneticHintsRequest,
    PhoneticHintsResponse,
    ScoreResponse,
)
from klara.services.phonetic_hints import generate_phonetic_hints

router = APIRouter(prefix="/pronunciation", tags=["pronunciation"])

log = structlog.get_logger(__name__)


def _resolve_bcp47(raw: str) -> str:
    """Accept either a BCP-47 tag ('de-DE') or a short code ('de')."""
    if "-" in raw:
        return raw
    if raw in SUPPORTED_LANGUAGES:
        return speech_locale(raw)
    return raw


AudioUpload = Annotated[UploadFile, File(description="User audio (webm/ogg/wav/mp3/m4a).")]
RefTextForm = Annotated[str, Form(description="Sentence the user was asked to say.")]
LanguageForm = Annotated[
    str,
    Form(description="BCP-47 tag (de-DE, en-US, …) or short code (de, en)."),
]


@router.post("/score", response_model=ScoreResponse)
async def score(
    user: CurrentUser,
    settings: SettingsDep,
    locale: LocaleDep,
    audio: AudioUpload,
    reference_text: RefTextForm,
    language: LanguageForm = "de-DE",
) -> ScoreResponse:
    if not settings.azure_speech_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=t("pron.unavailable", locale),
        )

    if not reference_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("pron.audio_empty", locale),
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("pron.audio_empty", locale),
        )
    if len(audio_bytes) > settings.pronunciation_max_audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=t("pron.audio_too_large", locale),
        )

    bcp47 = _resolve_bcp47(language)

    try:
        wav_path: Path = await run_in_threadpool(transcode_to_wav, audio_bytes)
    except TranscodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("pron.audio_undecodable", locale),
        ) from None
    except FfmpegMissingError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=t("pron.unavailable", locale),
        ) from None

    try:
        return await run_in_threadpool(
            score_pronunciation,
            wav_path,
            reference_text,
            bcp47,
            azure_key=settings.azure_speech_key or "",
            azure_region=settings.azure_speech_region,
        )
    except AzureSpeechError as e:
        if e.recoverable:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=t("pron.no_speech_detected", locale),
            ) from e
        # The 502 body only carries a localized user-facing message; this log
        # line is the only place Azure's CancellationDetails (auth / quota /
        # region / connectivity) ever surface. Don't drop it.
        log.error(
            "pronunciation.azure_failed",
            error=str(e),
            language=bcp47,
            region=settings.azure_speech_region,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=t("pron.upstream_error", locale),
        ) from e
    finally:
        wav_path.unlink(missing_ok=True)


@router.post("/phonetic-hints", response_model=PhoneticHintsResponse)
async def phonetic_hints(
    user: CurrentUser,
    llm: ChatLLM,
    payload: PhoneticHintsRequest,
) -> PhoneticHintsResponse:
    """Return hyphenated stress hints for a handful of mispronounced words.

    Best-effort: if the LLM call fails or returns malformed JSON, this still
    succeeds with `hints={}` so the UI can fall back to showing the verdict
    without a tip.
    """
    try:
        hints = await generate_phonetic_hints(llm, words=payload.words, language=payload.language)
    except Exception:
        hints = {}
    return PhoneticHintsResponse(hints=hints)
