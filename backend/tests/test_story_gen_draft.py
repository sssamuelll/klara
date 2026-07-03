"""generate_story_draft: the user-less generation core (library build + create_story share it)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from klara.llm.base import LLMResponse
from klara.models import Story
from klara.models.enums import CEFRLevel
from klara.services.story_gen import generate_story_draft

STORY_JSON = {
    "title": "Der Kaffee am Morgen",
    "sentences": [
        {
            "target": "Ich trinke Kaffee mit Milch.",
            "native": "Bebo café con leche.",
            "new_words": ["Kaffee", "Milch"],
            "breakdown": [
                {"word": "Ich", "translation": "yo"},
                {"word": "trinke", "translation": "bebo"},
                {"word": "Kaffee", "translation": "café"},
                {"word": "mit", "translation": "con"},
                {"word": "Milch", "translation": "leche"},
            ],
        }
    ],
    "comprehension_questions": [],
    "target_words": [
        {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translation": "café"},
        {"lemma": "Milch", "pos": "noun", "gender": "die", "translation": "leche"},
        {"lemma": "Zucker", "pos": "noun", "gender": "der", "translation": "azúcar"},
    ],
    "quiz_items": None,
}


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        self.calls += 1
        return LLMResponse(content=self.content, model="fake", provider="fake", cost_usd=0.001)

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_draft_creates_no_story_row_and_reports_dropped(db_session):
    llm = FakeLLM(json.dumps(STORY_JSON))
    draft = await generate_story_draft(
        db_session,
        llm,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        learning_context=None,
        topic="pedir un café",
        model=None,
        target_lemmas=["Kaffee", "Milch", "Zucker"],
        module_objective=None,
        avoid_lemmas=[],
    )
    assert draft.title == "Der Kaffee am Morgen"
    # Zucker was declared but never appears in the text → coverage drops it.
    assert "Zucker" in draft.dropped_lemmas
    kept = {w.lemma for w in draft.target_words}
    assert kept == {"Kaffee", "Milch"}
    assert draft.provider == "fake"
    n_stories = (await db_session.execute(select(func.count()).select_from(Story))).scalar_one()
    assert n_stories == 0
