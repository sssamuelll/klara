"""build_library: coverage gate, idempotency, per-module counts (FakeLLM)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from klara.llm.base import LLMResponse
from klara.models import StoryLibrary
from klara.scripts.build_story_library import TOPICS, build_library


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


async def _seed_cafe_module(db) -> None:
    """Module seq 1 with the single lemma 'Kaffee' (same loader path as prod)."""
    from klara.curriculum.modules import load_modules

    await load_modules(
        db,
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
    await db.commit()


def _scripted_response(sentence: str) -> LLMResponse:
    """Story JSON whose coverage is decided by the sentence alone: coverage
    scans target text AND breakdown words, so the breakdown must mirror the
    sentence (a lemma-carrying breakdown would mask an omitting sentence)."""
    story = json.loads(_story_json(sentence, "Kaffee"))
    story["sentences"][0]["breakdown"] = [{"word": sentence.split()[0], "translation": "x"}]
    return LLMResponse(content=json.dumps(story), model="fake", provider="fake")


class ScriptedLLM:
    """Yields one scripted sentence per call (last one repeats); the lemma is
    'Kaffee', so any sentence omitting it trips the coverage gate."""

    def __init__(self, sentences: list[str]) -> None:
        self.sentences = sentences
        self.calls = 0

    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        sentence = self.sentences[min(self.calls, len(self.sentences) - 1)]
        self.calls += 1
        return _scripted_response(sentence)

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


class TopicLLM(ScriptedLLM):
    """Omits the lemma (→ coverage failure) whenever the prompt carries one of
    the failing topics; otherwise emits a distinct covering sentence."""

    def __init__(self, failing: set[str]) -> None:
        super().__init__([])
        self.failing = failing

    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        self.calls += 1
        user = messages[-1].content
        if any(t in user for t in self.failing):
            sentence = "Das ist gut."  # no 'Kaffee' → dropped
        else:
            sentence = f"Der Kaffee Nummer {self.calls} ist gut."
        return _scripted_response(sentence)


@pytest.mark.asyncio
async def test_coverage_gate_retries_then_inserts(db_session):
    await _seed_cafe_module(db_session)
    # First response omits the lemma (coverage failure), second covers it.
    llm = ScriptedLLM(["Das ist gut.", "Der Kaffee ist sehr gut."])
    n = await build_library(db_session, llm, language="de", native="es", per_module=1)
    await db_session.commit()
    assert n == 1
    assert llm.calls == 2  # the retry actually happened
    count = (await db_session.execute(select(func.count()).select_from(StoryLibrary))).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_coverage_gate_gives_up_cleanly(db_session):
    await _seed_cafe_module(db_session)
    llm = ScriptedLLM(["Das ist gut."])  # never covers the lemma
    n = await build_library(db_session, llm, language="de", native="es", per_module=1)
    assert n == 0
    assert llm.calls == 3  # max_attempts exhausted, then skip-with-log
    count = (await db_session.execute(select(func.count()).select_from(StoryLibrary))).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_resume_regenerates_only_the_missing_topic(db_session):
    await _seed_cafe_module(db_session)
    topic_a, topic_b = TOPICS[1][:2]

    # Run 1: topic B exhausts retries, topic A succeeds → partial seed.
    llm = TopicLLM(failing={topic_b})
    n1 = await build_library(db_session, llm, language="de", native="es", per_module=2)
    await db_session.commit()
    assert n1 == 1

    # Run 2 (LLM healthy again): only the missing topic is generated. Reuse the
    # instance (call counter keeps rising) so run 2's content differs from run
    # 1's — a fresh counter would reproduce run 1's sentence and hash-dup out.
    llm.failing = set()
    n2 = await build_library(db_session, llm, language="de", native="es", per_module=2)
    await db_session.commit()
    assert n2 == 1
    rows = (await db_session.execute(select(StoryLibrary.topic))).scalars().all()
    assert sorted(rows) == sorted([topic_a, topic_b])  # A not duplicated, B present


@pytest.mark.asyncio
async def test_identical_content_across_topics_dedups_by_hash(db_session):
    await _seed_cafe_module(db_session)
    # Same covering sentence every call → byte-identical content → same hash.
    llm = ScriptedLLM(["Der Kaffee ist gut."])
    n = await build_library(db_session, llm, language="de", native="es", per_module=2)
    await db_session.commit()
    assert n == 1
    count = (await db_session.execute(select(func.count()).select_from(StoryLibrary))).scalar_one()
    assert count == 1
