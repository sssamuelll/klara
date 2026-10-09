"""GET /today (spec 2026-10-09 §5.1): una línea por idioma de estudio, en el
orden que pone primero al que lleva más tiempo sin terminarse."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from klara.models import LessonRun, UserFacet
from klara.models.enums import CardState
from klara.services.today import ordenar_idiomas
from tests.ayudas import entrar, usuario_por_email

AHORA = datetime.now(UTC).replace(microsecond=0)
SINCE = AHORA - timedelta(hours=3)
EMAIL = "hoy@example.com"


async def _hoy(client, cookie: str) -> dict:
    r = await client.get(
        "/api/v1/today", params={"since": SINCE.isoformat()}, headers={"Cookie": cookie}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _con_japones(db):
    u = await usuario_por_email(db, EMAIL)
    u.study_languages = ["ja"]
    await db.commit()
    return u


def _corrida(user, **kw) -> LessonRun:
    base = dict(
        user_id=user.id,
        idioma="ja",
        leccion_id="ja/hiragana/a",
        origen="hoy",
        repasos=4,
        started_at=AHORA - timedelta(hours=1),
        finished_at=AHORA - timedelta(minutes=30),
    )
    return LessonRun(**{**base, **kw})


async def test_since_fuera_de_rango_es_422(client, seed_invite, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    # `ahora` fresco, no AHORA: AHORA se fija al importar el módulo y la suite corre minutos
    # antes de llegar aquí; con más de 4 min de deriva, «AHORA + 5 min» cae dentro del minuto
    # de margen del router y el 422 no sale.
    ahora = datetime.now(UTC)
    for since in (
        ahora + timedelta(minutes=5),
        ahora - timedelta(hours=49),
        AHORA.replace(tzinfo=None),
    ):
        r = await client.get(
            "/api/v1/today", params={"since": since.isoformat()}, headers={"Cookie": cookie}
        )
        assert r.status_code == 422, since


async def test_sin_sesion_es_401(client, catalogo_mini):
    r = await client.get("/api/v1/today", params={"since": SINCE.isoformat()})
    assert r.status_code == 401


async def test_sin_idiomas_con_mapa_no_hay_lineas(client, seed_invite, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    assert await _hoy(client, cookie) == {"lineas": []}


async def test_cuenta_nueva_una_linea_con_la_primera_leccion(
    client, seed_invite, db_session, catalogo_mini
):
    cookie = await entrar(client, seed_invite, EMAIL)
    await _con_japones(db_session)
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea == {
        "idioma": "ja",
        "estado": "ahora",
        "minutos": 6,
        "repasos": 0,
        "leccion": {"id": "ja/hiragana/a", "titulo": "あ い う", "bajada": "la fila de あ"},
        "hecho": None,
    }


async def test_linea_hecha_hoy(client, seed_invite, db_session, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    db_session.add(_corrida(u))
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["estado"] == "hecha"
    assert linea["hecho"] == {"repasos": 4, "leccion": "あ い う"}
    assert linea["leccion"]["id"] == "ja/hiragana/e"


async def test_lo_de_ayer_no_marca_hoy(client, seed_invite, db_session, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    db_session.add(
        _corrida(u, started_at=SINCE - timedelta(hours=1), finished_at=SINCE - timedelta(seconds=1))
    )
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["estado"] == "ahora"
    assert linea["hecho"] is None


async def test_corrida_abierta_o_del_mapa_no_marcan(client, seed_invite, db_session, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    db_session.add_all([_corrida(u, finished_at=None), _corrida(u, origen="mapa")])
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["estado"] == "ahora"


async def test_repasos_que_vencen(client, seed_invite, db_session, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    for kana in "あいうえおを":
        db_session.add(
            UserFacet(
                user_id=u.id,
                idioma="ja",
                item_key=f"ja:kana:{kana}",
                faceta="escribir",
                state=CardState.REVIEWING,
                stability=2.0,
                difficulty=5.0,
                interval_days=2.0,
                repetitions=1,
                next_review_at=AHORA - timedelta(hours=1),
            )
        )
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["repasos"] == 6
    # 6 trazos de repaso x 20 s más los 312 s de la lección = 432 s
    assert linea["minutos"] == 8


async def test_con_el_mapa_terminado_la_linea_sigue_sin_leccion(
    client, seed_invite, db_session, catalogo_mini
):
    """Spec §5.1: «Solo repasos: terminaste el mapa». Sin lección que dar, la línea
    sigue ahí; no es un error."""
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    db_session.add_all(
        [
            _corrida(u, finished_at=SINCE - timedelta(hours=2)),
            _corrida(u, leccion_id="ja/hiragana/e", finished_at=SINCE - timedelta(hours=1)),
        ]
    )
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea == {
        "idioma": "ja",
        "estado": "ahora",
        "minutos": 0,
        "repasos": 0,
        "leccion": None,
        "hecho": None,
    }

    # Una corrida solo de repasos (sin lección) hoy: hecha, y no hay título que mostrar.
    db_session.add(_corrida(u, leccion_id=None, repasos=5))
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["estado"] == "hecha"
    assert linea["hecho"] == {"repasos": 5, "leccion": None}


async def test_varias_corridas_hoy_suman_repasos_y_nombran_la_ultima_leccion(
    client, seed_invite, db_session, catalogo_mini
):
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    # La lección a, «Otra lección» (e) y al final solo repasos: la última corrida no
    # trae lección, así que el título sale de la anterior.
    db_session.add_all(
        [
            _corrida(u, repasos=4, finished_at=AHORA - timedelta(minutes=150)),
            _corrida(
                u, leccion_id="ja/hiragana/e", repasos=3, finished_at=AHORA - timedelta(minutes=100)
            ),
            _corrida(u, leccion_id=None, repasos=2, finished_at=AHORA - timedelta(minutes=30)),
        ]
    )
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["estado"] == "hecha"
    assert linea["hecho"] == {"repasos": 9, "leccion": "え お を"}
    assert linea["leccion"] is None  # con a y e hechas, el mapa de juguete se acabó


async def test_el_orden_no_cambia_al_terminar_una_linea(
    client, seed_invite, db_session, catalogo_mini, monkeypatch
):
    # catalogo_mini solo trae el mapa de ja: «de» entra como un segundo idioma sin lecciones.
    monkeypatch.setattr("klara.services.today.idiomas_de_estudio", lambda user, cat: ["de", "ja"])
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await usuario_por_email(db_session, EMAIL)
    db_session.add(
        _corrida(
            u,
            idioma="de",
            leccion_id=None,
            started_at=SINCE - timedelta(days=1, minutes=10),
            finished_at=SINCE - timedelta(days=1),
        )
    )
    await db_session.commit()

    async def orden() -> list[tuple[str, str]]:
        return [(x["idioma"], x["estado"]) for x in (await _hoy(client, cookie))["lineas"]]

    # de terminó ayer y ja nunca: ja va primero.
    assert await orden() == [("ja", "ahora"), ("de", "pendiente")]
    # Terminar ja hoy no la manda al final: solo cuenta lo terminado antes de hoy.
    db_session.add(_corrida(u))
    await db_session.commit()
    assert await orden() == [("ja", "hecha"), ("de", "ahora")]


def test_ordenar_idiomas():
    ayer, antier = AHORA - timedelta(days=1), AHORA - timedelta(days=2)
    assert ordenar_idiomas(["de", "ja", "en"], {}) == ["de", "ja", "en"]
    assert ordenar_idiomas(["de", "ja", "en"], {"de": ayer, "ja": antier}) == ["en", "ja", "de"]
    assert ordenar_idiomas(["de", "ja"], {"de": ayer, "ja": ayer}) == ["de", "ja"]
