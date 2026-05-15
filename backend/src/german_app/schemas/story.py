from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from german_app.models.enums import CEFRLevel, PartOfSpeech


class StoryWordOut(BaseModel):
    id: UUID
    lemma: str
    pos: PartOfSpeech
    gender: str | None = None
    plural: str | None = None
    translation: str | None = None
    example_target: str | None = None


class StorySentenceOut(BaseModel):
    target: str
    native: str
    new_words: list[str] = Field(default_factory=list)


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


class StoryCreateRequest(BaseModel):
    topic: str | None = None
    level: CEFRLevel | None = None


class StoryListItem(BaseModel):
    id: UUID
    level: CEFRLevel
    target_language: str
    title: str
    created_at: datetime
