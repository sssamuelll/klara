"""Los ocho endpoints de `/api/v1/taller` (F0 PR2): overview, crear, bulk,
listar, due, review, archive, export.

Patrón de cookie: `test_srs_recall.py:20-33`. La allowlist se abre por test vía
`app_settings(TALLER_USER_IDS=...)` — el ajuste es un `Settings` cacheado con
`lru_cache`, así que sin ese fixture (que llama `get_settings.cache_clear()`)
el segundo test heredaría la allowlist del primero.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from klara.models import StudyCard, StudyCardReview, User


async def _register_and_login(client, seed_invite, email: str) -> str:
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def _usuario(db_session, email: str) -> User:
    return (await db_session.execute(select(User).where(User.email == email))).scalar_one()


def _allow(app_settings, *user_ids) -> None:
    app_settings(TALLER_USER_IDS=",".join(str(u) for u in user_ids))


async def _sembrada(client, seed_invite, db_session, app_settings, email: str) -> tuple[str, User]:
    """Un usuario registrado, logueado y dentro de la allowlist."""
    cookie = await _register_and_login(client, seed_invite, email)
    user = await _usuario(db_session, email)
    _allow(app_settings, user.id)
    return cookie, user


# --------------------------------------------------------------- allowlist


@pytest.mark.asyncio
async def test_usuario_fuera_de_allowlist_da_403(client, seed_invite, app_settings):
    cookie = await _register_and_login(client, seed_invite, "fuera@example.com")
    app_settings(TALLER_USER_IDS="")  # cerrado explícito, no el default heredado

    r = await client.get("/api/v1/taller/overview", headers={"Cookie": cookie})

    assert r.status_code == 403, r.text


# --------------------------------------------------------------- crear


@pytest.mark.asyncio
async def test_crear_tarjeta_simple(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "crear1@example.com")

    r = await client.post(
        "/api/v1/taller/cards",
        json={"front": "Anverso", "back": "Reverso", "tags": [], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["front"] == "Anverso"
    assert body["back"] == "Reverso"
    assert body["state"] == "new"
    assert body["repetitions"] == 0
    assert "next_intervals" in body


@pytest.mark.asyncio
async def test_front_con_tab_es_rechazado(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "tab1@example.com")

    r = await client.post(
        "/api/v1/taller/cards",
        json={
            "front": "Anverso\tconTab",
            "back": "Reverso",
            "tags": [],
            "batch_id": str(uuid.uuid4()),
        },
        headers={"Cookie": cookie},
    )

    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_tags_se_normalizan_strip_minusculas_dedupe(
    client, seed_invite, db_session, app_settings
):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "tags1@example.com")

    r = await client.post(
        "/api/v1/taller/cards",
        json={
            "front": "A",
            "back": "B",
            "tags": ["  Bio  ", "quimica", "BIO"],
            "batch_id": str(uuid.uuid4()),
        },
        headers={"Cookie": cookie},
    )

    assert r.status_code == 201, r.text
    assert r.json()["tags"] == ["bio", "quimica"]


@pytest.mark.asyncio
async def test_mas_de_10_tags_es_rechazado(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "tags2@example.com")

    r = await client.post(
        "/api/v1/taller/cards",
        json={
            "front": "A",
            "back": "B",
            "tags": [f"t{i}" for i in range(11)],
            "batch_id": str(uuid.uuid4()),
        },
        headers={"Cookie": cookie},
    )

    assert r.status_code == 422, r.text


# --------------------------------------------------------------- bulk


@pytest.mark.asyncio
async def test_bulk_es_todo_o_nada(client, seed_invite, db_session, app_settings):
    cookie, user = await _sembrada(
        client, seed_invite, db_session, app_settings, "bulk1@example.com"
    )
    cards = [{"front": f"F{i}", "back": f"B{i}"} for i in range(58)]
    cards[57] = {"front": "roto\tconTab", "back": "B57"}  # el índice 57 revienta

    r = await client.post(
        "/api/v1/taller/cards/bulk",
        json={"cards": cards, "tags": [], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )

    assert r.status_code == 422, r.text
    count = (
        (await db_session.execute(select(StudyCard).where(StudyCard.user_id == user.id)))
        .scalars()
        .all()
    )
    assert count == []  # cero filas, no 57 de 58


@pytest.mark.asyncio
async def test_bulk_topa_en_200(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "bulk2@example.com")
    cards = [{"front": f"F{i}", "back": f"B{i}"} for i in range(201)]

    r = await client.post(
        "/api/v1/taller/cards/bulk",
        json={"cards": cards, "tags": [], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )

    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_bulk_mismo_batch_id_no_duplica(client, seed_invite, db_session, app_settings):
    cookie, user = await _sembrada(
        client, seed_invite, db_session, app_settings, "bulk3@example.com"
    )
    batch_id = str(uuid.uuid4())
    payload = {
        "cards": [{"front": "F1", "back": "B1"}, {"front": "F2", "back": "B2"}],
        "tags": [],
        "batch_id": batch_id,
    }

    r1 = await client.post("/api/v1/taller/cards/bulk", json=payload, headers={"Cookie": cookie})
    assert r1.status_code == 201, r1.text
    assert r1.json()["created"] == 2
    first_ids = {c["id"] for c in r1.json()["cards"]}

    r2 = await client.post("/api/v1/taller/cards/bulk", json=payload, headers={"Cookie": cookie})
    assert r2.status_code == 201, r2.text
    assert r2.json()["created"] == 2
    assert {c["id"] for c in r2.json()["cards"]} == first_ids  # las MISMAS filas

    rows = (
        (await db_session.execute(select(StudyCard).where(StudyCard.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 2  # no 4


# --------------------------------------------------------------- listar


@pytest.mark.asyncio
async def test_listar_cards_filtra_por_tag_y_pagina(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(
        client, seed_invite, db_session, app_settings, "listar1@example.com"
    )
    for i in range(3):
        await client.post(
            "/api/v1/taller/cards",
            json={
                "front": f"F{i}",
                "back": f"B{i}",
                "tags": ["bio"],
                "batch_id": str(uuid.uuid4()),
            },
            headers={"Cookie": cookie},
        )
    await client.post(
        "/api/v1/taller/cards",
        json={"front": "Otra", "back": "B", "tags": ["quimica"], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )

    r = await client.get("/api/v1/taller/cards?tag=bio", headers={"Cookie": cookie})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert all("bio" in c["tags"] for c in body["items"])


# --------------------------------------------------------------- due


@pytest.mark.asyncio
async def test_due_ordena_por_vencimiento_y_topa_en_50(
    client, seed_invite, db_session, app_settings
):
    cookie, user = await _sembrada(
        client, seed_invite, db_session, app_settings, "due1@example.com"
    )
    now = datetime.now(UTC)
    for i in range(55):
        db_session.add(
            StudyCard(
                user_id=user.id,
                front=f"F{i}",
                back=f"B{i}",
                batch_id=uuid.uuid4(),
                next_review_at=now - timedelta(days=55 - i),  # i=0 es la más vieja
            )
        )
    await db_session.commit()

    sin_limite = await client.get("/api/v1/taller/cards/due", headers={"Cookie": cookie})
    assert sin_limite.status_code == 200, sin_limite.text
    assert len(sin_limite.json()) == 20  # default

    con_limite_alto = await client.get(
        "/api/v1/taller/cards/due?limit=999", headers={"Cookie": cookie}
    )
    assert con_limite_alto.status_code == 200, con_limite_alto.text
    topado = con_limite_alto.json()
    assert len(topado) == 50  # tope, no 55 ni error
    assert topado[0]["front"] == "F0"  # la más vieja primero


# --------------------------------------------------------------- review


@pytest.mark.asyncio
async def test_review_exige_device(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "rev1@example.com")
    created = await client.post(
        "/api/v1/taller/cards",
        json={"front": "A", "back": "B", "tags": [], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )
    card_id = created.json()["id"]

    r = await client.post(
        f"/api/v1/taller/cards/{card_id}/review",
        json={"rating": "good"},
        headers={"Cookie": cookie},
    )

    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_review_persiste_ledger_y_tarjeta(client, seed_invite, db_session, app_settings):
    cookie, user = await _sembrada(
        client, seed_invite, db_session, app_settings, "rev2@example.com"
    )
    created = await client.post(
        "/api/v1/taller/cards",
        json={"front": "A", "back": "B", "tags": [], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )
    card_id = created.json()["id"]

    r = await client.post(
        f"/api/v1/taller/cards/{card_id}/review",
        json={"rating": "good", "elapsed_seconds": 12, "device": "desktop"},
        headers={"Cookie": cookie},
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["repetitions"] == 1
    assert body["state"] != "new"

    reviews = (
        (
            await db_session.execute(
                select(StudyCardReview).where(StudyCardReview.study_card_id == uuid.UUID(card_id))
            )
        )
        .scalars()
        .all()
    )
    assert len(reviews) == 1
    assert reviews[0].device == "desktop"
    assert reviews[0].user_id == user.id


@pytest.mark.asyncio
async def test_elapsed_seconds_se_recorta_no_rechaza(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "rev3@example.com")
    created = await client.post(
        "/api/v1/taller/cards",
        json={"front": "A", "back": "B", "tags": [], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )
    card_id = created.json()["id"]

    r = await client.post(
        f"/api/v1/taller/cards/{card_id}/review",
        json={"rating": "good", "elapsed_seconds": 999_999, "device": "desktop"},
        headers={"Cookie": cookie},
    )

    assert r.status_code == 200, r.text  # nunca 422 por esto
    reviews = (
        (
            await db_session.execute(
                select(StudyCardReview).where(StudyCardReview.study_card_id == uuid.UUID(card_id))
            )
        )
        .scalars()
        .all()
    )
    assert reviews[0].elapsed_seconds == 3600


@pytest.mark.asyncio
async def test_tarjeta_ajena_da_404(client, seed_invite, db_session, app_settings):
    cookie_a, user_a = await _sembrada(
        client, seed_invite, db_session, app_settings, "aje1@example.com"
    )
    cookie_b = await _register_and_login(client, seed_invite, "aje2@example.com")
    user_b = await _usuario(db_session, "aje2@example.com")
    _allow(app_settings, user_a.id, user_b.id)  # ambos en la lista: aísla el 404 del 403

    created = await client.post(
        "/api/v1/taller/cards",
        json={"front": "A", "back": "B", "tags": [], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie_a},
    )
    card_id = created.json()["id"]

    r = await client.post(
        f"/api/v1/taller/cards/{card_id}/review",
        json={"rating": "good", "device": "desktop"},
        headers={"Cookie": cookie_b},
    )

    assert r.status_code == 404, r.text


# --------------------------------------------------------------- archive


@pytest.mark.asyncio
async def test_archivar_conserva_los_reviews(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "arch1@example.com")
    created = await client.post(
        "/api/v1/taller/cards",
        json={"front": "A", "back": "B", "tags": [], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )
    card_id = created.json()["id"]
    await client.post(
        f"/api/v1/taller/cards/{card_id}/review",
        json={"rating": "good", "device": "desktop"},
        headers={"Cookie": cookie},
    )

    r = await client.post(f"/api/v1/taller/cards/{card_id}/archive", headers={"Cookie": cookie})
    assert r.status_code == 204, r.text

    reviews = (
        (
            await db_session.execute(
                select(StudyCardReview).where(StudyCardReview.study_card_id == uuid.UUID(card_id))
            )
        )
        .scalars()
        .all()
    )
    assert len(reviews) == 1  # el ledger sobrevive

    overview = await client.get("/api/v1/taller/overview", headers={"Cookie": cookie})
    assert overview.json()["total"] == 0  # pero desaparece de los conteos activos


# --------------------------------------------------------------- overview


@pytest.mark.asyncio
async def test_overview_cuenta_etiquetas_solapadas(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "ov1@example.com")
    await client.post(
        "/api/v1/taller/cards",
        json={"front": "A", "back": "B", "tags": ["bio", "examen"], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )
    await client.post(
        "/api/v1/taller/cards",
        json={"front": "C", "back": "D", "tags": ["examen"], "batch_id": str(uuid.uuid4())},
        headers={"Cookie": cookie},
    )

    r = await client.get("/api/v1/taller/overview", headers={"Cookie": cookie})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    by_tag = {t["tag"]: t["count"] for t in body["tags"]}
    assert by_tag == {"bio": 1, "examen": 2}
    assert sum(by_tag.values()) != body["total"]  # la suma NO da el total


# --------------------------------------------------------------- export


@pytest.mark.asyncio
async def test_export_es_tsv_parseable(client, seed_invite, db_session, app_settings):
    cookie, _ = await _sembrada(client, seed_invite, db_session, app_settings, "exp1@example.com")
    await client.post(
        "/api/v1/taller/cards",
        json={
            "front": "Anverso uno",
            "back": "Reverso uno",
            "tags": ["a"],
            "batch_id": str(uuid.uuid4()),
        },
        headers={"Cookie": cookie},
    )
    await client.post(
        "/api/v1/taller/cards",
        json={
            "front": "Anverso dos",
            "back": "Reverso dos",
            "tags": [],
            "batch_id": str(uuid.uuid4()),
        },
        headers={"Cookie": cookie},
    )

    r = await client.get("/api/v1/taller/export", headers={"Cookie": cookie})

    assert r.status_code == 200, r.text
    lines = [ln for ln in r.text.split("\n") if ln]
    assert len(lines) == 2
    rows = [ln.split("\t") for ln in lines]
    assert all(len(row) == 5 for row in rows)
    fronts = {row[0] for row in rows}
    assert fronts == {"Anverso uno", "Anverso dos"}
