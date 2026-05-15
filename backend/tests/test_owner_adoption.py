import uuid

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_initial_owner_adopts_legacy_user(
    client, app_settings, legacy_owner_with_story, db_session
):
    """
    Signup with INITIAL_OWNER_EMAIL must adopt the existing email-NULL row
    instead of creating a new one. The user's id, and any stories owned by
    that id, must survive intact.
    """
    app_settings(
        ALLOWED_SIGNUP_EMAILS="samuel@klara.app",
        INITIAL_OWNER_EMAIL="samuel@klara.app",
    )

    pre_user_id = legacy_owner_with_story["user_id"]
    pre_story_id = legacy_owner_with_story["story_id"]

    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "samuel@klara.app",
            "password": "hunter2hunter2",
            "display_name": "Samuel",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == pre_user_id  # ← the critical assertion: same UUID

    from german_app.models import Story, User

    user = (
        await db_session.execute(
            select(User).where(User.id == uuid.UUID(pre_user_id))
        )
    ).scalar_one()
    assert user.email == "samuel@klara.app"
    assert user.hashed_password is not None

    story = (
        await db_session.execute(
            select(Story).where(Story.id == uuid.UUID(pre_story_id))
        )
    ).scalar_one()
    assert str(story.user_id) == pre_user_id


@pytest.mark.asyncio
async def test_non_owner_email_does_not_adopt(
    client, app_settings, legacy_owner_with_story, db_session
):
    """A non-owner email in the allowlist must NOT touch the legacy row."""
    app_settings(
        ALLOWED_SIGNUP_EMAILS="other@klara.app,samuel@klara.app",
        INITIAL_OWNER_EMAIL="samuel@klara.app",
    )

    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "other@klara.app", "password": "hunter2hunter2"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] != legacy_owner_with_story["user_id"]

    from german_app.models import User

    legacy_user = (
        await db_session.execute(
            select(User).where(User.id == uuid.UUID(legacy_owner_with_story["user_id"]))
        )
    ).scalar_one()
    # Legacy row untouched
    assert legacy_user.email is None
    assert legacy_user.hashed_password is None
