"""known_set deriva los lemas que el usuario ya tiene en SRS (UserCard),
canonicalizados, restringido al idioma. Es el sustraendo de la selección."""

import uuid

import pytest

from klara.curriculum.competence import known_set
from klara.models import User, UserCard, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


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
