from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from klara.models.pronunciation_diagnosis import PronunciationDiagnosis


@pytest.mark.asyncio
async def test_insert_and_read_back(db_session):
    db_session.add(
        PronunciationDiagnosis(
            native_language="es",
            target_language="de",
            word="autobus",
            weakest_phoneme="uː",
            phoneme_score=38.0,
            tip="La ú es cerrada: redondea los labios.",
        )
    )
    await db_session.commit()
    row = (
        await db_session.execute(
            select(PronunciationDiagnosis).where(PronunciationDiagnosis.word == "autobus")
        )
    ).scalar_one()
    assert row.hit_count == 1
    assert row.weakest_phoneme == "uː"


@pytest.mark.asyncio
async def test_unique_key_blocks_duplicates(db_session):
    for _ in range(2):
        db_session.add(
            PronunciationDiagnosis(
                native_language="es", target_language="de", word="haus",
                weakest_phoneme="aʊ", phoneme_score=40.0, tip="x",
            )
        )
    with pytest.raises(IntegrityError):
        await db_session.commit()
