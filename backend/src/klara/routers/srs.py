from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from klara.curriculum.modules import advance_module_if_mastered
from klara.dependencies import CurrentUser, DBSession, LocaleDep
from klara.i18n import t
from klara.models import Review, UserCard, VocabItem
from klara.schemas.srs import (
    CardCreateRequest,
    CardOut,
    PronunciationBatchIn,
    PronunciationBatchOut,
    ReviewOut,
    ReviewSubmitRequest,
)
from klara.services.practice_session import apply_pronunciation_reviews
from klara.services.srs_engine import schedule_next_review

router = APIRouter(prefix="/srs", tags=["srs"])


def _card_to_out(card: UserCard, vocab: VocabItem, native_language: str) -> CardOut:
    return CardOut(
        id=card.id,
        vocab_item_id=vocab.id,
        lemma=vocab.lemma,
        pos=vocab.pos,
        translation=(vocab.translations or {}).get(native_language),
        example_target=vocab.example_target,
        state=card.state,
        interval_days=card.interval_days,
        next_review_at=card.next_review_at,
        repetitions=card.repetitions,
    )


@router.post("/cards", response_model=CardOut, status_code=status.HTTP_201_CREATED)
async def add_card(
    payload: CardCreateRequest, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> CardOut:
    vocab = await db.get(VocabItem, payload.vocab_item_id)
    if vocab is None:
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))

    stmt = (
        pg_insert(UserCard)
        .values(user_id=user.id, vocab_item_id=vocab.id)
        .on_conflict_do_nothing(constraint="uq_user_card_user_vocab")
        .returning(UserCard.id)
    )
    result = await db.execute(stmt)
    new_id = result.scalar_one_or_none()
    if new_id is None:
        existing = (
            await db.execute(
                select(UserCard).where(
                    UserCard.user_id == user.id, UserCard.vocab_item_id == vocab.id
                )
            )
        ).scalar_one()
        await db.commit()
        return _card_to_out(existing, vocab, user.native_language)

    await db.commit()
    card = await db.get(UserCard, new_id)
    assert card is not None
    return _card_to_out(card, vocab, user.native_language)


@router.get("/cards/due", response_model=list[CardOut])
async def due_cards(
    db: DBSession,
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
) -> list[CardOut]:
    now = datetime.now(UTC)
    stmt = (
        select(UserCard, VocabItem)
        .join(VocabItem, VocabItem.id == UserCard.vocab_item_id)
        .where(
            UserCard.user_id == user.id,
            or_(UserCard.next_review_at.is_(None), UserCard.next_review_at <= now),
        )
        .order_by(UserCard.next_review_at.asc().nullsfirst())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [_card_to_out(c, v, user.native_language) for c, v in rows]


@router.post("/cards/{card_id}/review", response_model=ReviewOut)
async def submit_review(
    card_id: UUID,
    payload: ReviewSubmitRequest,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
) -> ReviewOut:
    card = await db.get(UserCard, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status_code=404, detail=t("errors.card_not_found", locale))

    prev_interval = card.interval_days
    new_interval, next_review, new_state = schedule_next_review(card, payload.rating)
    card.interval_days = new_interval
    card.next_review_at = next_review
    card.last_reviewed_at = datetime.now(UTC)
    card.state = new_state

    review = Review(
        user_card_id=card.id,
        user_id=user.id,
        rating=payload.rating,
        elapsed_seconds=payload.elapsed_seconds,
        prev_interval_days=prev_interval,
        new_interval_days=new_interval,
    )
    db.add(review)
    await advance_module_if_mastered(db, user=user, reviewed_vocab_item_id=card.vocab_item_id)
    await db.commit()
    await db.refresh(review)

    return ReviewOut(
        id=review.id,
        user_card_id=review.user_card_id,
        rating=review.rating,
        prev_interval_days=review.prev_interval_days,
        new_interval_days=review.new_interval_days,
        reviewed_at=review.reviewed_at,
    )


@router.post(
    "/cards/review-batch",
    response_model=PronunciationBatchOut,
    response_model_by_alias=True,
)
async def review_batch(
    payload: PronunciationBatchIn,
    db: DBSession,
    user: CurrentUser,
) -> PronunciationBatchOut:
    """Cierra el ciclo SRS desde una sesión de Practice: reprograma (mantenimiento)
    cada carta DUE del usuario respaldando una línea pronunciada. Atómico, idempotente
    por card_id. Las cartas no-due y las que no son del usuario se ignoran en silencio."""
    rescheduled = await apply_pronunciation_reviews(db, user_id=user.id, reviews=payload.reviews)
    return PronunciationBatchOut(rescheduled=rescheduled)
