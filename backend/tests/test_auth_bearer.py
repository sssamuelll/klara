from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update


@pytest.mark.asyncio
async def test_access_token_row_roundtrip(db_session, seed_invite):
    """La tabla existe (migración 0022) y el modelo mapea users.id, no user.id."""
    from klara.models import AccessToken, User

    await seed_invite()  # siembra un admin: nos sirve de dueño del token
    owner = (await db_session.execute(select(User))).scalars().first()
    assert owner is not None

    token = "a" * 43
    db_session.add(AccessToken(token=token, user_id=owner.id))
    await db_session.commit()

    row = await db_session.get(AccessToken, token)
    assert row is not None
    assert row.user_id == owner.id
    assert row.created_at.tzinfo is not None


EMAIL = "bearer@example.com"
PASSWORD = "hunter2hunter2"


async def _register(client, seed_invite, app_settings, email: str = EMAIL) -> None:
    app_settings(INITIAL_OWNER_EMAIL="")
    invite = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Bearer",
            "invite_token": invite,
        },
    )
    assert r.status_code == 201, r.text


async def _bearer_login(client, email: str = EMAIL, password: str = PASSWORD):
    return await client.post(
        "/api/v1/auth/bearer/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


@pytest.mark.asyncio
async def test_bearer_login_returns_token_that_opens_me(client, seed_invite, app_settings):
    await _register(client, seed_invite, app_settings)
    r = await _bearer_login(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) == 43
    assert "set-cookie" not in r.headers  # el transporte Bearer no toca cookies

    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200, me.text
    assert me.json()["display_name"] == "Bearer"


@pytest.mark.asyncio
async def test_bearer_login_bad_password_is_400(client, seed_invite, app_settings):
    await _register(client, seed_invite, app_settings)
    r = await _bearer_login(client, password="wrong-wrong-wrong")
    assert r.status_code == 400
    assert r.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


@pytest.mark.asyncio
async def test_bearer_logout_revokes_token(client, seed_invite, app_settings):
    await _register(client, seed_invite, app_settings)
    token = (await _bearer_login(client)).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    out = await client.post("/api/v1/auth/bearer/logout", headers=auth)
    assert out.status_code == 204, out.text

    me = await client.get("/api/v1/me", headers=auth)
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_bearer_expired_token_is_401(client, seed_invite, app_settings, db_session):
    from klara.config import get_settings
    from klara.models import AccessToken

    await _register(client, seed_invite, app_settings)
    token = (await _bearer_login(client)).json()["access_token"]

    too_old = datetime.now(UTC) - timedelta(seconds=get_settings().auth_bearer_max_age + 60)
    await db_session.execute(
        update(AccessToken).where(AccessToken.token == token).values(created_at=too_old)
    )
    await db_session.commit()

    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_cookie_login_unchanged(client, seed_invite, app_settings):
    """El backend nuevo no altera el de cookie: 204 + Set-Cookie, como siempre."""
    await _register(client, seed_invite, app_settings)
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 204, r.text
    assert "klara_session" in r.headers.get("set-cookie", "")
