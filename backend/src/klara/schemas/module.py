from uuid import UUID

from pydantic import BaseModel

from klara.models.enums import CEFRLevel


class ModuleCurrentOut(BaseModel):
    id: UUID
    title: str
    cefr_level: CEFRLevel
    can_dos: list[str]
    grammatical_focus: list[str]
    encountered: int
    mastered: int
    total: int
    gender_encountered: int
    gender_mastered: int
    gender_total: int


class ModulePathItemOut(BaseModel):
    id: UUID
    sequence_order: int
    title: str
    cefr_level: CEFRLevel
    can_dos: list[str]
    grammatical_focus: list[str]
    encountered: int
    mastered: int
    total: int
    gender_encountered: int
    gender_mastered: int
    gender_total: int
    stories_finished: int
    stories_to_complete: int
    completed: bool
    is_current: bool
    unlocked: bool
    library_available: int
