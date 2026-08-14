"""El esquema del taller: lo que la migración 0021 promete y lo que el ORM asume.

Ninguna de las dos cosas prueba esto por sí sola — la suite no toca las tablas
nuevas y `alembic upgrade` solo demuestra que el DDL corre. Un modelo que declare
una columna que la migración no creó (o al revés) revienta aquí, en PR1, en vez
de a mitad de PR2.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from klara.models import StudyCard, StudyCardReview, User
from klara.models.enums import CardState, ReviewRating


async def _usuario(db_session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"taller-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="T",
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _tarjeta(db_session, user: User) -> StudyCard:
    card = StudyCard(user_id=user.id, front="Anverso", back="Reverso", batch_id=uuid.uuid4())
    db_session.add(card)
    await db_session.flush()
    return card


@pytest.mark.asyncio
async def test_tarjeta_nace_vencida_con_los_defaults_del_esquema(db_session):
    user = await _usuario(db_session)

    card = await _tarjeta(db_session, user)
    await db_session.commit()
    await db_session.refresh(card)

    assert card.tags == []
    assert card.state == CardState.NEW
    assert card.interval_days == 0.0
    assert card.repetitions == 0
    assert card.stability is None
    assert card.archived_at is None
    # Nace vencida (next_review_at = created_at): es lo que da orden determinista
    # a la cola —la más vieja primero— sin la rama `is_(None)` que arrastra la
    # consulta del alemán.
    assert card.next_review_at == card.created_at


@pytest.mark.asyncio
async def test_el_ledger_persiste_un_repaso(db_session):
    user = await _usuario(db_session)
    card = await _tarjeta(db_session, user)

    review = StudyCardReview(
        user_id=user.id,
        study_card_id=card.id,
        rating=ReviewRating.GOOD,
        prev_interval_days=0.0,
        new_interval_days=1.0,
        device="desktop",
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)

    assert review.rating == ReviewRating.GOOD
    assert review.elapsed_seconds is None
    assert review.reviewed_at is not None


@pytest.mark.asyncio
async def test_device_fuera_de_la_lista_es_rechazado(db_session):
    user = await _usuario(db_session)
    card = await _tarjeta(db_session, user)

    db_session.add(
        StudyCardReview(
            user_id=user.id,
            study_card_id=card.id,
            rating=ReviewRating.GOOD,
            prev_interval_days=0.0,
            new_interval_days=1.0,
            device="tablet",
        )
    )

    # El nombre en el match importa: sin él, el test pasaría en verde si la fila
    # reventara por cualquier otra restricción y el CHECK no existiera.
    with pytest.raises(IntegrityError, match="ck_study_review_device"):
        await db_session.commit()
