"""El día de Hoy (spec 2026-09-30 §2.2): qué paradas están hechas desde `since`,
cuál sigue y con qué historia. Solo lee, y todo sale de tablas que ya existen."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.library import pick_library_entry
from klara.curriculum.modules import read_active_module
from klara.models import (
    Illustration,
    Module,
    PronunciationAttempt,
    Review,
    SpeakTurn,
    Story,
    StoryView,
    User,
    UserCard,
)
from klara.schemas.today import TodayModule, TodayOut, TodaySentence, TodaySteps, TodayStory
from klara.services.illustration import illustration_hash, illustration_path, normalize_scene

ORDER = ("read", "pronounce", "speak", "review")


async def _hay(db: AsyncSession, stmt) -> bool:
    return bool((await db.execute(select(exists(stmt)))).scalar())


async def _illustration_for(db: AsyncSession, scene: str | None) -> str | None:
    if not normalize_scene(scene):
        return None
    h = illustration_hash(scene)
    found = (await db.execute(select(Illustration.hash).where(Illustration.hash == h))).first()
    return illustration_path(h) if found else None


def _first_sentence(content: dict | None) -> TodaySentence | None:
    for s in (content or {}).get("sentences") or []:
        target = (s.get("target") or "").strip()
        native = (s.get("native") or "").strip()
        if target and native:
            return TodaySentence(target=target, native=native)
    return None


async def _from_story(db: AsyncSession, story: Story, state: str) -> TodayStory:
    return TodayStory(
        state=state,
        id=story.id,
        module_id=story.module_id,
        title=story.title,
        subtitle=story.subtitle,
        illustration_path=await _illustration_for(db, story.scene),
    )


async def _story_of_the_day(
    db: AsyncSession,
    user: User,
    *,
    read_done: bool,
    last_finished: Story | None,
    module: Module | None,
) -> TodayStory:
    # 1. La historia terminada hoy.
    if read_done and last_finished is not None:
        return await _from_story(db, last_finished, "done")
    # 2. La más reciente, si no está terminada. Solo esa: una vieja abandonada no vuelve.
    latest = (
        await db.execute(
            select(Story).where(Story.user_id == user.id).order_by(Story.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if latest is not None and not await _hay(
        db,
        select(StoryView.id).where(
            StoryView.story_id == latest.id, StoryView.finished_at.is_not(None)
        ),
    ):
        return await _from_story(db, latest, "continue")
    # 3. La próxima de la biblioteca del módulo activo, sin reclamarla.
    if module is not None:
        entry = await pick_library_entry(
            db, user_id=user.id, module_id=module.id, native_language=user.native_language
        )
        if entry is not None:
            return TodayStory(
                state="new",
                library_entry_id=entry.id,
                module_id=module.id,
                title=entry.title,
                subtitle=entry.subtitle,
                illustration_path=await _illustration_for(db, entry.scene),
            )
    # 4. Nada que proponer: que se la pida a Klara.
    return TodayStory(state="request")


async def build_today(
    db: AsyncSession, user: User, *, since: datetime, now: datetime | None = None
) -> TodayOut:
    now = now or datetime.now(UTC)
    due = (
        await db.execute(
            select(func.count())
            .select_from(UserCard)
            .where(
                UserCard.user_id == user.id,
                or_(UserCard.next_review_at.is_(None), UserCard.next_review_at <= now),
            )
        )
    ).scalar_one()
    last_view = (
        await db.execute(
            select(StoryView)
            .where(StoryView.user_id == user.id, StoryView.finished_at.is_not(None))
            .order_by(StoryView.finished_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_finished = await db.get(Story, last_view.story_id) if last_view else None

    steps = TodaySteps(
        read=last_view is not None and last_view.finished_at >= since,
        pronounce=await _hay(
            db,
            select(PronunciationAttempt.id).where(
                PronunciationAttempt.user_id == user.id,
                PronunciationAttempt.attempted_at >= since,
            ),
        ),
        speak=await _hay(
            db,
            select(SpeakTurn.id).where(SpeakTurn.user_id == user.id, SpeakTurn.created_at >= since),
        ),
        # Solo el canal "recall": la práctica de pronunciación también escribe reviews.
        review=due == 0
        or await _hay(
            db,
            select(Review.id).where(
                Review.user_id == user.id,
                Review.channel == "recall",
                Review.reviewed_at >= since,
            ),
        ),
    )
    module = await read_active_module(db, user)
    return TodayOut(
        now=next((s for s in ORDER if not getattr(steps, s)), None),
        steps=steps,
        story=await _story_of_the_day(
            db, user, read_done=steps.read, last_finished=last_finished, module=module
        ),
        sentence=_first_sentence(last_finished.content) if last_finished else None,
        due=due,
        module=TodayModule(id=module.id, title=module.title, cefr_level=module.cefr_level.value)
        if module
        else None,
    )
