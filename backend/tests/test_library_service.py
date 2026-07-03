"""curriculum.library: pick/claim/count, completion gate, pool recycle rules."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from klara.curriculum.library import (
    STORIES_TO_COMPLETE,
    advance_module_if_completed,
    claim_library_entry,
    count_available,
    library_content_hash,
    maybe_recycle_to_library,
    pick_library_entry,
    stories_finished_count,
)
from klara.curriculum.modules import load_modules
from klara.models import Module, Story, StoryLibrary, StoryView, User, UserCard, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech

CONTENT = {
    "sentences": [{"target": "Ich trinke Kaffee.", "native": "Bebo café.", "new_words": []}],
    "comprehension_questions": [],
}


async def _user(db) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"lib-{uuid.uuid4().hex[:6]}@klara.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="T",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.commit()
    return u


async def _module(db, seq: int = 1) -> Module:
    m = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=seq,
        title=f"M{seq}",
        can_dos=[],
        grammatical_focus=[],
    )
    db.add(m)
    await db.commit()
    return m


def _entry(module: Module, *, served: int = 0, hash_suffix: str = "0") -> StoryLibrary:
    return StoryLibrary(
        module_id=module.id,
        language="de",
        native_language="es",
        level=CEFRLevel.A1,
        title="T",
        content=CONTENT,
        target_vocab_item_ids=[],
        source="seed",
        content_hash=(hash_suffix * 64)[:64],
        times_served=served,
    )


@pytest.mark.asyncio
async def test_pick_prefers_least_served_and_skips_claimed(db_session):
    user = await _user(db_session)
    module = await _module(db_session)
    fresh = _entry(module, served=0, hash_suffix="a")
    worn = _entry(module, served=5, hash_suffix="b")
    db_session.add_all([fresh, worn])
    await db_session.commit()

    picked = await pick_library_entry(
        db_session, user_id=user.id, module_id=module.id, native_language="es"
    )
    assert picked is not None and picked.id == fresh.id

    story = await claim_library_entry(db_session, user=user, entry=picked, module=module)
    await db_session.commit()
    assert story.library_source_id == fresh.id
    assert story.module_id == module.id
    assert user.current_module_id == module.id
    assert fresh.times_served == 1

    # Already claimed → next pick returns the other entry; count drops to 1.
    second = await pick_library_entry(
        db_session, user_id=user.id, module_id=module.id, native_language="es"
    )
    assert second is not None and second.id == worn.id
    assert await count_available(
        db_session, user_id=user.id, module_id=module.id, native_language="es"
    ) == 1


@pytest.mark.asyncio
async def test_completion_gate_advances_pointer(db_session):
    user = await _user(db_session)
    m1 = await _module(db_session, seq=1)
    m2 = await _module(db_session, seq=2)
    user.current_module_id = m1.id
    for i in range(STORIES_TO_COMPLETE):
        s = Story(
            user_id=user.id,
            level=CEFRLevel.A1,
            target_language="de",
            native_language="es",
            title=f"S{i}",
            content=CONTENT,
            target_vocab_item_ids=[],
            module_id=m1.id,
        )
        db_session.add(s)
        await db_session.flush()
        db_session.add(
            StoryView(story_id=s.id, user_id=user.id, finished_at=datetime.now(UTC))
        )
    await db_session.commit()

    assert await stories_finished_count(db_session, user_id=user.id, module_id=m1.id) == 3
    assert await advance_module_if_completed(db_session, user=user) is True
    assert user.current_module_id == m2.id
    # Idempotent / forward-only: m2 has no finished stories → no advance.
    assert await advance_module_if_completed(db_session, user=user) is False


@pytest.mark.asyncio
async def test_claim_enrolls_only_module_vocab(db_session):
    user = await _user(db_session)
    # Seed the module + its vocab via the real loader (same path prod uses).
    await load_modules(
        db_session,
        language="de",
        modules=[
            {
                "sequence_order": 1,
                "title": "En el café",
                "cefr_level": "A1",
                "can_dos": [],
                "grammatical_focus": [],
                "vocab": [
                    {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translations": {"es": "café"}}
                ],
            }
        ],
    )
    await db_session.commit()
    module = (
        await db_session.execute(
            select(Module).where(Module.language == "de", Module.sequence_order == 1)
        )
    ).scalar_one()
    kaffee_id = (
        await db_session.execute(
            select(VocabItem.id).where(VocabItem.lemma == "Kaffee", VocabItem.language == "de")
        )
    ).scalar_one()
    # A vocab item that exists but is NOT in the module. Unique lemma: the
    # vocab_items table isn't truncated between tests.
    outsider = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"out-{uuid.uuid4().hex[:6]}", pos=PartOfSpeech.NOUN
    )
    db_session.add(outsider)
    entry = _entry(module, hash_suffix="c")
    entry.target_vocab_item_ids = [kaffee_id, outsider.id]
    db_session.add(entry)
    await db_session.commit()

    story = await claim_library_entry(db_session, user=user, entry=entry, module=module)
    await db_session.commit()

    # Clone is faithful: the story keeps BOTH ids...
    assert set(story.target_vocab_item_ids) == {kaffee_id, outsider.id}
    # ...but enrollment is intersected with the module's vocab.
    enrolled = set(
        (
            await db_session.execute(
                select(UserCard.vocab_item_id).where(UserCard.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert kaffee_id in enrolled
    assert outsider.id not in enrolled


@pytest.mark.asyncio
async def test_advance_stays_on_last_module(db_session):
    user = await _user(db_session)
    m1 = await _module(db_session, seq=1)  # the only module
    user.current_module_id = m1.id
    for i in range(STORIES_TO_COMPLETE):
        s = Story(
            user_id=user.id,
            level=CEFRLevel.A1,
            target_language="de",
            native_language="es",
            title=f"L{i}",
            content=CONTENT,
            target_vocab_item_ids=[],
            module_id=m1.id,
        )
        db_session.add(s)
        await db_session.flush()
        db_session.add(
            StoryView(story_id=s.id, user_id=user.id, finished_at=datetime.now(UTC))
        )
    await db_session.commit()

    # Gate is met but there is no next module → no advance, pointer stays.
    assert await advance_module_if_completed(db_session, user=user) is False
    assert user.current_module_id == m1.id


@pytest.mark.asyncio
async def test_pool_recycle_rules(db_session):
    user = await _user(db_session)
    module = await _module(db_session)
    story = Story(
        user_id=user.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="P",
        content=CONTENT,
        target_vocab_item_ids=[],
        module_id=module.id,
    )
    db_session.add(story)
    await db_session.commit()

    # free topic → rejected
    assert await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=[], topic="mi perra Luna", topic_origin="free"
    ) is False
    # dropped lemmas → rejected
    assert await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=["Zucker"], topic=None, topic_origin="none"
    ) is False
    # clean → accepted once, hash-deduped after
    assert await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=[], topic=None, topic_origin="none"
    ) is True
    await db_session.commit()
    assert await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=[], topic=None, topic_origin="none"
    ) is False


def test_content_hash_is_stable_and_target_only():
    h1 = library_content_hash(CONTENT)
    h2 = library_content_hash(
        {"sentences": [{"target": "Ich trinke Kaffee.", "native": "OTRA traducción", "new_words": []}]}
    )
    assert h1 == h2
    assert len(h1) == 64
