"""Las tablas nuevas (spec 2026-10-09 §2.2) y la columna de idiomas de estudio."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from klara.models import FacetReview, LessonRun, User, UserFacet
from klara.models.enums import CardState, CEFRLevel, ReviewRating


async def _usuario(db) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"f-{uuid.uuid4().hex[:6]}@klara.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Samuel",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def test_study_languages_nace_nula(db_session):
    u = await _usuario(db_session)
    await db_session.commit()
    assert u.study_languages is None


async def test_study_languages_guarda_una_lista(db_session):
    u = await _usuario(db_session)
    u.study_languages = ["de", "ja", "en"]
    await db_session.commit()
    await db_session.refresh(u)
    assert u.study_languages == ["de", "ja", "en"]


async def test_una_faceta_por_usuario_item_y_faceta(db_session):
    u = await _usuario(db_session)
    for _ in range(2):
        db_session.add(
            UserFacet(
                user_id=u.id,
                idioma="ja",
                item_key="ja:kana:あ",
                faceta="escribir",
                state=CardState.NEW,
                interval_days=0.0,
                repetitions=0,
            )
        )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_la_evidencia_guarda_su_corrida_y_su_detalle(db_session):
    u = await _usuario(db_session)
    run = LessonRun(user_id=u.id, idioma="ja", leccion_id="ja/hiragana/a", origen="hoy", repasos=3)
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        FacetReview(
            id=uuid.uuid4(),
            user_id=u.id,
            run_id=run.id,
            idioma="ja",
            item_key="ja:kana:あ",
            faceta="escribir",
            dinamica="trazo",
            modo="comprobar",
            acierto=True,
            pistas=1,
            ms=9000,
            nota=ReviewRating.HARD,
            detalle={"trazos": [{"n": 1, "media": 4.2, "largo": 1.0, "fallos": 0}]},
        )
    )
    await db_session.commit()
    guardada = (await db_session.execute(select(FacetReview))).scalar_one()
    assert guardada.run_id == run.id
    assert guardada.detalle["trazos"][0]["media"] == 4.2
    assert run.started_at is not None
    assert run.finished_at is None


async def test_origen_solo_hoy_o_mapa(db_session):
    u = await _usuario(db_session)
    db_session.add(LessonRun(user_id=u.id, idioma="ja", origen="otro"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_el_modo_de_la_evidencia_es_uno_de_los_tres(db_session):
    u = await _usuario(db_session)
    run = LessonRun(user_id=u.id, idioma="ja", origen="hoy")
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        FacetReview(
            id=uuid.uuid4(),
            user_id=u.id,
            run_id=run.id,
            idioma="ja",
            item_key="ja:kana:あ",
            faceta="escribir",
            dinamica="trazo",
            modo="repasar",
            acierto=True,
            pistas=0,
            ms=1,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
