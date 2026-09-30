"""GET /today (spec §2): las cuatro paradas, el «estás aquí», la historia del
panel, la frase de Pronunciar y las fichas que vencen, todo desde `since`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from klara.models import (
    Illustration,
    Module,
    PronunciationAttempt,
    Review,
    SpeakTurn,
    Story,
    StoryLibrary,
    StoryView,
    User,
    UserCard,
    VocabItem,
)
from klara.models.enums import CEFRLevel, ReviewRating
from klara.services.illustration import illustration_hash

AHORA = datetime.now(UTC).replace(microsecond=0)
SINCE = AHORA - timedelta(hours=3)
ANTES = SINCE - timedelta(seconds=1)
CONTENT = {
    "sentences": [
        {"target": "Der Bäcker öffnet um acht.", "native": "El panadero abre a las ocho."},
    ]
}
EMAIL = "hoy@example.com"


async def _login(client, seed_invite) -> str:
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": EMAIL, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def _yo(db) -> User:
    return (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()


async def _hoy(client, cookie) -> dict:
    resp = await client.get(
        "/api/v1/today", params={"since": SINCE.isoformat()}, headers={"Cookie": cookie}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _story(user: User, **kw) -> Story:
    base = dict(
        user_id=user.id,
        level=CEFRLevel.A2,
        target_language="de",
        native_language="es",
        title="Die Bäckerei am Samstag",
        content=CONTENT,
        target_vocab_item_ids=[],
    )
    return Story(**{**base, **kw})


def _intento(user: User, story: Story, cuando: datetime) -> PronunciationAttempt:
    return PronunciationAttempt(
        user_id=user.id,
        story_id=story.id,
        sentence_index=0,
        reference_text="x",
        overall_score=80.0,
        attempted_at=cuando,
    )


def _turno(user: User, cuando: datetime) -> SpeakTurn:
    return SpeakTurn(
        user_id=user.id,
        client_session_id=uuid.uuid4(),
        turn_index=0,
        language="de",
        focus_sound="ch",
        recognized_text="hallo",
        created_at=cuando,
    )


async def _ficha(db, user: User, next_review_at: datetime | None = None) -> UserCard:
    vocab = VocabItem(lemma=f"wort-{uuid.uuid4().hex[:8]}")
    db.add(vocab)
    await db.flush()
    card = UserCard(user_id=user.id, vocab_item_id=vocab.id, next_review_at=next_review_at)
    db.add(card)
    await db.flush()
    return card


@pytest.mark.asyncio
async def test_since_fuera_de_rango_es_422(client, seed_invite):
    cookie = await _login(client, seed_invite)
    # `ahora` fresco, no AHORA: AHORA se fija al importar el módulo y el suite corre minutos
    # antes de llegar aquí; con más de 4 min de deriva, «AHORA + 5 min» cae dentro del minuto
    # de margen y el 422 no sale.
    ahora = datetime.now(UTC)
    for since in (
        SINCE.replace(tzinfo=None).isoformat(),  # sin zona
        (ahora + timedelta(minutes=5)).isoformat(),  # en el futuro
        (ahora - timedelta(hours=49)).isoformat(),  # más de 48 h
    ):
        resp = await client.get(
            "/api/v1/today", params={"since": since}, headers={"Cookie": cookie}
        )
        assert resp.status_code == 422, since


@pytest.mark.asyncio
async def test_since_dentro_del_margen_es_200(client, seed_invite):
    """El reloj del dispositivo puede ir unos segundos adelantado, y en el cambio de hora
    el día local empieza hace 25 h: el margen de 1 min y el tope de 48 h no se aprietan."""
    cookie = await _login(client, seed_invite)
    ahora = datetime.now(UTC)
    for since in (ahora + timedelta(seconds=30), ahora - timedelta(hours=47)):
        resp = await client.get(
            "/api/v1/today", params={"since": since.isoformat()}, headers={"Cookie": cookie}
        )
        assert resp.status_code == 200, since


@pytest.mark.asyncio
async def test_sin_sesion_es_401(client):
    resp = await client.get("/api/v1/today", params={"since": SINCE.isoformat()})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cuenta_nueva(client, seed_invite):
    cookie = await _login(client, seed_invite)
    body = await _hoy(client, cookie)
    assert body["steps"] == {"read": False, "pronounce": False, "speak": False, "review": True}
    assert body["now"] == "read"
    assert body["story"]["state"] == "request" and body["story"]["title"] is None
    assert (body["sentence"], body["module"], body["due"]) == (None, None, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cuando, hecho", [(ANTES, False), (SINCE, True)], ids=["antes", "en-since"]
)
async def test_borde_de_since(client, seed_invite, db_session, cuando, hecho):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    story = _story(user)
    db_session.add(story)
    await db_session.flush()
    card = await _ficha(db_session, user, next_review_at=AHORA - timedelta(days=1))  # vence
    db_session.add_all(
        [
            StoryView(story_id=story.id, user_id=user.id, finished_at=cuando),
            _intento(user, story, cuando),
            _turno(user, cuando),
            Review(
                user_card_id=card.id,
                user_id=user.id,
                rating=ReviewRating.GOOD,
                channel="recall",
                reviewed_at=cuando,
            ),
        ]
    )
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["steps"] == {"read": hecho, "pronounce": hecho, "speak": hecho, "review": hecho}
    assert body["due"] == 1


@pytest.mark.asyncio
async def test_pronunciar_no_marca_repasar(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    card = await _ficha(db_session, user)  # sin fecha: vence
    db_session.add(
        Review(
            user_card_id=card.id,
            user_id=user.id,
            rating=ReviewRating.GOOD,
            channel="pronunciation",
            reviewed_at=AHORA,
        )
    )
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["steps"]["review"] is False
    assert body["due"] == 1


@pytest.mark.asyncio
async def test_estas_aqui_es_la_primera_que_falta(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    story = _story(user)
    db_session.add(story)
    await db_session.flush()
    db_session.add_all(
        [
            StoryView(story_id=story.id, user_id=user.id, finished_at=AHORA),
            _intento(user, story, AHORA),
        ]
    )
    await db_session.commit()
    assert (await _hoy(client, cookie))["now"] == "speak"

    db_session.add(_turno(user, AHORA))
    await db_session.commit()
    assert (await _hoy(client, cookie))["now"] is None  # repasar ya estaba hecho: no vence nada


@pytest.mark.asyncio
async def test_estas_aqui_recorre_las_cuatro_en_orden(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    story = _story(user)
    db_session.add(story)
    await db_session.flush()
    card = await _ficha(db_session, user)  # vence: Repasar cuenta
    await db_session.commit()
    assert (await _hoy(client, cookie))["now"] == "read"

    recall = Review(
        user_card_id=card.id,
        user_id=user.id,
        rating=ReviewRating.GOOD,
        channel="recall",
        reviewed_at=AHORA,
    )
    hecho = StoryView(story_id=story.id, user_id=user.id, finished_at=AHORA)
    for nuevo, sigue in [
        (hecho, "pronounce"),
        (_intento(user, story, AHORA), "speak"),
        (_turno(user, AHORA), "review"),
        (recall, None),
    ]:
        db_session.add(nuevo)
        await db_session.commit()
        assert (await _hoy(client, cookie))["now"] == sigue


@pytest.mark.asyncio
async def test_historia_terminada_hoy(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    story = _story(user, subtitle="Una panadería, un sábado a las ocho.")
    db_session.add(story)
    await db_session.flush()
    db_session.add(StoryView(story_id=story.id, user_id=user.id, finished_at=AHORA))
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["story"]["state"] == "done"
    assert body["story"]["id"] == str(story.id)
    assert body["story"]["subtitle"] == "Una panadería, un sábado a las ocho."
    assert body["sentence"] == {
        "target": "Der Bäcker öffnet um acht.",
        "native": "El panadero abre a las ocho.",
    }


@pytest.mark.asyncio
async def test_continuar_solo_mira_la_mas_reciente(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    vieja = _story(user, title="Die alte Geschichte", created_at=AHORA - timedelta(days=5))
    nueva = _story(user, title="Die neue Geschichte", created_at=AHORA - timedelta(days=1))
    db_session.add_all([vieja, nueva])
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert (body["story"]["state"], body["story"]["title"]) == ("continue", "Die neue Geschichte")

    # Si la más reciente se terminó ayer, la vieja abandonada no vuelve.
    db_session.add(
        StoryView(story_id=nueva.id, user_id=user.id, finished_at=AHORA - timedelta(days=1))
    )
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["story"]["state"] == "request"
    assert body["sentence"]["target"] == "Der Bäcker öffnet um acht."


@pytest.mark.asyncio
async def test_leer_a_medias_sigue_siendo_continuar(client, seed_invite, db_session):
    """Una vista sin `finished_at` (la columna lo admite) no cuenta como terminada."""
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    vieja = _story(user, title="Die alte Geschichte", created_at=AHORA - timedelta(days=3))
    nueva = _story(user, title="Die neue Geschichte", created_at=AHORA - timedelta(hours=1))
    db_session.add_all([vieja, nueva])
    await db_session.flush()
    db_session.add_all(
        [
            StoryView(story_id=vieja.id, user_id=user.id, finished_at=AHORA - timedelta(days=3)),
            StoryView(story_id=nueva.id, user_id=user.id, finished_at=None),
        ]
    )
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["steps"]["read"] is False
    assert (body["story"]["state"], body["story"]["title"]) == ("continue", "Die neue Geschichte")
    assert body["sentence"]["target"] == "Der Bäcker öffnet um acht."  # la de la vieja, terminada


@pytest.mark.asyncio
async def test_nueva_de_la_biblioteca_sin_reclamar(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    module = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A2,
        sequence_order=1,
        title="En la panadería",
        can_dos=[],
        grammatical_focus=[],
    )
    db_session.add(module)
    await db_session.flush()
    entry = StoryLibrary(
        module_id=module.id,
        language="de",
        native_language="es",
        level=CEFRLevel.A2,
        title="Die Bäckerei am Samstag",
        content=CONTENT,
        target_vocab_item_ids=[],
        source="seed",
        content_hash="9" * 64,
        subtitle="Una panadería.",
        scene="A small bakery at dawn.",
    )
    db_session.add(entry)
    user.current_module_id = module.id
    await db_session.commit()

    body = await _hoy(client, cookie)
    assert body["story"] == {
        "state": "new",
        "id": None,
        "library_entry_id": str(entry.id),
        "module_id": str(module.id),
        "title": "Die Bäckerei am Samstag",
        "subtitle": "Una panadería.",
        "illustration_path": None,
    }
    assert body["module"] == {"id": str(module.id), "title": "En la panadería", "cefr_level": "A2"}
    assert (await db_session.execute(select(Story))).scalars().all() == []  # mirar no reclama

    h = illustration_hash("A small bakery at dawn.")
    db_session.add(
        Illustration(
            hash=h,
            scene="A small bakery at dawn.",
            style_version=1,
            model="m",
            mime_type="image/jpeg",
            image_data=b"x",
            size_bytes=1,
        )
    )
    await db_session.commit()
    assert (await _hoy(client, cookie))["story"]["illustration_path"] == f"/illustrations/{h}"


@pytest.mark.asyncio
async def test_terminada_ayer_lleva_a_la_siguiente_de_la_biblioteca(
    client, seed_invite, db_session
):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    module = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A2,
        sequence_order=1,
        title="En la panadería",
        can_dos=[],
        grammatical_focus=[],
    )
    db_session.add(module)
    await db_session.flush()
    ayer = _story(user, module_id=module.id)
    entry = StoryLibrary(
        module_id=module.id,
        language="de",
        native_language="es",
        level=CEFRLevel.A2,
        title="Der Markt am Morgen",
        content=CONTENT,
        target_vocab_item_ids=[],
        source="seed",
        content_hash="8" * 64,
    )
    db_session.add_all([ayer, entry])
    await db_session.flush()
    db_session.add(
        StoryView(story_id=ayer.id, user_id=user.id, finished_at=AHORA - timedelta(days=1))
    )
    user.current_module_id = module.id
    await db_session.commit()

    body = await _hoy(client, cookie)
    assert body["steps"]["read"] is False
    assert body["now"] == "read"
    assert (body["story"]["state"], body["story"]["id"], body["story"]["title"]) == (
        "new",
        None,
        "Der Markt am Morgen",
    )


@pytest.mark.asyncio
async def test_no_cuenta_lo_de_otros(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    yo = await _yo(db_session)
    otro = User(
        email="otro@example.com",
        hashed_password="x",
        display_name="Otro",
        level=CEFRLevel.A2,
        native_language="es",
        target_language="de",
    )
    db_session.add(otro)
    await db_session.flush()
    terminada = _story(otro, created_at=AHORA - timedelta(days=2))
    en_curso = _story(otro, title="Die neue Geschichte", created_at=AHORA - timedelta(days=1))
    db_session.add_all([terminada, en_curso])
    await db_session.flush()
    await _ficha(db_session, yo)  # mi única ficha vence y nadie la repasó
    ficha_ajena = await _ficha(db_session, otro)
    db_session.add_all(
        [
            StoryView(story_id=terminada.id, user_id=otro.id, finished_at=AHORA),
            _intento(otro, terminada, AHORA),
            _turno(otro, AHORA),
            Review(
                user_card_id=ficha_ajena.id,
                user_id=otro.id,
                rating=ReviewRating.GOOD,
                channel="recall",
                reviewed_at=AHORA,
            ),
        ]
    )
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["steps"] == {"read": False, "pronounce": False, "speak": False, "review": False}
    assert (body["now"], body["due"], body["sentence"]) == ("read", 1, None)
    assert body["story"]["state"] == "request"


@pytest.mark.asyncio
async def test_vencen_exactas_con_mas_de_50(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    for _ in range(55):
        await _ficha(db_session, user)
    await _ficha(db_session, user, next_review_at=AHORA + timedelta(days=2))  # esta no vence
    await db_session.commit()
    assert (await _hoy(client, cookie))["due"] == 55
