"""Gender oracle (gender_lexicon) + VocabItem.gender_source provenance."""

import uuid

import pytest

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
