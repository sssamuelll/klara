"""next_target_words: top por frequency_rank, palabras de CONTENIDO, banda
<= user.level, MENOS el known-set. Es el cierre del lazo."""

import uuid

import pytest

from klara.curriculum.selection import next_target_words
from klara.models import User, UserCard, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


async def _user(db, level=CEFRLevel.A2) -> uuid.UUID:
    u = User(
        id=uuid.uuid4(),
        email=f"s-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="S",
        level=level,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u.id


async def _vocab(db, *, lemma, rank, cefr, language, pos=PartOfSpeech.NOUN) -> uuid.UUID:
    v = VocabItem(
        id=uuid.uuid4(),
        language=language,
        lemma=lemma,
        pos=pos,
        frequency_rank=rank,
        cefr_level=cefr,
    )
    db.add(v)
    await db.flush()
    return v.id


# AISLAMIENTO: vocab_items NO se trunca entre tests (conftest.py) y next_target_words
# consulta el pool GLOBAL por idioma — usa un código de idioma único por test para
# que lemas de otros tests no se filtren y rompan las aserciones de igualdad exacta.
@pytest.mark.asyncio
async def test_selects_top_frequency_content_words_minus_known(db_session):
    lang = "selt1"
    uid = await _user(db_session, CEFRLevel.A2)
    # función de altísima frecuencia: NO debe seleccionarse (no es contenido)
    await _vocab(
        db_session,
        lemma="und",
        rank=1,
        cefr=CEFRLevel.A1,
        language=lang,
        pos=PartOfSpeech.CONJUNCTION,
    )
    # contenido frecuente, no sabido → debe salir primero
    await _vocab(db_session, lemma="Haus", rank=10, cefr=CEFRLevel.A1, language=lang)
    # contenido más raro → después
    await _vocab(db_session, lemma="Brücke", rank=900, cefr=CEFRLevel.A2, language=lang)
    # fuera de banda (B2 > A2) → excluido
    await _vocab(db_session, lemma="Verfassung", rank=20, cefr=CEFRLevel.B2, language=lang)
    # ya sabido → excluido
    known_vid = await _vocab(db_session, lemma="Tisch", rank=5, cefr=CEFRLevel.A1, language=lang)
    db_session.add(UserCard(id=uuid.uuid4(), user_id=uid, vocab_item_id=known_vid))
    await db_session.commit()

    words = await next_target_words(db_session, user_id=uid, language=lang, level=CEFRLevel.A2, n=5)
    lemmas = [w.lemma for w in words]
    assert lemmas == ["Haus", "Brücke"]  # orden por rank, sin und/Verfassung/Tisch


@pytest.mark.asyncio
async def test_respects_limit_n(db_session):
    lang = "selt2"  # código distinto al otro test → pools aislados
    uid = await _user(db_session, CEFRLevel.B1)
    for i in range(8):
        await _vocab(db_session, lemma=f"Wort{i}", rank=i + 1, cefr=CEFRLevel.A1, language=lang)
    await db_session.commit()
    words = await next_target_words(db_session, user_id=uid, language=lang, level=CEFRLevel.B1, n=3)
    assert len(words) == 3
    assert [w.frequency_rank for w in words] == [1, 2, 3]
