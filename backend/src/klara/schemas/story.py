from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from klara.models.enums import CEFRLevel, PartOfSpeech


class StoryWordOut(BaseModel):
    id: UUID
    lemma: str
    pos: PartOfSpeech
    gender: str | None = None
    plural: str | None = None
    translation: str | None = None
    example_target: str | None = None
    frequency_rank: int | None = None


class WordBreakdown(BaseModel):
    """Per-word translation for the in-sentence tooltip (issue #24).

    Optional on the parent sentence — old stories generated before this
    field existed have `breakdown=None` and the UI falls back to making
    only the LLM-flagged target_words tappable.
    """

    word: str = Field(..., min_length=1, max_length=80)
    translation: str = Field(..., min_length=1, max_length=120)
    pos: str | None = Field(default=None, max_length=20)


class StorySentenceOut(BaseModel):
    target: str
    native: str
    new_words: list[str] = Field(default_factory=list)
    breakdown: list[WordBreakdown] | None = None


class ComprehensionQuestionOut(BaseModel):
    q_target: str
    q_native: str
    options_target: list[str]
    correct_index: int


class StoryContent(BaseModel):
    sentences: list[StorySentenceOut]
    comprehension_questions: list[ComprehensionQuestionOut] = Field(default_factory=list)


class StoryOut(BaseModel):
    id: UUID
    level: CEFRLevel
    target_language: str
    native_language: str
    title: str
    content: StoryContent
    target_words: list[StoryWordOut]
    generated_by_provider: str | None = None
    generated_by_model: str | None = None
    generation_cost_usd: float | None = None
    created_at: datetime
    curriculum_note: str | None = None
    module_id: UUID | None = None


class StoryCreateRequest(BaseModel):
    topic: str | None = None
    level: CEFRLevel | None = None
    # Explicit module conditioning (path module screen). None → active module.
    module_id: UUID | None = None
    # The backend can't distinguish a suggestion chip from free text; the pool
    # must never serve personal free-text topics to other users (spec §7).
    topic_origin: Literal["chip", "free", "none"] = "none"


class StoryListItem(BaseModel):
    id: UUID
    level: CEFRLevel
    target_language: str
    title: str
    created_at: datetime
