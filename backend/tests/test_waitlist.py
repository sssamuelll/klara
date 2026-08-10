import pytest
from sqlalchemy import select

from klara.models.waitlist import WaitlistSignup
from klara.routers import waitlist as waitlist_router


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    waitlist_router._hits.clear()
    yield
    waitlist_router._hits.clear()


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
