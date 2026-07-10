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
        await db_session.execute(select(OAuthAccount).where(OAuthAccount.id == oa_id))
    ).scalar_one()
    assert row.oauth_name == "google"
    assert row.user_id == user.id


@pytest.mark.asyncio
async def test_get_me_auth_methods_password_only(client, app_settings, seed_invite):
    """Usuario creado via signup -> auth_methods == ["password"], no google."""
    app_settings(INITIAL_OWNER_EMAIL="")
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


@pytest.mark.asyncio
async def test_post_onboarding_complete_sets_timestamp(db_session):
    """POST flippea needs_onboarding y setea onboarding_completed_at."""
    user = User(
        id=uuid.uuid4(),
        email="complete@example.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="C",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
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
        resp = await ac.post("/api/v1/me/onboarding/complete")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["needs_onboarding"] is False

    await db_session.refresh(user)
    assert user.onboarding_completed_at is not None


@pytest.mark.asyncio
async def test_post_onboarding_complete_idempotent(db_session):
    """Segunda llamada preserva el timestamp original (first-write-wins)."""
    user = User(
        id=uuid.uuid4(),
        email="idempotent@example.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="I",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
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
        r1 = await ac.post("/api/v1/me/onboarding/complete")
        await db_session.refresh(user)
        first_ts = user.onboarding_completed_at
        assert first_ts is not None
        r2 = await ac.post("/api/v1/me/onboarding/complete")
    assert r1.status_code == 200
    assert r2.status_code == 200
    await db_session.refresh(user)
    assert user.onboarding_completed_at == first_ts  # NO cambia


@pytest.mark.asyncio
async def test_post_onboarding_complete_requires_auth(client):
    """Sin sesión → 401."""
    resp = await client.post("/api/v1/me/onboarding/complete")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_password_sets_hashed_password(db_session, seed_oauth_account):
    """OAuth-only user → POST setea password, auth_methods en response incluye 'password'."""
    user = User(
        id=uuid.uuid4(),
        email="setpw@example.com",
        hashed_password=None,
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="SetPw",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.flush()
    await seed_oauth_account(user_id=user.id, account_email="setpw@example.com")
    await db_session.commit()

    from klara.auth.db import get_auth_session
    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db_session
    app.dependency_overrides[get_auth_session] = lambda: db_session
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/me/password", json={"password": "newpassword123"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["auth_methods"] == ["google", "password"]

    await db_session.refresh(user)
    assert user.hashed_password is not None


@pytest.mark.asyncio
async def test_post_password_rejects_short_password(db_session, seed_oauth_account):
    """Password < 8 chars → 422 con detail localizado via t()."""
    user = User(
        id=uuid.uuid4(),
        email="short@example.com",
        hashed_password=None,
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Short",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.flush()
    await seed_oauth_account(user_id=user.id, account_email="short@example.com")
    await db_session.commit()

    from klara.auth.db import get_auth_session
    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db_session
    app.dependency_overrides[get_auth_session] = lambda: db_session
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/me/password", json={"password": "abc"})
    assert resp.status_code == 422
    body = resp.json()
    # detail viene de t("auth.password_invalid", locale) — accept-language defaults to "es"
    assert "inválida" in body["detail"].lower() or "invalid" in body["detail"].lower()


@pytest.mark.asyncio
async def test_post_password_rejects_oversized_password(db_session):
    """Password > 128 chars → 422 (validación Pydantic). NO assertear body (Pydantic English)."""
    user = User(
        id=uuid.uuid4(),
        email="big@example.com",
        hashed_password=None,
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Big",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.commit()

    from klara.auth.db import get_auth_session
    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db_session
    app.dependency_overrides[get_auth_session] = lambda: db_session
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/me/password", json={"password": "x" * 200})
    assert resp.status_code == 422
    # Pydantic envelope is English by default — only check status + field loc:
    body = resp.json()
    locs = [".".join(str(x) for x in err["loc"]) for err in body["detail"]]
    assert any("password" in loc for loc in locs)


@pytest.mark.asyncio
async def test_post_password_already_set(db_session):
    """Usuario con password existente → 409."""
    user = User(
        id=uuid.uuid4(),
        email="hadpw@example.com",
        hashed_password="existing-hash",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Had",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.commit()

    from klara.auth.db import get_auth_session
    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db_session
    app.dependency_overrides[get_auth_session] = lambda: db_session
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/me/password", json={"password": "newpassword123"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_post_password_requires_auth(client):
    """Sin sesión → 401."""
    resp = await client.post("/api/v1/me/password", json={"password": "newpassword123"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_patch_me_display_name_ok_when_stored_langs_equal(db_session):
    """Regression: a display_name-only PATCH must succeed even when the stored
    native==target (e.g. German-locale signup seeds native="de", target defaults
    to "de"). The onboarding name step runs before the languages step, so
    rejecting it here trapped the user."""
    user = User(
        id=uuid.uuid4(),
        email="olaf@example.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="",
        level=CEFRLevel.A0,
        native_language="de",
        target_language="de",  # equal pair — the trap
    )
    db_session.add(user)
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
        resp = await ac.patch("/api/v1/me", json={"display_name": "Olaf"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["display_name"] == "Olaf"


@pytest.mark.asyncio
async def test_patch_me_rejects_setting_langs_equal(db_session):
    """The distinctness guard still fires when the PATCH itself makes the pair
    equal — here setting native to the stored target."""
    user = User(
        id=uuid.uuid4(),
        email="pair@example.com",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Pair",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
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
        resp = await ac.patch("/api/v1/me", json={"native_language": "de"})
    assert resp.status_code == 422, resp.text
