"""Curriculum Module foundation: model, services, endpoint, generation rewire, seed."""

import uuid

import pytest

from klara.models import Module, User, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


async def _user(db, level=CEFRLevel.A1) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"m-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="M",
        level=level,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def _vocab(db, *, lemma, language, pos=PartOfSpeech.NOUN) -> VocabItem:
    v = VocabItem(id=uuid.uuid4(), language=language, lemma=lemma, pos=pos)
    db.add(v)
    await db.flush()
    return v


async def _module(db, *, language, order, title, vocab, can_dos=None, focus=None) -> Module:
    m = Module(
        id=uuid.uuid4(),
        language=language,
        cefr_level=CEFRLevel.A1,
        sequence_order=order,
        title=title,
        can_dos=can_dos or ["puedo pedir algo en un café"],
        grammatical_focus=focus or ["género de sustantivos de comida"],
    )
    m.vocab_items = vocab
    db.add(m)
    await db.flush()
    return m


@pytest.mark.asyncio
async def test_module_roundtrips_with_vocab_and_user_pointer(db_session):
    v1 = await _vocab(db_session, lemma="Kaffee", language="modt1")
    v2 = await _vocab(db_session, lemma="Tasse", language="modt1")
    m = await _module(db_session, language="modt1", order=1, title="En el café", vocab=[v1, v2])
    u = await _user(db_session)
    u.current_module_id = m.id
    await db_session.commit()

    reloaded = await db_session.get(Module, m.id)
    assert reloaded.title == "En el café"
    assert reloaded.mastery_threshold == 0.85
    assert {v.lemma for v in reloaded.vocab_items} == {"Kaffee", "Tasse"}
    reloaded_user = await db_session.get(User, u.id)
    assert reloaded_user.current_module_id == m.id
