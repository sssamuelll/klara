from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from german_app.models.enums import CardState, PartOfSpeech, ReviewRating


class CardCreateRequest(BaseModel):
    vocab_item_id: UUID


class CardOut(BaseModel):
    id: UUID
    vocab_item_id: UUID
    lemma: str
    pos: PartOfSpeech
    translation: str | None
    example_target: str | None
    state: CardState
    interval_days: float
    next_review_at: datetime | None
    repetitions: int


class ReviewSubmitRequest(BaseModel):
    rating: ReviewRating
    elapsed_seconds: int | None = None


class ReviewOut(BaseModel):
    id: UUID
    user_card_id: UUID
    rating: ReviewRating
    prev_interval_days: float
    new_interval_days: float
    reviewed_at: datetime
