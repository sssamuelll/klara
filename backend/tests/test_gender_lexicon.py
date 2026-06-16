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
from klara.models.enums import PartOfSpeech


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
