"""La respuesta de GET /today (spec 2026-09-30 §2.3)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Step = Literal["read", "pronounce", "speak", "review"]


class TodaySteps(BaseModel):
    read: bool
    pronounce: bool
    speak: bool
    review: bool


class TodayStory(BaseModel):
    state: Literal["done", "continue", "new", "request"]
    id: UUID | None = None
    library_entry_id: UUID | None = None
    module_id: UUID | None = None
    title: str | None = None
    subtitle: str | None = None
    illustration_path: str | None = None


class TodaySentence(BaseModel):
    target: str
    native: str


class TodayModule(BaseModel):
    id: UUID
    title: str
    cefr_level: str


class TodayOut(BaseModel):
    now: Step | None
    steps: TodaySteps
    story: TodayStory
    sentence: TodaySentence | None
    due: int
    module: TodayModule | None
