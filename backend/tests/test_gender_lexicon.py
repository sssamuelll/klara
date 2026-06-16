"""Gender oracle (gender_lexicon) + VocabItem.gender_source provenance."""

import uuid

import pytest

from klara.curriculum.gender_lex import (
    GenderRow,
    load_gender_lexicon,
    parse_gender_csv,
    resolve_gender,
)
from klara.models import GenderLexicon, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech
from klara.services.story_gen import _upsert_vocab_items


@pytest.mark.asyncio
async def test_gender_lexicon_and_gender_source_roundtrip(db_session):
    db_session.add(GenderLexicon(lemma="Tisch", pos="noun", gender="der"))
    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Tisch",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
    )
    db_session.add(v)
    await db_session.commit()

    gl = await db_session.get(GenderLexicon, "Tisch")
    assert gl is not None and gl.gender == "der"
    reloaded = await db_session.get(VocabItem, v.id)
    assert reloaded.gender_source == "oracle"


def test_parse_gender_csv_maps_genus_to_article():
    csv_text = "lemma,pos,genus\nTisch,Substantiv,m\nMilch,Substantiv,f\nWasser,Substantiv,n\n"
    rows = parse_gender_csv(csv_text)
    by_lemma = {r.lemma: r.gender for r in rows}
    assert by_lemma == {"Tisch": "der", "Milch": "die", "Wasser": "das"}


def test_parse_gender_csv_skips_unknown_genus():
    csv_text = "lemma,pos,genus\nDing,Substantiv,n\nSkip,Substantiv,\nWeird,Substantiv,x\n"
    rows = parse_gender_csv(csv_text)
    assert {r.lemma for r in rows} == {"Ding"}  # empty + unrecognized genus dropped


def test_parse_gender_csv_accepts_article_valued_column():
    # An "artikel" column holding der/die/das resolves (no silent zero-row drop).
    rows = parse_gender_csv("lemma,artikel\nTisch,der\nMilch,die\n")
    assert {r.lemma: r.gender for r in rows} == {"Tisch": "der", "Milch": "die"}


def test_parse_gender_csv_raises_on_missing_columns():
    # Headers that resolve to neither a lemma nor a genus column.
    with pytest.raises(ValueError, match="lemma"):
        parse_gender_csv("foo,bar\nTisch,der\n")


@pytest.mark.asyncio
async def test_load_gender_lexicon_is_idempotent(db_session):
    rows = [
        GenderRow(lemma="Haus", pos="noun", gender="das"),
        GenderRow(lemma="Katze", pos="noun", gender="die"),
    ]
    n1 = await load_gender_lexicon(db_session, rows=rows)
    await db_session.commit()
    n2 = await load_gender_lexicon(db_session, rows=rows)
    await db_session.commit()
    assert n1 == 2 and n2 == 2
    gl = await db_session.get(GenderLexicon, "Haus")
    assert gl.gender == "das"


@pytest.mark.asyncio
async def test_resolve_gender_exact_and_compound(db_session):
    await load_gender_lexicon(
        db_session,
        rows=[
            GenderRow(lemma="Aufgabe", pos="noun", gender="die"),
            GenderRow(lemma="Tisch", pos="noun", gender="der"),
        ],
    )
    await db_session.commit()
    assert await resolve_gender(db_session, "Tisch") == "der"  # exact
    assert await resolve_gender(db_session, "Hausaufgabe") == "die"  # compound → Aufgabe
    assert await resolve_gender(db_session, "Quux") is None  # unknown → None, never a guess


@pytest.mark.asyncio
async def test_upsert_oracle_wins_over_llm_gender(db_session):
    # Each test uses a UNIQUE (uuid-suffixed) lemma because vocab_items is NOT
    # truncated between tests — avoids cross-test collisions on the shared table.
    lemma = f"Mond{uuid.uuid4().hex[:6]}"  # oracle says masculine (der); ES "la luna" trap
    await load_gender_lexicon(db_session, rows=[GenderRow(lemma=lemma, pos="noun", gender="der")])
    await db_session.commit()
    saved = await _upsert_vocab_items(
        db_session,
        [{"lemma": lemma, "pos": "noun", "gender": "die", "translation": "luna"}],  # LLM wrong
        CEFRLevel.A1,
        target_language="de",
        native_language="es",
    )
    await db_session.commit()
    assert saved[0].gender == "der"  # oracle wins
    assert saved[0].gender_source == "oracle"


@pytest.mark.asyncio
async def test_upsert_falls_back_to_llm_when_oracle_unknown(db_session):
    lemma = f"Quux{uuid.uuid4().hex[:6]}"  # not in the oracle
    saved = await _upsert_vocab_items(
        db_session,
        [{"lemma": lemma, "pos": "noun", "gender": "das", "translation": "x"}],
        CEFRLevel.A1,
        target_language="de",
        native_language="es",
    )
    await db_session.commit()
    assert saved[0].gender == "das"
    assert saved[0].gender_source == "llm"


@pytest.mark.asyncio
async def test_upsert_case_gate_protects_existing_oracle_gender(db_session):
    """The CASE gate ALONE must protect a stored oracle gender. Seed the oracle,
    land it, then REMOVE it from the oracle so resolve_gender returns None — a
    later (wrong) LLM write must still NOT clobber the stored oracle gender. This
    exercises the on_conflict CASE in isolation (without it, the gender would
    flip to the LLM's value)."""
    lemma = f"Sonne{uuid.uuid4().hex[:6]}"
    await load_gender_lexicon(db_session, rows=[GenderRow(lemma=lemma, pos="noun", gender="die")])
    await db_session.commit()
    await _upsert_vocab_items(  # 1st: oracle resolves → gender='die', source='oracle'
        db_session,
        [{"lemma": lemma, "pos": "noun", "gender": "die", "translation": "sol"}],
        CEFRLevel.A1,
        target_language="de",
        native_language="es",
    )
    await db_session.commit()
    gl = await db_session.get(GenderLexicon, lemma)  # remove from oracle → resolve_gender→None
    await db_session.delete(gl)
    await db_session.commit()
    saved = await _upsert_vocab_items(  # 2nd: resolve→None, source computed 'llm', excluded='der'
        db_session,
        [{"lemma": lemma, "pos": "noun", "gender": "der", "translation": "sol"}],
        CEFRLevel.A1,
        target_language="de",
        native_language="es",
    )
    await db_session.commit()
    assert saved[0].gender == "die"  # CASE kept the oracle value
    assert saved[0].gender_source == "oracle"
