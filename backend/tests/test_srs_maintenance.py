# backend/tests/test_srs_maintenance.py
"""El canal de pronunciación MANTIENE: escalera corta fija, sin tocar el estado
de promoción (ease/repetitions/state). schedule_next_review no se toca."""

from datetime import UTC, datetime

import pytest

from klara.models.enums import CardState
from klara.models.srs import UserCard
from klara.services.srs_engine import schedule_pronunciation_maintenance


def _card() -> UserCard:
    return UserCard(
        user_id=None,
        vocab_item_id=None,
        ease=2.5,
        interval_days=30.0,
        repetitions=5,
        state=CardState.REVIEWING,
    )


@pytest.mark.parametrize(
    "band,expected_days",
    [("bad", 0.0069), ("ok", 0.04), ("good", 1.0)],
)
def test_maintenance_ladder_intervals(band, expected_days):
    card = _card()
    interval, next_at = schedule_pronunciation_maintenance(card, band)
    assert interval == expected_days
    assert next_at > datetime.now(UTC)


def test_maintenance_never_touches_promotion_state():
    # Una carta promovida (REVIEWING, interval 30) dicha "good": el mantenimiento
    # NO multiplica por ease ni cambia ease/repetitions/state.
    card = _card()
    schedule_pronunciation_maintenance(card, "good")
    assert card.ease == 2.5
    assert card.repetitions == 5
    assert card.state == CardState.REVIEWING
