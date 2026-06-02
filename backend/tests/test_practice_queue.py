"""Tests for GET /api/v1/practice/queue (struggled-only queue).

The queue is assembled from PronunciationAttempt rows: recent + below-threshold
attempts, grouped by sentence, with the worst-scored token surfaced as the
focus word. These tests seed stories + attempts directly via db_session, then
hit the endpoint with the seeded user's cookie.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from klara.models import PronunciationAttempt, Story, User
from klara.models.enums import CEFRLevel
from klara.services.practice_queue import (
    RECENT_ATTEMPTS_WINDOW_DAYS,
    STRUGGLED_SCORE_THRESHOLD,
)


async def _register_and_login(client, seed_invite) -> str:
    """Seed an invite, register against it, log in. Mirrors test_pronunciation.

    Story + attempt seeding happens out-of-band via db_session; here we only
    need a real session cookie for the logged-in user.
    """
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "practice@example.com",
            "password": "hunter2hunter2",
            "invite_token": token,
        },
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "practice@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def _user_id_by_email(db_session, email: str) -> uuid.UUID:
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    return user.id


async def _seed_story(
    db_session,
    *,
    user_id: uuid.UUID,
    sentences: list[dict],
    title: str = "Eine Geschichte",
    target_language: str = "de",
) -> uuid.UUID:
    story = Story(
        id=uuid.uuid4(),
        user_id=user_id,
        level=CEFRLevel.A2,
        target_language=target_language,
        native_language="es",
        title=title,
        content={"sentences": sentences, "comprehension_questions": []},
        target_vocab_item_ids=[],
    )
    db_session.add(story)
    await db_session.commit()
    return story.id


async def _seed_attempt(
    db_session,
    *,
    user_id: uuid.UUID,
    story_id: uuid.UUID,
    sentence_index: int,
    reference_text: str,
    overall_score: float,
    word_bands: dict,
    attempted_at: datetime | None = None,
) -> uuid.UUID:
    row = PronunciationAttempt(
        id=uuid.uuid4(),
        user_id=user_id,
        story_id=story_id,
        sentence_index=sentence_index,
        reference_text=reference_text,
        recognized_text=None,
        overall_score=overall_score,
        word_bands=word_bands,
    )
    db_session.add(row)
    await db_session.flush()
    if attempted_at is not None:
        # attempted_at is server-default; override explicitly for window tests.
        row.attempted_at = attempted_at
    await db_session.commit()
    return row.id


@pytest.mark.asyncio
async def test_queue_requires_auth(client):
    r = await client.get("/api/v1/practice/queue")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_queue_empty_when_no_attempts(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["targetLanguage"] == "de"
    assert body["sourceTitle"] == ""


@pytest.mark.asyncio
async def test_queue_surfaces_struggled_with_worst_token(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    ref = "Die Nummer auf dem Bildschirm wechselt."
    story_id = await _seed_story(
        db_session,
        user_id=uid,
        title="El sello que tarda diez minutos.",
        sentences=[
            {
                "target": ref,
                "native": "El número en la pantalla cambia.",
                "new_words": [],
                "breakdown": [
                    {"word": "Bildschirm", "translation": "pantalla", "pos": "noun"},
                    {"word": "wechselt", "translation": "cambia", "pos": "verb"},
                ],
            }
        ],
    )
    # Token indices (frontend wordTokenIndices): words sit at 0,2,4,6,8,10.
    #   0 Die  2 Nummer  4 auf  6 dem  8 Bildschirm  10 wechselt
    # Mark "Bildschirm" (idx 8) as the worst (bad); others good/ok.
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=story_id,
        sentence_index=0,
        reference_text=ref,
        overall_score=55.0,
        word_bands={"0": "good", "8": "bad", "10": "ok"},
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["reason"] == "struggled"
    assert item["focusText"] == "Bildschirm"
    assert item["focusTx"] == "pantalla"  # resolved from breakdown
    assert item["variants"] == []
    assert item["sentence"]["target"] == ref
    assert item["source"] == "El sello que tarda diez minutos."
    assert body["sourceTitle"] == "El sello que tarda diez minutos."


@pytest.mark.asyncio
async def test_queue_excludes_passing_and_stale(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")
    ref = "Guten Tag heute."
    story_id = await _seed_story(
        db_session,
        user_id=uid,
        sentences=[{"target": ref, "native": "Buenos días hoy.", "new_words": []}],
    )

    # 1) A passing attempt (>= threshold) must be excluded.
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=story_id,
        sentence_index=0,
        reference_text=ref,
        overall_score=STRUGGLED_SCORE_THRESHOLD + 5,
        word_bands={"0": "good"},
    )
    # 2) A struggled attempt but OUTSIDE the recency window must be excluded.
    stale = datetime.now(UTC) - timedelta(days=RECENT_ATTEMPTS_WINDOW_DAYS + 2)
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=story_id,
        sentence_index=0,
        reference_text=ref,
        overall_score=30.0,
        word_bands={"0": "bad"},
        attempted_at=stale,
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_queue_dedups_to_latest_per_sentence(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")
    ref = "Sie nickt leise."
    story_id = await _seed_story(
        db_session,
        user_id=uid,
        sentences=[{"target": ref, "native": "Ella asiente en silencio.", "new_words": []}],
    )
    now = datetime.now(UTC)
    # Older struggled attempt: worst token "nickt" (idx 2).
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=story_id,
        sentence_index=0,
        reference_text=ref,
        overall_score=40.0,
        word_bands={"2": "bad", "4": "good"},
        attempted_at=now - timedelta(hours=2),
    )
    # Newer struggled attempt on SAME sentence: worst token "leise" (idx 4).
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=story_id,
        sentence_index=0,
        reference_text=ref,
        overall_score=50.0,
        word_bands={"2": "good", "4": "bad"},
        attempted_at=now - timedelta(minutes=5),
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    # One item (deduped), reflecting the NEWER attempt's worst token.
    assert len(body["items"]) == 1
    assert body["items"][0]["focusText"] == "leise"


@pytest.mark.asyncio
async def test_queue_respects_limit(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")
    sentences = [
        {"target": f"Satz Nummer {i}.", "native": f"Frase número {i}.", "new_words": []}
        for i in range(4)
    ]
    story_id = await _seed_story(db_session, user_id=uid, sentences=sentences)
    for i in range(4):
        await _seed_attempt(
            db_session,
            user_id=uid,
            story_id=story_id,
            sentence_index=i,
            reference_text=sentences[i]["target"],
            overall_score=40.0,
            word_bands={"0": "bad"},
        )

    r = await client.get("/api/v1/practice/queue?limit=2", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 2


@pytest.mark.asyncio
async def test_queue_excludes_other_target_language(client, seed_invite, db_session):
    """A user who switched learning languages must not get foreign-language
    items. The seeded user's target_language is "de" (registration default);
    a recent struggled attempt on an old "fr" story must be filtered out."""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    # Old story in a DIFFERENT target language (user used to learn French).
    fr_ref = "Le chat dort."
    fr_story = await _seed_story(
        db_session,
        user_id=uid,
        title="Une histoire",
        sentences=[{"target": fr_ref, "native": "El gato duerme.", "new_words": []}],
        target_language="fr",
    )
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=fr_story,
        sentence_index=0,
        reference_text=fr_ref,
        overall_score=35.0,
        word_bands={"0": "bad"},
    )

    # Current-language (de) story with a struggled attempt — this one stays.
    de_ref = "Der Hund schläft."
    de_story = await _seed_story(
        db_session,
        user_id=uid,
        title="Eine Geschichte",
        sentences=[{"target": de_ref, "native": "El perro duerme.", "new_words": []}],
        target_language="de",
    )
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=de_story,
        sentence_index=0,
        reference_text=de_ref,
        overall_score=35.0,
        word_bands={"0": "bad"},
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    # Only the German item survives; the French one is filtered by language.
    assert len(body["items"]) == 1
    assert body["items"][0]["sentence"]["target"] == de_ref
    assert body["targetLanguage"] == "de"
    assert body["sourceTitle"] == "Eine Geschichte"


@pytest.mark.asyncio
async def test_queue_blanks_source_title_for_mixed_stories(client, seed_invite, db_session):
    """A queue-level sourceTitle only makes sense for a single-story queue.
    When items span multiple stories, the field is blanked so the frontend
    omits the (now-ambiguous) 'from <story>' signature."""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    ref_a = "Der Hund schläft."
    story_a = await _seed_story(
        db_session,
        user_id=uid,
        title="Geschichte A",
        sentences=[{"target": ref_a, "native": "El perro duerme.", "new_words": []}],
    )
    ref_b = "Die Katze springt."
    story_b = await _seed_story(
        db_session,
        user_id=uid,
        title="Geschichte B",
        sentences=[{"target": ref_b, "native": "El gato salta.", "new_words": []}],
    )
    for sid, ref in ((story_a, ref_a), (story_b, ref_b)):
        await _seed_attempt(
            db_session,
            user_id=uid,
            story_id=sid,
            sentence_index=0,
            reference_text=ref,
            overall_score=35.0,
            word_bands={"0": "bad"},
        )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 2
    # Mixed stories → blank queue-level title; per-item source stays correct.
    assert body["sourceTitle"] == ""
    assert {it["source"] for it in body["items"]} == {"Geschichte A", "Geschichte B"}


@pytest.mark.asyncio
async def test_queue_focus_tx_empty_without_breakdown(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")
    ref = "Setzen Sie sich."
    story_id = await _seed_story(
        db_session,
        user_id=uid,
        sentences=[{"target": ref, "native": "Tome asiento.", "new_words": []}],
    )
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=story_id,
        sentence_index=0,
        reference_text=ref,
        overall_score=42.0,
        word_bands={"0": "bad"},
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["focusText"] == "Setzen"
    assert item["focusTx"] == ""  # documented degradation: no breakdown → empty
