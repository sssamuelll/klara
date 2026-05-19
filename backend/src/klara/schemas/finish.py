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


QuizItem = MCQuizItem | ClozeQuizItem | ShadowQuizItem


class QuizOut(BaseModel):
    items: list[QuizItem]


class InsightOut(BaseModel):
    title: str
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
