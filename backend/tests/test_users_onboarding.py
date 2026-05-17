import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from klara.models import User
from klara.models.enums import CEFRLevel


@pytest.mark.asyncio
async def test_user_onboarding_completed_at_roundtrips(db_session):
    """Column defaults to NULL and round-trips a timezone-aware datetime."""
    user = User(
        id=uuid.uuid4(),
        email=None,
        hashed_password=None,
        is_active=True,
        is_verified=False,
        is_superuser=False,
        display_name="Tester",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.onboarding_completed_at is None

    ts = datetime.now(UTC)
    user.onboarding_completed_at = ts
    await db_session.commit()
    await db_session.refresh(user)
    assert user.onboarding_completed_at is not None
    # Round-trips a tz-aware datetime (Postgres stores in UTC):
    assert user.onboarding_completed_at.tzinfo is not None


@pytest.mark.asyncio
async def test_seed_oauth_account_fixture_works(db_session, seed_oauth_account):
    """Fixture sanity: creates an oauth_account row linked to a fresh user."""
    user = User(
        id=uuid.uuid4(),
        email="oauth@example.com",
        hashed_password=None,
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Oauth Tester",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.flush()

    oa_id = await seed_oauth_account(
        user_id=user.id,
        account_email="oauth@example.com",
    )
    from klara.models import OAuthAccount
    row = (
        await db_session.execute(
            select(OAuthAccount).where(OAuthAccount.id == oa_id)
        )
    ).scalar_one()
    assert row.oauth_name == "google"
    assert row.user_id == user.id


@pytest.mark.asyncio
async def test_get_me_auth_methods_password_only(client, app_settings, seed_invite):
    """Usuario creado via signup -> auth_methods == ["password"], no google."""
    app_settings(ALLOWED_SIGNUP_EMAILS="", INITIAL_OWNER_EMAIL="")
    token = await seed_invite(email=None)
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "pwonly@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "pwonly@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["auth_methods"] == ["password"]
    assert body["needs_onboarding"] is True


@pytest.mark.asyncio
async def test_get_me_auth_methods_oauth_only(db_session, seed_oauth_account):
    """Usuario sin hashed_password, con oauth_account -> auth_methods == ["google"]."""
    user = User(
        id=uuid.uuid4(),
        email="oauthonly@example.com",
        hashed_password=None,
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="OAuth Only",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.flush()
    await seed_oauth_account(user_id=user.id, account_email="oauthonly@example.com")
    await db_session.commit()

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db_session
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["auth_methods"] == ["google"]
    assert body["needs_onboarding"] is True


@pytest.mark.asyncio
async def test_get_me_auth_methods_hybrid(db_session, seed_oauth_account):
    """Usuario con password Y oauth_account -> auth_methods == ["google", "password"]."""
    user = User(
        id=uuid.uuid4(),
        email="hybrid@example.com",
        hashed_password="x",  # contenido irrelevante para la query DISTINCT
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Hybrid",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.flush()
    await seed_oauth_account(user_id=user.id, account_email="hybrid@example.com")
    await db_session.commit()

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db_session
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["auth_methods"] == ["google", "password"]
    assert body["needs_onboarding"] is True
