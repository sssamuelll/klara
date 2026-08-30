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


def test_verify_rejects_token_signed_by_another_key(google_keys, rsa_key):
    """google_keys sustituye _signing_key por la clave pública de rsa_key (la
    PRIMERA); un token firmado con una segunda clave debe fallar la firma."""
    from klara.auth.google_native import InvalidGoogleToken, verify_google_id_token

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = _mint(other_key)
    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token(forged, AUD)


@pytest.mark.asyncio
async def test_jwks_unavailable_is_400_and_logged(client, app_settings, monkeypatch):
    """Fallo de transporte del JWKS (no de las claims): 400 igual, pero deja un
    warning distinguible en vez de morir en silencio como una firma inválida."""
    from structlog.testing import capture_logs

    from klara.auth import google_native

    app_settings(GOOGLE_OAUTH_CLIENT_ID=AUD)

    def _raise(_id_token):
        raise jwt.exceptions.PyJWKClientConnectionError("boom")

    monkeypatch.setattr(google_native, "_signing_key", _raise)

    with capture_logs() as logs:
        r = await client.post("/api/v1/auth/google/native", json={"id_token": "whatever"})

    assert r.status_code == 400
    assert "Google" in r.json()["detail"]  # auth.google_native.invalid

    warnings = [ln for ln in logs if ln.get("event") == "google_native.jwks_unavailable"]
    assert warnings, f"no se logueó jwks_unavailable: {[ln.get('event') for ln in logs]}"
    assert warnings[0]["log_level"] == "warning"
    assert "boom" in warnings[0]["error"]


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
async def test_native_accepts_a_real_sized_id_token(
    client, seed_invite, app_settings, google_keys, rsa_key
):
    """Un ID token de Google real pasa de 1024 caracteres.

    `oauth_accounts.access_token` es VARCHAR(1024) en fastapi-users. Guardar ahí
    el id_token reventaba con StringDataRightTruncationError — un 500 que además
    sale SIN cabeceras CORS, así que desde el WebView se veía como un error de
    CORS y no como lo que era. Los tokens de este archivo son cortos porque sus
    claims son mínimos; este los infla al tamaño de uno de verdad.
    """
    await _register_invited(client, seed_invite, app_settings, "invited@example.com")

    # Google mete name, picture, given_name, family_name, nonce, at_hash…
    # Un id_token real ronda los 1000-1300 caracteres; este pasa de 1024 seguro.
    gordo = _mint(
        rsa_key,
        name="Samuel Dario Ballesteros",
        picture="https://lh3.googleusercontent.com/a/" + "x" * 700,
        given_name="Samuel",
        family_name="Ballesteros",
    )
    assert len(gordo) > 1024, f"el token de prueba mide {len(gordo)}, no reproduce el fallo"

    r = await client.post("/api/v1/auth/google/native", json={"id_token": gordo})
    assert r.status_code == 200, r.text

    token = r.json()["access_token"]
    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200


@pytest.mark.asyncio
async def test_native_does_not_persist_the_id_token(
    client, seed_invite, app_settings, google_keys, rsa_key, db_session
):
    """El id_token no se guarda: es una aserción firmada de identidad, y la
    columna donde caía es para un access token de API que este flujo no tiene
    y que Klara nunca usa."""
    from sqlalchemy import select

    from klara.models.oauth import OAuthAccount

    await _register_invited(client, seed_invite, app_settings, "invited@example.com")
    minted = _mint(rsa_key)
    r = await client.post("/api/v1/auth/google/native", json={"id_token": minted})
    assert r.status_code == 200, r.text

    rows = (await db_session.execute(select(OAuthAccount))).scalars().all()
    assert rows, "debería haber quedado una cuenta OAuth enlazada"
    for row in rows:
        assert row.access_token != minted
        assert len(row.access_token) <= 1024


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
