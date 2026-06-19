import uuid

import pytest
from sqlalchemy import select


async def _seed_passwordless_user(db_session, email: str):
    """An OAuth-only user: email set, verified, active, hashed_password NULL."""
    from klara.models import User
    from klara.models.enums import CEFRLevel

    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=None,
        is_active=True,
        is_verified=True,
        is_superuser=True,
        display_name="Owner",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_forgot_password_null_is_silent(client, app_settings, captured_emails, db_session):
    app_settings(INITIAL_OWNER_EMAIL="")
    await _seed_passwordless_user(db_session, "owner@example.com")

    r = await client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    # No crash (was 500 before the fix), still 202, and no reset email sent.
    assert r.status_code in (200, 202), r.text
    assert not [e for e in captured_emails if e["kind"] == "reset"]


@pytest.mark.asyncio
async def test_login_null_password_returns_400(client, app_settings, db_session):
    app_settings(INITIAL_OWNER_EMAIL="")
    await _seed_passwordless_user(db_session, "owner@example.com")

    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "owner@example.com", "password": "anything12345"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # Clean bad-credentials, not a 500 from hashing None.
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_oauth_owner_adoption_leaves_password_null(
    client, app_settings, legacy_owner_with_story, db_session
):
    """Adopting the legacy owner via OAuth must NOT set a password hash."""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    from klara.auth.email import EmailService
    from klara.auth.manager import UserManager
    from klara.config import get_settings
    from klara.models import OAuthAccount, User

    app_settings(INITIAL_OWNER_EMAIL="owner@example.com")
    settings = get_settings()
    user_db = SQLAlchemyUserDatabase(db_session, User, OAuthAccount)
    manager = UserManager(user_db, settings, db_session, EmailService(settings))

    adopted = await manager.oauth_callback(
        "google",
        "access-tok",
        "google-acct-123",
        "owner@example.com",
        None,
        None,
        None,
    )

    assert str(adopted.id) == legacy_owner_with_story["user_id"]
    refreshed = (await db_session.execute(select(User).where(User.id == adopted.id))).scalar_one()
    assert refreshed.email == "owner@example.com"
    assert refreshed.hashed_password is None  # ← the regression guard
