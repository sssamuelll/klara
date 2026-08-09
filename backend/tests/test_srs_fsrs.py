"""Contrato FSRS (#125 v1): reemplaza SM-2 lite en el canal de recall.

- schedule_next_review delega en fsrs.Scheduler (desired_retention de settings,
  fuzzing APAGADO: el intervalo mostrado == el persistido, decisión D-D).
- project_intervals produce el preview honesto por rating (CardOut.next_intervals).
- El backfill (srs_backfill.backfill_fsrs_state) replay-ea el ledger `reviews`
  vía reschedule_card SIN tocar campos operativos (transición gradual, default
  de fsrs4anki): solo llena stability/difficulty/fsrs_step/fsrs_last_review.
- reviews.channel discrimina recall vs pronunciation (gate del Optimizer v2:
  el ledger mezclaba ambos canales sin discriminador — hallazgo del recon).
- El canal de mantenimiento de pronunciación sigue congelado: jamás escribe
  estado FSRS (extiende la invariante ease/repetitions/state de siempre).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from klara.models import Review, User, UserCard, VocabItem
from klara.models.enums import CardState, PartOfSpeech, ReviewRating
from klara.schemas.srs import PronunciationReviewIn
from klara.services.practice_session import apply_pronunciation_reviews
from klara.services.srs_backfill import backfill_fsrs_state
from klara.services.srs_engine import (
    get_scheduler,
    project_intervals,
    schedule_next_review,
)

# vocab_items NO se trunca entre tests — namespacea language (patrón de
# test_srs_recall.py).
_LANG = f"de-{uuid.uuid4().hex[:4]}"


def _card(**kw) -> UserCard:
    """UserCard en memoria con todos los campos que el motor lee, explícitos
    (los defaults de columna no aplican sin flush)."""
    defaults = dict(
        user_id=uuid.uuid4(),
        vocab_item_id=uuid.uuid4(),
        ease=2.5,
        interval_days=0.0,
        repetitions=0,
        next_review_at=None,
        last_reviewed_at=None,
        state=CardState.NEW,
        stability=None,
        difficulty=None,
        fsrs_step=None,
        fsrs_last_review=None,
    )
    defaults.update(kw)
    return UserCard(**defaults)


def _reviewing_card(days: float = 20.0) -> UserCard:
    now = datetime.now(UTC)
    return _card(
        state=CardState.REVIEWING,
        interval_days=days,
        repetitions=5,
        stability=days,
        difficulty=5.0,
        fsrs_last_review=now - timedelta(days=days),
        next_review_at=now,
    )


# ---------------------------------------------------------------- motor puro


def test_new_good_enters_learning():
    card = _card()
    interval, next_at, state = schedule_next_review(card, ReviewRating.GOOD)
    # FSRS: carta nueva + GOOD avanza al segundo learning step (~10 min), no
    # gradúa a 1 día como SM-2.
    assert state == CardState.LEARNING
    assert 0 < interval < 1.0
    assert next_at > datetime.now(UTC)
    assert card.stability is not None
    assert card.difficulty is not None
    assert card.fsrs_last_review is not None
    assert card.fsrs_step == 1
    assert card.repetitions == 1


def test_second_good_graduates_to_reviewing():
    card = _card()
    interval, next_at, state = schedule_next_review(card, ReviewRating.GOOD)
    # el router persiste el trío devuelto — espejamos eso entre llamadas
    card.interval_days, card.next_review_at, card.state = interval, next_at, state
    interval, _, state = schedule_next_review(card, ReviewRating.GOOD)
    assert state == CardState.REVIEWING
    assert interval >= 1.0
    assert card.fsrs_step is None  # graduada: fuera de learning steps


def test_again_on_reviewing_relearns():
    card = _reviewing_card()
    interval, _, state = schedule_next_review(card, ReviewRating.AGAIN)
    assert state == CardState.RELEARNING
    assert interval < 1.0  # relearning step ~10 min
    assert card.repetitions == 0
    assert card.stability is not None and card.stability < 20.0


def test_cold_start_reviewing_good_reaches_mastery():
    # Espejo exacto del seeding de test_modules (carta sin estado FSRS ni
    # last_reviewed_at): un GOOD sobre 20d debe superar el umbral de mastery
    # (21d) — contrato que mantiene vivo el avance de módulo.
    card = _card(state=CardState.REVIEWING, interval_days=20.0, repetitions=3)
    interval, _, state = schedule_next_review(card, ReviewRating.GOOD)
    assert state == CardState.REVIEWING
    assert interval >= 21.0
    assert card.repetitions == 4


def test_project_intervals_shape_order_determinism():
    card = _reviewing_card()
    a = project_intervals(card)
    b = project_intervals(card)
    assert a == b  # fuzzing apagado → determinista
    assert set(a) == {"again", "hard", "good", "easy"}
    assert all(v > 0 for v in a.values())
    assert a["again"] < a["hard"] < a["good"] < a["easy"]
    # el preview NO muta la carta
    assert card.stability == 20.0
    assert card.interval_days == 20.0
    assert card.state == CardState.REVIEWING


def test_project_intervals_new_card_untouched():
    card = _card()
    p = project_intervals(card)
    assert p["again"] < p["good"]
    assert card.stability is None
    assert card.state == CardState.NEW


def test_scheduler_settings_and_no_fuzzing(app_settings):
    app_settings(SRS_DESIRED_RETENTION="0.8")
    scheduler = get_scheduler()
    assert scheduler.desired_retention == 0.8
    assert scheduler.enable_fuzzing is False


# ------------------------------------------------------------- endpoints


async def _register_and_login(client, seed_invite, email: str) -> str:
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def _add_due_card(db, user_id, *, lemma: str) -> UserCard:
    vocab = VocabItem(
        language=_LANG,
        lemma=lemma,
        pos=PartOfSpeech.NOUN,
        gender=None,
        gender_source="llm",
        translations={"es": "x"},
        example_target="Ein Satz.",
    )
    db.add(vocab)
    await db.flush()
    card = UserCard(
        user_id=user_id, vocab_item_id=vocab.id, next_review_at=None, state=CardState.NEW
    )
    db.add(card)
    await db.commit()
    return card


@pytest.mark.asyncio
async def test_review_persists_fsrs_state_and_channel(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite, "fsrs1@example.com")
    user = (
        await db_session.execute(select(User).where(User.email == "fsrs1@example.com"))
    ).scalar_one()
    card = await _add_due_card(db_session, user.id, lemma="Fenster")

    r = await client.post(
        f"/api/v1/srs/cards/{card.id}/review",
        json={"rating": "good"},
        headers={"Cookie": cookie},
    )
    assert r.status_code == 200, r.text

    await db_session.refresh(card)
    assert card.stability is not None
    assert card.difficulty is not None
    assert card.fsrs_last_review is not None
    review = (
        await db_session.execute(select(Review).where(Review.user_card_id == card.id))
    ).scalar_one()
    assert review.channel == "recall"


@pytest.mark.asyncio
async def test_due_payload_includes_next_intervals(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite, "fsrs2@example.com")
    user = (
        await db_session.execute(select(User).where(User.email == "fsrs2@example.com"))
    ).scalar_one()
    await _add_due_card(db_session, user.id, lemma="Spiegel")

    r = await client.get("/api/v1/srs/cards/due", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    (card_json,) = [c for c in r.json() if c["lemma"] == "Spiegel"]
    ni = card_json["next_intervals"]
    assert set(ni) == {"again", "hard", "good", "easy"}
    assert all(isinstance(v, (int, float)) and v > 0 for v in ni.values())
    assert ni["again"] < ni["good"]


@pytest.mark.asyncio
async def test_pronunciation_keeps_fsrs_frozen_and_tags_channel(db_session):
    # Canal congelado: el mantenimiento de pronunciación mueve interval/next
    # pero JAMÁS el estado FSRS (la extensión natural de su invariante).
    user = User(
        id=uuid.uuid4(),
        email=f"fsrs-pron-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="P",
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.flush()
    vocab = VocabItem(
        language=_LANG,
        lemma="Haus",
        pos=PartOfSpeech.NOUN,
        gender="das",
        gender_source="oracle",
        translations={"es": "casa"},
        example_target="Das Haus ist groß.",
    )
    db_session.add(vocab)
    await db_session.flush()
    now = datetime.now(UTC)
    card = UserCard(
        user_id=user.id,
        vocab_item_id=vocab.id,
        state=CardState.REVIEWING,
        interval_days=12.0,
        repetitions=4,
        next_review_at=now - timedelta(hours=1),
        stability=12.0,
        difficulty=4.0,
        fsrs_step=None,
        fsrs_last_review=now - timedelta(days=12),
    )
    db_session.add(card)
    await db_session.commit()

    out = await apply_pronunciation_reviews(
        db_session,
        user_id=user.id,
        reviews=[
            PronunciationReviewIn(
                card_id=card.id,
                focus_text="Haus",
                sentence_target="Das Haus ist groß",
                word_bands={1: "good"},
            )
        ],
    )
    await db_session.commit()
    assert len(out) == 1

    await db_session.refresh(card)
    assert card.stability == 12.0
    assert card.difficulty == 4.0
    assert card.fsrs_step is None
    assert card.state == CardState.REVIEWING
    assert card.fsrs_last_review == now - timedelta(days=12)
    review = (
        await db_session.execute(select(Review).where(Review.user_card_id == card.id))
    ).scalar_one()
    assert review.channel == "pronunciation"


# --------------------------------------------------------------- backfill


async def _seed_card_with_history(db, *, n_reviews: int) -> UserCard:
    user = User(
        id=uuid.uuid4(),
        email=f"fsrs-bf-{uuid.uuid4().hex[:6]}@example.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="B",
        native_language="es",
        target_language="de",
    )
    db.add(user)
    await db.flush()
    vocab = VocabItem(
        language=_LANG,
        lemma=f"W{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN,
        gender=None,
        gender_source="llm",
        translations={"es": "x"},
        example_target="Ein Satz.",
    )
    db.add(vocab)
    await db.flush()
    now = datetime.now(UTC)
    card = UserCard(
        user_id=user.id,
        vocab_item_id=vocab.id,
        state=CardState.REVIEWING,
        interval_days=6.0,
        repetitions=n_reviews,
        next_review_at=now + timedelta(days=6),
        last_reviewed_at=now - timedelta(days=6) if n_reviews else None,
    )
    db.add(card)
    await db.flush()
    for i in range(n_reviews):
        db.add(
            Review(
                user_card_id=card.id,
                user_id=user.id,
                rating=ReviewRating.GOOD,
                prev_interval_days=float(i),
                new_interval_days=float(i + 1),
                reviewed_at=now - timedelta(days=15 - 3 * i),
            )
        )
    await db.commit()
    return card


@pytest.mark.asyncio
async def test_backfill_replays_ledger_without_touching_operational_fields(db_session):
    card = await _seed_card_with_history(db_session, n_reviews=3)
    prev_next = card.next_review_at
    prev_interval = card.interval_days
    prev_state = card.state

    updated = await db_session.run_sync(backfill_fsrs_state)
    assert updated == 1

    await db_session.refresh(card)
    assert card.stability is not None and card.stability > 0
    assert card.difficulty is not None
    # fsrs_last_review = la última review del ledger (now-9d, la más reciente)
    last = card.fsrs_last_review
    assert last is not None
    assert abs((last - (datetime.now(UTC) - timedelta(days=9))).total_seconds()) < 60
    # transición gradual: los campos operativos NO se reescriben
    assert card.next_review_at == prev_next
    assert card.interval_days == prev_interval
    assert card.state == prev_state


@pytest.mark.asyncio
async def test_backfill_skips_no_history_and_is_idempotent(db_session):
    bare = await _seed_card_with_history(db_session, n_reviews=0)
    seeded = await _seed_card_with_history(db_session, n_reviews=2)

    first = await db_session.run_sync(backfill_fsrs_state)
    assert first == 1  # solo la carta con historial

    await db_session.refresh(bare)
    await db_session.refresh(seeded)
    assert bare.stability is None  # sin reviews no se inventa memoria
    stability_after_first = seeded.stability
    assert stability_after_first is not None

    second = await db_session.run_sync(backfill_fsrs_state)
    assert second == 0  # idempotente: ya-backfilled no se re-toca

    await db_session.refresh(seeded)
    assert seeded.stability == stability_after_first
