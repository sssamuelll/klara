from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from klara.models.enums import CardState, PartOfSpeech, ReviewRating


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


class PronunciationReviewIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    card_id: UUID = Field(validation_alias="cardId")
    focus_text: str = Field(validation_alias="focusText")
    sentence_target: str = Field(validation_alias="sentenceTarget")
    word_bands: dict[int, Literal["bad", "ok", "good"]] = Field(validation_alias="wordBands")


class PronunciationBatchIn(BaseModel):
    # Cap el batch: la cola de práctica sirve <=50 líneas (practice/queue limit),
    # así que una sesión real nunca se acerca a esto; el tope evita que un payload
    # autenticado oversized mantenga la transacción de mantenimiento abierta.
    reviews: list[PronunciationReviewIn] = Field(max_length=100)


class RescheduledCardOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    focus_text: str = Field(serialization_alias="focusText")
    interval_days: float = Field(serialization_alias="intervalDays")
    next_review_at: datetime = Field(serialization_alias="nextReviewAt")


class PronunciationBatchOut(BaseModel):
    rescheduled: list[RescheduledCardOut]
