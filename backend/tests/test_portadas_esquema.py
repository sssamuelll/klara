"""Esquema de las portadas (spec §3.1-3.2): subtítulo y escena en historias y
biblioteca, y la tabla de ilustraciones con su hash único."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from klara.models import Illustration, Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel

CONTENT = {"sentences": [{"target": "Ich trinke Kaffee.", "native": "Bebo café."}]}
SUB = "Una panadería, un sábado a las ocho."
ESCENA = "A small bakery at dawn, a bicycle by the door."


@pytest.mark.asyncio
async def test_historia_y_biblioteca_guardan_subtitulo_y_escena(db_session):
    user = User(
        id=uuid.uuid4(),
        email=None,
        hashed_password=None,
        is_active=True,
        is_verified=False,
        is_superuser=False,
        display_name="Ana",
        level=CEFRLevel.A2,
        native_language="es",
        target_language="de",
    )
    module = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A2,
        sequence_order=1,
        title="En la panadería",
        can_dos=[],
        grammatical_focus=[],
    )
    db_session.add_all([user, module])
    await db_session.flush()
    db_session.add_all(
        [
            Story(
                user_id=user.id,
                level=CEFRLevel.A2,
                target_language="de",
                native_language="es",
                title="Die Bäckerei",
                content=CONTENT,
                target_vocab_item_ids=[],
                subtitle=SUB,
                scene=ESCENA,
            ),
            StoryLibrary(
                module_id=module.id,
                language="de",
                native_language="es",
                level=CEFRLevel.A2,
                title="Die Bäckerei",
                content=CONTENT,
                target_vocab_item_ids=[],
                source="seed",
                content_hash="e" * 64,
                subtitle=SUB,
                scene=ESCENA,
            ),
        ]
    )
    await db_session.commit()

    story = (await db_session.execute(select(Story))).scalar_one()
    entry = (await db_session.execute(select(StoryLibrary))).scalar_one()
    assert (story.subtitle, story.scene) == (SUB, ESCENA)
    assert (entry.subtitle, entry.scene) == (SUB, ESCENA)


@pytest.mark.asyncio
async def test_ilustracion_hash_unico(db_session):
    def fila() -> Illustration:
        return Illustration(
            hash="a" * 64,
            scene="x",
            style_version=1,
            model="m",
            mime_type="image/jpeg",
            image_data=b"\xff\xd8",
            size_bytes=2,
        )

    db_session.add(fila())
    await db_session.commit()
    db_session.add(fila())
    with pytest.raises(IntegrityError):
        await db_session.commit()
