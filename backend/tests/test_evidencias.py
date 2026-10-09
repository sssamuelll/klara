"""Registrar evidencias (spec §4): validación contra el catálogo, idempotencia por
id y FSRS solo en `comprobar`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from klara.models import FacetReview, LessonRun, UserFacet
from klara.models.enums import CardState, ReviewRating
from klara.schemas.catalogo import EvidenciaIn
from klara.services.evidencias import EvidenciaInvalida, registrar
from tests.ayudas import crear_usuario

AHORA = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


async def _corrida(db, user) -> LessonRun:
    run = LessonRun(user_id=user.id, idioma="ja", leccion_id="ja/hiragana/a", origen="hoy")
    db.add(run)
    await db.commit()
    return run


def _ev(run: LessonRun, **kw) -> EvidenciaIn:
    base = dict(
        id=uuid.uuid4(),
        run_id=run.id,
        dinamica="eleccion",
        modo="comprobar",
        item="ja:kana:あ",
        faceta="reconocer",
        acierto=True,
        pistas=0,
        ms=1500,
        detalle={"elegida": "ja:kana:あ"},
    )
    return EvidenciaIn(**{**base, **kw})


async def _facetas(db) -> list[UserFacet]:
    return list((await db.execute(select(UserFacet))).scalars())


async def _registro(db) -> list[FacetReview]:
    return list((await db.execute(select(FacetReview))).scalars())


async def test_la_practica_se_registra_y_no_mueve_fsrs(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    assert (
        await registrar(db_session, catalogo_mini, u.id, [_ev(run, modo="practicar")], AHORA) == 1
    )
    [fila] = await _registro(db_session)
    assert (fila.modo, fila.nota, fila.idioma) == ("practicar", None, "ja")
    assert await _facetas(db_session) == []


async def test_la_primera_prueba_crea_la_faceta(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    await registrar(db_session, catalogo_mini, u.id, [_ev(run)], AHORA)
    [f] = await _facetas(db_session)
    assert (f.item_key, f.faceta, f.idioma) == ("ja:kana:あ", "reconocer", "ja")
    assert f.state != CardState.NEW
    assert f.repetitions == 1
    assert f.next_review_at > AHORA
    [fila] = await _registro(db_session)
    assert fila.nota == ReviewRating.GOOD


@pytest.mark.parametrize(
    ("cambio", "esperada"),
    [
        ({"pistas": 1}, ReviewRating.HARD),
        ({"ms": 60_000}, ReviewRating.HARD),
        ({"acierto": False}, ReviewRating.AGAIN),
    ],
)
async def test_la_nota_sale_de_la_evidencia(db_session, catalogo_mini, cambio, esperada):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    await registrar(db_session, catalogo_mini, u.id, [_ev(run, **cambio)], AHORA)
    [fila] = await _registro(db_session)
    assert fila.nota == esperada


async def test_la_misma_evidencia_dos_veces_cuenta_una(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    ev = _ev(run)
    assert await registrar(db_session, catalogo_mini, u.id, [ev], AHORA) == 1
    assert await registrar(db_session, catalogo_mini, u.id, [ev], AHORA) == 0
    [f] = await _facetas(db_session)
    assert f.repetitions == 1
    assert len(await _registro(db_session)) == 1


async def test_una_respuesta_puede_dar_varias_evidencias(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    evs = [
        _ev(run, dinamica="emparejar", modo="practicar", item=i)
        for i in ("ja:kana:あ", "ja:kana:い", "ja:kana:う")
    ]
    assert await registrar(db_session, catalogo_mini, u.id, evs, AHORA) == 3


@pytest.mark.parametrize(
    "cambio",
    [
        {"dinamica": "dictado"},
        {"dinamica": "emparejar"},  # emparejar no soporta comprobar
        {"item": "ja:kana:か"},
        {"faceta": "genero"},
        {"faceta": "escribir"},  # eleccion no ejercita escribir
    ],
)
async def test_lo_que_no_cuadra_es_invalido_y_no_guarda_nada(db_session, catalogo_mini, cambio):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    with pytest.raises(EvidenciaInvalida):
        await registrar(db_session, catalogo_mini, u.id, [_ev(run), _ev(run, **cambio)], AHORA)
    await db_session.rollback()
    assert await _registro(db_session) == []
    assert await _facetas(db_session) == []


async def test_la_corrida_de_otro_es_invalida(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    otro = await crear_usuario(db_session)
    run_ajena = await _corrida(db_session, otro)
    with pytest.raises(EvidenciaInvalida):
        await registrar(db_session, catalogo_mini, u.id, [_ev(run_ajena)], AHORA)
