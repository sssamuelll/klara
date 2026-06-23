"""is_gender_eligible / gender_eligible_clause: the single source of truth for
'a der/die/das oracle German NOUN', replacing hand-copied predicates."""

import uuid

import pytest
from sqlalchemy import select

from klara.curriculum.gender_eligibility import gender_eligible_clause, is_gender_eligible
from klara.models import VocabItem
from klara.models.enums import PartOfSpeech


def _vocab(**kw):
    base = dict(
        id=uuid.uuid4(),
        language="de",
        lemma=f"Tisch{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
    )
    base.update(kw)
    return VocabItem(**base)


def test_is_gender_eligible_accepts_der_die_das_oracle_noun():
    assert is_gender_eligible(_vocab(gender="der")) is True
    assert is_gender_eligible(_vocab(gender="die")) is True
    assert is_gender_eligible(_vocab(gender="das")) is True


def test_is_gender_eligible_rejects_non_eligible():
    assert is_gender_eligible(_vocab(gender_source="llm")) is False
    assert is_gender_eligible(_vocab(pos=PartOfSpeech.VERB)) is False
    assert is_gender_eligible(_vocab(language="fr")) is False
    assert is_gender_eligible(_vocab(gender="den")) is False  # non-canonical article
    assert is_gender_eligible(_vocab(gender=None)) is False


@pytest.mark.asyncio
async def test_gender_eligible_clause_filters_in_a_query(db_session):
    keep = _vocab(gender="die")
    drop_llm = _vocab(gender_source="llm")
    drop_verb = _vocab(pos=PartOfSpeech.VERB, gender=None)
    db_session.add_all([keep, drop_llm, drop_verb])
    await db_session.commit()
    ids = (
        (await db_session.execute(select(VocabItem.id).where(*gender_eligible_clause())))
        .scalars()
        .all()
    )
    assert keep.id in ids
    assert drop_llm.id not in ids
    assert drop_verb.id not in ids
