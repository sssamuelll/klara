"""known_set deriva los lemas que el usuario ya tiene en SRS (UserCard),
canonicalizados, restringido al idioma. Es el sustraendo de la selección."""

import uuid
from datetime import UTC

import pytest

from klara.curriculum.competence import (
    GENDER_MASTERY_STREAK_N,
    MASTERY_INTERVAL_DAYS,
    _streak_mastered,
    is_mastered_gender,
    is_mastered_lexical,
    known_set,
    module_gender_progress,
    module_progress,
)
from klara.models import GenderAttempt, Module, User, UserCard, VocabItem
from klara.models.enums import CardState, CEFRLevel, PartOfSpeech


async def _user(db) -> uuid.UUID:
    u = User(
        id=uuid.uuid4(),
        email=f"c-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="C",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u.id


async def _vocab(db, lemma, language="de") -> uuid.UUID:
    v = VocabItem(id=uuid.uuid4(), language=language, lemma=lemma, pos=PartOfSpeech.NOUN)
    db.add(v)
    await db.flush()
    return v.id


@pytest.mark.asyncio
async def test_known_set_is_canonical_lemmas_with_a_card_in_language(db_session):
    uid = await _user(db_session)
    vid_de = await _vocab(db_session, "Haus", "de")
    vid_en = await _vocab(db_session, "house", "en")
    for vid in (vid_de, vid_en):
        db_session.add(UserCard(id=uuid.uuid4(), user_id=uid, vocab_item_id=vid))
    await db_session.commit()

    ks = await known_set(db_session, user_id=uid, language="de")
    assert "haus" in ks  # canonicalizado (minúsculas)
    assert "house" not in ks  # otro idioma excluido


@pytest.mark.asyncio
async def test_known_set_empty_when_no_cards(db_session):
    uid = await _user(db_session)
    await db_session.commit()
    assert await known_set(db_session, user_id=uid, language="de") == set()


def test_is_mastered_lexical_thresholds():
    reviewing_mature = UserCard(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        vocab_item_id=uuid.uuid4(),
        state=CardState.REVIEWING,
        interval_days=MASTERY_INTERVAL_DAYS,
    )
    reviewing_young = UserCard(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        vocab_item_id=uuid.uuid4(),
        state=CardState.REVIEWING,
        interval_days=5.0,
    )
    learning = UserCard(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        vocab_item_id=uuid.uuid4(),
        state=CardState.LEARNING,
        interval_days=99.0,
    )
    assert is_mastered_lexical(reviewing_mature) is True
    assert is_mastered_lexical(reviewing_young) is False
    assert is_mastered_lexical(learning) is False


@pytest.mark.asyncio
async def test_module_progress_counts_encountered_and_mastered(db_session):
    u = User(
        id=uuid.uuid4(),
        email=f"mp-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="MP",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db_session.add(u)
    vs = []
    for lemma in ("Kaffee", "Tasse", "Milch"):
        v = VocabItem(id=uuid.uuid4(), language="modt2", lemma=lemma, pos=PartOfSpeech.NOUN)
        db_session.add(v)
        vs.append(v)
    await db_session.flush()
    m = Module(
        id=uuid.uuid4(),
        language="modt2",
        cefr_level=CEFRLevel.A1,
        sequence_order=1,
        title="café",
        can_dos=["x"],
        grammatical_focus=["y"],
    )
    m.vocab_items = vs
    db_session.add(m)
    await db_session.flush()
    # Kaffee: mastered (REVIEWING, interval>=21). Tasse: encountered only (NEW). Milch: no card.
    db_session.add(
        UserCard(
            id=uuid.uuid4(),
            user_id=u.id,
            vocab_item_id=vs[0].id,
            state=CardState.REVIEWING,
            interval_days=30.0,
        )
    )
    db_session.add(
        UserCard(
            id=uuid.uuid4(),
            user_id=u.id,
            vocab_item_id=vs[1].id,
            state=CardState.NEW,
        )
    )
    await db_session.commit()

    encountered, mastered, total = await module_progress(db_session, user_id=u.id, module_id=m.id)
    assert (encountered, mastered, total) == (2, 1, 3)


def test_streak_mastered_pure():
    class _A:
        def __init__(self, c):
            self.was_correct = c

    assert _streak_mastered([_A(True), _A(True), _A(True)], 3) is True
    assert _streak_mastered([_A(True), _A(True)], 3) is False  # < N attempts
    # Most recent (index 0) is a fail → streak broken.
    assert _streak_mastered([_A(False), _A(True), _A(True), _A(True)], 3) is False
    # The fail is OLDER than the last N → still mastered.
    assert _streak_mastered([_A(True), _A(True), _A(True), _A(False)], 3) is True
    assert GENDER_MASTERY_STREAK_N == 3


async def _de_oracle_noun(db, *, gender):
    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=f"N{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN,
        gender=gender,
        gender_source="oracle",
    )
    db.add(v)
    await db.flush()
    return v


@pytest.mark.asyncio
async def test_is_mastered_gender_streak_and_recency(db_session):
    from datetime import datetime, timedelta

    uid = await _user(db_session)
    v = await _de_oracle_noun(db_session, gender="der")
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i, correct in enumerate([True, True, True]):  # 3 correct → mastered
        db_session.add(
            GenderAttempt(
                id=uuid.uuid4(),
                user_id=uid,
                vocab_item_id=v.id,
                picked_article="der",
                was_correct=correct,
                attempted_at=base + timedelta(minutes=i),
            )
        )
    await db_session.commit()
    assert await is_mastered_gender(db_session, user_id=uid, vocab_item_id=v.id) is True

    # A newer failed attempt breaks the most-recent-3 streak.
    db_session.add(
        GenderAttempt(
            id=uuid.uuid4(),
            user_id=uid,
            vocab_item_id=v.id,
            picked_article="die",
            was_correct=False,
            attempted_at=base + timedelta(minutes=9),
        )
    )
    await db_session.commit()
    assert await is_mastered_gender(db_session, user_id=uid, vocab_item_id=v.id) is False


@pytest.mark.asyncio
async def test_is_mastered_gender_false_below_floor(db_session):
    uid = await _user(db_session)
    v = await _de_oracle_noun(db_session, gender="die")
    for _ in range(2):  # only 2 attempts < N=3
        db_session.add(
            GenderAttempt(
                id=uuid.uuid4(),
                user_id=uid,
                vocab_item_id=v.id,
                picked_article="die",
                was_correct=True,
            )
        )
    await db_session.commit()
    assert await is_mastered_gender(db_session, user_id=uid, vocab_item_id=v.id) is False


@pytest.mark.asyncio
async def test_module_gender_progress_tristate(db_session):
    uid = await _user(db_session)
    mastered = await _de_oracle_noun(db_session, gender="der")  # 3 correct
    encountered = await _de_oracle_noun(db_session, gender="die")  # 2 attempts (< N)
    untouched = await _de_oracle_noun(db_session, gender="das")  # 0 attempts
    verb = VocabItem(  # not a NOUN → excluded
        id=uuid.uuid4(),
        language="de",
        lemma=f"V{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.VERB,
        gender=None,
        gender_source="oracle",
    )
    llm_noun = VocabItem(  # not oracle → excluded
        id=uuid.uuid4(),
        language="de",
        lemma=f"L{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="llm",
    )
    db_session.add_all([verb, llm_noun])
    await db_session.flush()
    m = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=1,
        title="g",
        can_dos=["x"],
        grammatical_focus=["y"],
    )
    m.vocab_items = [mastered, encountered, untouched, verb, llm_noun]
    db_session.add(m)
    await db_session.flush()
    for _ in range(3):
        db_session.add(
            GenderAttempt(
                id=uuid.uuid4(),
                user_id=uid,
                vocab_item_id=mastered.id,
                picked_article="der",
                was_correct=True,
            )
        )
    for _ in range(2):
        db_session.add(
            GenderAttempt(
                id=uuid.uuid4(),
                user_id=uid,
                vocab_item_id=encountered.id,
                picked_article="die",
                was_correct=True,
            )
        )
    await db_session.commit()

    enc, mast, total = await module_gender_progress(db_session, user_id=uid, module_id=m.id)
    assert (enc, mast, total) == (2, 1, 3)  # total: 3 oracle nouns; verb+llm excluded


@pytest.mark.asyncio
async def test_module_gender_progress_zero_when_no_eligible(db_session):
    uid = await _user(db_session)
    llm_noun = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=f"L{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="llm",
    )
    db_session.add(llm_noun)
    await db_session.flush()
    m = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=1,
        title="g",
        can_dos=["x"],
        grammatical_focus=["y"],
    )
    m.vocab_items = [llm_noun]
    db_session.add(m)
    await db_session.commit()
    assert await module_gender_progress(db_session, user_id=uid, module_id=m.id) == (0, 0, 0)
