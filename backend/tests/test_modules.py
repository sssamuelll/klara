"""Curriculum Module foundation: model, services, endpoint, generation rewire, seed."""

import uuid

import pytest

from klara.curriculum.modules import (
    advance_module_if_mastered,
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


@pytest.mark.asyncio
async def test_load_modules_replaces_vocab_links_on_reseed(db_session):
    # First seed: module has {Apfel, Birne}.
    spec_v1 = [
        {
            "sequence_order": 1,
            "title": "Obst",
            "cefr_level": "A1",
            "can_dos": ["x"],
            "grammatical_focus": ["y"],
            "vocab": [
                {
                    "lemma": "Apfel",
                    "pos": "noun",
                    "gender": "der",
                    "translations": {"es": "manzana"},
                },
                {"lemma": "Birne", "pos": "noun", "gender": "die", "translations": {"es": "pera"}},
            ],
        }
    ]
    await load_modules(db_session, language="modt9", modules=spec_v1)
    await db_session.commit()
    # Re-seed same module with a DIFFERENT vocab set {Apfel, Traube} — Birne dropped.
    spec_v2 = [
        {
            "sequence_order": 1,
            "title": "Obst",
            "cefr_level": "A1",
            "can_dos": ["x"],
            "grammatical_focus": ["y"],
            "vocab": [
                {
                    "lemma": "Apfel",
                    "pos": "noun",
                    "gender": "der",
                    "translations": {"es": "manzana"},
                },
                {"lemma": "Traube", "pos": "noun", "gender": "die", "translations": {"es": "uva"}},
            ],
        }
    ]
    await load_modules(db_session, language="modt9", modules=spec_v2)
    await db_session.commit()

    from sqlalchemy import select as _select

    from klara.models import Module

    m = (
        await db_session.execute(
            _select(Module).where(Module.language == "modt9", Module.sequence_order == 1)
        )
    ).scalar_one()
    # Links reflect ONLY the v2 set — no stale Birne link.
    assert {v.lemma for v in m.vocab_items} == {"Apfel", "Traube"}


async def _mastered_card(db, user_id, vocab_item_id):
    db.add(
        UserCard(
            id=uuid.uuid4(),
            user_id=user_id,
            vocab_item_id=vocab_item_id,
            state=CardState.REVIEWING,
            interval_days=30.0,
        )
    )


@pytest.mark.asyncio
async def test_advance_moves_pointer_when_module_mastered(db_session):
    v1 = await _vocab(db_session, lemma="Tag", language="modtA")
    v2 = await _vocab(db_session, lemma="Nacht", language="modtA")
    m1 = await _module(db_session, language="modtA", order=1, title="Uno", vocab=[v1, v2])
    m2 = await _module(db_session, language="modtA", order=2, title="Dos", vocab=[v1])
    u = await _user(db_session)
    u.target_language = "modtA"
    u.current_module_id = m1.id
    # Both m1 words mastered → 2/2 ≥ 0.85.
    await _mastered_card(db_session, u.id, v1.id)
    await _mastered_card(db_session, u.id, v2.id)
    await db_session.commit()

    advanced = await advance_module_if_mastered(db_session, user=u, reviewed_vocab_item_id=v1.id)
    assert advanced is True
    assert u.current_module_id == m2.id


@pytest.mark.asyncio
async def test_advance_noop_when_reviewed_card_not_in_active_module(db_session):
    v_in = await _vocab(db_session, lemma="Haus", language="modtB")
    v_out = await _vocab(db_session, lemma="Auto", language="modtB")
    m1 = await _module(db_session, language="modtB", order=1, title="Uno", vocab=[v_in])
    await _module(db_session, language="modtB", order=2, title="Dos", vocab=[v_in])
    u = await _user(db_session)
    u.target_language = "modtB"
    u.current_module_id = m1.id
    await _mastered_card(db_session, u.id, v_in.id)  # module IS mastered (1/1)
    await db_session.commit()

    # Reviewed an OFF-module card → no-op even though the module is mastered.
    advanced = await advance_module_if_mastered(db_session, user=u, reviewed_vocab_item_id=v_out.id)
    assert advanced is False
    assert u.current_module_id == m1.id


@pytest.mark.asyncio
async def test_advance_noop_when_not_yet_mastered(db_session):
    v1 = await _vocab(db_session, lemma="Brot", language="modtC")
    v2 = await _vocab(db_session, lemma="Milch", language="modtC")
    m1 = await _module(db_session, language="modtC", order=1, title="Uno", vocab=[v1, v2])
    await _module(db_session, language="modtC", order=2, title="Dos", vocab=[v1])
    u = await _user(db_session)
    u.target_language = "modtC"
    u.current_module_id = m1.id
    await _mastered_card(db_session, u.id, v1.id)  # only 1/2 mastered → 0.5 < 0.85
    db_session.add(
        UserCard(id=uuid.uuid4(), user_id=u.id, vocab_item_id=v2.id, state=CardState.NEW)
    )
    await db_session.commit()

    advanced = await advance_module_if_mastered(db_session, user=u, reviewed_vocab_item_id=v1.id)
    assert advanced is False
    assert u.current_module_id == m1.id


@pytest.mark.asyncio
async def test_advance_noop_on_last_module(db_session):
    v1 = await _vocab(db_session, lemma="Stadt", language="modtD")
    m1 = await _module(db_session, language="modtD", order=1, title="Único", vocab=[v1])
    u = await _user(db_session)
    u.target_language = "modtD"
    u.current_module_id = m1.id
    await _mastered_card(db_session, u.id, v1.id)  # mastered, but no next module
    await db_session.commit()

    advanced = await advance_module_if_mastered(db_session, user=u, reviewed_vocab_item_id=v1.id)
    assert advanced is False
    assert u.current_module_id == m1.id  # stays on the last module


@pytest.mark.asyncio
async def test_submit_review_advances_module_on_mastery(db_session):
    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    # Active module m1 with one word; mastering it should advance to m2.
    v = await _vocab(db_session, lemma="Wort", language="modtE")
    m1 = await _module(db_session, language="modtE", order=1, title="Uno", vocab=[v])
    m2 = await _module(db_session, language="modtE", order=2, title="Dos", vocab=[v])
    u = await _user(db_session)
    u.target_language = "modtE"
    u.current_module_id = m1.id
    # A card already near mastery (REVIEWING, interval 20) so one GOOD pushes it ≥21d.
    card = UserCard(
        id=uuid.uuid4(),
        user_id=u.id,
        vocab_item_id=v.id,
        state=CardState.REVIEWING,
        interval_days=20.0,
        ease=2.5,
        repetitions=3,
    )
    db_session.add(card)
    await db_session.commit()

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(f"/api/v1/srs/cards/{card.id}/review", json={"rating": "good"})
    assert resp.status_code == 200, resp.text
    # GOOD on a 20d REVIEWING card → interval *= ease (≈50d) ≥ 21 → mastered → advance.
    reloaded = await db_session.get(type(u), u.id)
    assert reloaded.current_module_id == m2.id
