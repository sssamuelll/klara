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
