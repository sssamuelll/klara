"""create_story: explicit module conditioning, provenance, pool recycle."""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from klara.dependencies import get_story_llm
from klara.llm.base import LLMResponse
from klara.models import Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel

STORY_JSON = json.dumps(
    {
        "title": "Der Kaffee",
        "sentences": [
            {
                "target": "Ich trinke Kaffee.",
                "native": "Bebo café.",
                "new_words": ["Kaffee"],
                "breakdown": [{"word": "Kaffee", "translation": "café"}],
            }
        ],
        "comprehension_questions": [],
        "target_words": [
            {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translation": "café"}
        ],
        "quiz_items": None,
    }
)


class FakeLLM:
    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        return LLMResponse(content=STORY_JSON, model="fake", provider="fake", cost_usd=0.001)

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest_asyncio.fixture
async def story_client():
    """Real register/login auth (mirrors test_claim_story._register_and_login)
    plus a controllable story LLM. conftest's `client` fixture builds its own
    FastAPI app internally without exposing it, so it has no override hook —
    build our own app here the same way (init_engine + create_app) with
    get_story_llm swapped for FakeLLM."""
    from klara.config import get_settings
    from klara.db import dispose_engine, init_engine
    from klara.main import create_app

    settings = get_settings()
    init_engine(settings)
    app = create_app()
    app.dependency_overrides[get_story_llm] = lambda: FakeLLM()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await dispose_engine()


async def _register_and_login(client, seed_invite, email: str) -> str:
    """Seed an invite, register against it, log in. Mirrors test_claim_story."""
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


@pytest.mark.asyncio
async def test_create_with_module_sets_provenance_and_recycles(
    story_client, seed_invite, db_session
):
    cookie = await _register_and_login(story_client, seed_invite, "module-story@example.com")

    module = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=1,
        title="En el café",
        can_dos=[],
        grammatical_focus=[],
    )
    db_session.add(module)
    await db_session.commit()

    resp = await story_client.post(
        "/api/v1/stories",
        json={"topic": "pedir un café", "module_id": str(module.id), "topic_origin": "chip"},
        headers={"Cookie": cookie},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["module_id"] == str(module.id)

    story = (await db_session.execute(select(Story))).scalar_one()
    assert story.module_id == module.id

    user = (
        await db_session.execute(select(User).where(User.email == "module-story@example.com"))
    ).scalar_one()
    assert user.current_module_id == module.id  # explicit module moves the pointer

    # chip topic + full coverage → recycled into the pool
    entry = (await db_session.execute(select(StoryLibrary))).scalar_one()
    assert entry.source == "pool"
    assert entry.source_story_id == story.id


@pytest.mark.asyncio
async def test_free_topic_is_not_recycled(story_client, seed_invite, db_session):
    cookie = await _register_and_login(story_client, seed_invite, "free-topic@example.com")

    module = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=1,
        title="M",
        can_dos=[],
        grammatical_focus=[],
    )
    db_session.add(module)
    await db_session.commit()

    resp = await story_client.post(
        "/api/v1/stories",
        json={"topic": "mi perra Luna", "module_id": str(module.id), "topic_origin": "free"},
        headers={"Cookie": cookie},
    )
    assert resp.status_code == 201, resp.text
    rows = (await db_session.execute(select(StoryLibrary))).scalars().all()
    assert rows == []
