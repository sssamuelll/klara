"""Curriculum Module foundation: model, services, endpoint, generation rewire, seed."""

import uuid

import pytest

from klara.curriculum.modules import (
    enroll_cards,
    ensure_active_module,
    load_modules,
    module_target_lemmas,
    module_vocab_ids,
    read_active_module,
)
from klara.models import Module, User, UserCard, VocabItem
from klara.models.enums import CardState, CEFRLevel, PartOfSpeech


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


@pytest.mark.asyncio
async def test_ensure_active_module_inits_pointer_when_null(db_session):
    v = await _vocab(db_session, lemma="Brot", language="modt3")
    m = await _module(db_session, language="modt3", order=1, title="café", vocab=[v])
    u = await _user(db_session)  # target_language="de"
    u.target_language = "modt3"
    await db_session.flush()

    assert u.current_module_id is None
    active = await ensure_active_module(db_session, u)
    assert active is not None and active.id == m.id
    assert u.current_module_id == m.id  # persisted on the user
    # Idempotent: second call returns the same module, doesn't move the pointer.
    again = await ensure_active_module(db_session, u)
    assert again.id == m.id


@pytest.mark.asyncio
async def test_read_active_module_does_not_init(db_session):
    u = await _user(db_session)
    assert await read_active_module(db_session, u) is None
    assert u.current_module_id is None  # read path never writes


@pytest.mark.asyncio
async def test_module_target_lemmas_and_vocab_ids(db_session):
    v1 = await _vocab(db_session, lemma="Wasser", language="modt4")
    v2 = await _vocab(db_session, lemma="Saft", language="modt4")
    m = await _module(db_session, language="modt4", order=1, title="café", vocab=[v1, v2])
    lemmas = await module_target_lemmas(db_session, m)
    assert set(lemmas) == {"Wasser", "Saft"}
    ids = await module_vocab_ids(db_session, m)
    assert ids == {v1.id, v2.id}


@pytest.mark.asyncio
async def test_enroll_cards_is_idempotent(db_session):
    v = await _vocab(db_session, lemma="Zucker", language="modt5")
    u = await _user(db_session)
    await enroll_cards(db_session, user_id=u.id, vocab_item_ids=[v.id])
    await enroll_cards(db_session, user_id=u.id, vocab_item_ids=[v.id])  # again
    await db_session.commit()
    from sqlalchemy import func, select

    n = (
        await db_session.execute(
            select(func.count())
            .select_from(UserCard)
            .where(UserCard.user_id == u.id, UserCard.vocab_item_id == v.id)
        )
    ).scalar_one()
    assert n == 1


@pytest.mark.asyncio
async def test_get_current_module_endpoint(db_session):
    v1 = await _vocab(db_session, lemma="Kuchen", language="modt6")
    v2 = await _vocab(db_session, lemma="Teller", language="modt6")
    m = await _module(db_session, language="modt6", order=1, title="En el café", vocab=[v1, v2])
    u = await _user(db_session)
    u.target_language = "modt6"
    u.current_module_id = m.id
    db_session.add(
        UserCard(id=uuid.uuid4(), user_id=u.id, vocab_item_id=v1.id, state=CardState.NEW)
    )
    await db_session.commit()

    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/modules/current")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "En el café"
    assert body["encountered"] == 1
    assert body["mastered"] == 0
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_get_current_module_empty_when_none(db_session):
    u = await _user(db_session)  # no current module, no modules for "de"
    await db_session.commit()

    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/modules/current")
    assert resp.status_code == 200, resp.text
    assert resp.json() is None


class _CafeLLM:
    """Returns a story that contains 'Kaffee' (covered) and declares it a target word."""

    def __init__(self):
        self.provider = "fake"
        self.model = "fake"
        self.cost_usd = 0.0

    async def complete(self, **kwargs):
        import json
        from types import SimpleNamespace

        data = {
            "title": "Der Kaffee",
            "sentences": [
                {
                    "target": "Der Kaffee ist heiß.",
                    "native": "El café está caliente.",
                    "new_words": ["Kaffee"],
                    "breakdown": [{"word": "Kaffee", "translation": "café", "pos": "noun"}],
                }
            ],
            "comprehension_questions": [],
            "target_words": [
                {
                    "lemma": "Kaffee",
                    "pos": "noun",
                    "gender": "der",
                    "translation": "café",
                    "example_target": "Der Kaffee.",
                },
            ],
        }
        return SimpleNamespace(
            content=json.dumps(data), provider="fake", model="fake", cost_usd=0.0
        )


@pytest.mark.asyncio
async def test_create_story_drives_from_module_and_auto_enrolls(db_session):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import func, select

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.dependencies import get_story_llm
    from klara.main import create_app

    # Module 'café' with vocab 'Kaffee' (the lemma the fake LLM will cover).
    v = await _vocab(db_session, lemma="Kaffee", language="modt7")
    m = await _module(db_session, language="modt7", order=1, title="En el café", vocab=[v])
    u = await _user(db_session)
    u.target_language = "modt7"
    await db_session.commit()
    assert u.current_module_id is None  # lazy-init happens in create_story

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    app.dependency_overrides[get_story_llm] = lambda: _CafeLLM()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/stories", json={"topic": None})
    assert resp.status_code == 201, resp.text

    # Pointer initialized to the module.
    reloaded = await db_session.get(type(u), u.id)
    assert reloaded.current_module_id == m.id
    # 'Kaffee' auto-enrolled as a NEW card.
    n = (
        await db_session.execute(
            select(func.count())
            .select_from(UserCard)
            .where(UserCard.user_id == u.id, UserCard.vocab_item_id == v.id)
        )
    ).scalar_one()
    assert n == 1


_SEED = [
    {
        "sequence_order": 1,
        "title": "En el café",
        "cefr_level": "A1",
        "can_dos": ["puedo pedir una bebida en un café"],
        "grammatical_focus": ["género de sustantivos de comida y bebida"],
        "vocab": [
            {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translations": {"es": "café"}},
            {"lemma": "Tee", "pos": "noun", "gender": "der", "translations": {"es": "té"}},
        ],
    }
]


@pytest.mark.asyncio
async def test_load_modules_is_idempotent(db_session):
    n1 = await load_modules(db_session, language="modt8", modules=_SEED)
    await db_session.commit()
    n2 = await load_modules(db_session, language="modt8", modules=_SEED)
    await db_session.commit()
    assert n1 == 1 and n2 == 1
    from sqlalchemy import func, select

    from klara.models import Module

    count = (
        await db_session.execute(
            select(func.count()).select_from(Module).where(Module.language == "modt8")
        )
    ).scalar_one()
    assert count == 1  # second load did not duplicate
    m = (
        await db_session.execute(
            select(Module).where(Module.language == "modt8", Module.sequence_order == 1)
        )
    ).scalar_one()
    assert {v.lemma for v in m.vocab_items} == {"Kaffee", "Tee"}
