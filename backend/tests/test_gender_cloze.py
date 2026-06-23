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
    # The answer is NEVER shipped to the client: the item carries exactly these
    # keys — no "gender"/"correct_gender"/"correct_article". Asserting the full
    # key set (not just one absent name) hardens the no-leak contract.
    assert set(item.keys()) == {"type", "cap", "lemma", "vocab_item_id", "en"}


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


def test_build_gender_cloze_skips_non_german_oracle_noun():
    from klara.services.finish_lessons import build_gender_cloze

    # der/die/das is German-specific; a non-German oracle noun must not surface.
    fr_noun = VocabItem(
        id=uuid.uuid4(),
        language="fr",
        lemma="lune",
        pos=PartOfSpeech.NOUN,
        gender="die",  # nonsensical for fr — exactly why the language guard matters
        gender_source="oracle",
    )
    assert build_gender_cloze([fr_noun], native_language="es") is None


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


@pytest.mark.asyncio
async def test_gender_attempt_404_when_vocab_not_in_story(db_session):
    """Authz/IDOR guard: a vocab the user's story does not target cannot be
    graded or recorded, even if it exists and has an oracle gender."""
    import uuid as _uuid

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import func, select

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app
    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    u = User(
        id=_uuid.uuid4(),
        email=f"gn-{_uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GN",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    in_story = VocabItem(
        id=_uuid.uuid4(),
        language="de",
        lemma=f"Tisch{_uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
    )
    outsider = VocabItem(  # exists + has a gender, but NOT in the story
        id=_uuid.uuid4(),
        language="de",
        lemma=f"Haus{_uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="das",
        gender_source="oracle",
    )
    db_session.add_all([u, in_story, outsider])
    await db_session.flush()
    story = Story(
        id=_uuid.uuid4(),
        user_id=u.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="t",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[in_story.id],
    )
    db_session.add(story)
    await db_session.commit()

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            f"/api/v1/stories/{story.id}/gender/attempts",
            json={"vocab_item_id": str(outsider.id), "picked_article": "das"},
        )
    assert resp.status_code == 404, resp.text
    count = (
        await db_session.execute(
            select(func.count())
            .select_from(GenderAttempt)
            .where(GenderAttempt.vocab_item_id == outsider.id)
        )
    ).scalar_one()
    assert count == 0  # no evidence written on the rejected path


@pytest.mark.asyncio
async def test_gender_attempt_404_when_vocab_has_no_gender(db_session):
    """A target word with no stored gender is not answerable — 404, no record."""
    import uuid as _uuid

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import func, select

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app
    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    u = User(
        id=_uuid.uuid4(),
        email=f"gg-{_uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GG",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    v = VocabItem(  # in the story, but gender is None
        id=_uuid.uuid4(),
        language="de",
        lemma=f"laufen{_uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.VERB,
        gender=None,
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
        resp = await ac.post(
            f"/api/v1/stories/{story.id}/gender/attempts",
            json={"vocab_item_id": str(v.id), "picked_article": "der"},
        )
    assert resp.status_code == 404, resp.text
    count = (
        await db_session.execute(
            select(func.count())
            .select_from(GenderAttempt)
            .where(GenderAttempt.vocab_item_id == v.id)
        )
    ).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_gender_attempt_404_when_gender_not_oracle(db_session):
    """Grading is oracle-only: an LLM-guessed gender must never be certified as
    evidence, even if the vocab is in the story and has a (non-oracle) gender.
    Without the gender_source gate the endpoint would grade the LLM's echo."""
    import uuid as _uuid

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import func, select

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app
    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    u = User(
        id=_uuid.uuid4(),
        email=f"gl-{_uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GL",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    v = VocabItem(  # in the story, has a gender, but it's the LLM's guess
        id=_uuid.uuid4(),
        language="de",
        lemma=f"Quux{_uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="llm",
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
        resp = await ac.post(
            f"/api/v1/stories/{story.id}/gender/attempts",
            json={"vocab_item_id": str(v.id), "picked_article": "die"},
        )
    assert resp.status_code == 404, resp.text  # rejected despite picked == stored gender
    count = (
        await db_session.execute(
            select(func.count())
            .select_from(GenderAttempt)
            .where(GenderAttempt.vocab_item_id == v.id)
        )
    ).scalar_one()
    assert count == 0


async def _gender_story_user(db_session, *, lemma, gender, gender_source="oracle"):
    """Create a user + an oracle-gendered de NOUN + a story targeting it. Returns
    (user, vocab, story). Lemmas are unique-prefixed so the real German suffix
    stays at the END (the detector matches the suffix), while vocab_items (not
    truncated) stays collision-free."""
    import uuid as _uuid

    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    u = User(
        id=_uuid.uuid4(),
        email=f"gp-{_uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GP",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    v = VocabItem(
        id=_uuid.uuid4(),
        language="de",
        lemma=lemma,
        pos=PartOfSpeech.NOUN,
        gender=gender,
        gender_source=gender_source,
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
    return u, v, story


async def _post_gender(db_session, u, story, vocab_id, picked):
    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post(
            f"/api/v1/stories/{story.id}/gender/attempts",
            json={"vocab_item_id": str(vocab_id), "picked_article": picked},
        )


@pytest.mark.asyncio
async def test_gender_attempt_case_a_returns_rule_and_persists_detail(db_session):
    from sqlalchemy import select

    lemma = f"q{uuid.uuid4().hex[:8]}heit"  # ends in -heit (hard die)
    u, v, story = await _gender_story_user(db_session, lemma=lemma, gender="die")
    resp = await _post_gender(db_session, u, story, v.id, "die")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["was_correct"] is True
    assert body["rule"] == {
        "suffix": "heit",
        "suffix_class": "hard",
        "rule_gender": "die",
        "is_exception": False,
    }
    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.detail == {
        "suffix": "heit",
        "suffix_class": "hard",
        "rule_gender": "die",
        "oracle_gender": "die",
        "agreement": True,
        "is_exception": False,
    }


@pytest.mark.asyncio
async def test_gender_attempt_case_b_suppresses_rule_but_persists_detail(db_session):
    from sqlalchemy import select

    lemma = f"q{uuid.uuid4().hex[:8]}er"  # ends in -er (tendency der); oracle die → disagree
    u, v, story = await _gender_story_user(db_session, lemma=lemma, gender="die")
    resp = await _post_gender(db_session, u, story, v.id, "die")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["rule"] is None  # suppressed on the wire
    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.detail["agreement"] is False and row.detail["is_exception"] is False
    assert set(row.detail.keys()) == {
        "suffix",
        "suffix_class",
        "rule_gender",
        "oracle_gender",
        "agreement",
        "is_exception",
    }


@pytest.mark.asyncio
async def test_gender_attempt_no_suffix_null_detail_and_rule(db_session):
    lemma = f"klotz{uuid.uuid4().hex[:6]}x"  # ends in 'x' → no suffix match
    u, v, story = await _gender_story_user(db_session, lemma=lemma, gender="der")
    resp = await _post_gender(db_session, u, story, v.id, "der")
    assert resp.status_code == 201, resp.text
    assert resp.json()["rule"] is None
    from sqlalchemy import select

    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.detail is None


def test_gender_cloze_quiz_item_has_no_rule_field():
    # No-leak contract: the PRE-answer quiz item must never carry the rule/answer.
    from klara.schemas.finish import GenderClozeQuizItem

    assert "rule" not in GenderClozeQuizItem.model_fields


def test_build_gender_cloze_prefer_order_picks_weakest():
    from klara.services.finish_lessons import build_gender_cloze

    a = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Tisch",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
        translations={"es": "mesa"},
    )
    b = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Lampe",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="oracle",
        translations={"es": "lámpara"},
    )
    # a is first in target order, but prefer_order ranks b ahead → b is chosen.
    item = build_gender_cloze([a, b], native_language="es", prefer_order=[b.id, a.id])
    assert item["vocab_item_id"] == str(b.id)
    assert item["lemma"] == "Lampe"


def test_build_gender_cloze_prefer_order_none_picks_first_eligible():
    from klara.services.finish_lessons import build_gender_cloze

    a = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Tisch",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
        translations={"es": "mesa"},
    )
    b = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Lampe",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="oracle",
        translations={"es": "lámpara"},
    )
    # No prefer_order → first eligible in target order (back-compat).
    item = build_gender_cloze([a, b], native_language="es")
    assert item["vocab_item_id"] == str(a.id)


@pytest.mark.asyncio
async def test_get_quiz_targets_weakest_gender_noun(db_session):
    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app
    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    u = User(
        id=uuid.uuid4(),
        email=f"gw-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GW",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    strong = VocabItem(  # FIRST in target order, but mastered → must NOT be picked
        id=uuid.uuid4(),
        language="de",
        lemma=f"Tisch{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
    )
    weak = VocabItem(  # second in target order, recently wrong → must be picked
        id=uuid.uuid4(),
        language="de",
        lemma=f"Lampe{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="oracle",
    )
    db_session.add_all([u, strong, weak])
    await db_session.flush()
    for _ in range(3):  # strong mastered
        db_session.add(
            GenderAttempt(
                id=uuid.uuid4(),
                user_id=u.id,
                vocab_item_id=strong.id,
                picked_article="der",
                was_correct=True,
            )
        )
    db_session.add(  # weak: most recent attempt wrong
        GenderAttempt(
            id=uuid.uuid4(),
            user_id=u.id,
            vocab_item_id=weak.id,
            picked_article="der",
            was_correct=False,
        )
    )
    story = Story(
        id=uuid.uuid4(),
        user_id=u.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="t",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[strong.id, weak.id],  # strong first
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
    gc = resp.json()["items"][-1]
    assert gc["type"] == "gender_cloze"
    assert gc["vocab_item_id"] == str(weak.id)  # weakest picked, not the first/mastered one
