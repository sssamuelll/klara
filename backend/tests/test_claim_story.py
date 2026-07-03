"""POST /modules/{id}/story: clone-on-claim, pointer move, 404 codes."""

from __future__ import annotations

import uuid

import pytest

from klara.models import Module, StoryLibrary
from klara.models.enums import CEFRLevel

CONTENT = {
    "sentences": [{"target": "Ich trinke Kaffee.", "native": "Bebo café.", "new_words": []}],
    "comprehension_questions": [],
}


async def _register_and_login(client, seed_invite) -> str:
    """Seed an invite, register against it, log in. Mirrors test_modules_path."""
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "claim@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "claim@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


@pytest.mark.asyncio
async def test_claim_clones_and_moves_pointer(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)

    module = Module(
        id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1,
        sequence_order=1, title="En el café", can_dos=[], grammatical_focus=[],
    )
    db_session.add(module)
    await db_session.flush()
    db_session.add(StoryLibrary(
        module_id=module.id, language="de", native_language="es", level=CEFRLevel.A1,
        title="Der Kaffee", content=CONTENT, target_vocab_item_ids=[],
        source="seed", content_hash="d" * 64,
    ))
    await db_session.commit()

    resp = await client.post(f"/api/v1/modules/{module.id}/story", headers={"Cookie": cookie})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Der Kaffee"
    assert body["content"]["sentences"][0]["target"] == "Ich trinke Kaffee."

    # Second claim: entry already seen by this user → library.empty.
    resp2 = await client.post(f"/api/v1/modules/{module.id}/story", headers={"Cookie": cookie})
    assert resp2.status_code == 404
    assert resp2.json()["detail"] == "library.empty"


@pytest.mark.asyncio
async def test_claim_unknown_module_404(client, seed_invite):
    cookie = await _register_and_login(client, seed_invite)
    resp = await client.post(f"/api/v1/modules/{uuid.uuid4()}/story", headers={"Cookie": cookie})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "module.not_found"
