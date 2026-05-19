import pytest


@pytest.mark.asyncio
async def test_signup_requires_invite_token(client, app_settings):
    """No invite + not bootstrap owner -> 400. The only gate."""
    app_settings(INITIAL_OWNER_EMAIL="")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "anyone@example.com", "password": "hunter2hunter2"},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    detail = body["detail"].lower()
    assert "invit" in detail


@pytest.mark.asyncio
async def test_signup_ok_with_invite_then_login(client, app_settings, seed_invite):
    app_settings(INITIAL_OWNER_EMAIL="")
    token = await seed_invite(email=None)

    r1 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ok@example.com",
            "password": "hunter2hunter2",
            "display_name": "Tester",
            "invite_token": token,
        },
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "ok@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    assert "klara_session" in r2.headers.get("set-cookie", "")

    cookie = r2.headers["set-cookie"].split(";")[0]
    r3 = await client.get(
        "/api/v1/me",
        headers={"Cookie": cookie},
    )
    assert r3.status_code == 200, r3.text
    body = r3.json()
    assert body["display_name"] == "Tester"


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    r = await client.get("/api/v1/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_email_is_case_insensitive(client, seed_invite):
    token = await seed_invite(email=None)
    r1 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "Case@Example.COM",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "case@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text


@pytest.mark.asyncio
async def test_signup_rejects_short_password_via_validate_password(
    client, app_settings, seed_invite
):
    """Regresión: el override de UserManager.validate_password aplica también en signup."""
    app_settings(INITIAL_OWNER_EMAIL="")
    token = await seed_invite(email=None)
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "shortpw@example.com",
            "password": "abc",  # 3 chars, < 8
            "invite_token": token,
        },
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["detail"]["code"] == "REGISTER_INVALID_PASSWORD"
    assert body["detail"]["reason"] == "too_short"
