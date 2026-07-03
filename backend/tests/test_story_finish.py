"""POST /stories/{id}/finish: StoryView write + completar advancement."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from klara.curriculum.library import STORIES_TO_COMPLETE
from klara.models import Module, Story, StoryView, User
from klara.models.enums import CEFRLevel

CONTENT = {
    "sentences": [{"target": "Hallo.", "native": "Hola.", "new_words": []}],
    "comprehension_questions": [],
}


async def _register_and_login(client, seed_invite, email: str = "finish@example.com") -> str:
    """Seed an invite, register against it, log in. Mirrors test_claim_story."""
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "hunter2hunter2",
            "invite_token": token,
        },
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
async def test_finish_is_idempotent_and_advances_on_third(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    # select by the email we just registered — more robust than limit(1)
    # if other rows exist (e.g. the seed_invite admin user).
    user = (
        await db_session.execute(select(User).where(User.email == "finish@example.com"))
    ).scalar_one()
    m1 = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=1,
        title="M1",
        can_dos=[],
        grammatical_focus=[],
    )
    m2 = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=2,
        title="M2",
        can_dos=[],
        grammatical_focus=[],
    )
    db_session.add_all([m1, m2])
    await db_session.flush()
    user.current_module_id = m1.id
    stories = []
    for i in range(STORIES_TO_COMPLETE):
        s = Story(
            user_id=user.id,
            level=CEFRLevel.A1,
            target_language="de",
            native_language="es",
            title=f"S{i}",
            content=CONTENT,
            target_vocab_item_ids=[],
            module_id=m1.id,
        )
        db_session.add(s)
        stories.append(s)
    await db_session.commit()

    r1 = await client.post(f"/api/v1/stories/{stories[0].id}/finish", headers={"Cookie": cookie})
    assert r1.status_code == 200
    assert r1.json()["module_advanced"] is False
    first_ts = r1.json()["finished_at"]

    # Idempotent: same timestamp, still one view row.
    r1b = await client.post(f"/api/v1/stories/{stories[0].id}/finish", headers={"Cookie": cookie})
    assert r1b.json()["finished_at"] == first_ts

    await client.post(f"/api/v1/stories/{stories[1].id}/finish", headers={"Cookie": cookie})
    r3 = await client.post(f"/api/v1/stories/{stories[2].id}/finish", headers={"Cookie": cookie})
    assert r3.json()["module_advanced"] is True

    await db_session.refresh(user)
    assert user.current_module_id == m2.id
    views = (
        (await db_session.execute(select(StoryView).where(StoryView.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(views) == 3
