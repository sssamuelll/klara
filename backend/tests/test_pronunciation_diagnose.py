from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from klara.llm.base import LLMResponse
from klara.models.pronunciation_diagnosis import PronunciationDiagnosis
from klara.pronunciation.schemas import PhonemeScore
from klara.services.pronunciation_diagnose import generate_diagnosis


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


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0
        self.last_messages = None

    async def complete(self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None):
        self.calls += 1
        self.last_messages = messages
        return LLMResponse(content=self.content, model="fake", provider="fake")

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


def _phonemes():
    return [PhonemeScore(phoneme="aʊ", accuracy_score=90.0), PhonemeScore(phoneme="uː", accuracy_score=38.0)]


@pytest.mark.asyncio
async def test_empty_phonemes_skips_llm(db_session):
    llm = FakeLLM('{"tip": "x"}')
    out = await generate_diagnosis(llm, db_session, word="Haus", phonemes=[], target_language="de", native_language="es")
    assert out.tip == "" and out.weakest_phoneme == ""
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_cache_miss_calls_llm_and_inserts_row(db_session):
    llm = FakeLLM('{"tip": "La ú es cerrada: redondea los labios."}')
    out = await generate_diagnosis(llm, db_session, word="Autobus", phonemes=_phonemes(), target_language="de-DE", native_language="es")
    assert out.weakest_phoneme == "uː"
    assert "redondea" in out.tip
    assert llm.calls == 1
    count = (await db_session.execute(select(func.count()).select_from(PronunciationDiagnosis))).scalar()
    assert count == 1
    row = (await db_session.execute(select(PronunciationDiagnosis))).scalar_one()
    assert row.word == "autobus" and row.target_language == "de" and row.native_language == "es"


@pytest.mark.asyncio
async def test_cache_hit_skips_llm_and_bumps_hit_count(db_session):
    first = FakeLLM('{"tip": "tip uno"}')
    await generate_diagnosis(first, db_session, word="Autobus", phonemes=_phonemes(), target_language="de", native_language="es")
    second = FakeLLM('{"tip": "tip dos — should NOT be used"}')
    out = await generate_diagnosis(second, db_session, word="autobus", phonemes=_phonemes(), target_language="de", native_language="es")
    assert out.tip == "tip uno"          # cached value, not the new LLM content
    assert second.calls == 0
    row = (await db_session.execute(select(PronunciationDiagnosis))).scalar_one()
    assert row.hit_count == 2


@pytest.mark.asyncio
async def test_malformed_json_returns_empty_no_row(db_session):
    llm = FakeLLM("not json at all")
    out = await generate_diagnosis(llm, db_session, word="Haus", phonemes=_phonemes(), target_language="de", native_language="es")
    assert out.tip == ""
    count = (await db_session.execute(select(func.count()).select_from(PronunciationDiagnosis))).scalar()
    assert count == 0


@pytest.mark.asyncio
async def test_blank_tip_returns_empty_no_row(db_session):
    llm = FakeLLM('{"tip": "   "}')
    out = await generate_diagnosis(llm, db_session, word="Haus", phonemes=_phonemes(), target_language="de", native_language="es")
    assert out.tip == ""
    count = (await db_session.execute(select(func.count()).select_from(PronunciationDiagnosis))).scalar()
    assert count == 0


class RaisingLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None):
        self.calls += 1
        raise RuntimeError("llm down")

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_llm_failure_returns_empty_no_row(db_session):
    llm = RaisingLLM()
    out = await generate_diagnosis(llm, db_session, word="Haus", phonemes=_phonemes(), target_language="de", native_language="es")
    assert out.tip == ""
    assert llm.calls == 1
    count = (await db_session.execute(select(func.count()).select_from(PronunciationDiagnosis))).scalar()
    assert count == 0
