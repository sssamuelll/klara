"""Schemas for the end-of-story flow: quiz, insight, and attempt records."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ---- Quiz item types (discriminated by `type`) ---------------------------
# Stored as JSONB inside Story.quiz_items, served as a polymorphic list to
# the frontend. Keep each type's fields minimal — the rendering details
# live in the frontend's question components.


class MCQuizItem(BaseModel):
    type: Literal["mc"]
    cap: str
    prompt: str
    options: list[str] = Field(..., min_length=2, max_length=4)
    correct: int
    after: str | None = None


class ClozeQuizItem(BaseModel):
    type: Literal["cloze"]
    cap: str
    sentence_pre: str
    sentence_post: str = ""
    answer: str
    en: str | None = None
    hint: str | None = None


class ShadowQuizItem(BaseModel):
    type: Literal["shadow"]
    cap: str
    sentence: str
    en: str | None = None
    after: str | None = None


class GenderClozeQuizItem(BaseModel):
    type: Literal["gender_cloze"]
    cap: str
    lemma: str
    vocab_item_id: str
    en: str | None = None  # native-language gloss for context; NOT the answer


QuizItem = MCQuizItem | ClozeQuizItem | ShadowQuizItem | GenderClozeQuizItem


class QuizOut(BaseModel):
    items: list[QuizItem]


class InsightOut(BaseModel):
    title: str
    body: str


class KlaraNoteOut(BaseModel):
    body: str


# ---- Attempt records ----------------------------------------------------


class PronunciationAttemptIn(BaseModel):
    """Recorded after Azure scoring lands client-side. Best-effort."""

    sentence_index: int = Field(..., ge=0, le=100)
    reference_text: str = Field(..., min_length=1, max_length=2000)
    recognized_text: str | None = Field(default=None, max_length=2000)
    overall_score: float = Field(..., ge=0, le=100)
    # Keyed by full token index (matches bandsByTokenIndex on the frontend).
    word_bands: dict[str, str] = Field(default_factory=dict)


class PronunciationAttemptOut(BaseModel):
    id: UUID
    sentence_index: int
    overall_score: float
    attempted_at: datetime


class QuizAttemptIn(BaseModel):
    question_index: int = Field(..., ge=0, le=20)
    # gender_cloze is deliberately NOT accepted here: this generic endpoint trusts
    # the client's was_correct, whereas gender is graded server-side and recorded
    # via POST /gender/attempts. Excluding it keeps the single-write guarantee.
    question_type: Literal["mc", "cloze", "shadow"]
    was_correct: bool
    was_revealed: bool = False
    detail: dict | None = None


class QuizAttemptOut(BaseModel):
    id: UUID
    question_index: int
    question_type: str
    was_correct: bool
    was_revealed: bool
    attempted_at: datetime


class GenderAttemptIn(BaseModel):
    vocab_item_id: UUID
    picked_article: Literal["der", "die", "das"]


class GenderAttemptOut(BaseModel):
    was_correct: bool
    correct_gender: str


# ---- Schedule entries — per-target-word SRS state for the Finish summary -


# Coarse buckets the frontend turns into localized labels. The exact day
# thresholds live on the backend so all clients format identically.
ScheduleBucket = Literal[
    "not_in_srs",  # never added a card for this word
    "due_now",  # overdue OR due within 24h
    "soon",  # due in 1-3 days
    "this_week",  # due in 4-7 days
    "next_week",  # due in 8-14 days
    "later",  # due in 15+ days
]


class ScheduleEntry(BaseModel):
    vocab_item_id: UUID
    has_card: bool
    bucket: ScheduleBucket
    next_review_at: datetime | None = None


class ScheduleOut(BaseModel):
    entries: list[ScheduleEntry]


class MCResolveOut(BaseModel):
    """Result of voice-resolving an MC quiz answer.

    `picked_index` is null when nothing matches well enough — the UI
    should ask the user to repeat instead of guessing.
    """

    transcript: str
    picked_index: int | None
    option_scores: list[float] = Field(default_factory=list)
