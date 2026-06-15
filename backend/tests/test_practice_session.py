# backend/tests/test_practice_session.py
"""Cierre del ciclo SRS por pronunciación (canal de mantenimiento)."""

from __future__ import annotations

import uuid

from klara.schemas.srs import PronunciationBatchIn, RescheduledCardOut


def test_batch_in_deserializes_camelcase():
    # El frontend envía camelCase; validation_alias debe aceptarlo (si no, 422).
    payload = PronunciationBatchIn.model_validate(
        {
            "reviews": [
                {
                    "cardId": str(uuid.uuid4()),
                    "focusText": "Brot",
                    "sentenceTarget": "Ich esse Brot.",
                    "wordBands": {"0": "good", "2": "good", "4": "bad"},
                }
            ]
        }
    )
    assert payload.reviews[0].focus_text == "Brot"
    assert payload.reviews[0].word_bands[4] == "bad"  # llaves coercionadas a int


def test_rescheduled_out_serializes_camelcase():
    from datetime import UTC, datetime

    out = RescheduledCardOut(focus_text="Brot", interval_days=1.0, next_review_at=datetime.now(UTC))
    dumped = out.model_dump(by_alias=True)
    assert "focusText" in dumped and "intervalDays" in dumped and "nextReviewAt" in dumped
