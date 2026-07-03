"""GET /modules: full path with derived completed/unlocked/is_current states."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from klara.curriculum.library import STORIES_TO_COMPLETE
from klara.models import Module, Story, StoryLibrary, StoryView, User
from klara.models.enums import CEFRLevel

CONTENT = {
    "sentences": [{"target": "Hallo.", "native": "Hola.", "new_words": []}],
    "comprehension_questions": [],
}


async def _register_and_login(client, seed_invite) -> str:
    """Seed an invite, register against it, log in. Mirrors test_practice_queue."""
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "path@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "path@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


@pytest.mark.asyncio
async def test_list_modules_states(client, seed_invite, db_session):
    # client fixture: unauthenticated httpx AsyncClient (conftest.py) — the
    # pattern used by protected-endpoint tests (e.g. test_practice_queue.py) is
    # to register + log in for real and pass the session cookie explicitly.
    # test_modules.py itself never uses an authenticated `client` fixture (its
    # endpoint tests build the app + dependency_overrides inline per-test), so
    # this copies test_practice_queue.py's _register_and_login idiom instead.
    cookie = await _register_and_login(client, seed_invite)

    # Arrange three modules; user finished 3 stories in m1 and is current on m2.
    user = (
        await db_session.execute(select(User).where(User.email == "path@example.com"))
    ).scalar_one()  # the client fixture's user
    mods = []
    for seq in (1, 2, 3):
        m = Module(
            id=uuid.uuid4(),
            language="de",
            cefr_level=CEFRLevel.A1,
            sequence_order=seq,
            title=f"M{seq}",
            can_dos=[],
            grammatical_focus=[],
        )
        db_session.add(m)
        mods.append(m)
    await db_session.flush()
    for i in range(STORIES_TO_COMPLETE):
        s = Story(
            user_id=user.id,
            level=CEFRLevel.A1,
            target_language="de",
            native_language="es",
            title=f"S{i}",
            content=CONTENT,
            target_vocab_item_ids=[],
            module_id=mods[0].id,
        )
        db_session.add(s)
        await db_session.flush()
        db_session.add(StoryView(story_id=s.id, user_id=user.id, finished_at=datetime.now(UTC)))
    db_session.add(
        StoryLibrary(
            module_id=mods[1].id,
            language="de",
            native_language="es",
            level=CEFRLevel.A1,
            title="L",
            content=CONTENT,
            target_vocab_item_ids=[],
            source="seed",
            content_hash="c" * 64,
        )
    )
    user.current_module_id = mods[1].id
    await db_session.commit()

    resp = await client.get("/api/v1/modules", headers={"Cookie": cookie})
    assert resp.status_code == 200
    items = resp.json()
    assert [it["sequence_order"] for it in items] == [1, 2, 3]
    m1, m2, m3 = items
    assert m1["completed"] is True and m1["unlocked"] is True
    assert m2["is_current"] is True and m2["unlocked"] is True
    assert m2["library_available"] == 1
    assert m3["completed"] is False and m3["unlocked"] is False
    assert m2["stories_to_complete"] == STORIES_TO_COMPLETE
