"""POST /evidencias con lo que manda el frontend (spec §4): la forma de cada
dinámica, el `ms` que se recorta en vez de perder la respuesta y el tope de `detalle`."""

from __future__ import annotations

import uuid

from sqlalchemy import select, text

from klara.models import FacetReview, UserFacet
from klara.models.enums import ReviewRating
from tests.ayudas import entrar

EMAIL = "evidencias@example.com"


async def _corrida(client, seed_invite) -> tuple[dict, str]:
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    r = await client.post("/api/v1/lesson-runs", json={"idioma": "ja", "origen": "hoy"}, headers=h)
    assert r.status_code == 201, r.text
    return h, r.json()["id"]


def _ev(run_id: str, **kw) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "run_id": run_id,
        "dinamica": "eleccion",
        "modo": "comprobar",
        "item": "ja:kana:あ",
        "faceta": "reconocer",
        "acierto": True,
        "pistas": 0,
        "ms": 1200,
        **kw,
    }


async def _mandar(client, h, *evs: dict):
    return await client.post("/api/v1/evidencias", json={"evidencias": list(evs)}, headers=h)


async def _registro(db) -> list[FacetReview]:
    return list((await db.execute(select(FacetReview))).scalars())


async def _facetas(db) -> list[UserFacet]:
    return list((await db.execute(select(UserFacet))).scalars())


async def test_mas_de_una_hora_se_recorta_y_la_respuesta_cuenta(
    client, seed_invite, db_session, catalogo_mini
):
    # Una actividad abierta con el teléfono en segundo plano: antes, 422 y la respuesta perdida.
    h, run = await _corrida(client, seed_invite)
    r = await _mandar(client, h, _ev(run, ms=7_200_000))
    assert r.status_code == 200, r.text
    [fila] = await _registro(db_session)
    assert (fila.ms, fila.nota) == (3_600_000, ReviewRating.HARD)
    [f] = await _facetas(db_session)
    assert (f.item_key, f.faceta, f.repetitions) == ("ja:kana:あ", "reconocer", 1)


async def test_un_detalle_de_mas_de_16_kb_es_422_y_no_guarda_nada(
    client, seed_invite, db_session, catalogo_mini
):
    h, run = await _corrida(client, seed_invite)
    r = await _mandar(client, h, _ev(run), _ev(run, detalle={"x": "a" * 20_000}))
    assert r.status_code == 422, r.text
    assert await _registro(db_session) == []
    assert await _facetas(db_session) == []


async def test_sin_detalle_se_guarda_null_de_sql(client, seed_invite, db_session, catalogo_mini):
    h, run = await _corrida(client, seed_invite)
    assert (await _mandar(client, h, _ev(run))).status_code == 200
    # Leído desde Python, el null de JSON y el de SQL dan los dos None: se pregunta a la base.
    nulo = (
        await db_session.execute(text("SELECT detalle IS NULL FROM facet_reviews"))
    ).scalar_one()
    assert nulo is True


async def test_lo_que_mandan_el_trazo_y_el_tablero(client, seed_invite, db_session, catalogo_mini):
    h, run = await _corrida(client, seed_invite)
    # (a) Un trazo en la prueba con el detalle de evidenciaTrazo (frontend/src/lib/dinamicas/trazo.ts):
    # あ en tres trazos; el segundo, dos intentos que no valieron y la pista al primero.
    detalle = {
        "trazos": [
            {"n": 1, "media": 4.12, "largo": 1.03, "fallos": 0},
            {
                "n": 2,
                "media": 6.5,
                "largo": 0.91,
                "fallos": 2,
                "rechazos": [{"media": 14.2, "largo": 1.1}, {"media": 12.9, "largo": 0.6}],
            },
            {"n": 3, "media": 5.01, "largo": 1.12, "fallos": 0},
        ]
    }
    trazo = _ev(run, dinamica="trazo", faceta="escribir", pistas=1, ms=9_400, detalle=detalle)
    # (b) Un tablero de emparejar: una evidencia por pareja, sin detalle, en práctica.
    tablero = [
        _ev(
            run,
            dinamica="emparejar",
            modo="practicar",
            item=f"ja:kana:{k}",
            acierto=k not in "いお",
        )
        for k in "あいうえお"
    ]
    r = await _mandar(client, h, trazo)
    assert r.json() == {"guardadas": 1}, r.text
    r = await _mandar(client, h, *tablero)
    assert r.json() == {"guardadas": 5}, r.text

    filas = {f.id: f for f in await _registro(db_session)}
    t = filas.pop(uuid.UUID(trazo["id"]))
    assert (t.dinamica, t.modo, t.acierto, t.pistas, t.nota) == (
        "trazo",
        "comprobar",
        True,
        1,
        ReviewRating.HARD,
    )
    assert t.detalle == detalle
    assert sorted((f.item_key, f.acierto, f.modo, f.nota, f.detalle) for f in filas.values()) == [
        ("ja:kana:あ", True, "practicar", None, None),
        ("ja:kana:い", False, "practicar", None, None),
        ("ja:kana:う", True, "practicar", None, None),
        ("ja:kana:え", True, "practicar", None, None),
        ("ja:kana:お", False, "practicar", None, None),
    ]
    # Solo la prueba mueve FSRS: una faceta, la del trazo.
    [f] = await _facetas(db_session)
    assert (f.item_key, f.faceta, f.repetitions) == ("ja:kana:あ", "escribir", 1)
