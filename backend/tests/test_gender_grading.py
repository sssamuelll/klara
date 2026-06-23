"""grade_gender_attempt (shared gender grading) + the consolidated gender schemas."""

import uuid

import pytest

from klara.models.enums import CEFRLevel, PartOfSpeech


def test_gender_schemas_live_in_gender_module():
    from klara.schemas.gender import (
        GenderAttemptIn,
        GenderAttemptOut,
        GenderReviewItem,
        GenderRuleOut,
    )

    item = GenderReviewItem(vocab_item_id=uuid.uuid4(), lemma="Tisch", en="mesa")
    assert item.en == "mesa"
    assert GenderAttemptIn(vocab_item_id=uuid.uuid4(), picked_article="der").picked_article == "der"
    out = GenderAttemptOut(was_correct=True, correct_gender="der", rule=None)
    assert out.rule is None
    assert (
        GenderRuleOut(
            suffix="ung", suffix_class="hard", rule_gender="die", is_exception=False
        ).rule_gender
        == "die"
    )


async def _user(db):
    from klara.models import User

    u = User(
        id=uuid.uuid4(),
        email=f"gg-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GG",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def _oracle_noun(db, *, lemma, gender):
    from klara.models import VocabItem

    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=lemma,
        pos=PartOfSpeech.NOUN,
        gender=gender,
        gender_source="oracle",
    )
    db.add(v)
    await db.flush()
    return v


@pytest.mark.asyncio
async def test_grade_gender_attempt_correct_and_wrong(db_session):
    from sqlalchemy import select

    from klara.models import GenderAttempt
    from klara.services.gender_grading import grade_gender_attempt

    u = await _user(db_session)
    v = await _oracle_noun(db_session, lemma=f"Tisch{uuid.uuid4().hex[:6]}", gender="der")
    await db_session.commit()

    ok = await grade_gender_attempt(
        db_session, user_id=u.id, vocab_item_id=v.id, picked_article="der"
    )
    assert ok is not None and ok.was_correct is True and ok.correct_gender == "der"

    bad = await grade_gender_attempt(
        db_session, user_id=u.id, vocab_item_id=v.id, picked_article="die"
    )
    assert bad is not None and bad.was_correct is False and bad.correct_gender == "der"

    rows = (
        (await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 2  # both attempts recorded


@pytest.mark.asyncio
async def test_grade_gender_attempt_none_when_not_oracle(db_session):
    from klara.models import VocabItem
    from klara.services.gender_grading import grade_gender_attempt

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

    assert (
        await grade_gender_attempt(
            db_session, user_id=u.id, vocab_item_id=llm.id, picked_article="die"
        )
        is None
    )
    assert (
        await grade_gender_attempt(
            db_session, user_id=u.id, vocab_item_id=uuid.uuid4(), picked_article="die"
        )
        is None
    )  # missing vocab


@pytest.mark.asyncio
async def test_grade_gender_attempt_show_gates_rule(db_session):
    from klara.services.gender_grading import grade_gender_attempt

    u = await _user(db_session)
    # "-ung" is a hard rule for die; an agreeing oracle gender shows the rule.
    # UUID prefix keeps lemma unique while preserving the "-ung" suffix.
    v = await _oracle_noun(db_session, lemma=f"X{uuid.uuid4().hex[:6]}zeitung", gender="die")
    await db_session.commit()
    out = await grade_gender_attempt(
        db_session, user_id=u.id, vocab_item_id=v.id, picked_article="die"
    )
    assert out is not None and out.rule is not None
    assert out.rule.rule_gender == "die"
