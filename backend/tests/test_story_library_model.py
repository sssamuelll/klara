"""StoryLibrary rows persist and stories accept module/library provenance."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from klara.models import Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel


async def _seed_module(db_session) -> Module:
    module = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=1,
        title="En el café",
        can_dos=["puedo pedir una bebida"],
        grammatical_focus=["género de sustantivos"],
    )
    db_session.add(module)
    await db_session.commit()
    return module


async def _seed_user(db_session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"lib-{uuid.uuid4().hex[:6]}@klara.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Test",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_story_library_roundtrip(db_session):
    module = await _seed_module(db_session)
    entry = StoryLibrary(
        module_id=module.id,
        language="de",
        native_language="es",
        level=CEFRLevel.A1,
        title="Der Kaffee",
        content={
            "sentences": [
                {"target": "Ich trinke Kaffee.", "native": "Bebo café.", "new_words": []}
            ],
            "comprehension_questions": [],
        },
        target_vocab_item_ids=[],
        topic="pedir un café",
        source="seed",
        content_hash="a" * 64,
    )
    db_session.add(entry)
    await db_session.commit()

    row = (await db_session.execute(select(StoryLibrary))).scalar_one()
    assert row.times_served == 0
    assert row.is_active is True
    assert row.source == "seed"
    assert row.module_id == module.id


@pytest.mark.asyncio
async def test_story_accepts_module_and_library_provenance(db_session):
    module = await _seed_module(db_session)
    user = await _seed_user(db_session)
    story = Story(
        user_id=user.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="Test",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[],
        module_id=module.id,
        library_source_id=None,
    )
    db_session.add(story)
    await db_session.commit()
    await db_session.refresh(story)
    assert story.module_id == module.id
    assert story.library_source_id is None
