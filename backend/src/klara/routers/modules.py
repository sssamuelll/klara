from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from klara.curriculum.competence import module_gender_progress, module_progress
from klara.curriculum.library import (
    STORIES_TO_COMPLETE,
    claim_library_entry,
    count_available,
    pick_library_entry,
    stories_finished_count,
)
from klara.curriculum.modules import read_active_module
from klara.dependencies import CurrentUser, DBSession
from klara.models import Module
from klara.routers.stories import _load_words, _serialize_story
from klara.schemas.module import ModuleCurrentOut, ModulePathItemOut
from klara.schemas.story import StoryOut

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("/current", response_model=ModuleCurrentOut | None)
async def get_current_module(db: DBSession, user: CurrentUser) -> ModuleCurrentOut | None:
    """The user's active module + progress, or null if none is active yet
    (fresh account / unseeded DB). Read-only: never initializes the pointer."""
    module = await read_active_module(db, user)
    if module is None:
        return None
    encountered, mastered, total = await module_progress(db, user_id=user.id, module_id=module.id)
    g_enc, g_mast, g_total = await module_gender_progress(db, user_id=user.id, module_id=module.id)
    return ModuleCurrentOut(
        id=module.id,
        title=module.title,
        cefr_level=module.cefr_level,
        can_dos=module.can_dos or [],
        grammatical_focus=module.grammatical_focus or [],
        encountered=encountered,
        mastered=mastered,
        total=total,
        gender_encountered=g_enc,
        gender_mastered=g_mast,
        gender_total=g_total,
    )


@router.get("", response_model=list[ModulePathItemOut])
async def list_modules(db: DBSession, user: CurrentUser) -> list[ModulePathItemOut]:
    """The full path for the user's target language, ordered. Locked/completed
    are derived on read — no completion-history table (accepted debt, spec §5).
    ponytail: ~5 queries per module x 8 modules; fine at this scale, batch if a
    language ever ships 50 modules."""
    modules = (
        (
            await db.execute(
                select(Module)
                .where(Module.language == user.target_language)
                .order_by(Module.sequence_order.asc())
            )
        )
        .scalars()
        .all()
    )
    active = await read_active_module(db, user)
    out: list[ModulePathItemOut] = []
    prev_completed = True  # first module is always unlocked
    for m in modules:
        encountered, mastered, total = await module_progress(db, user_id=user.id, module_id=m.id)
        g_enc, g_mast, g_total = await module_gender_progress(db, user_id=user.id, module_id=m.id)
        finished = await stories_finished_count(db, user_id=user.id, module_id=m.id)
        completed = finished >= STORIES_TO_COMPLETE
        unlocked = prev_completed or (active is not None and m.sequence_order <= active.sequence_order)
        available = await count_available(
            db, user_id=user.id, module_id=m.id, native_language=user.native_language
        )
        out.append(
            ModulePathItemOut(
                id=m.id,
                sequence_order=m.sequence_order,
                title=m.title,
                cefr_level=m.cefr_level,
                can_dos=m.can_dos or [],
                grammatical_focus=m.grammatical_focus or [],
                encountered=encountered,
                mastered=mastered,
                total=total,
                gender_encountered=g_enc,
                gender_mastered=g_mast,
                gender_total=g_total,
                stories_finished=finished,
                stories_to_complete=STORIES_TO_COMPLETE,
                completed=completed,
                is_current=active is not None and m.id == active.id,
                unlocked=unlocked,
                library_available=available,
            )
        )
        prev_completed = completed
    return out


@router.post("/{module_id}/story", response_model=StoryOut, status_code=status.HTTP_201_CREATED)
async def claim_module_story(module_id: UUID, db: DBSession, user: CurrentUser) -> StoryOut:
    """Instant story: clone the next unseen library entry for this module into
    the user's stories. No LLM in this path — milliseconds, audio already warm
    from library-build precache. detail codes ('module.not_found',
    'library.empty') are contracts with the frontend, not display strings."""
    module = await db.get(Module, module_id)
    if module is None or module.language != user.target_language:
        raise HTTPException(status_code=404, detail="module.not_found")
    entry = await pick_library_entry(
        db, user_id=user.id, module_id=module.id, native_language=user.native_language
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="library.empty")
    story = await claim_library_entry(db, user=user, entry=entry, module=module)
    await db.commit()
    words = await _load_words(db, list(story.target_vocab_item_ids or []))
    return _serialize_story(story, words, user.native_language)
