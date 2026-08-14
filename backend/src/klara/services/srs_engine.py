from datetime import UTC, datetime, timedelta
from typing import Protocol

from fsrs import Card, Rating, Scheduler, State

from klara.config import get_settings
from klara.models.enums import CardState, ReviewRating
from klara.models.srs import UserCard

# klara ReviewRating -> fsrs Rating (escalas de 4 valores, misma semántica).
_RATING_MAP: dict[ReviewRating, Rating] = {
    ReviewRating.AGAIN: Rating.Again,
    ReviewRating.HARD: Rating.Hard,
    ReviewRating.GOOD: Rating.Good,
    ReviewRating.EASY: Rating.Easy,
}

# fsrs State -> klara CardState.
_STATE_TO_KLARA: dict[State, CardState] = {
    State.Learning: CardState.LEARNING,
    State.Relearning: CardState.RELEARNING,
    State.Review: CardState.REVIEWING,
}

# klara CardState -> fsrs State. SUSPENDED mapea a Review defensivamente:
# hoy es un estado muerto (ningún código lo asigna), pero si algún día llega,
# tratarlo como Review es lo menos destructivo.
_STATE_TO_FSRS: dict[CardState, State] = {
    CardState.LEARNING: State.Learning,
    CardState.RELEARNING: State.Relearning,
    CardState.REVIEWING: State.Review,
    CardState.SUSPENDED: State.Review,
}


class FsrsCard(Protocol):
    """Los nueve atributos que el motor lee y escribe — todo lo que necesita de
    una tarjeta. `UserCard` (alemán) y `StudyCard` (taller) lo cumplen; el motor
    no conoce a ninguna de las dos. El repo no corre mypy: esto es contrato de
    revisión, no gate de CI."""

    state: CardState
    stability: float | None
    difficulty: float | None
    fsrs_step: int | None
    fsrs_last_review: datetime | None
    interval_days: float
    next_review_at: datetime | None
    last_reviewed_at: datetime | None
    repetitions: int


def get_scheduler() -> Scheduler:
    """Scheduler fresco desde settings. enable_fuzzing=False es decisión D-D:
    el intervalo mostrado en el botón debe ser exactamente el persistido."""
    return Scheduler(
        desired_retention=get_settings().srs_desired_retention,
        enable_fuzzing=False,
    )


def _utc(dt: datetime | None) -> datetime | None:
    """Normaliza a timezone.utc para fsrs, que lanza ValueError si el tzinfo no
    es exactamente timezone.utc. Hoy todo llega por asyncpg (ya utc); el
    astimezone es defensa barata ante cualquier driver/offset futuro."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _to_fsrs_card(card: FsrsCard, now: datetime) -> Card:
    """Proyección pura FsrsCard -> fsrs.Card (NO muta `card`)."""
    if card.state == CardState.NEW:
        # Carta fresca: Card() pone state=Learning, step=0.
        return Card(card_id=1)

    if card.stability is None:
        # Cold start: carta legacy sin estado FSRS (p.ej. seeds pre-backfill).
        # Estima la estabilidad desde el intervalo; dificultad default.
        interval = max(card.interval_days, 0.1)
        return Card(
            card_id=1,
            state=_STATE_TO_FSRS[card.state],
            stability=interval,
            difficulty=5.0,
            step=0 if card.state in (CardState.LEARNING, CardState.RELEARNING) else None,
            due=_utc(card.next_review_at) or now,
            last_review=_utc(card.fsrs_last_review) or (now - timedelta(days=interval)),
        )

    return Card(
        card_id=1,
        state=_STATE_TO_FSRS[card.state],
        step=card.fsrs_step,
        stability=card.stability,
        difficulty=card.difficulty,
        due=_utc(card.next_review_at) or now,
        last_review=_utc(card.fsrs_last_review)
        or (now - timedelta(days=max(card.interval_days, 0.1))),
    )


def schedule_next_review(card: FsrsCard, rating: ReviewRating) -> tuple[float, datetime, CardState]:
    """FSRS (#125) — reemplaza el cuerpo SM-2 lite. Devuelve
    (interval_days, next_review_at, new_state); `apply_review` persiste ese trío
    (los routers ya no lo hacen). Muta las columnas FSRS (stability/difficulty/fsrs_step/
    fsrs_last_review + repetitions) — mismo reparto que SM-2 tenía con
    ease/repetitions. ease queda congelado (columna legacy). Fuzzing apagado
    (D-D): el intervalo mostrado == el persistido.
    """
    now = datetime.now(UTC)
    new_card, _ = get_scheduler().review_card(
        _to_fsrs_card(card, now), _RATING_MAP[rating], review_datetime=now
    )
    interval_days = round((new_card.due - now).total_seconds() / 86400, 4)

    card.stability = new_card.stability
    card.difficulty = new_card.difficulty
    card.fsrs_step = new_card.step
    card.fsrs_last_review = now
    card.repetitions = 0 if rating == ReviewRating.AGAIN else card.repetitions + 1
    # card.ease: columna legacy, NO se toca.

    return interval_days, new_card.due, _STATE_TO_KLARA[new_card.state]


def apply_review(card: FsrsCard, rating: ReviewRating) -> float:
    """Programa **y** escribe: el único sitio donde una tarjeta queda persistida
    tras un repaso. Devuelve el `interval_days` ANTERIOR, que el ledger guarda
    como `prev_interval_days`.

    Existe porque calcular en un sitio y asignar en cada router es la misma
    deriva de FSRS que unificar el cálculo pretendía evitar: un router nuevo que
    olvide `state` o `last_reviewed_at` no rompe ningún test hasta producción.
    """
    prev_interval_days = card.interval_days
    interval_days, next_review_at, new_state = schedule_next_review(card, rating)
    card.interval_days = interval_days
    card.next_review_at = next_review_at
    card.last_reviewed_at = datetime.now(UTC)
    card.state = new_state
    return prev_interval_days


def project_intervals(card: FsrsCard) -> dict[str, float]:
    """Preview honesto por rating (CardOut.next_intervals): un `now`, UNA
    construcción _to_fsrs_card y 4 llamadas review_card. review_card copia
    internamente — ni fcard ni card se mutan."""
    now = datetime.now(UTC)
    fcard = _to_fsrs_card(card, now)
    scheduler = get_scheduler()
    out: dict[str, float] = {}
    for key, fsrs_rating in (
        ("again", Rating.Again),
        ("hard", Rating.Hard),
        ("good", Rating.Good),
        ("easy", Rating.Easy),
    ):
        projected, _ = scheduler.review_card(fcard, fsrs_rating, review_datetime=now)
        out[key] = round((projected.due - now).total_seconds() / 86400, 4)
    return out


# Maintenance ladder for the pronunciation channel. Short, FIXED steps — this
# channel keeps due cards in circulation; it NEVER promotes to long intervals
# (that's the recall channel's job, future). Mirrors the LEARNING-path steps of
# schedule_next_review WITHOUT its REVIEWING exponential growth, and crucially
# does NOT touch ease/repetitions/state (promotion state owned by recall).
_MAINTENANCE_INTERVAL_DAYS: dict[str, float] = {
    "bad": 0.0069,  # ~10 min — re-drill soon (rating Again)
    "ok": 0.04,  # ~1 hour (rating Hard)
    "good": 1.0,  # +1 day — maintained, not graduated (rating Good)
}


def schedule_pronunciation_maintenance(card: UserCard, band: str) -> tuple[float, datetime]:
    """Pronunciation maintenance channel. Returns (interval_days, next_review_at).

    The caller persists card.interval_days / next_review_at / last_reviewed_at
    (this function deliberately does NOT mutate the card — schedule_next_review
    mutates ease/repetitions, this one keeps the card's promotion state frozen).
    `band` is one of "bad" | "ok" | "good".
    """
    interval = _MAINTENANCE_INTERVAL_DAYS[band]
    next_review = datetime.now(UTC) + timedelta(days=interval)
    return interval, next_review
