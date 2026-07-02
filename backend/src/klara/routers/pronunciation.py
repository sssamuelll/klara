"""POST /api/v1/pronunciation/score — wraps Azure Pronunciation Assessment.

Auth-gated. Audio comes in as multipart (any browser-encoded format),
gets transcoded to WAV via ffmpeg, then evaluated against `reference_text`.
Response carries per-word and per-phoneme scores so the UI can highlight
mispronounced parts.
"""

from __future__ import annotations

import contextlib
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, status
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocketDisconnect

from klara.config import Settings, get_settings
from klara.dependencies import ChatLLM, CurrentUser, DBSession, LocaleDep, SettingsDep
from klara.i18n import t
from klara.i18n.languages import SUPPORTED_LANGUAGES, speech_locale
from klara.pronunciation.audio import (
    FfmpegMissingError,
    TranscodeError,
    transcode_to_wav,
)
from klara.pronunciation.azure_client import AzureSpeechError, score_pronunciation
from klara.pronunciation.azure_stream import AzureStreamingRecognizer
from klara.pronunciation.schemas import (
    DiagnoseRequest,
    DiagnoseResponse,
    PhoneticHintsRequest,
    PhoneticHintsResponse,
    PronunciationScores,
    ScoreResponse,
    WordScore,
)
from klara.pronunciation.streaming import (
    WS_CLOSE_AUTH,
    WS_CLOSE_CAPACITY,
    WS_CLOSE_FAILURE,
    WS_CLOSE_OK,
    SessionOutcome,
    StreamingSession,
)
from klara.pronunciation.ws_auth import authenticate_ws, origin_allowed
from klara.services.phonetic_hints import generate_phonetic_hints
from klara.services.pronunciation_diagnose import generate_diagnosis

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


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(
    user: CurrentUser,
    llm: ChatLLM,
    db: DBSession,
    payload: DiagnoseRequest,
) -> DiagnoseResponse:
    """Corrective tip for the single worst mispronounced word.

    Best-effort: any failure returns an empty tip so the UI keeps the
    stress hint. native_language comes from the authenticated user, never
    the request body.
    """
    try:
        return await generate_diagnosis(
            llm,
            db,
            word=payload.word,
            phonemes=payload.phonemes,
            target_language=payload.language,
            native_language=user.native_language,
        )
    except Exception:
        return DiagnoseResponse()


# --- #22 live streaming (WS /pronunciation/stream) ---------------------------
# Module-level caps (single worker, one event loop → plain ints are safe).
# ponytail: process-local counters; move to Redis if we ever run >1 worker.
_active_global = 0
_active_per_user: dict[str, int] = defaultdict(int)


class _WSAdapter:
    """Maps Starlette WebSocket to the minimal surface StreamingSession uses.

    Starlette's receive() RETURNS a websocket.disconnect message instead of
    raising; the session's receiver-error teardown expects an exception, so
    normalize disconnect into WebSocketDisconnect by design.
    """

    def __init__(self, ws: WebSocket):
        self._ws = ws

    async def send_json(self, obj: dict) -> None:
        await self._ws.send_json(obj)

    async def receive(self) -> dict:
        msg = await self._ws.receive()
        if msg["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(msg.get("code", 1006))
        return msg


def _build_stream_recognizer(
    settings: Settings, reference_text: str, language: str
) -> AzureStreamingRecognizer:
    return AzureStreamingRecognizer(
        language=_resolve_bcp47(language),
        reference_text=reference_text,
        azure_key=settings.azure_speech_key or "",
        azure_region=settings.azure_speech_region,
    )


def _session_scores(words: list[WordScore]) -> PronunciationScores:
    """v1: summarise the accumulator. Azure's session-level PronunciationScores
    are available via the last result; for v1 we average per-word accuracy and
    leave fluency/completeness to the batch floor if the client needs exactness."""
    acc = sum(w.accuracy_score for w in words) / len(words) if words else 0.0
    return PronunciationScores(accuracy=acc, fluency=acc, completeness=100.0, pronunciation=acc)


async def _safe_close(websocket: WebSocket, code: int) -> None:
    # The peer may already be gone (disconnect raced the close) — never let
    # the courtesy close mask the session outcome or leak out of the handler.
    with contextlib.suppress(Exception):
        await websocket.close(code=code)


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    global _active_global
    settings = get_settings()

    if not origin_allowed(websocket, settings):
        await websocket.close(code=WS_CLOSE_AUTH)
        return
    await websocket.accept()  # accept first so the app close code reaches the client
    user = await authenticate_ws(websocket, settings)
    if user is None:
        await _safe_close(websocket, WS_CLOSE_AUTH)
        return
    if not settings.azure_speech_configured:
        await _safe_close(websocket, WS_CLOSE_FAILURE)  # client falls back to batch
        return

    uid = str(user.id)
    if _active_global >= settings.pron_stream_global_cap or (
        _active_per_user[uid] >= settings.pron_stream_per_user_cap
    ):
        await _safe_close(websocket, WS_CLOSE_CAPACITY)
        return
    _active_global += 1
    _active_per_user[uid] += 1
    try:
        # Handshake: first client frame is JSON text {"reference_text", "language"}.
        # Consumed here, BEFORE the session starts — the only text frame the
        # session's receiver ever sees is end-of-speech.
        try:
            handshake = await websocket.receive_json()
            reference_text = handshake["reference_text"]
            language = handshake["language"]
            if not (isinstance(reference_text, str) and isinstance(language, str)):
                raise TypeError("handshake fields must be strings")
        except Exception:
            await _safe_close(websocket, WS_CLOSE_FAILURE)
            return
        recognizer = _build_stream_recognizer(settings, reference_text, language)
        outcome = await StreamingSession(
            recognizer, _WSAdapter(websocket), scores_of=_session_scores, settings=settings
        ).run()
        await _safe_close(
            websocket, WS_CLOSE_OK if outcome is SessionOutcome.COMPLETED else WS_CLOSE_FAILURE
        )
    finally:
        # Runs on EVERY exit, including CancelledError out of run() — cap
        # slots must never leak.
        _active_global -= 1
        _active_per_user[uid] -= 1
        if _active_per_user[uid] <= 0:
            _active_per_user.pop(uid, None)
