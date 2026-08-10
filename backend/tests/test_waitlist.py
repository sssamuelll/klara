import pytest
from sqlalchemy import select
from starlette.requests import Request

from klara.models.waitlist import WaitlistSignup
from klara.routers import waitlist as waitlist_router


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


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    waitlist_router._hits.clear()
    yield
    waitlist_router._hits.clear()


def _make_request(client_host: str, headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "client": (client_host, 12345),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_signup_creates_row_lowercased(client, db_session):
    r = await client.post("/api/v1/waitlist", json={"email": "Ana@Example.com", "locale": "es"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    row = await db_session.scalar(select(WaitlistSignup))
    assert row is not None
    assert row.email == "ana@example.com"
    assert row.locale == "es"
    assert row.invited_at is None


@pytest.mark.asyncio
async def test_signup_idempotent_same_response_no_enumeration(client, db_session):
    r1 = await client.post("/api/v1/waitlist", json={"email": "ana@example.com"})
    r2 = await client.post("/api/v1/waitlist", json={"email": "ANA@example.com"})
    assert (r1.status_code, r1.json()) == (r2.status_code, r2.json())
    rows = (await db_session.scalars(select(WaitlistSignup))).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_signup_invalid_email_422(client):
    r = await client.post("/api/v1/waitlist", json={"email": "no-es-un-correo"})
    assert r.status_code == 422


def test_client_ip_ignores_xff_from_non_private_peer():
    # El peer no es el proxy del host (IP pública real, no loopback/privada): el
    # XFF es spoofeable, se ignora.
    req = _make_request("8.8.8.8", {"x-forwarded-for": "9.9.9.9"})
    assert waitlist_router._client_ip(req) == "8.8.8.8"


def test_client_ip_uses_last_xff_hop_from_trusted_peer():
    # El peer es el hop confiable (nginx del host, loopback/privado): tomamos la
    # última IP del XFF que el propio proxy anexó; las anteriores son spoofeables.
    req = _make_request("127.0.0.1", {"x-forwarded-for": "1.2.3.4, 5.6.7.8"})
    assert waitlist_router._client_ip(req) == "5.6.7.8"


@pytest.mark.asyncio
async def test_rate_limit_429_after_10(client):
    for i in range(10):
        r = await client.post("/api/v1/waitlist", json={"email": f"p{i}@example.com"})
        assert r.status_code == 200
    r11 = await client.post("/api/v1/waitlist", json={"email": "p11@example.com"})
    assert r11.status_code == 429


def test_rate_limit_window_resets():
    waitlist_router._hits.clear()
    for _ in range(10):
        assert waitlist_router._rate_limited("1.2.3.4", now=1000.0) is False
    assert waitlist_router._rate_limited("1.2.3.4", now=1000.0) is True
    assert waitlist_router._rate_limited("1.2.3.4", now=1000.0 + 3601) is False


@pytest.mark.asyncio
async def test_admin_waitlist_requires_admin(client):
    r = await client.get("/api/v1/admin/waitlist")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_admin_lists_and_marks_invited(client, app_settings, db_session):
    cookie = await _register_owner(client, app_settings, db_session)
    await client.post("/api/v1/waitlist", json={"email": "fan@example.com", "locale": "de"})

    r = await client.get("/api/v1/admin/waitlist", headers={"Cookie": cookie})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1 and rows[0]["email"] == "fan@example.com"
    assert rows[0]["invited_at"] is None

    r2 = await client.post(
        f"/api/v1/admin/waitlist/{rows[0]['id']}/invited", headers={"Cookie": cookie}
    )
    assert r2.status_code == 200
    assert r2.json()["invited_at"] is not None
