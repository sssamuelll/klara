"""Schemas for the Speak voice-conversation endpoints.

camelCase aliases on the wire (TS contract), snake_case in Python — same
convention as schemas/practice.py. SpeakTurnOut is a discriminated shape:
when no_speech is true, every other field is absent/default and the client
must branch on it FIRST.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpeakTokenOut(BaseModel):
    t: str
    s: str  # "good" | "ok" | "bad"
    focus: bool


class SpeakScoresOut(BaseModel):
    accuracy: float
    fluency: float
    pronunciation: float


class SpeakTargetOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    word: str
    gloss: str | None = None
    focus_accuracy: float = Field(serialization_alias="focusAccuracy")
    should_ipa: str = Field(serialization_alias="shouldIpa")
    model_sentence: str | None = Field(default=None, serialization_alias="modelSentence")


class SpeakReplyOut(BaseModel):
    target: str
    native: str


class SpeakTurnOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    no_speech: bool = Field(default=False, serialization_alias="noSpeech")
    low_confidence: bool = Field(default=False, serialization_alias="lowConfidence")
    recognized_text: str = Field(default="", serialization_alias="recognizedText")
    tokens: list[SpeakTokenOut] = Field(default_factory=list)
    scores: SpeakScoresOut | None = None
    target: SpeakTargetOut | None = None
    focus_hit: bool = Field(default=False, serialization_alias="focusHit")
    focus_clear: bool = Field(default=False, serialization_alias="focusClear")
    reply: SpeakReplyOut | None = None


class SpeakFinishWordIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    word: str = Field(min_length=1, max_length=40)
    gloss: str | None = Field(default=None, max_length=120)
    model_sentence: str | None = Field(
        default=None, max_length=200, validation_alias="modelSentence"
    )

    @field_validator("word")
    @classmethod
    def single_token(cls, v: str) -> str:
        v = v.strip()
        if not v or any(ch.isspace() for ch in v):
            raise ValueError("word must be a single token")
        return v


class SpeakFinishIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    language: str = Field(min_length=2, max_length=8)
    focus_sound: str = Field(max_length=8, validation_alias="focusSound")
    clear_count: int = Field(ge=0, le=500, validation_alias="clearCount")
    total_count: int = Field(ge=0, le=500, validation_alias="totalCount")
    duration_seconds: int = Field(ge=0, le=7200, validation_alias="durationSeconds")
    words: list[SpeakFinishWordIn] = Field(default_factory=list, max_length=8)


class SpeakFinishOut(BaseModel):
    added: int
    skipped: int
