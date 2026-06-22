"""load_l1_notes: idempotent upsert (edits update), l1 canonicalized to lowercase,
validation rejects empty/over-length. gender_l1_notes is truncated between tests."""

import pytest
from sqlalchemy import select

from klara.curriculum.l1_notes import L1NoteRow, load_l1_notes
from klara.models import GenderL1Note


@pytest.mark.asyncio
async def test_load_l1_notes_inserts(db_session):
    n = await load_l1_notes(
        db_session,
        rows=[
            L1NoteRow(lemma="Auto", l1_language="es", note="nota uno"),
            L1NoteRow(lemma="Tisch", l1_language="es", note="nota dos"),
        ],
    )
    await db_session.commit()
    assert n == 2
    rows = (await db_session.execute(select(GenderL1Note))).scalars().all()
    assert {(r.lemma, r.l1_language) for r in rows} == {("Auto", "es"), ("Tisch", "es")}


@pytest.mark.asyncio
async def test_load_l1_notes_idempotent_and_editable(db_session):
    await load_l1_notes(db_session, rows=[L1NoteRow(lemma="Auto", l1_language="es", note="vieja")])
    await db_session.commit()
    # Re-seed edited prose -> updates in place, no duplicate row.
    await load_l1_notes(db_session, rows=[L1NoteRow(lemma="Auto", l1_language="es", note="nueva")])
    await db_session.commit()
    rows = (await db_session.execute(select(GenderL1Note))).scalars().all()
    assert len(rows) == 1
    assert rows[0].note == "nueva"


@pytest.mark.asyncio
async def test_load_l1_notes_canonicalizes_l1_lowercase(db_session):
    await load_l1_notes(db_session, rows=[L1NoteRow(lemma="Auto", l1_language="ES", note="x")])
    await db_session.commit()
    row = (await db_session.execute(select(GenderL1Note))).scalars().one()
    assert row.l1_language == "es"


@pytest.mark.asyncio
async def test_load_l1_notes_rejects_empty(db_session):
    with pytest.raises(ValueError):
        await load_l1_notes(db_session, rows=[L1NoteRow(lemma="X", l1_language="es", note="   ")])


@pytest.mark.asyncio
async def test_load_l1_notes_rejects_too_long(db_session):
    with pytest.raises(ValueError):
        await load_l1_notes(
            db_session, rows=[L1NoteRow(lemma="X", l1_language="es", note="a" * 401)]
        )
