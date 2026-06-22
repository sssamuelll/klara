# Curated ES→DE gender L1-notes — Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans.

**Goal:** A `gender_l1_notes` table + oracle-gated serve endpoint + a "trampas de género" section in the StoryFinish summary, seeded corpus-complete (~20 A1 ES↔DE clashes).

**Architecture:** Curated, never-LLM (mirrors GenderLexicon). The displayed der/die/das is resolved from the oracle (`VocabItem.gender_source == "oracle"`) at serve time, never stored. Spec: `docs/superpowers/specs/2026-06-22-gender-l1-notes-design.md`.

**Tech:** FastAPI + SQLAlchemy async + Postgres + Alembic; React+TS; 6 locales. ruff (E,F,I,B,UP,RUF).

---

## Task 1: Model + migration + conftest truncate

**Files:** Create `backend/src/klara/models/gender_l1_note.py`; Modify `backend/src/klara/models/__init__.py`; Create `backend/alembic/versions/20260622_0012_gender_l1_notes.py`; Modify `backend/tests/conftest.py`.

- [ ] **Model:**
```python
# backend/src/klara/models/gender_l1_note.py
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base


class GenderL1Note(Base):
    """Hand-curated L1 gender-transfer note: for a German lemma and a learner's
    native language, prose explaining the ES<->DE gender clash. Authoritative,
    never written by the LLM. The DE gender is NOT stored here -- it is resolved
    from the oracle (VocabItem.gender, gender_source='oracle') at serve time."""

    __tablename__ = "gender_l1_notes"

    lemma: Mapped[str] = mapped_column(String(120), primary_key=True)
    l1_language: Mapped[str] = mapped_column(String(8), primary_key=True)
    note: Mapped[str] = mapped_column(String(400), nullable=False)
```
- [ ] **Register** in `models/__init__.py`: import `from klara.models.gender_l1_note import GenderL1Note` and add `"GenderL1Note"` to `__all__`.
- [ ] **Migration** `20260622_0012_gender_l1_notes.py`:
```python
"""gender_l1_notes curated L1 transfer notes

Revision ID: 20260622_0012
Revises: 20260616_0011
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260622_0012"
down_revision: str | None = "20260616_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gender_l1_notes",
        sa.Column("lemma", sa.String(120), primary_key=True),
        sa.Column("l1_language", sa.String(8), primary_key=True),
        sa.Column("note", sa.String(400), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gender_l1_notes")
```
- [ ] **conftest:** add `gender_l1_notes` to the TRUNCATE list (after `gender_lexicon`).
- [ ] **Verify:** `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` (roundtrip clean).

---

## Task 2: Upsert loader + seed script (TDD)

**Files:** Create `backend/src/klara/curriculum/l1_notes.py`; Create `backend/src/klara/scripts/load_de_l1_notes.py`; Test `backend/tests/test_l1_notes.py`.

- [ ] **Loader** `curriculum/l1_notes.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import GenderL1Note


@dataclass(frozen=True, slots=True)
class L1NoteRow:
    lemma: str
    l1_language: str
    note: str


def _validate(rows: list[L1NoteRow]) -> None:
    for r in rows:
        if not r.note or not r.note.strip():
            raise ValueError(f"empty note for {r.lemma}/{r.l1_language}")
        if len(r.note) > 400:
            raise ValueError(f"note too long ({len(r.note)}) for {r.lemma}/{r.l1_language}")


async def load_l1_notes(db: AsyncSession, *, rows: list[L1NoteRow]) -> int:
    """Idempotent upsert of curated L1 notes. Returns rows processed."""
    _validate(rows)
    for r in rows:
        note = r.note.strip()
        stmt = (
            pg_insert(GenderL1Note)
            .values(lemma=r.lemma, l1_language=r.l1_language.lower(), note=note)
            .on_conflict_do_update(
                index_elements=["lemma", "l1_language"], set_={"note": note}
            )
        )
        await db.execute(stmt)
    return len(rows)
```
- [ ] **Seed script** `scripts/load_de_l1_notes.py` (the 20 es seeds inline; mirrors `load_de_gender.py` engine bootstrap; commits in-script):
```python
"""Seed the curated ES->DE gender L1-transfer notes (es).

Usage:
    uv run python -m klara.scripts.load_de_l1_notes

Hand-authored, corpus-complete over the A1 corpus (load_de_modules.py). Idempotent.
"""

from __future__ import annotations

import asyncio

from klara.config import get_settings
from klara.curriculum.l1_notes import L1NoteRow, load_l1_notes
from klara.db import dispose_engine, get_sessionmaker, init_engine

_ES_NOTES: list[tuple[str, str]] = [
    ("Tisch", "En español «la mesa» es femenino, pero en alemán es masculino."),
    ("Stuhl", "En español «la silla» es femenino, pero en alemán es masculino."),
    ("Apfel", "En español «la manzana» es femenino, pero en alemán es masculino."),
    ("Bahnhof", "En español «la estación» es femenino, pero en alemán es masculino."),
    ("Auto", "En español «el coche» es masculino, pero en alemán es neutro."),
    ("Geld", "En español «el dinero» es masculino, pero en alemán es neutro."),
    ("Jahr", "En español «el año» es masculino, pero en alemán es neutro."),
    ("Brot", "En español «el pan» es masculino, pero en alemán es neutro."),
    ("Land", "En español «el país» es masculino, pero en alemán es neutro."),
    ("Haus", "En español «la casa» es femenino, pero en alemán es neutro."),
    ("Bett", "En español «la cama» es femenino, pero en alemán es neutro."),
    ("Fenster", "En español «la ventana» es femenino, pero en alemán es neutro."),
    ("Zimmer", "En español «la habitación» es femenino, pero en alemán es neutro."),
    ("Geschäft", "En español «la tienda» es femenino, pero en alemán es neutro."),
    ("Fahrrad", "En español «la bicicleta» es femenino, pero en alemán es neutro."),
    ("Minute", "En español «el minuto» es masculino, pero en alemán es femenino."),
    ("Sprache", "En español «el idioma» es masculino, pero en alemán es femenino."),
    ("Wohnung", "En español «el piso» es masculino, pero en alemán es femenino."),
    ("Zahl", "En español «el número» es masculino, pero en alemán es femenino."),
    ("Bahn", "En español «el tren» es masculino, pero en alemán es femenino."),
]


async def _run() -> None:
    rows = [L1NoteRow(lemma=lemma, l1_language="es", note=note) for lemma, note in _ES_NOTES]
    settings = get_settings()
    init_engine(settings)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            n = await load_l1_notes(db, rows=rows)
            await db.commit()
        print(f"Cargadas {n} notas de trampa de género (es).")
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
```
- [ ] **Tests** `test_l1_notes.py`: (a) `load_l1_notes` inserts; (b) re-seeding edited prose updates the note (idempotent + editable); (c) `_validate` rejects empty/whitespace and >400. `cd backend && uv run pytest tests/test_l1_notes.py -q`.

---

## Task 3: Schema + endpoint (TDD)

**Files:** Modify `backend/src/klara/schemas/finish.py`; Modify `backend/src/klara/routers/stories.py`; Test `backend/tests/test_l1_notes_endpoint.py`.

- [ ] **Schema** (finish.py):
```python
class GenderL1NoteItem(BaseModel):
    lemma: str
    gender: Literal["der", "die", "das"]
    note: str


class GenderL1NotesOut(BaseModel):
    notes: list[GenderL1NoteItem]
```
- [ ] **Endpoint** (stories.py — add imports: `GenderL1Note` from models, `GenderL1NoteItem, GenderL1NotesOut` from finish, `PartOfSpeech` from enums, ensure `func, select` imported):
```python
@router.get("/{story_id}/gender/l1-notes", response_model=GenderL1NotesOut)
async def get_story_l1_notes(
    story_id: UUID,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
) -> GenderL1NotesOut:
    """Curated ES<->DE gender-trap notes for the story's target words, keyed by
    the story's L1. Display gender is oracle-gated; non-oracle words are dropped."""
    story = await _load_or_404(db, story_id, user.id, locale)
    ids = list(story.target_vocab_item_ids or [])
    if not ids:
        return GenderL1NotesOut(notes=[])
    words = await _load_words(db, ids)
    # eligible[lower(lemma)] = oracle gender; de nouns with an authoritative gender only
    eligible: dict[str, str] = {
        w.lemma.lower(): w.gender
        for w in words
        if w.language == "de"
        and w.pos == PartOfSpeech.NOUN
        and w.gender_source == "oracle"
        and w.gender in ("der", "die", "das")
    }
    if not eligible:
        return GenderL1NotesOut(notes=[])
    l1 = (story.native_language or "").lower()
    rows = (
        await db.execute(
            select(GenderL1Note.lemma, GenderL1Note.note).where(
                GenderL1Note.l1_language == l1,
                func.lower(GenderL1Note.lemma).in_(list(eligible.keys())),
            )
        )
    ).all()
    notes: list[GenderL1NoteItem] = []
    seen: set[str] = set()
    for note_lemma, note in rows:
        key = note_lemma.lower()
        gender = eligible.get(key)
        if gender is None or key in seen:
            continue
        seen.add(key)
        # Display the seed's (capitalized) lemma, not the possibly-drifted VocabItem casing.
        notes.append(GenderL1NoteItem(lemma=note_lemma, gender=gender, note=note))
    return GenderL1NotesOut(notes=notes)
```
- [ ] **Tests** `test_l1_notes_endpoint.py` (seed in-fixture; mirror existing gender endpoint tests): oracle-resolved notes returned for `es`; `gender_source="llm"` word + seed NOT returned; seed `"Auto"` matches VocabItem `"auto"`; empty for non-seeded L1 / no trap words / empty target list; `native_language="ES"` matches `es`; owner 404. `cd backend && uv run pytest tests/test_l1_notes_endpoint.py -q`.

---

## Task 4: Frontend section + i18n

**Files:** Modify `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/components/StoryFinish.tsx`, `frontend/src/locales/{es,en,de,fr,pt,ja}/common.json`.

- [ ] **types.ts:**
```ts
export interface L1GenderNote {
  lemma: string;
  gender: "der" | "die" | "das";
  note: string;
}

export interface L1GenderNotesResponse {
  notes: L1GenderNote[];
}
```
- [ ] **client.ts:** `getStoryL1Notes: (storyId: string) => request<L1GenderNotesResponse>(\`/stories/${storyId}/gender/l1-notes\`)`.
- [ ] **StoryFinish.tsx Summary:** fetch async like the insight fetch (`useEffect` + state, with the existing skeleton idiom if cheap; otherwise plain). Render, only when `notes.length > 0`, a section: localized `title` + `hint`, then one line per note: a bold `«{gender} {lemma}»` followed by `{note}` as plain text. (Read the Summary component's insight-fetch + section markup at execution time and mirror it.)
- [ ] **i18n** — add to `story.finish.summary` in all 6 locales (es source):
```jsonc
// es
"l1Notes": { "title": "Trampas de género", "hint": "El género no coincide entre tu idioma y el alemán." }
// en
"l1Notes": { "title": "Gender traps", "hint": "The gender differs between your language and German." }
// de
"l1Notes": { "title": "Genus-Fallen", "hint": "Das Genus unterscheidet sich zwischen deiner Sprache und dem Deutschen." }
// fr
"l1Notes": { "title": "Pièges de genre", "hint": "Le genre diffère entre ta langue et l'allemand." }
// pt
"l1Notes": { "title": "Armadilhas de género", "hint": "O género muda entre a tua língua e o alemão." }
// ja
"l1Notes": { "title": "性の落とし穴", "hint": "母語とドイツ語で性が異なる語。" }
```
- [ ] **Verify:** `cd frontend && npm run typecheck && npm run i18n:check && npm run build`.

---

## Task 5: Final verify + ship

- [ ] Backend: `cd backend && uv run ruff check --fix src tests && uv run ruff format src tests && uv run pytest -q` (full suite green; migration roundtrip).
- [ ] Frontend gates green.
- [ ] Run `uv run python -m klara.scripts.load_de_l1_notes` against the test DB as a smoke.
- [ ] Adversarial review (workflow), then PR, merge on green (explicit prod-deploy authorization).
