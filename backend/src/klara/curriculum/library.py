"""Story library: shared per-module catalog served by copy-on-claim, the
completar gate (finished stories), and pool recycling (spec 2026-07-03)."""

from __future__ import annotations

import hashlib
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.modules import enroll_cards, module_vocab_ids
from klara.models import Module, Story, StoryLibrary, StoryView, User

log = structlog.get_logger(__name__)

# Fast gate: N finished stories complete a module (the slow SRS "dominar" gate
# in modules.advance_module_if_mastered stays untouched). ponytail: constant,
# promote to a Module column if per-module tuning is ever needed.
STORIES_TO_COMPLETE = 3
POOL_CAP_PER_PAIR = 50


def library_content_hash(content: dict) -> str:
    """Dedup key: target-language sentence texts only (translations vary per
    native language pair without changing what the learner reads)."""
    targets = [(s.get("target") or "").strip() for s in (content.get("sentences") or [])]
    return hashlib.sha256("\n".join(targets).encode("utf-8")).hexdigest()


def _claimed_by_user(user_id: UUID):
    return select(Story.library_source_id).where(
        Story.user_id == user_id, Story.library_source_id.is_not(None)
    )


async def pick_library_entry(
    db: AsyncSession, *, user_id: UUID, module_id: UUID, native_language: str
) -> StoryLibrary | None:
    """Least-served active entry the user hasn't claimed; ties → oldest."""
    stmt = (
        select(StoryLibrary)
        .where(
            StoryLibrary.module_id == module_id,
            StoryLibrary.native_language == native_language,
            StoryLibrary.is_active.is_(True),
            StoryLibrary.id.not_in(_claimed_by_user(user_id)),
        )
        .order_by(StoryLibrary.times_served.asc(), StoryLibrary.created_at.asc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def count_available(
    db: AsyncSession, *, user_id: UUID, module_id: UUID, native_language: str
) -> int:
    stmt = (
        select(func.count())
        .select_from(StoryLibrary)
        .where(
            StoryLibrary.module_id == module_id,
            StoryLibrary.native_language == native_language,
            StoryLibrary.is_active.is_(True),
            StoryLibrary.id.not_in(_claimed_by_user(user_id)),
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def claim_library_entry(
    db: AsyncSession, *, user: User, entry: StoryLibrary, module: Module
) -> Story:
    """Clone the entry into the user's stories (copy-on-claim: every downstream
    flow works on a normal owned story), enroll module vocab, move the pointer.
    Caller commits."""
    story = Story(
        user_id=user.id,
        level=entry.level,
        target_language=entry.language,
        native_language=entry.native_language,
        title=entry.title,
        content=entry.content,
        target_vocab_item_ids=list(entry.target_vocab_item_ids or []),
        generated_by_provider=entry.generated_by_provider,
        generated_by_model=entry.generated_by_model,
        # The claimer didn't pay a generation — cost stays on the library row.
        generation_cost_usd=None,
        quiz_items=entry.quiz_items,
        insight_title=entry.insight_title,
        insight_body=entry.insight_body,
        module_id=module.id,
        library_source_id=entry.id,
    )
    db.add(story)
    entry.times_served += 1
    # Starting a story in module M moves the pointer to M (gated-suave skip and
    # replay are the same gesture; the gates push forward from wherever it is).
    user.current_module_id = module.id
    mod_vids = await module_vocab_ids(db, module)
    enrolled = [vid for vid in (entry.target_vocab_item_ids or []) if vid in mod_vids]
    await enroll_cards(db, user_id=user.id, vocab_item_ids=enrolled)
    await db.flush()
    await db.refresh(story)
    return story


async def stories_finished_count(db: AsyncSession, *, user_id: UUID, module_id: UUID) -> int:
    stmt = (
        select(func.count(func.distinct(Story.id)))
        .select_from(Story)
        .join(StoryView, (StoryView.story_id == Story.id) & (StoryView.user_id == user_id))
        .where(
            Story.user_id == user_id,
            Story.module_id == module_id,
            StoryView.finished_at.is_not(None),
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def advance_module_if_completed(db: AsyncSession, *, user: User) -> bool:
    """Completar gate: N finished stories in the ACTIVE module advance the
    pointer to the next sequence_order. Forward-only. Caller commits."""
    if user.current_module_id is None:
        return False
    module = await db.get(Module, user.current_module_id)
    if module is None or module.language != user.target_language:
        return False
    finished = await stories_finished_count(db, user_id=user.id, module_id=module.id)
    if finished < STORIES_TO_COMPLETE:
        return False
    nxt = (
        await db.execute(
            select(Module)
            .where(
                Module.language == user.target_language,
                Module.sequence_order > module.sequence_order,
            )
            .order_by(Module.sequence_order.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if nxt is None:
        return False  # last module — stay
    user.current_module_id = nxt.id
    await db.flush()
    return True


async def maybe_recycle_to_library(
    db: AsyncSession,
    *,
    story: Story,
    dropped_lemmas: list[str],
    topic: str | None,
    topic_origin: str,
) -> bool:
    """Pool growth: copy a clean live generation into the library. Rules
    (spec §7): no free-text topics (privacy), full coverage only (quality),
    module-conditioned only, hash-deduped, capped per (module, native).
    Best-effort — callers must never let a failure here break story creation."""
    if story.module_id is None or dropped_lemmas:
        return False
    # Fail closed on provenance (privacy, spec §7): a present topic is only
    # shareable when the client explicitly marked it as a suggestion chip.
    # "none" is trusted only for surprise-me (no topic) generations.
    if topic_origin != "chip" and topic is not None:
        return False
    content = story.content or {}
    h = library_content_hash(content)
    exists = (
        await db.execute(select(StoryLibrary.id).where(StoryLibrary.content_hash == h))
    ).first()
    if exists is not None:
        return False
    n = (
        await db.execute(
            select(func.count())
            .select_from(StoryLibrary)
            .where(
                StoryLibrary.module_id == story.module_id,
                StoryLibrary.native_language == story.native_language,
                StoryLibrary.is_active.is_(True),
            )
        )
    ).scalar_one()
    if n >= POOL_CAP_PER_PAIR:
        return False
    # Secure everything already pending at the OUTER transaction level, so the
    # savepoint rollback below can only ever undo the pool insert — never the
    # caller's story/pointer writes (which would otherwise flush inside the
    # savepoint and be lost with it). No-op when autoflush already ran.
    await db.flush()
    # A concurrent request can commit the same content_hash between the
    # precheck above and this INSERT; the SAVEPOINT confines the unique
    # violation so the caller's transaction stays healthy (a poisoned session
    # would turn the endpoint's commit into PendingRollbackError → 500).
    try:
        async with db.begin_nested():
            db.add(
                StoryLibrary(
                    module_id=story.module_id,
                    language=story.target_language,
                    native_language=story.native_language,
                    level=story.level,
                    title=story.title,
                    content=content,
                    target_vocab_item_ids=list(story.target_vocab_item_ids or []),
                    quiz_items=story.quiz_items,
                    insight_title=story.insight_title,
                    insight_body=story.insight_body,
                    topic=topic,
                    source="pool",
                    source_story_id=story.id,
                    content_hash=h,
                    generated_by_provider=story.generated_by_provider,
                    generated_by_model=story.generated_by_model,
                    generation_cost_usd=story.generation_cost_usd,
                )
            )
            # flush happens on savepoint exit
    except IntegrityError:
        log.info("library.pool.hash_race", story_id=str(story.id))
        return False
    log.info("library.pool.recycled", story_id=str(story.id), module_id=str(story.module_id))
    return True
