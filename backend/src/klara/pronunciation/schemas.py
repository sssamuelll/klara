"""Response schemas for /pronunciation/score (Azure Pronunciation Assessment)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PhonemeScore(BaseModel):
    phoneme: str
    accuracy_score: float = Field(..., description="0-100, phoneme quality.")


class WordScore(BaseModel):
    word: str
    accuracy_score: float
    error_type: str = Field(..., description="None | Mispronunciation | Omission | Insertion")
    phonemes: list[PhonemeScore] = []


class PronunciationScores(BaseModel):
    accuracy: float
    fluency: float
    completeness: float
    pronunciation: float


class ScoreResponse(BaseModel):
    recognized_text: str
    reference_text: str
    language: str
    scores: PronunciationScores
    words: list[WordScore]
