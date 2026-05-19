from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select


async def _login_cookie(client, email: str, password: str) -> str:
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 204, r.text
    return r.headers["set-cookie"].split(";")[0]


async def _register_owner(client, app_settings, db_session):
    """Bootstrap the owner via the legacy-row adoption path; returns the cookie."""
    from klara.models import User
    from klara.models.enums import CEFRLevel

    db_session.add(
        User(
            email=None,
            hashed_password=None,
            is_active=True,
            is_verified=False,
            is_superuser=False,
            display_name="Samuel",
            level=CEFRLevel.A0,
            native_language="es",
            target_language="de",
        )
    )
    await db_session.commit()

    app_settings(INITIAL_OWNER_EMAIL="owner@klara.app")
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@klara.app", "password": "hunter2hunter2"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_superuser"] is True
    return await _login_cookie(client, "owner@klara.app", "hunter2hunter2")


@pytest.mark.asyncio
async def test_admin_creates_invite_and_friend_signs_up(client, app_settings, db_session):
    """End-to-end: owner bootstraps → owner creates invite → friend signs up with it."""
    cookie = await _register_owner(client, app_settings, db_session)

    r1 = await client.post(
        "/api/v1/admin/invitations",
        headers={"Cookie": cookie},
        json={"email": "friend@example.com", "note": "Wave 1"},
    )
    assert r1.status_code == 201, r1.text
    inv = r1.json()
    assert inv["state"] == "active"
    assert inv["email"] == "friend@example.com"
    assert "/signup?invite=" in inv["share_url"]
    token = inv["token"]

    # Public lookup of the token returns the pre-fill info.
    pub = await client.get(f"/api/v1/invitations/{token}")
    assert pub.status_code == 200
    assert pub.json()["email"] == "friend@example.com"
    assert pub.json()["state"] == "active"

    # Friend can now sign up.
    r2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "friend@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["is_superuser"] is False

    # Token can't be reused.
    r3 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "friend2@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r3.status_code == 400
    assert "usad" in r3.json()["detail"].lower() or "used" in r3.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invite_email_mismatch_blocked(client, app_settings, db_session):
    cookie = await _register_owner(client, app_settings, db_session)

    r1 = await client.post(
        "/api/v1/admin/invitations",
        headers={"Cookie": cookie},
        json={"email": "alice@example.com"},
    )
    token = r1.json()["token"]

    r2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r2.status_code == 400
    detail = r2.json()["detail"].lower()
    assert "otro correo" in detail or "different email" in detail or "outro" in detail


@pytest.mark.asyncio
async def test_open_invite_accepts_any_email(client, app_settings, db_session):
    """An invite without a specific email works for any signup."""
    cookie = await _register_owner(client, app_settings, db_session)

    r1 = await client.post(
        "/api/v1/admin/invitations",
        headers={"Cookie": cookie},
        json={},
    )
    token = r1.json()["token"]
    assert r1.json()["email"] is None

    r2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "whoever@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r2.status_code == 201, r2.text


@pytest.mark.asyncio
async def test_revoked_invite_rejected(client, app_settings, db_session):
    cookie = await _register_owner(client, app_settings, db_session)

    r1 = await client.post(
        "/api/v1/admin/invitations",
        headers={"Cookie": cookie},
        json={},
    )
    inv_id = r1.json()["id"]
    token = r1.json()["token"]

    r2 = await client.post(
        f"/api/v1/admin/invitations/{inv_id}/revoke",
        headers={"Cookie": cookie},
    )
    assert r2.status_code == 200
    assert r2.json()["state"] == "revoked"

    r3 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "x@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r3.status_code == 400
    assert "revoc" in r3.json()["detail"].lower()


@pytest.mark.asyncio
async def test_expired_invite_rejected(client, app_settings, db_session):
    cookie = await _register_owner(client, app_settings, db_session)

    r1 = await client.post(
        "/api/v1/admin/invitations",
        headers={"Cookie": cookie},
        json={},
    )
    inv_id = r1.json()["id"]
    token = r1.json()["token"]

    # Backdate the expiry directly in the DB.
    from klara.models import Invitation

    inv = await db_session.get(Invitation, inv_id)
    inv.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    r2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "y@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r2.status_code == 400
    assert "expir" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_non_admin_cannot_create_invite(client, app_settings, db_session, seed_invite):
    """Non-superuser hitting the admin route gets 403."""
    app_settings(INITIAL_OWNER_EMAIL="")
    token = await seed_invite(email=None)
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "regular@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    cookie = await _login_cookie(client, "regular@example.com", "hunter2hunter2")
    r = await client.post(
        "/api/v1/admin/invitations",
        headers={"Cookie": cookie},
        json={},
    )
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_anonymous_cannot_create_invite(client):
    r = await client.post("/api/v1/admin/invitations", json={})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invitation_marked_used_in_db(client, app_settings, db_session):
    cookie = await _register_owner(client, app_settings, db_session)
    r1 = await client.post(
        "/api/v1/admin/invitations",
        headers={"Cookie": cookie},
        json={},
    )
    token = r1.json()["token"]
    inv_id = r1.json()["id"]

    r2 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "claimer@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r2.status_code == 201
    new_user_id = r2.json()["id"]

    from klara.models import Invitation

    # Different session — must re-query.
    db_session.expire_all()
    inv = (await db_session.execute(select(Invitation).where(Invitation.id == inv_id))).scalar_one()
    assert inv.used_at is not None
    assert str(inv.used_by) == new_user_id
