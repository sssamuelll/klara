from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from german_app.dependencies import CurrentUser, DBSession
from german_app.models import Review, UserCard, VocabItem
from german_app.schemas.srs import CardCreateRequest, CardOut, ReviewOut, ReviewSubmitRequest
from german_app.services.srs_engine import schedule_next_review

router = APIRouter(prefix="/srs", tags=["srs"])


def _card_to_out(card: UserCard, vocab: VocabItem) -> CardOut:
    return CardOut(
        id=card.id,
        vocab_item_id=vocab.id,
        lemma=vocab.lemma,
        pos=vocab.pos,
        translation_es=vocab.translation_es,
        example_de=vocab.example_de,
        state=card.state,
        interval_days=card.interval_days,
        next_review_at=card.next_review_at,
        repetitions=card.repetitions,
    )


@router.post("/cards", response_model=CardOut, status_code=status.HTTP_201_CREATED)
async def add_card(payload: CardCreateRequest, db: DBSession, user: CurrentUser) -> CardOut:
    vocab = await db.get(VocabItem, payload.vocab_item_id)
    if vocab is None:
        raise HTTPException(status_code=404, detail="Vocab item not found")

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
        return _card_to_out(existing, vocab)

    await db.commit()
    card = await db.get(UserCard, new_id)
    assert card is not None
    return _card_to_out(card, vocab)


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
    return [_card_to_out(c, v) for c, v in rows]


@router.post("/cards/{card_id}/review", response_model=ReviewOut)
async def submit_review(
    card_id: UUID,
    payload: ReviewSubmitRequest,
    db: DBSession,
    user: CurrentUser,
) -> ReviewOut:
    card = await db.get(UserCard, card_id)
    if card is None or card.user_id != user.id:
        raise HTTPException(status_code=404, detail="Card not found")

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
