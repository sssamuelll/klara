"""build_library: coverage gate, idempotency, per-module counts (FakeLLM)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from klara.llm.base import LLMResponse
from klara.models import StoryLibrary
from klara.scripts.build_story_library import build_library


def _story_json(sentence: str, lemma: str) -> str:
    return json.dumps(
        {
            "title": f"Geschichte {lemma}",
            "sentences": [
                {
                    "target": sentence,
                    "native": "x",
                    "new_words": [lemma],
                    "breakdown": [{"word": lemma, "translation": "x"}],
                }
            ],
            "comprehension_questions": [],
            "target_words": [{"lemma": lemma, "pos": "noun", "gender": "der", "translation": "x"}],
            "quiz_items": None,
        }
    )


class SequenceLLM:
    """Returns a different story per call so content hashes differ."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        self.calls += 1
        return LLMResponse(
            content=_story_json(f"Der Kaffee Nummer {self.calls} ist gut. Kaffee!", "Kaffee"),
            model="fake",
            provider="fake",
            cost_usd=0.001,
        )

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_build_inserts_per_module_and_is_idempotent(db_session):
    # Seed the module + its vocab via the real loader (same path prod uses).
    from klara.curriculum.modules import load_modules

    await load_modules(
        db_session,
        language="de",
        modules=[
            {
                "sequence_order": 1,
                "title": "En el café",
                "cefr_level": "A1",
                "can_dos": ["pedir"],
                "grammatical_focus": ["género"],
                "vocab": [
                    {
                        "lemma": "Kaffee",
                        "pos": "noun",
                        "gender": "der",
                        "translations": {"es": "café"},
                    }
                ],
            }
        ],
    )
    await db_session.commit()

    warmed: list[list[str]] = []

    async def warm(texts: list[str]) -> None:
        warmed.append(texts)

    n = await build_library(
        db_session, SequenceLLM(), language="de", native="es", per_module=2, warm_audio=warm
    )
    await db_session.commit()
    assert n == 2
    assert len(warmed) == 2
    count = (await db_session.execute(select(func.count()).select_from(StoryLibrary))).scalar_one()
    assert count == 2
    row = (await db_session.execute(select(StoryLibrary).limit(1))).scalar_one()
    assert row.source == "seed"
    assert row.native_language == "es"

    # Re-run: hashes differ per call BUT the per-module target count is already
    # met, so nothing new is inserted.
    n2 = await build_library(
        db_session, SequenceLLM(), language="de", native="es", per_module=2, warm_audio=warm
    )
    assert n2 == 0
