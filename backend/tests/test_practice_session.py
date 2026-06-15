# backend/tests/test_practice_session.py
"""Cierre del ciclo SRS por pronunciación (canal de mantenimiento)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from klara.models import Review, User, UserCard, VocabItem
from klara.models.enums import CardState, PartOfSpeech, ReviewRating
from klara.schemas.srs import PronunciationBatchIn, PronunciationReviewIn, RescheduledCardOut
from klara.services.practice_session import apply_pronunciation_reviews


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


async def _seed_user(db_session) -> uuid.UUID:
    from klara.models.enums import CEFRLevel

    u = User(
        id=uuid.uuid4(),
        email=f"u-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="U",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(u)
    await db_session.flush()
    return u.id


async def _seed_card(db_session, *, user_id, lemma, next_review_at, language="de"):
    # vocab_items NO se trunca entre tests (conftest.py) y hay unique
    # (lemma, language, pos) — sufija el lemma para no chocar entre casos.
    # Ningún assert compara el lemma exacto, así que el sufijo es inocuo.
    vocab = VocabItem(
        id=uuid.uuid4(),
        language=language,
        lemma=f"{lemma}-{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN,
    )
    db_session.add(vocab)
    await db_session.flush()
    card = UserCard(
        id=uuid.uuid4(),
        user_id=user_id,
        vocab_item_id=vocab.id,
        ease=2.5,
        interval_days=30.0,
        repetitions=5,
        state=CardState.REVIEWING,
        next_review_at=next_review_at,
    )
    db_session.add(card)
    await db_session.commit()
    return card.id


def _review(card_id, focus, target, bands):
    return PronunciationReviewIn(
        card_id=card_id, focus_text=focus, sentence_target=target, word_bands=bands
    )


@pytest.mark.asyncio
async def test_due_card_reschedules_without_promotion(db_session):
    uid = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=uid, lemma="Brot", next_review_at=None)
    # "Ich esse Brot." -> tokens 0 Ich, 2 esse, 4 Brot. Foco "Brot" en idx 4 = bad.
    out = await apply_pronunciation_reviews(
        db_session,
        user_id=uid,
        reviews=[_review(cid, "Brot", "Ich esse Brot.", {0: "good", 2: "good", 4: "bad"})],
    )
    assert len(out) == 1 and out[0].focus_text == "Brot"
    assert out[0].interval_days == 0.0069  # bad -> Again ladder
    card = await db_session.get(UserCard, cid)
    assert card.ease == 2.5 and card.repetitions == 5 and card.state == CardState.REVIEWING
    assert card.next_review_at > datetime.now(UTC)
    review = (
        await db_session.execute(select(Review).where(Review.user_card_id == cid))
    ).scalar_one()
    assert review.rating == ReviewRating.AGAIN


@pytest.mark.asyncio
async def test_non_due_card_is_skipped(db_session):
    uid = await _seed_user(db_session)
    future = datetime.now(UTC) + timedelta(days=10)
    cid = await _seed_card(db_session, user_id=uid, lemma="Haus", next_review_at=future)
    out = await apply_pronunciation_reviews(
        db_session,
        user_id=uid,
        reviews=[_review(cid, "Haus", "Das Haus.", {2: "good"})],
    )
    assert out == []
    card = await db_session.get(UserCard, cid)
    assert card.next_review_at == future  # intacta


@pytest.mark.asyncio
async def test_other_users_card_is_ignored(db_session):
    owner = await _seed_user(db_session)
    attacker = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=owner, lemma="Tür", next_review_at=None)
    out = await apply_pronunciation_reviews(
        db_session,
        user_id=attacker,
        reviews=[_review(cid, "Tür", "Die Tür.", {2: "bad"})],
    )
    assert out == []


@pytest.mark.asyncio
async def test_focus_band_fallback_to_worst_when_focus_absent(db_session):
    uid = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=uid, lemma="Zug", next_review_at=None)
    # Foco "Zug" no aparece en la frase -> fallback peor banda (bad) -> Again.
    out = await apply_pronunciation_reviews(
        db_session,
        user_id=uid,
        reviews=[_review(cid, "Zug", "Das Auto faehrt.", {0: "good", 2: "bad", 4: "ok"})],
    )
    assert out[0].interval_days == 0.0069


@pytest.mark.asyncio
async def test_duplicate_card_ids_applied_once(db_session):
    uid = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=uid, lemma="Wort", next_review_at=None)
    out = await apply_pronunciation_reviews(
        db_session,
        user_id=uid,
        reviews=[
            _review(cid, "Wort", "Ein Wort.", {2: "good"}),
            _review(cid, "Wort", "Ein Wort.", {2: "bad"}),
        ],
    )
    assert len(out) == 1  # dedup intra-batch
    reviews = (
        (await db_session.execute(select(Review).where(Review.user_card_id == cid))).scalars().all()
    )
    assert len(reviews) == 1


@pytest.mark.asyncio
async def test_band_to_rating_never_easy(db_session):
    uid = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=uid, lemma="gut", next_review_at=None)
    out = await apply_pronunciation_reviews(
        db_session,
        user_id=uid,
        reviews=[_review(cid, "gut", "Sehr gut.", {2: "good"})],
    )
    assert out[0].interval_days == 1.0  # good -> Good (+1 day), nunca Easy
    review = (
        await db_session.execute(select(Review).where(Review.user_card_id == cid))
    ).scalar_one()
    assert review.rating == ReviewRating.GOOD
