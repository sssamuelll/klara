"""Las rutas del catálogo (spec §4), contra el catálogo de juguete."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from klara.models import LessonRun, UserFacet
from klara.models.enums import CardState
from tests.ayudas import crear_usuario, entrar, usuario_por_email

EMAIL = "catalogo@example.com"


async def _cabeceras(client, seed_invite) -> dict:
    return {"Cookie": await entrar(client, seed_invite, EMAIL)}


def _evidencia(run_id: str) -> dict:
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
    }


_RUN = "00000000-0000-4000-8000-000000000000"  # fijo: el id del test no cambia entre corridas


# Con cuerpos válidos: el 401 tiene que salir de la cuenta, no de la validación.
@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    [
        ("GET", "/api/v1/sesiones/ja", None),
        ("GET", "/api/v1/lecciones/ja/hiragana/a", None),
        ("POST", "/api/v1/lesson-runs", {"idioma": "ja", "origen": "hoy"}),
        ("POST", f"/api/v1/lesson-runs/{_RUN}/fin", None),
        ("POST", "/api/v1/evidencias", {"evidencias": [_evidencia(_RUN)]}),
        ("GET", "/api/v1/mapas", None),
    ],
)
async def test_las_rutas_del_catalogo_piden_cuenta(client, catalogo_mini, metodo, ruta, cuerpo):
    r = await client.request(metodo, ruta, json=cuerpo)
    assert r.status_code == 401, r.text


async def test_sesion_de_una_cuenta_nueva(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    r = await client.get("/api/v1/sesiones/ja", headers=h)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["idioma"] == "ja"
    assert s["leccion"] == {"id": "ja/hiragana/a", "titulo": "あ い う", "bajada": "la fila de あ"}
    assert len(s["actividades"]) == 22
    primera = s["actividades"][0]
    assert (primera["id"], primera["dinamica"], primera["modo"], primera["repaso"]) == (
        "a0",
        "trazo",
        "presentar",
        False,
    )
    assert primera["contenido"]["audio"] == "/audio/ja/a.mp3"


async def test_idioma_sin_mapa_es_404(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    assert (await client.get("/api/v1/sesiones/de", headers=h)).status_code == 404


async def test_sin_repasos_cuando_se_pide(client, seed_invite, db_session, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    u = await usuario_por_email(db_session, EMAIL)
    db_session.add(
        UserFacet(
            user_id=u.id,
            idioma="ja",
            item_key="ja:kana:あ",
            faceta="escribir",
            state=CardState.REVIEWING,
            stability=2.0,
            difficulty=5.0,
            interval_days=2.0,
            repetitions=1,
            next_review_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.commit()
    con = (await client.get("/api/v1/sesiones/ja", headers=h)).json()
    sin = (await client.get("/api/v1/sesiones/ja", params={"repasos": "false"}, headers=h)).json()
    assert con["actividades"][0]["repaso"] is True
    assert not any(a["repaso"] for a in sin["actividades"])


async def test_repetir_una_leccion_es_todo_practica(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    r = await client.get("/api/v1/lecciones/ja/hiragana/a", headers=h)
    assert r.status_code == 200, r.text
    assert {a["modo"] for a in r.json()["actividades"]} <= {"presentar", "practicar"}
    assert (await client.get("/api/v1/lecciones/ja/hiragana/zz", headers=h)).status_code == 404


async def test_abrir_y_cerrar_una_corrida(client, seed_invite, db_session, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    r = await client.post(
        "/api/v1/lesson-runs",
        json={"idioma": "ja", "leccion_id": "ja/hiragana/a", "origen": "hoy", "repasos": 2},
        headers=h,
    )
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]
    r2 = await client.post(f"/api/v1/lesson-runs/{run_id}/fin", headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json() == {"manana": 0}
    run = (await db_session.execute(select(LessonRun))).scalar_one()
    assert run.finished_at is not None
    assert run.repasos == 2
    primera = run.finished_at
    await client.post(f"/api/v1/lesson-runs/{run_id}/fin", headers=h)
    await db_session.refresh(run)
    assert run.finished_at == primera


async def test_corrida_con_leccion_o_idioma_que_no_existen(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    mala = {"idioma": "ja", "leccion_id": "ja/hiragana/zz", "origen": "hoy"}
    assert (await client.post("/api/v1/lesson-runs", json=mala, headers=h)).status_code == 422
    sin_mapa = {"idioma": "de", "origen": "hoy"}
    assert (await client.post("/api/v1/lesson-runs", json=sin_mapa, headers=h)).status_code == 404


async def test_cerrar_la_corrida_de_otro_es_404(client, seed_invite, db_session, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    otro = await crear_usuario(db_session)
    run = LessonRun(user_id=otro.id, idioma="ja", origen="hoy")
    db_session.add(run)
    await db_session.commit()
    assert (await client.post(f"/api/v1/lesson-runs/{run.id}/fin", headers=h)).status_code == 404


async def test_evidencias(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    run_id = (
        await client.post("/api/v1/lesson-runs", json={"idioma": "ja", "origen": "hoy"}, headers=h)
    ).json()["id"]
    ev = _evidencia(run_id)
    r = await client.post("/api/v1/evidencias", json={"evidencias": [ev]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"guardadas": 1}
    malo = {**ev, "id": str(uuid.uuid4()), "faceta": "genero"}
    assert (
        await client.post("/api/v1/evidencias", json={"evidencias": [malo]}, headers=h)
    ).status_code == 422
    assert (
        await client.post("/api/v1/evidencias", json={"evidencias": []}, headers=h)
    ).status_code == 422


async def test_audio_sin_cuenta(client, catalogo_mini):
    r = await client.get("/api/v1/audio/ja/a.mp3")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3"
    for ruta in ("/api/v1/audio/ja/zz.mp3", "/api/v1/audio/ja/a.wav", "/api/v1/audio/de/a.mp3"):
        assert (await client.get(ruta)).status_code == 404, ruta


# Ni salir de la carpeta del audio ni abrir a.mp3 con otras mayúsculas (Windows no las distingue).
@pytest.mark.parametrize("archivo", ["..%5Ca.mp3", "%2e%2e%2fx.mp3", "A.mp3", "a.MP3"])
async def test_audio_solo_con_el_nombre_exacto(client, catalogo_mini, archivo):
    assert (await client.get(f"/api/v1/audio/ja/{archivo}")).status_code == 404


async def test_mapas(client, seed_invite, db_session, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    assert (await client.get("/api/v1/mapas", headers=h)).json() == [
        {"idioma": "ja", "estudias": False, "nivel": "かな", "progreso": 0.0, "vencen": 0}
    ]
    u = await usuario_por_email(db_session, EMAIL)
    u.study_languages = ["ja"]
    db_session.add(
        LessonRun(
            user_id=u.id,
            idioma="ja",
            leccion_id="ja/hiragana/a",
            origen="hoy",
            finished_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    [m] = (await client.get("/api/v1/mapas", headers=h)).json()
    assert m["estudias"] is True
    assert m["progreso"] == 0.5
