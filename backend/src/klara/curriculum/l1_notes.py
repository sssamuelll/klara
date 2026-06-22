"""Curated L1 gender-transfer notes: idempotent upsert + validation. The only
write path for gender_l1_notes (never the LLM). Hand-authored prose asserting
an ES<->DE gender clash for a German lemma in a learner's native language."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import GenderL1Note

_MAX_NOTE = 400


@dataclass(frozen=True, slots=True)
class L1NoteRow:
    lemma: str
    l1_language: str
    note: str


def _validate(rows: list[L1NoteRow]) -> None:
    for r in rows:
        if not r.note or not r.note.strip():
            raise ValueError(f"empty note for {r.lemma}/{r.l1_language}")
        if len(r.note) > _MAX_NOTE:
            raise ValueError(f"note too long ({len(r.note)}) for {r.lemma}/{r.l1_language}")


async def load_l1_notes(db: AsyncSession, *, rows: list[L1NoteRow]) -> int:
    """Idempotent upsert of curated L1 notes; re-seeding edited prose updates the
    row. Caller commits. Returns rows processed."""
    _validate(rows)
    for r in rows:
        note = r.note.strip()
        stmt = (
            pg_insert(GenderL1Note)
            .values(lemma=r.lemma, l1_language=r.l1_language.lower(), note=note)
            .on_conflict_do_update(index_elements=["lemma", "l1_language"], set_={"note": note})
        )
        await db.execute(stmt)
    return len(rows)
