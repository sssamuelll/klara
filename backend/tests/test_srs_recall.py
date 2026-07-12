"""GET /srs/cards/due exposes gender (oracle nouns only) + ease; review persists elapsed_seconds."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from klara.models import Review, User, UserCard, VocabItem
from klara.models.enums import CardState, PartOfSpeech

# vocab_items NO se trunca entre tests (conftest.py) y hay unique (lemma, language,
# pos) — namespacea el language de este módulo para no chocar con otros archivos
# que también usan lemma="Haus" en language="de" (mismo patrón que test_practice_session.py).
# language es VARCHAR(8): "de-" (3) + 4 hex = 7, cabe.
_LANG = f"de-{uuid.uuid4().hex[:4]}"


async def _register_and_login(client, seed_invite, email: str) -> str:
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def _add_due_card(db, user_id, *, lemma, pos, gender, gender_source):
    vocab = VocabItem(
        language=_LANG,
        lemma=lemma,
        pos=pos,
        gender=gender,
        gender_source=gender_source,
        translations={"es": "x"},
        example_target="Ein Satz.",
    )
    db.add(vocab)
    await db.flush()
    card = UserCard(
        user_id=user_id, vocab_item_id=vocab.id, next_review_at=None, state=CardState.NEW
    )
    db.add(card)
    await db.commit()
    return card


@pytest.mark.asyncio
async def test_due_exposes_gender_for_oracle_nouns_only(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite, "recall1@example.com")
    user = (
        await db_session.execute(select(User).where(User.email == "recall1@example.com"))
    ).scalar_one()
    await _add_due_card(
        db_session,
        user.id,
        lemma="Bäckerei",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="oracle",
    )
    await _add_due_card(
        db_session, user.id, lemma="Haus", pos=PartOfSpeech.NOUN, gender="das", gender_source="llm"
    )
    await _add_due_card(
        db_session, user.id, lemma="gehen", pos=PartOfSpeech.VERB, gender=None, gender_source="llm"
    )

    r = await client.get("/api/v1/srs/cards/due", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    by_lemma = {c["lemma"]: c for c in r.json()}
    assert by_lemma["Bäckerei"]["gender"] == "die"  # oracle noun → article
    assert by_lemma["Haus"]["gender"] is None  # llm noun → hidden
    assert by_lemma["gehen"]["gender"] is None  # non-noun → null
    assert isinstance(by_lemma["Bäckerei"]["ease"], (int, float))


@pytest.mark.asyncio
async def test_review_persists_elapsed_seconds(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite, "recall2@example.com")
    user = (
        await db_session.execute(select(User).where(User.email == "recall2@example.com"))
    ).scalar_one()
    card = await _add_due_card(
        db_session, user.id, lemma="lesen", pos=PartOfSpeech.VERB, gender=None, gender_source="llm"
    )

    r = await client.post(
        f"/api/v1/srs/cards/{card.id}/review",
        json={"rating": "good", "elapsed_seconds": 7},
        headers={"Cookie": cookie},
    )
    assert r.status_code == 200, r.text
    review = (
        await db_session.execute(select(Review).where(Review.user_card_id == card.id))
    ).scalar_one()
    assert review.elapsed_seconds == 7
