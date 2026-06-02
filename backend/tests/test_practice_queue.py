"""Tests for GET /api/v1/practice/queue (struggled + review queue).

Struggled items come from PronunciationAttempt rows (recent + below-threshold,
grouped by sentence, worst token surfaced). Review items come from SRS-due
UserCards, resolved to a story sentence or falling back to the vocab item's
example. These tests seed stories / attempts / cards directly via db_session,
then hit the endpoint with the seeded user's cookie.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from klara.models import PronunciationAttempt, Story, User, UserCard, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech
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
    target_vocab_item_ids: list[uuid.UUID] | None = None,
    created_at: datetime | None = None,
) -> uuid.UUID:
    story = Story(
        id=uuid.uuid4(),
        user_id=user_id,
        level=CEFRLevel.A2,
        target_language=target_language,
        native_language="es",
        title=title,
        content={"sentences": sentences, "comprehension_questions": []},
        target_vocab_item_ids=target_vocab_item_ids or [],
    )
    db_session.add(story)
    await db_session.flush()
    if created_at is not None:
        # created_at is server-default; override explicitly to test "most-recent
        # story where the lemma appears" tie-breaking.
        story.created_at = created_at
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


async def _seed_due_card(
    db_session,
    *,
    user_id: uuid.UUID,
    lemma: str,
    translation: str | None,
    example_target: str | None,
    language: str = "de",
    pos: PartOfSpeech = PartOfSpeech.NOUN,
    next_review_at: datetime | None = None,
) -> uuid.UUID:
    """Seed a VocabItem + a due UserCard, return the vocab id.

    `vocab_items` is NOT truncated between tests (it's shared reference data),
    so callers pass unique `lemma`s to dodge the (lemma, language, pos) unique
    constraint. `next_review_at=None` makes the card due (NULL = never reviewed,
    matches the due_cards clause).
    """
    vocab = VocabItem(
        id=uuid.uuid4(),
        language=language,
        lemma=lemma,
        pos=pos,
        translations={"es": translation} if translation is not None else {},
        example_target=example_target,
    )
    db_session.add(vocab)
    await db_session.flush()
    card = UserCard(
        id=uuid.uuid4(),
        user_id=user_id,
        vocab_item_id=vocab.id,
        next_review_at=next_review_at,
    )
    db_session.add(card)
    await db_session.commit()
    return vocab.id


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
    # PR #3b: struggled items carry their origin (storyId, sentenceIndex) so a
    # Practice attempt persists against the same grouping the struggle came from.
    assert item["storyId"] == str(story_id)
    assert item["sentenceIndex"] == 0


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


@pytest.mark.asyncio
async def test_queue_surfaces_review_item_from_story_breakdown(client, seed_invite, db_session):
    """A due card whose lemma appears in a story breakdown surfaces as a
    "review" item carrying that story's sentence (target + native straight
    from the story) and the breakdown gloss as focusTx."""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    lemma = f"Bildschirm-{uuid.uuid4().hex[:8]}"
    vocab_id = await _seed_due_card(
        db_session,
        user_id=uid,
        lemma=lemma,
        translation="pantalla",
        example_target="Ein Bildschirm.",
    )
    target = f"Die Nummer auf dem {lemma} wechselt."
    # Lemma sits in the SECOND sentence (index 1), not the first. PR #3b must
    # persist the REAL story index, so this proves it isn't hard-coded to 0 nor
    # confused with a queue position.
    story_id = await _seed_story(
        db_session,
        user_id=uid,
        title="Geschichte mit Wort",
        sentences=[
            {
                "target": "Ein erster Satz ohne das Wort.",
                "native": "Una primera frase sin la palabra.",
                "new_words": [],
                "breakdown": [],
            },
            {
                "target": target,
                "native": "El número en la pantalla cambia.",
                "new_words": [],
                "breakdown": [
                    {"word": lemma, "translation": "pantalla", "pos": "noun"},
                ],
            },
        ],
        target_vocab_item_ids=[vocab_id],
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["reason"] == "review"
    assert item["focusText"] == lemma
    assert item["focusTx"] == "pantalla"  # from breakdown
    assert item["sentence"]["target"] == target
    assert item["sentence"]["native"] == "El número en la pantalla cambia."
    assert item["source"] == "Geschichte mit Wort"
    # PR #3b: a story-sourced review item carries the origin story id and the
    # REAL index of the matched sentence within that story (1, not 0).
    assert item["storyId"] == str(story_id)
    assert item["sentenceIndex"] == 1
    # A review item present → queue-level sourceTitle blanked.
    assert body["sourceTitle"] == ""


@pytest.mark.asyncio
async def test_queue_review_falls_back_to_example_target(client, seed_invite, db_session):
    """When the due lemma surfaces in no breakdown (no story, or only inflected
    forms), the review item falls back to the vocab item's example_target as
    the line to say, with the lemma translation as the (approximate) native
    gloss — documented: VocabItem has no full-sentence native translation."""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    lemma = f"Regenschirm-{uuid.uuid4().hex[:8]}"
    await _seed_due_card(
        db_session,
        user_id=uid,
        lemma=lemma,
        translation="paraguas",
        example_target="Ich nehme meinen Regenschirm mit.",
    )
    # No story references this vocab → forced fallback.

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["reason"] == "review"
    assert item["focusText"] == lemma
    assert item["sentence"]["target"] == "Ich nehme meinen Regenschirm mit."
    # native is the lemma translation as an approximate gloss (see service doc).
    assert item["sentence"]["native"] == "paraguas"
    assert item["focusTx"] == "paraguas"
    assert item["source"] == ""  # no origin story
    # PR #3b: a fallback example_target line has no real story sentence to
    # attribute an attempt to → not persisted from Practice.
    assert item["storyId"] is None
    assert item["sentenceIndex"] is None


@pytest.mark.asyncio
async def test_queue_review_falls_back_when_lemma_inflected_in_story(
    client, seed_invite, db_session
):
    """The lemma is a target vocab of a story, but only an INFLECTED form shows
    in the breakdown (lemma itself never matches). We fall back to
    example_target; `source` is BLANK because the line being practised
    (example_target) does NOT come from that story — it would be a false
    attribution to credit a story that doesn't contain the sentence."""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    lemma = f"laufen-{uuid.uuid4().hex[:8]}"
    vocab_id = await _seed_due_card(
        db_session,
        user_id=uid,
        lemma=lemma,
        translation="correr",
        example_target="Wir laufen schnell.",
        pos=PartOfSpeech.VERB,
    )
    # Story references the vocab, but the breakdown only has the inflected form.
    await _seed_story(
        db_session,
        user_id=uid,
        title="Lauf-Geschichte",
        sentences=[
            {
                "target": "Er läuft jeden Morgen.",
                "native": "Él corre cada mañana.",
                "new_words": [],
                "breakdown": [
                    {"word": "läuft", "translation": "corre", "pos": "verb"},
                ],
            }
        ],
        target_vocab_item_ids=[vocab_id],
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["reason"] == "review"
    assert item["sentence"]["target"] == "Wir laufen schnell."  # example fallback
    assert item["sentence"]["native"] == "correr"  # lemma gloss, documented
    # example_target is NOT the story's sentence → no story attribution.
    assert item["source"] == ""
    # Same reasoning for persistence: the line isn't a real story sentence.
    assert item["storyId"] is None
    assert item["sentenceIndex"] is None


@pytest.mark.asyncio
async def test_queue_review_skipped_when_no_story_and_no_example(client, seed_invite, db_session):
    """A due card with neither an origin story nor an example_target has
    nothing to say aloud → it is skipped, not emitted with an empty target."""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    lemma = f"Nichts-{uuid.uuid4().hex[:8]}"
    await _seed_due_card(
        db_session,
        user_id=uid,
        lemma=lemma,
        translation="nada",
        example_target=None,
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_queue_dedups_struggled_and_review(client, seed_invite, db_session):
    """A word that is BOTH recently struggled AND SRS-due appears ONCE, as
    "struggled" (the more urgent signal). Dedup is by focus_text.casefold()
    against the review lemma."""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    # Struggled: worst token is "Bildschirm" (idx 8).
    ref = "Die Nummer auf dem Bildschirm wechselt."
    story_id = await _seed_story(
        db_session,
        user_id=uid,
        title="Struggled-Story",
        sentences=[
            {
                "target": ref,
                "native": "El número en la pantalla cambia.",
                "new_words": [],
                "breakdown": [
                    {"word": "Bildschirm", "translation": "pantalla", "pos": "noun"},
                ],
            }
        ],
    )
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=story_id,
        sentence_index=0,
        reference_text=ref,
        overall_score=45.0,
        word_bands={"8": "bad", "10": "ok"},
    )

    # Same word is ALSO an SRS-due card. casefold should match "Bildschirm".
    await _seed_due_card(
        db_session,
        user_id=uid,
        lemma="bildschirm",  # lowercase: dedup is casefold, must still match
        translation="pantalla",
        example_target="Ein Bildschirm.",
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    # ONE item only, and it's the struggled one.
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["reason"] == "struggled"
    assert item["focusText"] == "Bildschirm"


@pytest.mark.asyncio
async def test_queue_combines_struggled_then_review(client, seed_invite, db_session):
    """Distinct struggled and review words both surface: struggled first,
    then review."""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    # Struggled on "Hund" (idx 2).
    ref = "Der Hund schläft."
    story_id = await _seed_story(
        db_session,
        user_id=uid,
        title="Hund-Story",
        sentences=[
            {
                "target": ref,
                "native": "El perro duerme.",
                "new_words": [],
                "breakdown": [{"word": "Hund", "translation": "perro", "pos": "noun"}],
            }
        ],
    )
    await _seed_attempt(
        db_session,
        user_id=uid,
        story_id=story_id,
        sentence_index=0,
        reference_text=ref,
        overall_score=40.0,
        word_bands={"2": "bad"},
    )

    # A DIFFERENT word is SRS-due (fallback to example).
    lemma = f"Katze-{uuid.uuid4().hex[:8]}"
    await _seed_due_card(
        db_session,
        user_id=uid,
        lemma=lemma,
        translation="gato",
        example_target="Die Katze springt.",
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [it["reason"] for it in body["items"]] == ["struggled", "review"]
    assert body["items"][0]["focusText"] == "Hund"
    assert body["items"][1]["focusText"] == lemma
    # Struggled carries its origin; the review here fell back to example_target
    # (no story references the lemma) → no provenance, not persisted.
    assert body["items"][0]["storyId"] == str(story_id)
    assert body["items"][0]["sentenceIndex"] == 0
    assert body["items"][1]["storyId"] is None
    assert body["items"][1]["sentenceIndex"] is None


@pytest.mark.asyncio
async def test_queue_review_excludes_other_target_language(client, seed_invite, db_session):
    """A due card on a vocab item in a DIFFERENT language is filtered out, so
    the queue stays single-language. (See service doc on the VocabItem.language
    default-'de' data fragility — the filter is the right call regardless.)"""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    # User's target is "de"; this due card is French → excluded.
    await _seed_due_card(
        db_session,
        user_id=uid,
        lemma=f"chien-{uuid.uuid4().hex[:8]}",
        translation="perro",
        example_target="Le chien dort.",
        language="fr",
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_queue_review_picks_most_recent_story(client, seed_invite, db_session):
    """When the lemma appears as a target vocab item in multiple stories, the
    most-recent story (created_at DESC) supplies the sentence."""
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    lemma = f"Buch-{uuid.uuid4().hex[:8]}"
    vocab_id = await _seed_due_card(
        db_session,
        user_id=uid,
        lemma=lemma,
        translation="libro",
        example_target="Ein Buch.",
    )
    now = datetime.now(UTC)
    # Older story with the lemma.
    await _seed_story(
        db_session,
        user_id=uid,
        title="Alte Geschichte",
        sentences=[
            {
                "target": f"Das alte {lemma} liegt hier.",
                "native": "El libro viejo está aquí.",
                "new_words": [],
                "breakdown": [{"word": lemma, "translation": "libro", "pos": "noun"}],
            }
        ],
        target_vocab_item_ids=[vocab_id],
        created_at=now - timedelta(days=3),
    )
    # Newer story with the lemma — this one should win.
    await _seed_story(
        db_session,
        user_id=uid,
        title="Neue Geschichte",
        sentences=[
            {
                "target": f"Das neue {lemma} ist gut.",
                "native": "El libro nuevo es bueno.",
                "new_words": [],
                "breakdown": [{"word": lemma, "translation": "libro", "pos": "noun"}],
            }
        ],
        target_vocab_item_ids=[vocab_id],
        created_at=now - timedelta(hours=1),
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["reason"] == "review"
    assert item["sentence"]["target"] == f"Das neue {lemma} ist gut."
    assert item["source"] == "Neue Geschichte"


@pytest.mark.asyncio
async def test_queue_review_unusable_due_cards_dont_underfill(client, seed_invite, db_session):
    """Regression (CodeRabbit Major): the review query must NOT pre-limit at
    SQL level. Earlier-due cards that yield no item (no story AND no
    example_target → skipped) must not crowd usable cards out of the queue.

    Seed two unusable due cards with the SOONEST next_review_at (they'd be the
    first `limit` rows under a SQL `.limit(limit)`), then two usable ones due
    later. With limit=2 and a SQL pre-limit the queue would come back EMPTY;
    with the in-memory guard as the only cut it fills with the two usable cards.
    """
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    now = datetime.now(UTC)
    # Two unusable cards (no story, no example_target) due FIRST.
    for i in range(2):
        await _seed_due_card(
            db_session,
            user_id=uid,
            lemma=f"Leer-{i}-{uuid.uuid4().hex[:8]}",
            translation="vacío",
            example_target=None,
            next_review_at=now - timedelta(days=10 + i),
        )
    # Two usable cards (example_target present) due LATER.
    usable_lemmas = []
    for i in range(2):
        lemma = f"Voll-{i}-{uuid.uuid4().hex[:8]}"
        usable_lemmas.append(lemma)
        await _seed_due_card(
            db_session,
            user_id=uid,
            lemma=lemma,
            translation="lleno",
            example_target=f"Ein Satz Nummer {i}.",
            next_review_at=now - timedelta(days=1 + i),
        )

    r = await client.get("/api/v1/practice/queue?limit=2", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    body = r.json()
    # Filled with the two USABLE cards, not under-filled by the unusable ones.
    assert len(body["items"]) == 2
    assert {it["focusText"] for it in body["items"]} == set(usable_lemmas)
    assert all(it["reason"] == "review" for it in body["items"])


@pytest.mark.asyncio
async def test_queue_review_focus_tx_uses_resolved_index_not_first_target_match(
    client, seed_invite, db_session
):
    """Regression (CodeRabbit Minor): focus_tx must be read from the RESOLVED
    sentence index, not re-scanned for the first sentence whose target matches.

    The story has two sentences with an IDENTICAL `target`. The lemma's
    breakdown lives ONLY in the SECOND (index 1); the first carries a different,
    WRONG gloss for the same lemma. The old code re-scanned by matching target
    and grabbed the first sentence → wrong gloss. Indexing directly with the
    resolved story_sentence_index pulls the correct gloss from sentence 1.
    """
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    lemma = f"Schloss-{uuid.uuid4().hex[:8]}"
    vocab_id = await _seed_due_card(
        db_session,
        user_id=uid,
        lemma=lemma,
        translation="castillo",  # vocab-level fallback gloss, must NOT win here
        example_target="Ein Schloss.",
    )
    repeated_target = f"Das {lemma} steht dort."
    story_id = await _seed_story(
        db_session,
        user_id=uid,
        title="Doppelte Geschichte",
        sentences=[
            # Index 0: SAME target, but the lemma is NOT in its breakdown — it
            # carries a different word with a WRONG gloss for the lemma. The old
            # target re-scan would land here and read this wrong gloss.
            {
                "target": repeated_target,
                "native": "Una traducción equivocada.",
                "new_words": [],
                "breakdown": [
                    {"word": "steht", "translation": "ESTÁ-MAL", "pos": "verb"},
                ],
            },
            # Index 1: SAME target, lemma present in the breakdown → resolves
            # HERE. The correct gloss is "cerradura" (context-specific), not the
            # vocab translation "castillo".
            {
                "target": repeated_target,
                "native": "El cerrojo está ahí.",
                "new_words": [],
                "breakdown": [
                    {"word": lemma, "translation": "cerradura", "pos": "noun"},
                ],
            },
        ],
        target_vocab_item_ids=[vocab_id],
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["reason"] == "review"
    assert item["focusText"] == lemma
    # Resolved at index 1: the gloss must come from sentence 1's breakdown,
    # not from sentence 0 (the first target match) nor the vocab fallback.
    assert item["sentenceIndex"] == 1
    assert item["storyId"] == str(story_id)
    assert item["focusTx"] == "cerradura"


@pytest.mark.asyncio
async def test_queue_review_source_blank_for_example_target_despite_matching_story(
    client, seed_invite, db_session
):
    """Regression (CodeRabbit Minor): when the line comes from `example_target`
    (lemma absent from every breakdown), `source` is "" even though a story
    matched the lemma as a target vocab item. The matched story does not
    contain the example sentence, so attributing it would be false provenance.
    """
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")

    lemma = f"singen-{uuid.uuid4().hex[:8]}"
    vocab_id = await _seed_due_card(
        db_session,
        user_id=uid,
        lemma=lemma,
        translation="cantar",
        example_target="Wir singen zusammen.",
        pos=PartOfSpeech.VERB,
    )
    # Story references the vocab but its breakdown only has an inflected form,
    # so the lemma never matches → fallback to example_target.
    await _seed_story(
        db_session,
        user_id=uid,
        title="Sing-Geschichte",
        sentences=[
            {
                "target": "Sie singt allein.",
                "native": "Ella canta sola.",
                "new_words": [],
                "breakdown": [
                    {"word": "singt", "translation": "canta", "pos": "verb"},
                ],
            }
        ],
        target_vocab_item_ids=[vocab_id],
    )

    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    item = r.json()["items"][0]
    assert item["reason"] == "review"
    assert item["sentence"]["target"] == "Wir singen zusammen."  # example fallback
    # The matched story does NOT contain this sentence → no attribution.
    assert item["source"] == ""
