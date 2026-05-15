import pytest


@pytest.mark.asyncio
async def test_signup_blocked_by_allowlist(client, app_settings):
    app_settings(ALLOWED_SIGNUP_EMAILS="ok@example.com")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "intruder@example.com", "password": "hunter2hunter2"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert "autorizado" in body["detail"].lower() or "authorized" in body["detail"].lower()


@pytest.mark.asyncio
async def test_signup_ok_then_login(client, app_settings):
    app_settings(ALLOWED_SIGNUP_EMAILS="ok@example.com")

    r1 = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "ok@example.com",
            "password": "hunter2hunter2",
            "display_name": "Tester",
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
async def test_signup_with_empty_allowlist_allows_all(client, app_settings):
    """When ALLOWED_SIGNUP_EMAILS is empty the gate is off — open registration."""
    app_settings(ALLOWED_SIGNUP_EMAILS="")
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "anyone@example.com", "password": "hunter2hunter2"},
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_email_is_case_insensitive(client, app_settings):
    app_settings(ALLOWED_SIGNUP_EMAILS="case@example.com")
    r1 = await client.post(
        "/api/v1/auth/register",
        json={"email": "Case@Example.COM", "password": "hunter2hunter2"},
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "case@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
