"""POST /stories/{id}/difficulty: persiste el tap, last-write-wins, owner-gated, 422 en basura."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from klara.auth.users import current_active_user
from klara.dependencies import db_session as db_session_dep
from klara.main import create_app
from klara.models import Story, User
from klara.models.enums import CEFRLevel


async def _user(db):
    u = User(
        id=uuid.uuid4(),
        email=f"diff-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="D",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def _story(db, *, user):
    s = Story(
        id=uuid.uuid4(),
        user_id=user.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="t",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[],
    )
    db.add(s)
    await db.flush()
    return s


async def _post(db, user, story_id, body):
    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post(f"/api/v1/stories/{story_id}/difficulty", json=body)


@pytest.mark.asyncio
async def test_sets_persists_and_overwrites(db_session):
    u = await _user(db_session)
    s = await _story(db_session, user=u)
    await db_session.commit()

    resp = await _post(db_session, u, s.id, {"value": "too_hard"})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"value": "too_hard"}
    await db_session.refresh(s)
    assert s.perceived_difficulty == "too_hard"

    # last-write-wins
    resp = await _post(db_session, u, s.id, {"value": "right"})
    assert resp.status_code == 200, resp.text
    await db_session.refresh(s)
    assert s.perceived_difficulty == "right"


@pytest.mark.asyncio
async def test_owner_gated_404(db_session):
    owner = await _user(db_session)
    other = await _user(db_session)
    s = await _story(db_session, user=owner)
    await db_session.commit()
    resp = await _post(db_session, other, s.id, {"value": "right"})
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_invalid_value_422(db_session):
    u = await _user(db_session)
    s = await _story(db_session, user=u)
    await db_session.commit()
    resp = await _post(db_session, u, s.id, {"value": "imposible"})
    assert resp.status_code == 422, resp.text
