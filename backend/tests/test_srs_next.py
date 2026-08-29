import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

EMAIL = "next@example.com"
PASSWORD = "hunter2hunter2"


async def _login(client, seed_invite, app_settings) -> dict[str, str]:
    app_settings(INITIAL_OWNER_EMAIL="")
    invite = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "display_name": "Next",
            "invite_token": invite,
        },
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 204
    return {"Cookie": r.headers["set-cookie"].split(";")[0]}


async def _user_id(db_session) -> uuid.UUID:
    from klara.models import User

    user = (await db_session.execute(select(User).where(User.email == EMAIL))).scalar_one()
    return user.id


async def _add_user_card(db_session, user_id, next_review_at):
    from klara.models import UserCard, VocabItem
    from klara.models.enums import PartOfSpeech

    vocab = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=f"wort-{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        translations={"es": "palabra"},
        example_target=None,
    )
    db_session.add(vocab)
    await db_session.flush()
    db_session.add(
        UserCard(
            id=uuid.uuid4(), user_id=user_id, vocab_item_id=vocab.id, next_review_at=next_review_at
        )
    )
    await db_session.commit()


async def _add_study_card(db_session, user_id, next_review_at, archived: bool = False):
    from klara.models import StudyCard

    db_session.add(
        StudyCard(
            id=uuid.uuid4(),
            user_id=user_id,
            front="f",
            back="b",
            tags=[],
            batch_id=uuid.uuid4(),
            next_review_at=next_review_at,
            archived_at=datetime.now(UTC) if archived else None,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_next_requires_auth(client):
    assert (await client.get("/api/v1/srs/next")).status_code == 401


@pytest.mark.asyncio
async def test_next_empty(client, seed_invite, app_settings):
    headers = await _login(client, seed_invite, app_settings)
    r = await client.get("/api/v1/srs/next", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"due_now": 0, "next_due_at": None}


@pytest.mark.asyncio
async def test_next_counts_due_and_finds_earliest_future(
    client, seed_invite, app_settings, db_session
):
    headers = await _login(client, seed_invite, app_settings)
    uid = await _user_id(db_session)
    now = datetime.now(UTC)
    in_2h = (now + timedelta(hours=2)).replace(microsecond=0)
    in_1d = (now + timedelta(days=1)).replace(microsecond=0)

    await _add_user_card(db_session, uid, next_review_at=None)  # NULL = vencida (srs.py:95)
    await _add_user_card(db_session, uid, next_review_at=in_1d)
    await _add_study_card(db_session, uid, next_review_at=now - timedelta(minutes=1))  # vencida
    await _add_study_card(db_session, uid, next_review_at=in_2h)
    await _add_study_card(db_session, uid, next_review_at=now + timedelta(minutes=5), archived=True)

    r = await client.get("/api/v1/srs/next", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["due_now"] == 2
    assert datetime.fromisoformat(body["next_due_at"]) == in_2h
