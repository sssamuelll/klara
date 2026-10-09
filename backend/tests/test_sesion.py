"""Componer la sesión de una línea (spec §4): repasos vencidos con tope, sin dos
facetas del mismo ítem seguidas, y la siguiente lección del mapa."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from klara.models import LessonRun, UserFacet
from klara.models.enums import CardState
from klara.services import sesion
from klara.services.sesion import (
    Plan,
    componer,
    contar_vencidas,
    contenido,
    huerfanas,
    idiomas_de_estudio,
    minutos,
    orden_de_mapas,
    plan_para_repetir,
    separar_mismo_item,
)
from tests.ayudas import crear_usuario

AHORA = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _faceta(user_id, item: str, faceta: str, vence: datetime) -> UserFacet:
    return UserFacet(
        user_id=user_id,
        idioma=item.split(":")[0],
        item_key=item,
        faceta=faceta,
        state=CardState.REVIEWING,
        stability=3.0,
        difficulty=5.0,
        interval_days=3.0,
        repetitions=1,
        next_review_at=vence,
    )


def _corrida(user_id, leccion_id: str, *, origen: str = "hoy", terminada: bool = True) -> LessonRun:
    return LessonRun(
        user_id=user_id,
        idioma="ja",
        leccion_id=leccion_id,
        origen=origen,
        finished_at=AHORA - timedelta(hours=1) if terminada else None,
    )


def test_separar_mismo_item():
    pares = [("a", "x"), ("a", "y"), ("b", "x"), ("c", "x")]
    out = separar_mismo_item(pares)
    assert sorted(out) == sorted(pares)
    assert all(out[i][0] != out[i + 1][0] for i in range(len(out) - 1))
    assert out[0] == ("a", "x")


def test_separar_cuando_no_se_puede():
    assert separar_mismo_item([("a", "x"), ("a", "y")]) == [("a", "x"), ("a", "y")]


async def test_cuenta_nueva_empieza_por_la_primera_leccion(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.repasos == ()
    assert plan.leccion.id == "ja/hiragana/a"


async def test_leccion_hecha_pasa_a_la_siguiente(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add(_corrida(u.id, "ja/hiragana/a"))
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.leccion.id == "ja/hiragana/e"


async def test_ni_el_mapa_ni_una_corrida_abierta_cuentan(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add_all(
        [
            _corrida(u.id, "ja/hiragana/a", origen="mapa"),
            _corrida(u.id, "ja/hiragana/a", terminada=False),
        ]
    )
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.leccion.id == "ja/hiragana/a"


async def test_mapa_terminado(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add_all([_corrida(u.id, "ja/hiragana/a"), _corrida(u.id, "ja/hiragana/e")])
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.leccion is None


async def test_repasos_vencidos_en_orden_y_con_tope(db_session, catalogo_mini, monkeypatch):
    monkeypatch.setattr(sesion, "CAP_REPASOS", 4)
    u = await crear_usuario(db_session)
    items = ["ja:kana:あ", "ja:kana:い", "ja:kana:う", "ja:kana:え", "ja:kana:お"]
    db_session.add_all(
        [
            _faceta(u.id, it, "reconocer", AHORA - timedelta(hours=10 - n))
            for n, it in enumerate(items)
        ]
    )
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert [a.items[0] for a in plan.repasos] == items[:4]
    assert {(a.dinamica, a.modo) for a in plan.repasos} == {("eleccion", "comprobar")}


async def test_componer_no_junta_dos_facetas_del_mismo_item(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add_all(
        [
            _faceta(u.id, "ja:kana:あ", "reconocer", AHORA - timedelta(hours=3)),
            _faceta(u.id, "ja:kana:あ", "escribir", AHORA - timedelta(hours=2)),
            _faceta(u.id, "ja:kana:い", "reconocer", AHORA - timedelta(hours=1)),
        ]
    )
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert [(a.items[0], a.faceta) for a in plan.repasos] == [
        ("ja:kana:あ", "reconocer"),
        ("ja:kana:い", "reconocer"),
        ("ja:kana:あ", "escribir"),
    ]


async def test_fuera_lo_que_no_vence_lo_ajeno_y_lo_huerfano(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    otro = await crear_usuario(db_session)
    db_session.add_all(
        [
            _faceta(u.id, "ja:kana:あ", "escribir", AHORA - timedelta(minutes=5)),
            _faceta(u.id, "ja:kana:い", "escribir", AHORA + timedelta(hours=1)),
            _faceta(otro.id, "ja:kana:う", "escribir", AHORA - timedelta(hours=1)),
            _faceta(u.id, "ja:kana:か", "escribir", AHORA - timedelta(hours=1)),
        ]
    )
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert [(a.dinamica, a.items) for a in plan.repasos] == [("trazo", ("ja:kana:あ",))]


async def test_sin_repasos_cuando_se_pide(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add(_faceta(u.id, "ja:kana:あ", "escribir", AHORA - timedelta(minutes=5)))
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA, con_repasos=False)
    assert plan.repasos == ()
    assert plan.leccion.id == "ja/hiragana/a"


async def test_contar_vencidas(db_session):
    u = await crear_usuario(db_session)
    otro = await crear_usuario(db_session)
    db_session.add_all(
        [
            _faceta(u.id, "ja:kana:あ", "reconocer", AHORA - timedelta(minutes=5)),
            _faceta(u.id, "ja:kana:あ", "escribir", AHORA),
            _faceta(u.id, "ja:kana:い", "escribir", AHORA + timedelta(hours=1)),
            _faceta(otro.id, "ja:kana:う", "escribir", AHORA - timedelta(hours=1)),
        ]
    )
    await db_session.commit()
    assert await contar_vencidas(db_session, u.id, "ja", AHORA) == 2
    assert await contar_vencidas(db_session, u.id, "de", AHORA) == 0


def test_minutos(catalogo_mini):
    plan = Plan(idioma="ja", repasos=(), leccion=catalogo_mini.lecciones["ja/hiragana/a"])
    # trazo 3 x 20 + 3 x 25, elección 6 x 6, tablero 45, prueba: trazo 3 x 20 + elección 6 x 6 = 312 s
    assert minutos(plan) == 6


async def test_contenido_numera_y_marca_los_repasos(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add(_faceta(u.id, "ja:kana:あ", "escribir", AHORA - timedelta(minutes=1)))
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    acts = contenido(catalogo_mini, plan, semilla=1)
    assert (acts[0]["id"], acts[0]["repaso"], acts[0]["dinamica"]) == ("a0", True, "trazo")
    assert all(a["repaso"] is False for a in acts[1:])
    assert len({a["id"] for a in acts}) == len(acts)
    assert acts[0]["contenido"]["kana"] == "あ"


async def test_los_repasos_no_usan_distractores_de_la_leccion_nueva(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add_all(
        [
            _corrida(u.id, "ja/hiragana/a"),
            _faceta(u.id, "ja:kana:あ", "reconocer", AHORA - timedelta(minutes=1)),
        ]
    )
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.leccion.id == "ja/hiragana/e"
    repaso = contenido(catalogo_mini, plan, semilla=3)[0]
    assert repaso["repaso"] is True
    vistos = {"ja:kana:あ", "ja:kana:い", "ja:kana:う"}
    assert {o["item"] for o in repaso["contenido"]["opciones"]} <= vistos


def test_plan_para_repetir_no_mueve_fsrs(catalogo_mini):
    plan = plan_para_repetir(catalogo_mini.lecciones["ja/hiragana/a"], frozenset())
    assert plan.repasos == ()
    assert {a.modo for a in plan.actividades} <= {"presentar", "practicar"}
    assert len(plan.actividades) == 22


async def test_idiomas_de_estudio(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    assert idiomas_de_estudio(u, catalogo_mini) == []  # «de» todavía no tiene mapa
    u.study_languages = ["ja", "de"]
    assert idiomas_de_estudio(u, catalogo_mini) == ["ja"]


def test_orden_de_mapas_y_huerfanas(catalogo_mini):
    assert orden_de_mapas(catalogo_mini) == ["ja"]
    assert huerfanas({"ja:kana:あ", "ja:kana:か"}, catalogo_mini) == ["ja:kana:か"]


def test_orden_de_mapas_sigue_idiomas_orden(catalogo_mini):
    ja = catalogo_mini.mapas["ja"]
    cat = replace(catalogo_mini, mapas={k: ja for k in ("zz", "en", "ja", "aa", "de")})
    assert orden_de_mapas(cat) == ["de", "ja", "en", "aa", "zz"]
