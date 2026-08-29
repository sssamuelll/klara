import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

AUD = "web-client-id.apps.googleusercontent.com"


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _mint(rsa_key, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": AUD,
        "sub": "g-123",
        "email": "invited@example.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 600,
    }
    claims.update(overrides)
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "test-kid"})


@pytest.fixture
def google_keys(monkeypatch, rsa_key):
    """Sustituye la descarga del JWKS de Google por la clave pública local."""
    from klara.auth import google_native

    monkeypatch.setattr(google_native, "_signing_key", lambda _tok: rsa_key.public_key())


# --- verificación pura -------------------------------------------------------


def test_verify_accepts_valid_token(google_keys, rsa_key):
    from klara.auth.google_native import verify_google_id_token

    claims = verify_google_id_token(_mint(rsa_key), AUD)
    assert claims.sub == "g-123"
    assert claims.email == "invited@example.com"
    assert claims.exp > int(time.time())


@pytest.mark.parametrize(
    "override",
    [
        {"aud": "other-client"},
        {"iss": "https://evil.example"},
        {"exp": int(time.time()) - 5},
        {"email_verified": False},
        {"email": ""},
    ],
)
def test_verify_rejects(google_keys, rsa_key, override):
    from klara.auth.google_native import InvalidGoogleToken, verify_google_id_token

    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token(_mint(rsa_key, **override), AUD)


def test_verify_rejects_garbage(google_keys):
    from klara.auth.google_native import InvalidGoogleToken, verify_google_id_token

    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token("not.a.jwt", AUD)


# --- ruta ----------------------------------------------------------------------


async def _register_invited(client, seed_invite, app_settings, email: str) -> None:
    app_settings(INITIAL_OWNER_EMAIL="", GOOGLE_OAUTH_CLIENT_ID=AUD)
    invite = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "hunter2hunter2",
            "display_name": "Invited",
            "invite_token": invite,
        },
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_native_links_existing_invited_user(
    client, seed_invite, app_settings, google_keys, rsa_key
):
    await _register_invited(client, seed_invite, app_settings, "invited@example.com")

    r = await client.post("/api/v1/auth/google/native", json={"id_token": _mint(rsa_key)})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == "Invited"

    # Segunda vez: mismo sub → login, no duplica cuenta ni falla.
    r2 = await client.post("/api/v1/auth/google/native", json={"id_token": _mint(rsa_key)})
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_native_unknown_email_requires_invite(client, app_settings, google_keys, rsa_key):
    app_settings(INITIAL_OWNER_EMAIL="", GOOGLE_OAUTH_CLIENT_ID=AUD)
    r = await client.post(
        "/api/v1/auth/google/native",
        json={"id_token": _mint(rsa_key, email="stranger@example.com", sub="g-999")},
    )
    assert r.status_code == 400
    assert "invitaci" in r.json()["detail"]  # auth.invite_required (es)


@pytest.mark.asyncio
async def test_native_invalid_token_is_400(client, app_settings, google_keys, rsa_key):
    app_settings(INITIAL_OWNER_EMAIL="", GOOGLE_OAUTH_CLIENT_ID=AUD)
    r = await client.post(
        "/api/v1/auth/google/native",
        json={"id_token": _mint(rsa_key, aud="other-client")},
    )
    assert r.status_code == 400
    assert "Google" in r.json()["detail"]  # auth.google_native.invalid


@pytest.mark.asyncio
async def test_native_without_client_id_is_503(client, app_settings, google_keys, rsa_key):
    app_settings(GOOGLE_OAUTH_CLIENT_ID=None)
    r = await client.post("/api/v1/auth/google/native", json={"id_token": _mint(rsa_key)})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_native_adopts_legacy_owner(
    client, app_settings, google_keys, rsa_key, legacy_owner_with_story
):
    """Mismo camino que el callback del navegador: el dueño bootstrap adopta la
    fila legacy (email NULL) y sale superuser."""
    app_settings(INITIAL_OWNER_EMAIL="owner@example.com", GOOGLE_OAUTH_CLIENT_ID=AUD)
    r = await client.post(
        "/api/v1/auth/google/native",
        json={"id_token": _mint(rsa_key, email="owner@example.com", sub="g-owner")},
    )
    assert r.status_code == 200, r.text
    me = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["is_superuser"] is True
