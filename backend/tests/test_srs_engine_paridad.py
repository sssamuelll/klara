"""Un solo scheduler (F0 del taller): `apply_review` calcula **y** escribe.

Hasta ahora `schedule_next_review` mutaba cinco columnas y devolvía un trío que
`routers/srs.py:116-121` asignaba a otras cuatro. Un segundo tipo de tarjeta con
su propio router habría duplicado esa asignación: la deriva de FSRS por la puerta
de atrás, que el kickoff nombra como el peor resultado posible. `apply_review` es
el único sitio donde una tarjeta queda escrita, y estos tests son lo que se pone
rojo si alguien la forkea.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from klara.models import StudyCard, UserCard, UserFacet
from klara.models.enums import CardState, ReviewRating
from klara.services import srs_engine
from klara.services.srs_engine import apply_review

# Los nueve atributos que definen el estado programado de una tarjeta. El test
# de paridad compara estos nueve, no el trío devuelto: un router que olvidara
# asignar `state` o `last_reviewed_at` pasaría un test del retorno en verde.
_NUEVE = (
    "state",
    "stability",
    "difficulty",
    "fsrs_step",
    "fsrs_last_review",
    "interval_days",
    "next_review_at",
    "last_reviewed_at",
    "repetitions",
)


@dataclass
class _Doble:
    """Doble mínimo que cumple el Protocol `FsrsCard`. Sin ORM y sin DB: si el
    motor llegara a leer o escribir algo fuera de los nueve, revienta aquí."""

    state: CardState = CardState.NEW
    stability: float | None = None
    difficulty: float | None = None
    fsrs_step: int | None = None
    fsrs_last_review: datetime | None = None
    interval_days: float = 0.0
    next_review_at: datetime | None = None
    last_reviewed_at: datetime | None = None
    repetitions: int = 0


def _repasada(days: float = 20.0) -> _Doble:
    """Tarjeta en REVIEWING con estado FSRS explícito (rama determinista de
    `_to_fsrs_card`, sin cold start)."""
    now = datetime.now(UTC)
    return _Doble(
        state=CardState.REVIEWING,
        stability=days,
        difficulty=5.0,
        fsrs_last_review=now - timedelta(days=days),
        interval_days=days,
        next_review_at=now,
        last_reviewed_at=now - timedelta(days=days),
        repetitions=5,
    )


def test_apply_review_escribe_los_nueve_atributos():
    card = _Doble()
    antes = {attr: getattr(card, attr) for attr in _NUEVE}

    apply_review(card, ReviewRating.GOOD)

    sin_escribir = [attr for attr in _NUEVE if getattr(card, attr) == antes[attr]]
    assert sin_escribir == []


def test_apply_review_devuelve_prev_interval():
    card = _repasada(days=20.0)

    prev_interval = apply_review(card, ReviewRating.GOOD)

    assert prev_interval == 20.0
    # Y devolvió el ANTERIOR, no el que acaba de escribir.
    assert card.interval_days != 20.0


# ------------------------------------------------------------------- paridad


_ARRANQUE = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def reloj(monkeypatch):
    """Reloj gobernado: las dos tarjetas de la paridad ven el MISMO `now` en
    cada ronda, y el test lo adelanta entre rondas.

    Con el reloj real las dos llamadas caen con microsegundos de diferencia y
    los nueve atributos solo se pueden comparar con tolerancia — justo el margen
    donde se escondería un fork. Pararlo del todo tampoco sirve: el elapsed se
    vuelve 0, FSRS deja de mover stability y tres atributos salen iguales por
    construcción. Adelantarlo da comparación exacta con intervalos reales."""
    estado = {"ahora": _ARRANQUE}

    class _Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return estado["ahora"]

    monkeypatch.setattr(srs_engine, "datetime", _Reloj)
    return estado


def _sembrada(cls, **propias):
    """Misma tarjeta en los dos tipos: los nueve atributos explícitos (los
    defaults de columna no aplican sin flush) más lo que cada tabla exige."""
    return cls(
        state=CardState.REVIEWING,
        stability=20.0,
        difficulty=5.0,
        fsrs_step=None,
        fsrs_last_review=_ARRANQUE - timedelta(days=20),
        interval_days=20.0,
        next_review_at=_ARRANQUE,
        last_reviewed_at=_ARRANQUE - timedelta(days=20),
        repetitions=5,
        **propias,
    )


def test_paridad_usercard_studycard(reloj):
    user_id = uuid.uuid4()
    aleman = _sembrada(UserCard, user_id=user_id, vocab_item_id=uuid.uuid4(), ease=2.5)
    taller = _sembrada(
        StudyCard, user_id=user_id, front="Anverso", back="Reverso", tags=[], batch_id=uuid.uuid4()
    )

    for dias, rating in (
        (0, ReviewRating.GOOD),
        (1, ReviewRating.AGAIN),
        (3, ReviewRating.HARD),
        (10, ReviewRating.EASY),
    ):
        reloj["ahora"] += timedelta(days=dias)
        apply_review(aleman, rating)
        apply_review(taller, rating)

    divergentes = [a for a in _NUEVE if getattr(aleman, a) != getattr(taller, a)]
    assert divergentes == []


def test_paridad_usercard_userfacet(reloj):
    """`UserFacet` (Klara en tres idiomas) recorre FSRS igual que `UserCard`."""
    user_id = uuid.uuid4()
    aleman = _sembrada(UserCard, user_id=user_id, vocab_item_id=uuid.uuid4(), ease=2.5)
    faceta = _sembrada(
        UserFacet, user_id=user_id, idioma="ja", item_key="ja:kana:あ", faceta="escribir"
    )

    for dias, rating in (
        (0, ReviewRating.GOOD),
        (1, ReviewRating.AGAIN),
        (3, ReviewRating.HARD),
        (10, ReviewRating.EASY),
    ):
        reloj["ahora"] += timedelta(days=dias)
        apply_review(aleman, rating)
        apply_review(faceta, rating)

    divergentes = [a for a in _NUEVE if getattr(aleman, a) != getattr(faceta, a)]
    assert divergentes == []
