"""Unit tests for ensure_klara_note — the Finish summary teaser cache."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from klara.llm.base import LLMResponse
from klara.models import Story, User
from klara.models.enums import CEFRLevel
from klara.services.finish_lessons import ensure_klara_note


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        self.calls += 1
        return LLMResponse(content=self.content, model="fake", provider="fake")

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest_asyncio.fixture
async def _user(db_session):
    """Seed a real user so Story's FK to users.id is satisfied."""
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:6]}@klara.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Test",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _make_story(db_session, user: User) -> Story:
    story = Story(
        id=uuid.uuid4(),
        user_id=user.id,
        level=CEFRLevel.A0,
        target_language="de",
        native_language="es",
        title="En el autobús",
        content={
            "sentences": [
                {"target": "Hoy voy en autobús.", "native": "Hoy voy en autobús.", "new_words": []},
            ],
            "comprehension_questions": [],
        },
        target_vocab_item_ids=[],
    )
    db_session.add(story)
    await db_session.commit()
    await db_session.refresh(story)
    return story


@pytest.mark.asyncio
async def test_cached_skips_llm(db_session, _user):
    """If story.klara_note is already set, the service returns it without
    calling the LLM."""
    story = await _make_story(db_session, _user)
    story.klara_note = "Mañana, otra. Probablemente más larga."
    await db_session.commit()
    await db_session.refresh(story)

    llm = FakeLLM('{"body": "should not be called"}')
    out = await ensure_klara_note(db_session, story, llm)
    assert out == "Mañana, otra. Probablemente más larga."
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_generates_and_persists(db_session, _user):
    story = await _make_story(db_session, _user)

    # Service strips trailing punctuation/quotes (covered separately by
    # test_strips_outer_quotes_and_periods). Use a body without a trailing
    # period here so the equality check focuses on the persistence path.
    llm = FakeLLM('{"body": "Mañana, otra; tal vez más larga"}')
    out = await ensure_klara_note(db_session, story, llm)
    assert out == "Mañana, otra; tal vez más larga"
    assert story.klara_note == "Mañana, otra; tal vez más larga"
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_strips_outer_quotes_and_periods(db_session, _user):
    story = await _make_story(db_session, _user)

    llm = FakeLLM('{"body": "«Mañana, otra.» "}')
    out = await ensure_klara_note(db_session, story, llm)
    # Outer guillemets stripped; the UI adds them back.
    assert out == "Mañana, otra"


@pytest.mark.asyncio
async def test_malformed_json_returns_none(db_session, _user):
    story = await _make_story(db_session, _user)

    llm = FakeLLM("not valid json at all")
    out = await ensure_klara_note(db_session, story, llm)
    assert out is None
    assert story.klara_note is None


@pytest.mark.asyncio
async def test_empty_body_returns_none(db_session, _user):
    story = await _make_story(db_session, _user)

    llm = FakeLLM('{"body": "   "}')
    out = await ensure_klara_note(db_session, story, llm)
    assert out is None
