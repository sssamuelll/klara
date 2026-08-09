"""Persist one scored Speak turn (#127, D-K clause 2026-08-09).

The per-turn assessment is the learner's longitudinal signal; before this it
was computed in memory and thrown away with the response. It must not die
with the request — and must not kill it either: a failed insert logs and the
scored turn ships anyway (same degradation philosophy as the LLM fallback,
spec review F14).
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import SpeakTurn
from klara.models.user import User
from klara.pronunciation.schemas import PronunciationScores
from klara.services.speak_analysis import TurnAnalysis

log = structlog.get_logger(__name__)


def parse_session_id(raw: str | None) -> uuid.UUID:
    """Client-generated session UUID; a fresh one when missing or invalid so
    old clients degrade to per-turn groups instead of losing the signal."""
    try:
        return uuid.UUID(raw or "")
    except ValueError:
        return uuid.uuid4()


async def record_turn(
    db: AsyncSession,
    user: User,
    *,
    client_session_id: uuid.UUID,
    language: str,
    focus_sound: str,
    recognized_text: str,
    analysis: TurnAnalysis,
    scores: PronunciationScores,
    retry_word: str | None,
) -> None:
    """Commits its own row. Never raises — the turn response has priority."""
    try:
        turn_index = (
            await db.execute(
                select(func.count())
                .select_from(SpeakTurn)
                .where(
                    SpeakTurn.user_id == user.id,
                    SpeakTurn.client_session_id == client_session_id,
                )
            )
        ).scalar_one()
        db.add(
            SpeakTurn(
                user_id=user.id,
                client_session_id=client_session_id,
                turn_index=turn_index,
                language=language,
                focus_sound=focus_sound,
                recognized_text=recognized_text,
                tokens=[{"t": tk.t, "s": tk.s, "focus": tk.focus} for tk in analysis.tokens],
                target=(
                    {
                        "word": analysis.target.word,
                        "focus_accuracy": analysis.target.focus_accuracy,
                        "should_ipa": analysis.target.should_ipa,
                    }
                    if analysis.target
                    else None
                ),
                scores={
                    "accuracy": scores.accuracy,
                    "fluency": scores.fluency,
                    "pronunciation": scores.pronunciation,
                },
                focus_hit=analysis.focus_hit,
                focus_clear=analysis.focus_clear,
                retry_word=retry_word,
            )
        )
        await db.commit()
    except Exception:
        log.exception("speak.turn_persist_failed", user_id=str(user.id))
        await db.rollback()
