"""GET /gender/review (weak set, answer hidden) + POST /gender/attempts (standalone
oracle-gated grade). Authed via dependency overrides; lemmas uuid-suffixed."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from klara.auth.users import current_active_user
from klara.dependencies import db_session as db_session_dep
from klara.main import create_app
from klara.models import GenderAttempt, User, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


async def _user(db, *, native_language="es"):
    u = User(
        id=uuid.uuid4(),
        email=f"gr-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GR",
        level=CEFRLevel.A1,
        native_language=native_language,
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def _oracle_noun(db, *, lemma, gender, translations=None):
    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=lemma,
        pos=PartOfSpeech.NOUN,
        gender=gender,
        gender_source="oracle",
        translations=translations or {},
    )
    db.add(v)
    await db.flush()
    return v


def _client(db, user):
    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_review_returns_weak_only_answer_hidden(db_session):
    u = await _user(db_session)
    mastered = await _oracle_noun(db_session, lemma=f"Tisch{uuid.uuid4().hex[:6]}", gender="der")
    weak = await _oracle_noun(
        db_session,
        lemma=f"Lampe{uuid.uuid4().hex[:6]}",
        gender="die",
        translations={"es": "lámpara"},
    )
    for _ in range(3):
        db_session.add(
            GenderAttempt(
                id=uuid.uuid4(),
                user_id=u.id,
                vocab_item_id=mastered.id,
                picked_article="der",
                was_correct=True,
            )
        )
    db_session.add(
        GenderAttempt(
            id=uuid.uuid4(),
            user_id=u.id,
            vocab_item_id=weak.id,
            picked_article="der",
            was_correct=False,
        )
    )
    await db_session.commit()

    async with _client(db_session, u) as ac:
        resp = await ac.get("/api/v1/gender/review")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert [i["vocab_item_id"] for i in items] == [str(weak.id)]  # mastered excluded
    assert items[0]["lemma"] == weak.lemma and items[0]["en"] == "lámpara"
    assert "gender" not in items[0] and "correct_gender" not in items[0]  # answer hidden


@pytest.mark.asyncio
async def test_review_empty_when_caught_up(db_session):
    u = await _user(db_session)
    async with _client(db_session, u) as ac:
        resp = await ac.get("/api/v1/gender/review")
    assert resp.status_code == 200 and resp.json() == []


@pytest.mark.asyncio
async def test_grade_endpoint_records_and_grades(db_session):
    from sqlalchemy import select

    u = await _user(db_session)
    v = await _oracle_noun(db_session, lemma=f"Mond{uuid.uuid4().hex[:6]}", gender="der")
    await db_session.commit()
    async with _client(db_session, u) as ac:
        resp = await ac.post(
            "/api/v1/gender/attempts",
            json={"vocab_item_id": str(v.id), "picked_article": "die"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["was_correct"] is False and body["correct_gender"] == "der"
    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.user_id == u.id  # written to the caller's ledger


@pytest.mark.asyncio
async def test_grade_endpoint_404_for_non_oracle(db_session):
    u = await _user(db_session)
    llm = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=f"Llm{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="llm",
    )
    db_session.add(llm)
    await db_session.commit()
    async with _client(db_session, u) as ac:
        resp = await ac.post(
            "/api/v1/gender/attempts",
            json={"vocab_item_id": str(llm.id), "picked_article": "die"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_grade_endpoint_is_user_isolated(db_session):
    """IDOR isolation: a grade always lands on the CALLER's ledger, never another
    user's. The vocab is shared; the attempt's user_id is server-derived."""
    from sqlalchemy import select

    owner = await _user(db_session)  # noqa: F841 — seeded to prove IDOR isolation
    other = await _user(db_session)
    v = await _oracle_noun(db_session, lemma=f"Haus{uuid.uuid4().hex[:6]}", gender="das")
    await db_session.commit()
    async with _client(db_session, other) as ac:  # `other` is the authed caller
        resp = await ac.post(
            "/api/v1/gender/attempts",
            json={"vocab_item_id": str(v.id), "picked_article": "das"},
        )
    assert resp.status_code == 201
    rows = (
        (await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1 and rows[0].user_id == other.id  # never owner.id
