"""known_set deriva los lemas que el usuario ya tiene en SRS (UserCard),
canonicalizados, restringido al idioma. Es el sustraendo de la selección."""

import uuid

import pytest

from klara.curriculum.competence import (
    MASTERY_INTERVAL_DAYS,
    is_mastered_lexical,
    known_set,
    module_progress,
)
from klara.models import Module, User, UserCard, VocabItem
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
