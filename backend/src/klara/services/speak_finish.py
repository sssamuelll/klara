"""Close the Speak → Practice circle.

Words the learner struggled with go into the SRS as VocabItem + UserCard so
they surface in GET /practice/queue (reason "review") with zero queue-builder
changes. The session itself persists as one StudySession row (type CHAT) —
the only data source a future weak-phoneme scheduler will have.

Trust model (spec review F2/F13): the words arrive from the client, so this
service NEVER overwrites existing shared vocab content — `vocab_items` is a
global table other users' practice queues read drill material from.
- Existing row (matched by lemma, case-insensitive, ANY pos — Speak words are
  surface forms with pos unknown; inserting pos=OTHER next to a story-gen
  pos=NOUN row would give the learner duplicate cards forever): reuse it,
  filling ONLY empty fields.
- No row and no model sentence: SKIP — the practice queue silently drops
  vocab without example_target (practice_queue.py), so the card would be a
  dead row pretending the hand-off worked.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import StudySession, UserCard, VocabItem
from klara.models.enums import SessionType
from klara.models.user import User

log = structlog.get_logger(__name__)


@dataclass
class FinishWord:
    word: str
    gloss: str | None
    model_sentence: str | None


async def record_speak_session(
    db: AsyncSession,
    user: User,
    *,
    language: str,
    focus_sound: str,
    clear_count: int,
    total_count: int,
    duration_seconds: int,
    words: list[FinishWord],
) -> tuple[int, int]:
    """Returns (added, skipped). Commits once."""
    added = 0
    skipped = 0
    attached: set = set()

    for entry in words:
        vocab_id = await _resolve_vocab_id(db, entry, language=language, user=user)
        if vocab_id is None or vocab_id in attached:
            skipped += 1
            continue
        card_stmt = (
            pg_insert(UserCard)
            .values(user_id=user.id, vocab_item_id=vocab_id)
            .on_conflict_do_nothing(constraint="uq_user_card_user_vocab")
        )
        await db.execute(card_stmt)
        attached.add(vocab_id)
        # A conflict means the user ALREADY has a card for this word — it is
        # in their practice deck either way, which is what `added` reports to
        # the summary ("vuelven a Práctica"), not raw row inserts.
        added += 1

    now = datetime.now(UTC)
    db.add(
        StudySession(
            user_id=user.id,
            session_type=SessionType.CHAT,
            started_at=now - timedelta(seconds=duration_seconds),
            ended_at=now,
            wins={
                "focus_sound": focus_sound,
                "clear_count": clear_count,
                "total_count": total_count,
                "duration_seconds": duration_seconds,
                "words": [w.word for w in words],
            },
        )
    )
    await db.commit()
    log.info(
        "speak.session_recorded",
        user_id=str(user.id),
        focus_sound=focus_sound,
        added=added,
        skipped=skipped,
    )
    return added, skipped


async def _resolve_vocab_id(
    db: AsyncSession,
    entry: FinishWord,
    *,
    language: str,
    user: User,
) -> object | None:
    existing = (
        await db.execute(
            select(VocabItem)
            .where(
                func.lower(VocabItem.lemma) == entry.word.lower(),
                VocabItem.language == language,
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing is not None:
        # Fill ONLY empty fields — never clobber story-gen content.
        if not existing.example_target and entry.model_sentence:
            existing.example_target = entry.model_sentence
        if entry.gloss and not (existing.translations or {}).get(user.native_language):
            existing.translations = {
                **(existing.translations or {}),
                user.native_language: entry.gloss,
            }
        return existing.id

    if not entry.model_sentence:
        return None

    item = VocabItem(
        lemma=entry.word,
        language=language,
        example_target=entry.model_sentence,
        translations={user.native_language: entry.gloss} if entry.gloss else {},
        cefr_level=user.level,
    )
    db.add(item)
    await db.flush()
    return item.id
