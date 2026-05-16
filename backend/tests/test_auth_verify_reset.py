import pytest


@pytest.mark.asyncio
async def test_verify_flow_with_token(client, app_settings, captured_emails, seed_invite):
    """Register → captured verify token → POST /verify → user.is_verified=True."""
    app_settings(ALLOWED_SIGNUP_EMAILS="", INITIAL_OWNER_EMAIL="")
    token_invite = await seed_invite(email=None)

    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "verify@example.com",
            "password": "hunter2hunter2",
            "invite_token": token_invite,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_verified"] is False

    verify = next((e for e in captured_emails if e["kind"] == "verify"), None)
    assert verify is not None, "verify email should have been triggered on register"
    token = verify["token"]

    r2 = await client.post("/api/v1/auth/verify", json={"token": token})
    assert r2.status_code == 200, r2.text
    assert r2.json()["is_verified"] is True


@pytest.mark.asyncio
async def test_verify_with_bad_token(client, app_settings):
    app_settings(ALLOWED_SIGNUP_EMAILS="", INITIAL_OWNER_EMAIL="")
    r = await client.post("/api/v1/auth/verify", json={"token": "not-a-real-token"})
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_reset_password_flow(client, app_settings, captured_emails, seed_invite):
    """Register → forgot-password → captured reset token → reset → new password logs in."""
    app_settings(ALLOWED_SIGNUP_EMAILS="", INITIAL_OWNER_EMAIL="")
    invite_token = await seed_invite(email=None)

    email = "reset@example.com"
    old_pw = "hunter2hunter2"
    new_pw = "newpass9876543"

    r0 = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": old_pw, "invite_token": invite_token},
    )
    assert r0.status_code == 201, r0.text

    # captured_emails has a verify entry from register; clear and request reset.
    captured_emails.clear()

    r1 = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    # fastapi-users returns 202 Accepted regardless of whether the email exists
    # (anti-enumeration). We don't care about the status — only that the email
    # service was actually invoked with a real token.
    assert r1.status_code in (200, 202), r1.text

    reset = next((e for e in captured_emails if e["kind"] == "reset"), None)
    assert reset is not None, "reset email should have been triggered"
    token = reset["token"]

    r2 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": new_pw},
    )
    assert r2.status_code == 200, r2.text

    # New password works for login.
    r3 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": new_pw},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r3.status_code == 204, r3.text

    # Old password no longer works.
    r4 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": old_pw},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r4.status_code == 400


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_is_silent(client, app_settings, captured_emails):
    """Anti-enumeration: forgot-password for a missing email must NOT email anyone."""
    app_settings(ALLOWED_SIGNUP_EMAILS="", INITIAL_OWNER_EMAIL="")
    r = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ghost@example.com"},
    )
    assert r.status_code in (200, 202)
    assert not [e for e in captured_emails if e["kind"] == "reset"]


# TODO: OAuth happy-path test. Needs a fixture that mocks
# httpx_oauth.clients.google.GoogleOAuth2.get_id_email so the callback handler
# doesn't actually hit Google. Skipped for now — the /authorize route shape is
# verified by the route registration in main.py.
