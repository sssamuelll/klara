"""Speak — pronunciation-oriented voice conversation.

POST /speak/turn   : one full turn — unscripted assessment + Klara's reply.
POST /speak/finish : close the session — struggled words → SRS, session row.

The correction shown to the user comes from the assessment (speak_analysis);
the LLM only continues the conversation. An LLM failure degrades to
reply=null — the user's scored turn always survives (spec review F14).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from klara.dependencies import ChatLLM, CurrentUser, DBSession, LocaleDep, SettingsDep
from klara.i18n import t
from klara.i18n.languages import speech_locale
from klara.pronunciation.audio import (
    FfmpegMissingError,
    TranscodeError,
    transcode_to_wav,
)
from klara.pronunciation.azure_client import AzureSpeechError, score_unscripted
from klara.schemas.speak import (
    SpeakFinishIn,
    SpeakFinishOut,
    SpeakReplyOut,
    SpeakScoresOut,
    SpeakTargetOut,
    SpeakTokenOut,
    SpeakTurnOut,
)
from klara.services.speak_analysis import FOCUS_PHONEME_SETS, analyze_turn
from klara.services.speak_chat import generate_reply
from klara.services.speak_finish import FinishWord, record_speak_session
from klara.services.tts_precache import precache_texts

router = APIRouter(prefix="/speak", tags=["speak"])

log = structlog.get_logger(__name__)

#: Below this NBest confidence the transcript is likely fabricated (mixed
#: language, mumbling) — scoring a hallucination against itself looks
#: confident and is dishonest. The client shows a gentle retry instead.
LOW_CONFIDENCE_THRESHOLD = 0.5

MAX_HISTORY_TURNS = 8
MAX_HISTORY_CHARS = 300

AudioUpload = Annotated[UploadFile, File(description="User audio (webm/ogg/wav/mp3/m4a).")]


def _short_language(raw: str) -> str:
    return raw.split("-", 1)[0].lower()


def _parse_history(raw: str) -> list[dict]:
    """Client-supplied conversation context: clamp hard, never trust size."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    turns: list[dict] = []
    for item in data[-MAX_HISTORY_TURNS:]:
        if not isinstance(item, dict):
            continue
        who = "klara" if item.get("who") == "klara" else "you"
        text = str(item.get("text", ""))[:MAX_HISTORY_CHARS]
        if text:
            turns.append({"who": who, "text": text})
    return turns


@router.post("/turn", response_model=SpeakTurnOut, response_model_by_alias=True)
async def speak_turn(
    user: CurrentUser,
    db: DBSession,
    settings: SettingsDep,
    locale: LocaleDep,
    llm: ChatLLM,
    background: BackgroundTasks,
    audio: AudioUpload,
    language: Annotated[str, Form()] = "de",
    focus_sound: Annotated[str, Form(max_length=8)] = "ü",
    focus_examples: Annotated[str, Form(max_length=200)] = "",
    history: Annotated[str, Form(max_length=8000)] = "[]",
    retry_word: Annotated[str | None, Form(max_length=40)] = None,
) -> SpeakTurnOut:
    if not settings.azure_speech_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=t("pron.unavailable", locale),
        )

    short_lang = _short_language(language)
    focus_phonemes = FOCUS_PHONEME_SETS.get(short_lang)
    if focus_phonemes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("speak.language_unsupported", locale),
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
        score, confidence = await run_in_threadpool(
            score_unscripted,
            wav_path,
            speech_locale(short_lang),
            azure_key=settings.azure_speech_key or "",
            azure_region=settings.azure_speech_region,
        )
    except AzureSpeechError as e:
        if e.recoverable:
            # Breath, background noise, nothing recognizable: a gentle retry,
            # not an error (resolve-mc precedent).
            return SpeakTurnOut(no_speech=True)
        log.error(
            "speak.azure_failed",
            error=str(e),
            language=short_lang,
            region=settings.azure_speech_region,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=t("pron.upstream_error", locale),
        ) from e
    finally:
        wav_path.unlink(missing_ok=True)

    # Azure can return RecognizedSpeech with empty text (a breath) — same
    # user experience as NoMatch (runtime review B4).
    if not score.recognized_text.strip() or not score.words:
        return SpeakTurnOut(no_speech=True)

    analysis = analyze_turn(score, focus_phonemes)
    tokens = [SpeakTokenOut(t=tk.t, s=tk.s, focus=tk.focus) for tk in analysis.tokens]
    scores = SpeakScoresOut(
        accuracy=score.scores.accuracy,
        fluency=score.scores.fluency,
        pronunciation=score.scores.pronunciation,
    )

    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        # The transcript is probably fabricated; don't converse over it and
        # don't dress it up as a correction.
        return SpeakTurnOut(
            low_confidence=True,
            recognized_text=score.recognized_text,
            tokens=tokens,
            scores=scores,
        )

    examples = [w.strip() for w in focus_examples.split(",") if w.strip()][:6]
    reply = await generate_reply(
        llm,
        target_language=short_lang,
        native_language=user.native_language,
        level=user.level.value,
        focus_sound=focus_sound,
        focus_examples=examples,
        recognized_text=score.recognized_text,
        history=_parse_history(history),
        focus_clear=analysis.focus_clear,
        target_word=analysis.target.word if analysis.target else None,
        retry_word=retry_word,
    )

    target = None
    if analysis.target is not None:
        target = SpeakTargetOut(
            word=analysis.target.word,
            gloss=reply.target_word_gloss if reply else None,
            focus_accuracy=analysis.target.focus_accuracy,
            should_ipa=analysis.target.should_ipa,
            model_sentence=reply.target_word_sentence if reply else None,
        )

    if reply is not None:
        background.add_task(precache_texts, settings, [reply.reply_target], short_lang)

    return SpeakTurnOut(
        recognized_text=score.recognized_text,
        tokens=tokens,
        scores=scores,
        target=target,
        focus_hit=analysis.focus_hit,
        focus_clear=analysis.focus_clear,
        reply=(
            SpeakReplyOut(target=reply.reply_target, native=reply.reply_native) if reply else None
        ),
    )


@router.post("/finish", response_model=SpeakFinishOut)
async def speak_finish(
    payload: SpeakFinishIn,
    user: CurrentUser,
    db: DBSession,
    locale: LocaleDep,
) -> SpeakFinishOut:
    short_lang = _short_language(payload.language)
    if short_lang != user.target_language:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("speak.language_unsupported", locale),
        )

    added, skipped = await record_speak_session(
        db,
        user,
        language=short_lang,
        focus_sound=payload.focus_sound,
        clear_count=payload.clear_count,
        total_count=payload.total_count,
        duration_seconds=payload.duration_seconds,
        words=[
            FinishWord(word=w.word, gloss=w.gloss, model_sentence=w.model_sentence)
            for w in payload.words
        ],
    )
    return SpeakFinishOut(added=added, skipped=skipped)
