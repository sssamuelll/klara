import pytest
from sqlalchemy import select
from starlette.requests import Request

from klara.models.waitlist import WaitlistSignup
from klara.routers import waitlist as waitlist_router


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
