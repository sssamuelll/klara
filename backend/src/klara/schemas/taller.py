"""Schemas del taller (F0): tarjetas de tema libre, aisladas del dominio de alemán."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from klara.models.enums import CardState, ReviewRating


def _validate_card_text(value: str, max_length: int) -> str:
    """strip() y reglas de longitud; rechaza TAB/CR/LF.

    El export TSV une columnas con `\t` sin escapar, así que esos caracteres se
    rechazan en la frontera, no se escapan al exportar.
    """
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    if len(text) > max_length:
        raise ValueError(f"must be at most {max_length} characters")
    if any(ch in text for ch in "\t\r\n"):
        raise ValueError("must not contain tab, CR or LF characters")
    return text


def _normalize_tags(tags: list[str]) -> list[str]:
    """strip + lower, dedupe preservando el orden de primera aparición."""
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in tags:
        tag = raw.strip().lower()
        if tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def _validate_tags(tags: list[str]) -> list[str]:
    if len(tags) > 10:
        raise ValueError("at most 10 tags")
    normalized = _normalize_tags(tags)
    for tag in normalized:
        if not 1 <= len(tag) <= 32:
            raise ValueError("each tag must be 1..32 characters after normalization")
    return normalized


class CardCreateIn(BaseModel):
    front: str
    back: str
    tags: list[str] = Field(default_factory=list)
    batch_id: UUID

    @field_validator("front")
    @classmethod
    def _check_front(cls, value: str) -> str:
        return _validate_card_text(value, max_length=500)

    @field_validator("back")
    @classmethod
    def _check_back(cls, value: str) -> str:
        return _validate_card_text(value, max_length=2000)

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, value: list[str]) -> list[str]:
        return _validate_tags(value)


class BulkCardIn(BaseModel):
    front: str
    back: str

    @field_validator("front")
    @classmethod
    def _check_front(cls, value: str) -> str:
        return _validate_card_text(value, max_length=500)

    @field_validator("back")
    @classmethod
    def _check_back(cls, value: str) -> str:
        return _validate_card_text(value, max_length=2000)


class BulkCreateIn(BaseModel):
    cards: list[BulkCardIn] = Field(min_length=1, max_length=200)
    tags: list[str] = Field(default_factory=list)
    batch_id: UUID

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, value: list[str]) -> list[str]:
        return _validate_tags(value)


class ReviewIn(BaseModel):
    rating: ReviewRating
    elapsed_seconds: int | None = None
    # Obligatorio, sin default: si el cliente no lo manda, 422.
    device: Literal["desktop", "mobile"]

    @field_validator("elapsed_seconds")
    @classmethod
    def _clamp_elapsed_seconds(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return min(value, 3600)


class StudyCardOut(BaseModel):
    id: UUID
    front: str
    back: str
    tags: list[str]
    batch_id: UUID
    archived_at: datetime | None
    state: CardState
    interval_days: float
    next_review_at: datetime
    last_reviewed_at: datetime | None
    repetitions: int
    next_intervals: dict[str, float]
    created_at: datetime
    updated_at: datetime


class TagCountOut(BaseModel):
    tag: str
    count: int


class OverviewOut(BaseModel):
    total: int
    due: int
    tags: list[TagCountOut]


class CardListOut(BaseModel):
    total: int
    items: list[StudyCardOut]


class BulkOut(BaseModel):
    created: int
    cards: list[StudyCardOut]
