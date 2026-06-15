from datetime import UTC, datetime, timedelta

from klara.models.enums import CardState, ReviewRating
from klara.models.srs import UserCard


def schedule_next_review(card: UserCard, rating: ReviewRating) -> tuple[float, datetime, CardState]:
    """SM-2 lite — returns (new_interval_days, next_review_at, new_state).

    Pragmatic adaptation: short steps for new cards, exponential growth once reviewing.
    Tunable later when we add FSRS proper.
    """
    now = datetime.now(UTC)
    prev_state = card.state
    ease = card.ease

    if rating == ReviewRating.AGAIN:
        new_interval = 0.0069  # ~10 min
        new_state = CardState.RELEARNING if prev_state != CardState.NEW else CardState.LEARNING
        ease = max(1.3, ease - 0.2)
        repetitions = 0
    elif prev_state in (CardState.NEW, CardState.LEARNING, CardState.RELEARNING):
        if rating == ReviewRating.HARD:
            new_interval = 0.04  # ~1 hour
            new_state = CardState.LEARNING
            repetitions = card.repetitions
        elif rating == ReviewRating.GOOD:
            new_interval = 1.0
            new_state = CardState.REVIEWING
            repetitions = card.repetitions + 1
        else:
            new_interval = 4.0
            new_state = CardState.REVIEWING
            repetitions = card.repetitions + 1
            ease = min(3.0, ease + 0.15)
    else:
        if rating == ReviewRating.HARD:
            multiplier = 1.2
            ease = max(1.3, ease - 0.15)
        elif rating == ReviewRating.GOOD:
            multiplier = ease
        else:
            multiplier = ease * 1.3
            ease = min(3.0, ease + 0.1)
        prev = max(card.interval_days, 1.0)
        new_interval = round(prev * multiplier, 2)
        new_state = CardState.REVIEWING
        repetitions = card.repetitions + 1

    card.ease = ease
    card.repetitions = repetitions
    next_review = now + timedelta(days=new_interval)
    return new_interval, next_review, new_state


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
