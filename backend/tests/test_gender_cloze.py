"""Gender cloze: evidence table, deterministic build, serve, server-side grading."""

import uuid

import pytest

from klara.models import GenderAttempt, VocabItem
from klara.models.enums import PartOfSpeech


@pytest.mark.asyncio
async def test_gender_attempt_roundtrips(db_session):
    from klara.models import User
    from klara.models.enums import CEFRLevel

    u = User(
        id=uuid.uuid4(),
        email=f"ga-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GA",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=f"Tisch{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
    )
    db_session.add_all([u, v])
    await db_session.flush()
    db_session.add(
        GenderAttempt(
            id=uuid.uuid4(),
            user_id=u.id,
            vocab_item_id=v.id,
            picked_article="die",
            was_correct=False,
        )
    )
    await db_session.commit()

    from sqlalchemy import select

    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.user_id == u.id))
    ).scalar_one()
    assert row.picked_article == "die" and row.was_correct is False


def test_build_gender_cloze_picks_oracle_noun():
    from klara.services.finish_lessons import build_gender_cloze

    verb = VocabItem(id=uuid.uuid4(), language="de", lemma="laufen", pos=PartOfSpeech.VERB)
    llm_noun = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Quux",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="llm",
    )
    oracle_noun = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Tisch",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
        translations={"es": "mesa"},
    )
    # Only the oracle-sourced noun qualifies; verbs and llm-gender nouns are skipped.
    item = build_gender_cloze([verb, llm_noun, oracle_noun], native_language="es")
    assert item is not None
    assert item["type"] == "gender_cloze"
    assert item["lemma"] == "Tisch"
    assert item["vocab_item_id"] == str(oracle_noun.id)
    assert item["en"] == "mesa"
    assert "correct_gender" not in item  # answer is NOT shipped to the client


def test_build_gender_cloze_none_when_no_oracle_noun():
    from klara.services.finish_lessons import build_gender_cloze

    only_llm = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Quux",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="llm",
    )
    assert build_gender_cloze([only_llm], native_language="es") is None


@pytest.mark.asyncio
async def test_get_quiz_appends_gender_cloze(db_session):
    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app
    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    u = User(
        id=uuid.uuid4(),
        email=f"gq-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GQ",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=f"Tisch{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
    )
    db_session.add_all([u, v])
    await db_session.flush()
    story = Story(
        id=uuid.uuid4(),
        user_id=u.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="t",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[v.id],
        # Pre-set quiz_items (non-empty) so ensure_quiz_items returns them
        # without calling the LLM; the gender_cloze is appended on top.
        quiz_items=[{"type": "shadow", "cap": "x", "sentence": "Hallo.", "en": "Hola."}],
    )
    db_session.add(story)
    await db_session.commit()

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/stories/{story.id}/quiz")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    gc = items[-1]
    assert gc["type"] == "gender_cloze"
    assert gc["vocab_item_id"] == str(v.id)
    assert "correct_gender" not in gc  # answer never shipped


@pytest.mark.asyncio
async def test_gender_attempt_endpoint_grades_against_oracle(db_session):
    import uuid as _uuid

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app
    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    u = User(
        id=_uuid.uuid4(),
        email=f"ge-{_uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GE",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    v = VocabItem(
        id=_uuid.uuid4(),
        language="de",
        lemma=f"Mond{_uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
    )
    db_session.add_all([u, v])
    await db_session.flush()
    story = Story(
        id=_uuid.uuid4(),
        user_id=u.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="t",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[v.id],
    )
    db_session.add(story)
    await db_session.commit()

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Wrong pick "die" (the ES "la luna" trap) — oracle says "der".
        resp = await ac.post(
            f"/api/v1/stories/{story.id}/gender/attempts",
            json={"vocab_item_id": str(v.id), "picked_article": "die"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["was_correct"] is False
    assert body["correct_gender"] == "der"  # the answer arrives only after picking
    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.picked_article == "die" and row.was_correct is False
