# Slice 3 PR-A — gender oracle + provenance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Establish an authoritative German gender oracle (a `gender_lexicon` table seeded from an open dataset, with compound resolution) and make it WIN over the LLM, so `VocabItem.gender` stops being corrupted per-story — the precondition for teaching gender with correction.

**Architecture:** A new `gender_lexicon(lemma, pos, gender)` table is seeded offline from the gambolputty/german-nouns CSV (genus m/f/n → der/die/das). `resolve_gender(db, lemma)` does an exact lookup then a longest-suffix compound fallback (Hausaufgabe→Aufgabe→die), returning None when unknown — never the LLM's guess. `VocabItem` gains a `gender_source` column (oracle|llm|user); `_upsert_vocab_items` consults the oracle before insert and a conditional `on_conflict` (via SQL `CASE`) ensures an `oracle` gender is never overwritten by the LLM. No quiz/frontend changes — that's PR-B.

**Tech Stack:** FastAPI, SQLAlchemy async, Postgres, Alembic, pytest. Data: gambolputty/german-nouns `nouns.csv` (CC-BY-SA 4.0). No new runtime dependency (the CSV is parsed by a one-time load script; the pip package is NOT used at runtime).

**Spec:** `docs/superpowers/specs/2026-06-16-learning-sequence-slice3-gender-correction-design.md` (this is PR-A of 3).

---

## File Structure

**Create:**
- `backend/src/klara/models/gender_lexicon.py` — `GenderLexicon` model.
- `backend/src/klara/curriculum/gender_lex.py` — `GenderRow`, `parse_gender_csv`, `load_gender_lexicon`, `resolve_gender`.
- `backend/src/klara/scripts/load_de_gender.py` — CLI: parse a CSV path → load.
- `backend/alembic/versions/20260616_0010_gender_lexicon_provenance.py` — create table + add column.
- `backend/tests/test_gender_lexicon.py` — model, parse, load, resolve, provenance gate.

**Modify:**
- `backend/src/klara/models/vocab.py` — add `gender_source`.
- `backend/src/klara/models/__init__.py` — export `GenderLexicon`.
- `backend/alembic/env.py` — import `gender_lexicon` (autogenerate hygiene).
- `backend/src/klara/services/story_gen.py` — provenance gate in `_upsert_vocab_items`.
- `backend/tests/conftest.py` — add `gender_lexicon` to the TRUNCATE list.

No frontend changes in PR-A.

---

## Task 1: GenderLexicon model + VocabItem.gender_source + migration

**Files:**
- Create: `backend/src/klara/models/gender_lexicon.py`
- Modify: `backend/src/klara/models/vocab.py`, `backend/src/klara/models/__init__.py`, `backend/alembic/env.py`, `backend/tests/conftest.py`
- Create: `backend/alembic/versions/20260616_0010_gender_lexicon_provenance.py`
- Test: `backend/tests/test_gender_lexicon.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_gender_lexicon.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_gender_lexicon.py::test_gender_lexicon_and_gender_source_roundtrip -v`
Expected: FAIL — `ImportError: cannot import name 'GenderLexicon'`.

- [ ] **Step 3: Create the model**

Create `backend/src/klara/models/gender_lexicon.py`:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base


class GenderLexicon(Base):
    """Authoritative German noun gender, seeded offline from an open dataset
    (gambolputty/german-nouns, CC-BY-SA 4.0). The curriculum's source of truth
    for der/die/das — never written by the LLM."""

    __tablename__ = "gender_lexicon"

    lemma: Mapped[str] = mapped_column(String(120), primary_key=True)
    pos: Mapped[str] = mapped_column(String(16), default="noun", nullable=False)
    gender: Mapped[str] = mapped_column(String(8), nullable=False)  # der | die | das
```

- [ ] **Step 4: Add `gender_source` to VocabItem**

Modify `backend/src/klara/models/vocab.py` — add the column right after `gender` (line 24):

```python
    gender_source: Mapped[str] = mapped_column(
        String(8), server_default="llm", default="llm", nullable=False
    )  # oracle | llm | user
```

(`String` is already imported in `vocab.py`.)

- [ ] **Step 5: Export the model + register for autogenerate**

Modify `backend/src/klara/models/__init__.py` — add to the imports and `__all__`:

```python
from klara.models.gender_lexicon import GenderLexicon
```
Add `"GenderLexicon"` to `__all__`.

Modify `backend/alembic/env.py` — add `gender_lexicon` to the model-import tuple (keep alphabetical: `... gender_lexicon, module, oauth, ...`) so `Base.metadata` registers the new table.

- [ ] **Step 6: Write the migration**

Create `backend/alembic/versions/20260616_0010_gender_lexicon_provenance.py`:

```python
"""gender_lexicon oracle table + vocab_items.gender_source

Revision ID: 20260616_0010
Revises: 20260616_0009
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260616_0010"
down_revision: str | None = "20260616_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gender_lexicon",
        sa.Column("lemma", sa.String(120), primary_key=True),
        sa.Column("pos", sa.String(16), nullable=False, server_default="noun"),
        sa.Column("gender", sa.String(8), nullable=False),
    )
    op.add_column(
        "vocab_items",
        sa.Column("gender_source", sa.String(8), nullable=False, server_default="llm"),
    )


def downgrade() -> None:
    op.drop_column("vocab_items", "gender_source")
    op.drop_table("gender_lexicon")
```

- [ ] **Step 7: Add gender_lexicon to the conftest TRUNCATE list**

Modify `backend/tests/conftest.py` — the TRUNCATE statement. Add `gender_lexicon` (it has no inbound FKs; order doesn't matter, keep it grouped with reference tables):

```python
        await conn.execute(
            text(
                "TRUNCATE invitations, oauth_accounts, reviews, user_cards, "
                "story_views, study_sessions, stories, module_vocab, modules, "
                "gender_lexicon, users RESTART IDENTITY CASCADE"
            )
        )
```

- [ ] **Step 8: Verify migration round-trips**

Run:
```bash
cd backend
uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head
```
Expected: all three succeed.

- [ ] **Step 9: Run the test**

Run: `cd backend && uv run pytest tests/test_gender_lexicon.py -v`
Expected: PASS. Then `uv run pytest -q` (full suite — adding a NOT NULL column with `server_default` to vocab_items is safe for existing rows/inserts; confirm no regression). Then `uv run ruff check src tests` and `uv run ruff format --check src tests`.

- [ ] **Step 10: Commit**

```bash
git add backend/src/klara/models/gender_lexicon.py backend/src/klara/models/vocab.py backend/src/klara/models/__init__.py backend/alembic/env.py backend/alembic/versions/20260616_0010_gender_lexicon_provenance.py backend/tests/conftest.py backend/tests/test_gender_lexicon.py
git commit -m "feat(curriculum): gender_lexicon oracle table + VocabItem.gender_source"
```

---

## Task 2: resolve_gender + load_gender_lexicon + CSV parse

**Files:**
- Create: `backend/src/klara/curriculum/gender_lex.py`
- Test: `backend/tests/test_gender_lexicon.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_gender_lexicon.py`. Add `GenderRow, load_gender_lexicon, parse_gender_csv, resolve_gender` to the top-of-file import block (`from klara.curriculum.gender_lex import ...`), then append:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_gender_lexicon.py -v -k "parse_gender or load_gender or resolve_gender"`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum.gender_lex'`.

- [ ] **Step 3: Implement**

Create `backend/src/klara/curriculum/gender_lex.py`:

```python
"""The German gender oracle: parse the open dataset, load it, and resolve a
lemma's gender (exact, then longest-suffix compound) authoritatively."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import GenderLexicon

# genus single-letter code → German definite article.
_GENUS_TO_ARTICLE = {"m": "der", "f": "die", "n": "das"}
# Compound resolution: only trust a known noun as a compound head if it's at
# least this long, to avoid spurious short-suffix matches (e.g. "-ei").
_MIN_COMPOUND_HEAD = 4


@dataclass(frozen=True, slots=True)
class GenderRow:
    lemma: str
    pos: str
    gender: str  # der | die | das


def _find_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    for name in fieldnames:
        if name.strip().lower() in candidates:
            return name
    return None


def parse_gender_csv(text: str) -> list[GenderRow]:
    """Parse the gambolputty/german-nouns CSV. Reads the `lemma` and `genus`
    columns by name (case-insensitive); maps genus m/f/n → der/die/das. Rows
    with empty/unrecognized genus or empty lemma are skipped. Raises if the
    required columns are absent."""
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    lemma_col = _find_column(fields, {"lemma", "wort", "word"})
    genus_col = _find_column(fields, {"genus", "gender", "artikel", "article"})
    if lemma_col is None or genus_col is None:
        raise ValueError(
            f"CSV must have a lemma and a genus column; got headers: {fields}"
        )
    pos_col = _find_column(fields, {"pos", "wortart"})
    out: list[GenderRow] = []
    for row in reader:
        lemma = (row.get(lemma_col) or "").strip()
        genus = (row.get(genus_col) or "").strip().lower()
        if not lemma:
            continue
        article = _GENUS_TO_ARTICLE.get(genus[:1]) if genus else None
        if article is None:
            continue
        pos = (row.get(pos_col) or "noun").strip().lower() if pos_col else "noun"
        out.append(GenderRow(lemma=lemma, pos=pos or "noun", gender=article))
    return out


async def load_gender_lexicon(db: AsyncSession, *, rows: list[GenderRow]) -> int:
    """Idempotent upsert of the oracle. Returns rows processed."""
    for r in rows:
        stmt = (
            pg_insert(GenderLexicon)
            .values(lemma=r.lemma, pos=r.pos, gender=r.gender)
            .on_conflict_do_update(
                index_elements=["lemma"], set_={"pos": r.pos, "gender": r.gender}
            )
        )
        await db.execute(stmt)
    return len(rows)


async def resolve_gender(db: AsyncSession, lemma: str) -> str | None:
    """Authoritative gender for `lemma`, or None if unknown. Exact match first;
    then the longest known noun that is a suffix of `lemma` (compound head:
    Hausaufgabe → Aufgabe → die). Never guesses."""
    lemma = (lemma or "").strip()
    if not lemma:
        return None
    exact = await db.get(GenderLexicon, lemma)
    if exact is not None:
        return exact.gender
    # Compound: the longest lexicon lemma that is a (case-insensitive) suffix of
    # the input and long enough to be a real head (Haus+aufgabe → Aufgabe).
    # ILIKE handles the lower-cased join in compounds. Bounded scan; only runs
    # on exact misses.
    stmt = (
        select(GenderLexicon.gender)
        .where(
            func.length(GenderLexicon.lemma) >= _MIN_COMPOUND_HEAD,
            func.length(GenderLexicon.lemma) < func.length(lemma),
            literal(lemma).ilike(func.concat("%", GenderLexicon.lemma)),
        )
        .order_by(func.length(GenderLexicon.lemma).desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_gender_lexicon.py -v`
Expected: all pass. Then `uv run ruff check src/klara/curriculum/gender_lex.py` and `uv run ruff format src/klara/curriculum/gender_lex.py tests/test_gender_lexicon.py` (apply format).

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/curriculum/gender_lex.py backend/tests/test_gender_lexicon.py
git commit -m "feat(curriculum): gender oracle — parse CSV, load, resolve (exact + compound)"
```

---

## Task 3: load_de_gender CLI script

**Files:**
- Create: `backend/src/klara/scripts/load_de_gender.py`

- [ ] **Step 1: Implement (mirrors `scripts/load_de_lexical.py`)**

Create `backend/src/klara/scripts/load_de_gender.py`:

```python
"""Load the authoritative German gender oracle from the gambolputty/german-nouns
CSV into the gender_lexicon table.

Usage:
    uv run python -m klara.scripts.load_de_gender <path-to-nouns.csv>

The dataset (https://github.com/gambolputty/german-nouns, CC-BY-SA 4.0) is
acquired separately and attributed in NOTICE; this script does not vendor it.
Idempotent wrapper over curriculum.gender_lex.load_gender_lexicon.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from klara.config import get_settings
from klara.curriculum.gender_lex import load_gender_lexicon, parse_gender_csv
from klara.db import dispose_engine, get_sessionmaker, init_engine


async def _run(path: Path) -> None:
    rows = parse_gender_csv(path.read_text(encoding="utf-8"))
    settings = get_settings()
    init_engine(settings)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            n = await load_gender_lexicon(db, rows=rows)
            await db.commit()
        print(f"Cargadas {n} entradas de género (de).")
    finally:
        await dispose_engine()


def main() -> None:
    if len(sys.argv) != 2:
        print("uso: python -m klara.scripts.load_de_gender <ruta-al-csv>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(_run(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it imports + lints (do NOT run against a DB)**

Run:
```bash
cd backend
uv run python -c "import klara.scripts.load_de_gender"
uv run ruff check src/klara/scripts/load_de_gender.py
uv run ruff format --check src/klara/scripts/load_de_gender.py
```
Expected: import OK, ruff clean.

- [ ] **Step 3: Commit**

```bash
git add backend/src/klara/scripts/load_de_gender.py
git commit -m "feat(curriculum): load_de_gender CLI (CSV → gender_lexicon)"
```

---

## Task 4: Provenance gate in `_upsert_vocab_items`

**Files:**
- Modify: `backend/src/klara/services/story_gen.py`
- Test: `backend/tests/test_gender_lexicon.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_gender_lexicon.py` (add `from klara.curriculum.gender_lex import GenderRow, load_gender_lexicon` is already imported; add `from klara.services.story_gen import _upsert_vocab_items` and `from klara.models.enums import CEFRLevel`):

```python
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
        db_session, [{"lemma": lemma, "pos": "noun", "gender": "die", "translation": "sol"}],
        CEFRLevel.A1, target_language="de", native_language="es",
    )
    await db_session.commit()
    gl = await db_session.get(GenderLexicon, lemma)  # remove from oracle → resolve_gender→None
    await db_session.delete(gl)
    await db_session.commit()
    saved = await _upsert_vocab_items(  # 2nd: resolve→None, source computed 'llm', excluded='der'
        db_session, [{"lemma": lemma, "pos": "noun", "gender": "der", "translation": "sol"}],
        CEFRLevel.A1, target_language="de", native_language="es",
    )
    await db_session.commit()
    assert saved[0].gender == "die"  # CASE kept the oracle value
    assert saved[0].gender_source == "oracle"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_gender_lexicon.py -v -k "oracle_wins or falls_back or not_clobbered"`
Expected: FAIL — gender_source is whatever the old code sets / oracle not consulted.

- [ ] **Step 3: Implement the gate**

Modify `backend/src/klara/services/story_gen.py`.

Add imports — respect ruff isort order (do NOT add stray import lines):
- Merge `case` into the existing sqlalchemy import: change `from sqlalchemy import select` to `from sqlalchemy import case, select` (one line, alphabetical).
- Insert `from klara.curriculum.gender_lex import resolve_gender` in the `klara.curriculum.*` group — alphabetically AFTER `from klara.curriculum.coverage import verify_coverage` and BEFORE `from klara.curriculum.lemmatize import canonical_lemma`.

In `_upsert_vocab_items`, replace the gender computation + the insert/on_conflict block (current lines 116, 121–139) with the oracle-aware version. The loop body becomes:

```python
        pos = _parse_pos(w.get("pos"))
        lemma, inferred_gender = _clean_lemma(raw_lemma, target_language=target_language)
        llm_gender = _parse_gender(w.get("gender"), target_language=target_language) or inferred_gender

        # Oracle wins: if the authoritative lexicon resolves this lemma, use it
        # and mark provenance 'oracle'; otherwise fall back to the LLM's guess.
        oracle_gender = await resolve_gender(db, lemma) if target_language == "de" else None
        if oracle_gender is not None:
            gender, gender_source = oracle_gender, "oracle"
        else:
            gender, gender_source = llm_gender, "llm"

        translation = (w.get("translation") or "").strip() or None
        translations = {native_language: translation} if translation else {}

        stmt = pg_insert(VocabItem).values(
            lemma=lemma,
            language=target_language,
            pos=pos,
            gender=gender,
            gender_source=gender_source,
            plural=w.get("plural") or None,
            translations=translations,
            example_target=w.get("example_target") or None,
            cefr_level=level,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_vocab_lemma_lang_pos",
            set_={
                "translations": VocabItem.translations.op("||")(stmt.excluded.translations),
                "example_target": stmt.excluded.example_target,
                "plural": stmt.excluded.plural,
                # Never let a non-oracle write clobber an existing oracle gender.
                "gender": case(
                    (VocabItem.gender_source == "oracle", VocabItem.gender),
                    else_=stmt.excluded.gender,
                ),
                "gender_source": case(
                    (VocabItem.gender_source == "oracle", VocabItem.gender_source),
                    else_=stmt.excluded.gender_source,
                ),
            },
        ).returning(VocabItem.id)
        result = await db.execute(stmt)
        vocab_id = result.scalar_one()

        item = await db.get(VocabItem, vocab_id)
        if item is not None:
            saved.append(item)
```

Note: `db.get(VocabItem, vocab_id)` may return a session-cached instance with stale `gender`/`gender_source` after the `CASE` update (the UPDATE happens in SQL, not the ORM). Add `await db.refresh(item)` before appending so the test sees the persisted values:

```python
        item = await db.get(VocabItem, vocab_id)
        if item is not None:
            await db.refresh(item)
            saved.append(item)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_gender_lexicon.py -v`
Expected: all pass. Then `uv run pytest -q` (FULL suite — existing story tests must stay green; the gate is a no-op when the oracle is empty, falling back to `llm`, which matches prior behavior except `gender_source` is now set). Then `uv run ruff check src/klara/services/story_gen.py` and `uv run ruff format src/klara/services/story_gen.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/services/story_gen.py backend/tests/test_gender_lexicon.py
git commit -m "feat(stories): oracle wins over LLM for noun gender (provenance gate)"
```

---

## Task 5: Full verification

- [ ] **Step 1: Backend — tests, lint, format**

Run (from `backend/`):
```bash
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
```
Expected: all pass; ruff clean. Run `uv run ruff format src tests` (apply) first if `--check` reports anything, then re-run `--check`.

- [ ] **Step 2: Migration round-trip**

Run (from `backend/`): `uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head`
Expected: success.

- [ ] **Step 3: Commit any fixups** (skip if none).

---

## Notes for the implementer

- **ruff hygiene (every task):** run `uv run ruff check --fix` AND `uv run ruff format` on every file you touch — including `tests/` and `scripts/`. Put new imports in the top import block in alphabetical first-party order; never mid-file (E402). This bit prior PRs.
- **Test isolation:** `gender_lexicon` IS truncated between tests (Task 1, Step 7), so tests can seed specific lemmas freely. `vocab_items` is NOT truncated — keep the existing convention of unique lemmas where it matters.
- **No frontend / no quiz changes in PR-A.** The gender-cloze + `gender_attempt` + the user-facing correction are PR-B.
- **CSV acquisition (deploy-time, not code):** download `nouns.csv` from gambolputty/german-nouns (CC-BY-SA 4.0; add attribution to the repo's NOTICE/about), then run `uv run python -m klara.scripts.load_de_gender <path>` in prod. Until then the oracle is empty and the gate falls back to LLM gender (no regression — gender just isn't authoritative yet).
- **Known v1 limitations (documented, acceptable):** homograph nouns with two genders (der/die See) collapse to one in the lexicon (last write wins on the `lemma` PK); the compound resolver is longest-suffix only (no full morphological decomposition) and **only runs on exact misses** (rare for A1, which is mostly in the 100k lexicon exactly), accepting rare false positives — `_MIN_COMPOUND_HEAD=4` is the floor. Both are fine for A1 and revisited if needed.
- **Verification decisions (settled, intentional — don't "fix" them):**
  - `load_gender_lexicon` does NOT commit internally (the caller commits) — caller-controls-transaction is the chosen contract here, even though the sibling `inventory.load_frequency` commits internally. The CLI and tests commit explicitly.
  - `db.refresh(item)` per noun after the SQL `CASE` update is deliberate (the identity-map instance is stale after an UPDATE-by-SQL); the extra SELECT is negligible against the LLM call on this path.
  - `gender_lexicon.pos` is non-functional metadata — `resolve_gender` matches on lemma only (the table is noun-only).
  - `gender_source` `server_default='llm'` is permanent (consistent with the repo's server-default convention); an unset provenance honestly reads as `llm`.
  - `env.py`: insert `gender_lexicon` into the model-import tuple right after `audio` (the tuple starts at `audio`; it is already non-exhaustive — that's pre-existing, out of scope here).
- **CSV header (verify at deploy):** `parse_gender_csv` resolves the lemma/genus columns by name (tolerant set, case-insensitive) and FAILS FAST listing the real headers if absent. When acquiring `nouns.csv`, confirm its actual `lemma`/`genus` column names match the candidate sets; widen them if needed before running the CLI in prod.
- **PR-B (next plan):** `gender_attempt` table + `is_mastered_gender` + deterministic `gender_cloze` in Finish + tap picker + grading vs oracle + i18n.
