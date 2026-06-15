"""load_frequency upsertea VocabItem desde una lista curada: puebla frequency_rank
y SOBREESCRIBE cefr_level (el inferido por LLM es ruido). Idempotente."""

import uuid

import pytest
from sqlalchemy import select

from klara.curriculum.inventory import FrequencyRow, load_frequency, parse_frequency_tsv
from klara.models import VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


def test_parse_tsv_rows():
    text = "lemma\tpos\tcefr\trank\nHaus\tnoun\tA1\t10\nlaufen\tverb\tA1\t12\n"
    rows = parse_frequency_tsv(text)
    assert rows == [
        FrequencyRow(
            lemma="Haus", pos=PartOfSpeech.NOUN, cefr_level=CEFRLevel.A1, frequency_rank=10
        ),
        FrequencyRow(
            lemma="laufen", pos=PartOfSpeech.VERB, cefr_level=CEFRLevel.A1, frequency_rank=12
        ),
    ]


@pytest.mark.asyncio
async def test_load_populates_rank_and_overwrites_cefr_idempotently(db_session):
    lang = "invt1"  # idioma de prueba aislado (vocab_items NO se trunca entre tests)
    # pre-existente en CASO NATURAL con cefr ruidoso y rank NULL. load almacena el
    # lema tal cual ("Haus", sin minusculizar), así que el on_conflict por
    # uq_vocab_lemma_lang_pos casa "Haus"=="Haus" y ACTUALIZA (no duplica).
    pre = VocabItem(
        id=uuid.uuid4(),
        language=lang,
        lemma="Haus",
        pos=PartOfSpeech.NOUN,
        cefr_level=CEFRLevel.B2,
        frequency_rank=None,
    )
    db_session.add(pre)
    await db_session.commit()

    rows = [
        FrequencyRow(
            lemma="Haus", pos=PartOfSpeech.NOUN, cefr_level=CEFRLevel.A1, frequency_rank=10
        )
    ]
    n1 = await load_frequency(db_session, language=lang, rows=rows)
    n2 = await load_frequency(db_session, language=lang, rows=rows)  # idempotente

    items = (
        (
            await db_session.execute(
                select(VocabItem).where(VocabItem.language == lang, VocabItem.lemma == "Haus")
            )
        )
        .scalars()
        .all()
    )
    assert len(items) == 1  # no duplica
    assert items[0].frequency_rank == 10  # rank poblado
    assert items[0].cefr_level == CEFRLevel.A1  # cefr sobrescrito (era B2)
    assert n1 == 1 and n2 == 1
