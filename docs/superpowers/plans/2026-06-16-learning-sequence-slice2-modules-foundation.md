# Curriculum Foundation (Modules) — PR-A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a `Module` curriculum entity (objectives, not a story container), drive story generation from the user's active module, auto-enroll the module's vocab into the SRS as it appears in stories, and surface a minimal "current module" progress panel.

**Architecture:** A `Module` is a predicate (CEFR can-dos + a curated vocab microlist + grammatical focus + mastery threshold). `create_story` reads the user's active module, feeds its vocab as `target_lemmas` (the existing R1 injection path), injects a can-do/focus objective block into the prompt, and — after coverage — **auto-enrolls** the covered module words as SRS cards. Reading thus produces SRS state; a later PR-B reads that state for the advancement gate. Two honest signals: *encountered* (a card exists — moves with reading, monotonic, drives the panel) and *mastered* (`REVIEWING` + interval ≥ 21d — drives PR-B's gate). The frequency TSV is NOT required: the module supplies its own vocab.

**Tech Stack:** FastAPI, SQLAlchemy async, Postgres, Alembic, Pydantic v2, pytest/pytest-asyncio; React + Vite + TypeScript, react-i18next (6 locales).

**Out of scope (PR-B):** the advancement gate (`submit_review` wiring + forward-only pointer advance), authoring the full ~8-module A1 sequence, any gamification/mastery map. PR-A seeds **one** module ("En el café") to prove the loop.

**Spec:** `docs/superpowers/specs/2026-06-16-learning-sequence-slice2-modules-foundation-design.md`

---

## File Structure

**Backend (create):**
- `backend/src/klara/models/module.py` — `Module` model + `module_vocab` association table.
- `backend/src/klara/curriculum/modules.py` — active-module read/init, target lemmas, vocab ids, card enrollment, seed loader.
- `backend/src/klara/schemas/module.py` — `ModuleCurrentOut`.
- `backend/src/klara/routers/modules.py` — `GET /modules/current`.
- `backend/src/klara/scripts/load_de_modules.py` — seed one A1 module.
- `backend/alembic/versions/20260616_0009_modules.py` — schema migration.
- `backend/tests/test_modules.py` — module model, services, endpoint, generation-rewire, seed.

**Backend (modify):**
- `backend/src/klara/models/__init__.py` — export `Module`.
- `backend/src/klara/models/user.py` — add `current_module_id`.
- `backend/src/klara/curriculum/competence.py` — add `is_mastered_lexical`, `module_progress`.
- `backend/src/klara/llm/prompts.py` — `build_story_user_prompt` gains `module_objective`.
- `backend/src/klara/services/story_gen.py` — `generate_story` gains `module_objective`, threads to prompt.
- `backend/src/klara/routers/stories.py` — `create_story` drives generation from the active module + auto-enroll.
- `backend/src/klara/main.py` — register `modules` router.
- `backend/tests/conftest.py` — add `modules, module_vocab` to the TRUNCATE list.
- `backend/tests/test_curriculum_competence.py` — tests for the new competence functions.
- `backend/tests/test_story_prompt.py` — test for the objective block.

**Frontend (modify):**
- `frontend/src/api/types.ts` — `ModuleCurrent` type.
- `frontend/src/api/client.ts` — `api.currentModule()`.
- `frontend/src/routes/Home.tsx` — module panel + empty state.
- `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` — `home.module` keys.

---

## Task 1: Module model + migration + User.current_module_id

**Files:**
- Create: `backend/src/klara/models/module.py`
- Modify: `backend/src/klara/models/__init__.py`, `backend/src/klara/models/user.py`
- Create: `backend/alembic/versions/20260616_0009_modules.py`
- Modify: `backend/tests/conftest.py:65-68` (TRUNCATE list)
- Test: `backend/tests/test_modules.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_modules.py`:

```python
"""Curriculum Module foundation: model, services, endpoint, generation rewire, seed."""

import uuid

import pytest

from klara.models import Module, User, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


async def _user(db, level=CEFRLevel.A1) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"m-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="M",
        level=level,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def _vocab(db, *, lemma, language, pos=PartOfSpeech.NOUN) -> VocabItem:
    v = VocabItem(id=uuid.uuid4(), language=language, lemma=lemma, pos=pos)
    db.add(v)
    await db.flush()
    return v


async def _module(db, *, language, order, title, vocab, can_dos=None, focus=None) -> Module:
    m = Module(
        id=uuid.uuid4(),
        language=language,
        cefr_level=CEFRLevel.A1,
        sequence_order=order,
        title=title,
        can_dos=can_dos or ["puedo pedir algo en un café"],
        grammatical_focus=focus or ["género de sustantivos de comida"],
    )
    m.vocab_items = vocab
    db.add(m)
    await db.flush()
    return m


@pytest.mark.asyncio
async def test_module_roundtrips_with_vocab_and_user_pointer(db_session):
    v1 = await _vocab(db_session, lemma="Kaffee", language="modt1")
    v2 = await _vocab(db_session, lemma="Tasse", language="modt1")
    m = await _module(db_session, language="modt1", order=1, title="En el café", vocab=[v1, v2])
    u = await _user(db_session)
    u.current_module_id = m.id
    await db_session.commit()

    reloaded = await db_session.get(Module, m.id)
    assert reloaded.title == "En el café"
    assert reloaded.mastery_threshold == 0.85
    assert {v.lemma for v in reloaded.vocab_items} == {"Kaffee", "Tasse"}
    reloaded_user = await db_session.get(User, u.id)
    assert reloaded_user.current_module_id == m.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_modules.py::test_module_roundtrips_with_vocab_and_user_pointer -v`
Expected: FAIL — `ImportError: cannot import name 'Module' from 'klara.models'`

- [ ] **Step 3: Create the model**

Create `backend/src/klara/models/module.py`:

```python
from sqlalchemy import Column, Float, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from klara.models.base import Base, created_ts, pg_enum
from klara.models.enums import CEFRLevel
from klara.models.vocab import VocabItem

# Association: a module's curated vocab microlist. Cascade so dropping a module
# (or a vocab item) cleans its links without orphaning rows.
module_vocab = Table(
    "module_vocab",
    Base.metadata,
    Column(
        "module_id",
        PGUUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "vocab_item_id",
        PGUUID(as_uuid=True),
        ForeignKey("vocab_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Module(Base):
    """A curriculum unit defined by INTENSION (objectives), never a container of
    stories. Content is conditioned by the module and verified against it; the
    module never references a Story."""

    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("language", "sequence_order", name="uq_module_lang_seq"),)

    id: Mapped[uuid_pk]
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    cefr_level: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, name="cefr_level", create_type=False), nullable=False
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    can_dos: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    grammatical_focus: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    mastery_threshold: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    created_at: Mapped[created_ts]

    vocab_items: Mapped[list[VocabItem]] = relationship(secondary=module_vocab, lazy="selectin")
```

Add the missing import at the top (the `uuid_pk` annotation): change the first import line to also import `uuid_pk`:

```python
from klara.models.base import Base, created_ts, pg_enum, uuid_pk
```

- [ ] **Step 4: Export the model**

Modify `backend/src/klara/models/__init__.py` — add `Module` (and `module_vocab`) to the imports and `__all__`. Find the existing model imports and add:

```python
from klara.models.module import Module, module_vocab
```

Add `"Module"` and `"module_vocab"` to the `__all__` list (match the existing style — alphabetical or grouped as the file does).

- [ ] **Step 5: Add the user pointer**

Modify `backend/src/klara/models/user.py` — add the column after `learning_context` (line 36). Add to the imports at top: `from uuid import UUID` is already implied by mapped types; add the FK column:

```python
    current_module_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("modules.id", ondelete="SET NULL"),
        nullable=True,
    )
```

Add the needed imports to `user.py`'s import block:

```python
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
```

(Merge with the existing `from sqlalchemy import String, Text` line — replace it with the line above. `UUID` from `uuid` is new.)

- [ ] **Step 6: Write the migration**

Create `backend/alembic/versions/20260616_0009_modules.py`:

```python
"""modules + module_vocab + users.current_module_id

Revision ID: 20260616_0009
Revises: 20260520_0008
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260616_0009"
down_revision: str | None = "20260520_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reference the EXISTING cefr_level enum — create_type=False so the migration
# never tries to CREATE TYPE (it already exists from the initial migration).
cefr_level = sa.Enum(
    "A0", "A1", "A2", "B1", "B2", "C1", name="cefr_level", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "modules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("cefr_level", cefr_level, nullable=False),
        sa.Column("sequence_order", sa.Integer, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("can_dos", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "grammatical_focus", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column("mastery_threshold", sa.Float, nullable=False, server_default=sa.text("0.85")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("language", "sequence_order", name="uq_module_lang_seq"),
    )
    op.create_table(
        "module_vocab",
        sa.Column(
            "module_id",
            UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "vocab_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("vocab_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "current_module_id",
            UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Reverse dependency order: drop the FK column on users first, then the
    # association, then modules. Do NOT drop the shared cefr_level enum.
    op.drop_column("users", "current_module_id")
    op.drop_table("module_vocab")
    op.drop_table("modules")
```

- [ ] **Step 7: Add the test tables to conftest TRUNCATE**

Modify `backend/tests/conftest.py:64-68` — the TRUNCATE statement. Add `modules, module_vocab` (before `users`, CASCADE handles the FK):

```python
        await conn.execute(
            text(
                "TRUNCATE invitations, oauth_accounts, reviews, user_cards, "
                "story_views, study_sessions, stories, module_vocab, modules, users "
                "RESTART IDENTITY CASCADE"
            )
        )
```

- [ ] **Step 8: Verify the migration round-trips locally**

Run:
```bash
cd backend
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```
Expected: all three succeed with no error (this is exactly what the CI `migration roundtrip` job runs).

- [ ] **Step 9: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/test_modules.py::test_module_roundtrips_with_vocab_and_user_pointer -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add backend/src/klara/models/module.py backend/src/klara/models/__init__.py backend/src/klara/models/user.py backend/alembic/versions/20260616_0009_modules.py backend/tests/conftest.py backend/tests/test_modules.py
git commit -m "feat(curriculum): Module entity + module_vocab + user.current_module_id"
```

---

## Task 2: Competence — is_mastered_lexical + module_progress

**Files:**
- Modify: `backend/src/klara/curriculum/competence.py`
- Test: `backend/tests/test_curriculum_competence.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_curriculum_competence.py`:

```python
import uuid

import pytest

from klara.curriculum.competence import (
    MASTERY_INTERVAL_DAYS,
    is_mastered_lexical,
    module_progress,
)
from klara.models import Module, UserCard, VocabItem
from klara.models.enums import CardState, CEFRLevel, PartOfSpeech


def test_is_mastered_lexical_thresholds():
    reviewing_mature = UserCard(
        id=uuid.uuid4(), user_id=uuid.uuid4(), vocab_item_id=uuid.uuid4(),
        state=CardState.REVIEWING, interval_days=MASTERY_INTERVAL_DAYS,
    )
    reviewing_young = UserCard(
        id=uuid.uuid4(), user_id=uuid.uuid4(), vocab_item_id=uuid.uuid4(),
        state=CardState.REVIEWING, interval_days=5.0,
    )
    learning = UserCard(
        id=uuid.uuid4(), user_id=uuid.uuid4(), vocab_item_id=uuid.uuid4(),
        state=CardState.LEARNING, interval_days=99.0,
    )
    assert is_mastered_lexical(reviewing_mature) is True
    assert is_mastered_lexical(reviewing_young) is False
    assert is_mastered_lexical(learning) is False


@pytest.mark.asyncio
async def test_module_progress_counts_encountered_and_mastered(db_session):
    from klara.models import User

    u = User(
        id=uuid.uuid4(), email=f"mp-{uuid.uuid4().hex[:6]}@k.app", hashed_password="x",
        is_active=True, is_verified=True, is_superuser=False, display_name="MP",
        level=CEFRLevel.A1, native_language="es", target_language="de",
    )
    db_session.add(u)
    vs = []
    for lemma in ("Kaffee", "Tasse", "Milch"):
        v = VocabItem(id=uuid.uuid4(), language="modt2", lemma=lemma, pos=PartOfSpeech.NOUN)
        db_session.add(v)
        vs.append(v)
    await db_session.flush()
    m = Module(
        id=uuid.uuid4(), language="modt2", cefr_level=CEFRLevel.A1, sequence_order=1,
        title="café", can_dos=["x"], grammatical_focus=["y"],
    )
    m.vocab_items = vs
    db_session.add(m)
    await db_session.flush()
    # Kaffee: mastered (REVIEWING, interval>=21). Tasse: encountered only (NEW). Milch: no card.
    db_session.add(UserCard(
        id=uuid.uuid4(), user_id=u.id, vocab_item_id=vs[0].id,
        state=CardState.REVIEWING, interval_days=30.0,
    ))
    db_session.add(UserCard(
        id=uuid.uuid4(), user_id=u.id, vocab_item_id=vs[1].id, state=CardState.NEW,
    ))
    await db_session.commit()

    encountered, mastered, total = await module_progress(
        db_session, user_id=u.id, module_id=m.id
    )
    assert (encountered, mastered, total) == (2, 1, 3)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -v -k "mastered or module_progress"`
Expected: FAIL — `ImportError: cannot import name 'is_mastered_lexical'`

- [ ] **Step 3: Implement**

Append to `backend/src/klara/curriculum/competence.py`:

Add to the existing import block (do not duplicate `select`/`UserCard`): add `and_, func` to the `from sqlalchemy import ...` line, add `module_vocab` to the `from klara.models import ...` line, and add `from klara.models.enums import CardState`.

```python
# A lexical card is "mastered" once it's in long-term review with a stable
# interval. The advancement gate (PR-B) reads this; the visible panel reads the
# monotonic "encountered" signal instead (PR-A).
MASTERY_INTERVAL_DAYS = 21.0


def is_mastered_lexical(card: UserCard) -> bool:
    """Lexical-axis mastery predicate. Gender (R3) will define its own."""
    return card.state == CardState.REVIEWING and card.interval_days >= MASTERY_INTERVAL_DAYS


async def module_progress(
    db: AsyncSession, *, user_id: UUID, module_id: UUID
) -> tuple[int, int, int]:
    """(encountered, mastered, total) for the module's vocab, in two aggregate
    queries (no N+1). `encountered` = the user has a card; `mastered` =
    is_mastered_lexical. `total` = size of the module's vocab microlist."""
    total = (
        await db.execute(
            select(func.count())
            .select_from(module_vocab)
            .where(module_vocab.c.module_id == module_id)
        )
    ).scalar_one()
    enc_q = (
        select(
            func.count(UserCard.id),
            func.count(UserCard.id).filter(
                and_(
                    UserCard.state == CardState.REVIEWING,
                    UserCard.interval_days >= MASTERY_INTERVAL_DAYS,
                )
            ),
        )
        .select_from(module_vocab)
        .join(
            UserCard,
            and_(
                UserCard.vocab_item_id == module_vocab.c.vocab_item_id,
                UserCard.user_id == user_id,
            ),
        )
        .where(module_vocab.c.module_id == module_id)
    )
    encountered, mastered = (await db.execute(enc_q)).one()
    return int(encountered), int(mastered), int(total)
```

Note: `competence.py` already imports `select`, `AsyncSession`, `UUID`, and `UserCard` (Task uses them). Add the new imports (`and_`, `func`, `Module`/`module_vocab`, `CardState`) to the existing import block; do not duplicate `select`.

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -v`
Expected: PASS (existing known_set tests + the two new ones)

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/curriculum/competence.py backend/tests/test_curriculum_competence.py
git commit -m "feat(curriculum): is_mastered_lexical + module_progress (two-signal, single-query)"
```

---

## Task 3: curriculum/modules.py — active module, target lemmas, enrollment

**Files:**
- Create: `backend/src/klara/curriculum/modules.py`
- Test: `backend/tests/test_modules.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_modules.py`:

```python
from klara.curriculum.modules import (
    enroll_cards,
    ensure_active_module,
    module_target_lemmas,
    module_vocab_ids,
    read_active_module,
)
from klara.models import UserCard


@pytest.mark.asyncio
async def test_ensure_active_module_inits_pointer_when_null(db_session):
    v = await _vocab(db_session, lemma="Brot", language="modt3")
    m = await _module(db_session, language="modt3", order=1, title="café", vocab=[v])
    u = await _user(db_session)  # target_language="de"
    u.target_language = "modt3"
    await db_session.flush()

    assert u.current_module_id is None
    active = await ensure_active_module(db_session, u)
    assert active is not None and active.id == m.id
    assert u.current_module_id == m.id  # persisted on the user
    # Idempotent: second call returns the same module, doesn't move the pointer.
    again = await ensure_active_module(db_session, u)
    assert again.id == m.id


@pytest.mark.asyncio
async def test_read_active_module_does_not_init(db_session):
    u = await _user(db_session)
    assert await read_active_module(db_session, u) is None
    assert u.current_module_id is None  # read path never writes


@pytest.mark.asyncio
async def test_module_target_lemmas_and_vocab_ids(db_session):
    v1 = await _vocab(db_session, lemma="Wasser", language="modt4")
    v2 = await _vocab(db_session, lemma="Saft", language="modt4")
    m = await _module(db_session, language="modt4", order=1, title="café", vocab=[v1, v2])
    lemmas = await module_target_lemmas(db_session, m)
    assert set(lemmas) == {"Wasser", "Saft"}
    ids = await module_vocab_ids(db_session, m)
    assert ids == {v1.id, v2.id}


@pytest.mark.asyncio
async def test_enroll_cards_is_idempotent(db_session):
    v = await _vocab(db_session, lemma="Zucker", language="modt5")
    u = await _user(db_session)
    await enroll_cards(db_session, user_id=u.id, vocab_item_ids=[v.id])
    await enroll_cards(db_session, user_id=u.id, vocab_item_ids=[v.id])  # again
    await db_session.commit()
    from sqlalchemy import func, select
    n = (
        await db_session.execute(
            select(func.count()).select_from(UserCard).where(
                UserCard.user_id == u.id, UserCard.vocab_item_id == v.id
            )
        )
    ).scalar_one()
    assert n == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "ensure_active or read_active or target_lemmas or enroll_cards"`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum.modules'`

- [ ] **Step 3: Implement**

Create `backend/src/klara/curriculum/modules.py`:

```python
"""Active-module helpers: the read/write of the user's curriculum position, the
module's target lemmas (fed to generation), and auto-enrollment of module vocab
into the SRS (the "heat source" — reading produces SRS state)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import Module, User, UserCard, VocabItem, module_vocab


async def read_active_module(db: AsyncSession, user: User) -> Module | None:
    """Read-only: the user's active module, or None. Never writes (used by GET)."""
    if user.current_module_id is None:
        return None
    return await db.get(Module, user.current_module_id)


async def ensure_active_module(db: AsyncSession, user: User) -> Module | None:
    """Write path: if the user has no active module and modules exist for their
    target language, set it to the lowest sequence_order and persist. The single
    canonical initialization point (called from create_story)."""
    if user.current_module_id is not None:
        return await db.get(Module, user.current_module_id)
    stmt = (
        select(Module)
        .where(Module.language == user.target_language)
        .order_by(Module.sequence_order.asc())
        .limit(1)
    )
    first = (await db.execute(stmt)).scalar_one_or_none()
    if first is None:
        return None
    user.current_module_id = first.id
    await db.flush()
    return first


async def module_target_lemmas(db: AsyncSession, module: Module) -> list[str]:
    stmt = (
        select(VocabItem.lemma)
        .join(module_vocab, module_vocab.c.vocab_item_id == VocabItem.id)
        .where(module_vocab.c.module_id == module.id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def module_vocab_ids(db: AsyncSession, module: Module) -> set[UUID]:
    stmt = select(module_vocab.c.vocab_item_id).where(module_vocab.c.module_id == module.id)
    return set((await db.execute(stmt)).scalars().all())


async def enroll_cards(db: AsyncSession, *, user_id: UUID, vocab_item_ids: list[UUID]) -> None:
    """Idempotently create NEW SRS cards for the given vocab items. Reuses the
    unique constraint to skip words the user already has. Caller commits."""
    if not vocab_item_ids:
        return
    stmt = (
        pg_insert(UserCard)
        .values([{"user_id": user_id, "vocab_item_id": vid} for vid in vocab_item_ids])
        .on_conflict_do_nothing(constraint="uq_user_card_user_vocab")
    )
    await db.execute(stmt)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "ensure_active or read_active or target_lemmas or enroll_cards"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/curriculum/modules.py backend/tests/test_modules.py
git commit -m "feat(curriculum): active-module read/init, target lemmas, card enrollment"
```

---

## Task 4: Objective prompt block

**Files:**
- Modify: `backend/src/klara/llm/prompts.py:101-122`
- Test: `backend/tests/test_story_prompt.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_story_prompt.py`:

```python
from klara.llm.prompts import build_story_user_prompt


def test_user_prompt_includes_module_objective_when_present():
    out = build_story_user_prompt(
        topic="café",
        target_label="alemán",
        recent_vocab="(ninguno)",
        target_lemmas=["Kaffee"],
        module_objective="OBJETIVO DEL MÓDULO: puedo pedir algo en un café. Foco: género de comida.",
    )
    assert "OBJETIVO DEL MÓDULO" in out
    assert "Kaffee" in out  # target block still present


def test_user_prompt_omits_objective_block_when_none():
    out = build_story_user_prompt(
        topic="café",
        target_label="alemán",
        recent_vocab="(ninguno)",
        target_lemmas=[],
        module_objective=None,
    )
    assert "OBJETIVO DEL MÓDULO" not in out
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_story_prompt.py -v -k "module_objective or objective_block"`
Expected: FAIL — `TypeError: build_story_user_prompt() got an unexpected keyword argument 'module_objective'`

- [ ] **Step 3: Implement**

Modify `backend/src/klara/llm/prompts.py`. Change the `STORY_USER_PROMPT` template (line 101-106) to add a sibling block placeholder:

```python
STORY_USER_PROMPT = """Genera una nueva micro-historia.

Tema: {topic}
Vocabulario reciente del estudiante en {target_label} (intenta NO repetir): {recent_vocab}
{objective_block}{target_block}
Genera el JSON ahora."""
```

Change `build_story_user_prompt` (line 109-122):

```python
def build_story_user_prompt(
    *,
    topic: str,
    target_label: str,
    recent_vocab: str,
    target_lemmas: list[str],
    module_objective: str | None = None,
) -> str:
    if target_lemmas:
        joined = ", ".join(target_lemmas)
        target_block = (
            f"\nPALABRAS OBJETIVO DE HOY (el currículo las eligió; la historia "
            f"DEBE girar en torno a ellas y deben aparecer en `target_words`): {joined}\n"
        )
    else:
        target_block = ""
    objective_block = f"\n{module_objective.strip()}\n" if module_objective else ""
    return STORY_USER_PROMPT.format(
        topic=topic,
        target_label=target_label,
        recent_vocab=recent_vocab,
        objective_block=objective_block,
        target_block=target_block,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_story_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/llm/prompts.py backend/tests/test_story_prompt.py
git commit -m "feat(prompts): module objective block in story user prompt"
```

---

## Task 5: ModuleCurrentOut schema + GET /modules/current + router registration

**Files:**
- Create: `backend/src/klara/schemas/module.py`, `backend/src/klara/routers/modules.py`
- Modify: `backend/src/klara/main.py:21-31,219-227`
- Test: `backend/tests/test_modules.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_modules.py`:

```python
@pytest.mark.asyncio
async def test_get_current_module_endpoint(db_session):
    v1 = await _vocab(db_session, lemma="Kuchen", language="modt6")
    v2 = await _vocab(db_session, lemma="Teller", language="modt6")
    m = await _module(db_session, language="modt6", order=1, title="En el café", vocab=[v1, v2])
    u = await _user(db_session)
    u.target_language = "modt6"
    u.current_module_id = m.id
    db_session.add(UserCard(id=uuid.uuid4(), user_id=u.id, vocab_item_id=v1.id, state=CardState.NEW))
    await db_session.commit()

    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/modules/current")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "En el café"
    assert body["encountered"] == 1
    assert body["mastered"] == 0
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_get_current_module_empty_when_none(db_session):
    u = await _user(db_session)  # no current module, no modules for "de"
    await db_session.commit()

    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/modules/current")
    assert resp.status_code == 200, resp.text
    assert resp.json() is None
```

Add `from klara.models.enums import CardState` to the top imports of `test_modules.py` (alongside CEFRLevel, PartOfSpeech) — remove the inline duplicate import if redundant.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "current_module_endpoint or empty_when_none"`
Expected: FAIL — 404 (route not registered)

- [ ] **Step 3: Create the schema**

Create `backend/src/klara/schemas/module.py`:

```python
from uuid import UUID

from pydantic import BaseModel

from klara.models.enums import CEFRLevel


class ModuleCurrentOut(BaseModel):
    id: UUID
    title: str
    cefr_level: CEFRLevel
    can_dos: list[str]
    grammatical_focus: list[str]
    encountered: int
    mastered: int
    total: int
```

- [ ] **Step 4: Create the router**

Create `backend/src/klara/routers/modules.py`:

```python
from fastapi import APIRouter

from klara.curriculum.competence import module_progress
from klara.curriculum.modules import read_active_module
from klara.dependencies import CurrentUser, DBSession
from klara.schemas.module import ModuleCurrentOut

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("/current", response_model=ModuleCurrentOut | None)
async def get_current_module(db: DBSession, user: CurrentUser) -> ModuleCurrentOut | None:
    """The user's active module + progress, or null if none is active yet
    (fresh account / unseeded DB). Read-only: never initializes the pointer."""
    module = await read_active_module(db, user)
    if module is None:
        return None
    encountered, mastered, total = await module_progress(
        db, user_id=user.id, module_id=module.id
    )
    return ModuleCurrentOut(
        id=module.id,
        title=module.title,
        cefr_level=module.cefr_level,
        can_dos=module.can_dos or [],
        grammatical_focus=module.grammatical_focus or [],
        encountered=encountered,
        mastered=mastered,
        total=total,
    )
```

- [ ] **Step 5: Register the router**

Modify `backend/src/klara/main.py`. Add `modules` to the router import (line 21-31):

```python
from klara.routers import (
    health,
    invitations,
    modules,
    practice,
    pronunciation,
    speak,
    srs,
    stories,
    tts,
    users,
)
```

Add the include (after line 220, near the other `app.include_router(... prefix="/api/v1")` calls):

```python
    app.include_router(modules.router, prefix="/api/v1")
```

- [ ] **Step 6: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "current_module_endpoint or empty_when_none"`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/src/klara/schemas/module.py backend/src/klara/routers/modules.py backend/src/klara/main.py backend/tests/test_modules.py
git commit -m "feat(api): GET /modules/current with progress"
```

---

## Task 6: create_story rewire — module-driven generation + auto-enroll

**Files:**
- Modify: `backend/src/klara/services/story_gen.py:167-195` (signature + prompt call)
- Modify: `backend/src/klara/routers/stories.py:108-141` (create_story)
- Test: `backend/tests/test_modules.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_modules.py`. Reuse the `_FakeLLM` shape from `test_story_curriculum.py` (returns a story containing "Kaffee"):

```python
class _CafeLLM:
    """Returns a story that contains 'Kaffee' (covered) and declares it a target word."""

    def __init__(self):
        self.provider = "fake"
        self.model = "fake"
        self.cost_usd = 0.0

    async def complete(self, **kwargs):
        import json
        from types import SimpleNamespace

        data = {
            "title": "Der Kaffee",
            "sentences": [
                {
                    "target": "Der Kaffee ist heiß.",
                    "native": "El café está caliente.",
                    "new_words": ["Kaffee"],
                    "breakdown": [{"word": "Kaffee", "translation": "café", "pos": "noun"}],
                }
            ],
            "comprehension_questions": [],
            "target_words": [
                {"lemma": "Kaffee", "pos": "noun", "gender": "der",
                 "translation": "café", "example_target": "Der Kaffee."},
            ],
        }
        return SimpleNamespace(content=json.dumps(data), provider="fake", model="fake", cost_usd=0.0)


@pytest.mark.asyncio
async def test_create_story_drives_from_module_and_auto_enrolls(db_session):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import func, select

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep, get_story_llm
    from klara.main import create_app

    # Module 'café' with vocab 'Kaffee' (the lemma the fake LLM will cover).
    v = await _vocab(db_session, lemma="Kaffee", language="modt7")
    m = await _module(db_session, language="modt7", order=1, title="En el café", vocab=[v])
    u = await _user(db_session)
    u.target_language = "modt7"
    await db_session.commit()
    assert u.current_module_id is None  # lazy-init happens in create_story

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    app.dependency_overrides[get_story_llm] = lambda: _CafeLLM()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/stories", json={"topic": None})
    assert resp.status_code == 201, resp.text

    # Pointer initialized to the module.
    reloaded = await db_session.get(type(u), u.id)
    assert reloaded.current_module_id == m.id
    # 'Kaffee' auto-enrolled as a NEW card.
    n = (
        await db_session.execute(
            select(func.count()).select_from(UserCard).where(
                UserCard.user_id == u.id, UserCard.vocab_item_id == v.id
            )
        )
    ).scalar_one()
    assert n == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "drives_from_module"`
Expected: FAIL — no card enrolled (count 0) / pointer still None

- [ ] **Step 3: Thread module_objective through generate_story**

Modify `backend/src/klara/services/story_gen.py`. Add the parameter to the signature (after `target_lemmas`, line 178):

```python
    target_lemmas: list[str] | None = None,
    module_objective: str | None = None,
) -> GeneratedStory:
```

Pass it to the prompt builder (line 190-195):

```python
    user = build_story_user_prompt(
        topic=topic or "libre — algo cotidiano",
        target_label=target_label,
        recent_vocab=", ".join(recent) if recent else "(ninguno)",
        target_lemmas=target_lemmas or [],
        module_objective=module_objective,
    )
```

- [ ] **Step 4: Rewire create_story**

Modify `backend/src/klara/routers/stories.py`. Add imports (near line 20):

```python
from klara.curriculum.modules import (
    ensure_active_module,
    enroll_cards,
    module_target_lemmas,
    module_vocab_ids,
)
```

Replace the body of `create_story` (lines 117-133, from `level = ...` through `serialized = ...`) with:

```python
    level = payload.level or user.level
    active = await ensure_active_module(db, user)
    if active is not None:
        target_lemmas = await module_target_lemmas(db, active)
        mod_vids = await module_vocab_ids(db, active)
        objective = _module_objective(active)
    else:
        target_words_sel = await next_target_words(
            db, user_id=user.id, language=user.target_language, level=level, n=5
        )
        target_lemmas = [w.lemma for w in target_words_sel]
        mod_vids = set()
        objective = None

    result = await generate_story(
        db,
        llm,
        user_id=user.id,
        level=level,
        target_language=user.target_language,
        native_language=user.native_language,
        learning_context=user.learning_context,
        topic=payload.topic,
        model=None,
        target_lemmas=target_lemmas,
        module_objective=objective,
    )

    if active is not None:
        enrolled = [w.id for w in result.target_words if w.id in mod_vids]
        await enroll_cards(db, user_id=user.id, vocab_item_ids=enrolled)
        await db.commit()

    serialized = _serialize_story(result.story, result.target_words, user.native_language)
```

Add the objective-builder helper near the top of `routers/stories.py` (after `_serialize_story`, before `create_story`):

```python
def _module_objective(module) -> str:
    """Build the module objective block injected into the story prompt."""
    can_dos = "; ".join(module.can_dos or [])
    focus = "; ".join(module.grammatical_focus or [])
    parts = ["OBJETIVO DEL MÓDULO (la historia debe servir este objetivo, sin forzar):"]
    if can_dos:
        parts.append(f"Can-do: {can_dos}.")
    if focus:
        parts.append(f"Foco gramatical: {focus}.")
    return " ".join(parts)
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "drives_from_module"`
Expected: PASS

- [ ] **Step 6: Run the full backend suite (no regressions)**

Run: `cd backend && uv run pytest -q`
Expected: all pass (existing story/curriculum tests still green — the fallback path is unchanged when no module is active).

- [ ] **Step 7: Commit**

```bash
git add backend/src/klara/services/story_gen.py backend/src/klara/routers/stories.py backend/tests/test_modules.py
git commit -m "feat(stories): drive generation from active module + auto-enroll its vocab"
```

---

## Task 7: Seed script — load one A1 module

**Files:**
- Modify: `backend/src/klara/curriculum/modules.py` (add `load_modules`)
- Create: `backend/src/klara/scripts/load_de_modules.py`
- Test: `backend/tests/test_modules.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_modules.py`:

```python
from klara.curriculum.modules import load_modules

_SEED = [
    {
        "sequence_order": 1,
        "title": "En el café",
        "cefr_level": "A1",
        "can_dos": ["puedo pedir una bebida en un café"],
        "grammatical_focus": ["género de sustantivos de comida y bebida"],
        "vocab": [
            {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translations": {"es": "café"}},
            {"lemma": "Tee", "pos": "noun", "gender": "der", "translations": {"es": "té"}},
        ],
    }
]


@pytest.mark.asyncio
async def test_load_modules_is_idempotent(db_session):
    n1 = await load_modules(db_session, language="modt8", modules=_SEED)
    await db_session.commit()
    n2 = await load_modules(db_session, language="modt8", modules=_SEED)
    await db_session.commit()
    assert n1 == 1 and n2 == 1
    from sqlalchemy import func, select

    from klara.models import Module
    count = (
        await db_session.execute(
            select(func.count()).select_from(Module).where(Module.language == "modt8")
        )
    ).scalar_one()
    assert count == 1  # second load did not duplicate
    m = (
        await db_session.execute(
            select(Module).where(Module.language == "modt8", Module.sequence_order == 1)
        )
    ).scalar_one()
    assert {v.lemma for v in m.vocab_items} == {"Kaffee", "Tee"}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "load_modules_is_idempotent"`
Expected: FAIL — `cannot import name 'load_modules'`

- [ ] **Step 3: Implement load_modules**

Append to `backend/src/klara/curriculum/modules.py` (add imports `from klara.models import VocabItem, Module, module_vocab` already present; add `PartOfSpeech`, `CEFRLevel`):

```python
from klara.models.enums import CEFRLevel, PartOfSpeech


async def load_modules(db: AsyncSession, *, language: str, modules: list[dict]) -> int:
    """Idempotently seed curriculum modules + their vocab for a language.
    Upserts VocabItems on (lemma, language, pos), modules on (language,
    sequence_order), and links them in module_vocab. Returns module count."""
    for spec in modules:
        # Upsert the module (idempotent on language + sequence_order).
        mod_stmt = (
            pg_insert(Module)
            .values(
                language=language,
                cefr_level=CEFRLevel(spec["cefr_level"]),
                sequence_order=spec["sequence_order"],
                title=spec["title"],
                can_dos=spec.get("can_dos", []),
                grammatical_focus=spec.get("grammatical_focus", []),
            )
            .on_conflict_do_update(
                constraint="uq_module_lang_seq",
                set_={
                    "title": spec["title"],
                    "can_dos": spec.get("can_dos", []),
                    "grammatical_focus": spec.get("grammatical_focus", []),
                },
            )
            .returning(Module.id)
        )
        module_id = (await db.execute(mod_stmt)).scalar_one()

        for w in spec["vocab"]:
            voc_stmt = (
                pg_insert(VocabItem)
                .values(
                    lemma=w["lemma"],
                    language=language,
                    pos=PartOfSpeech(w.get("pos", "noun")),
                    gender=w.get("gender"),
                    translations=w.get("translations", {}),
                )
                .on_conflict_do_update(
                    constraint="uq_vocab_lemma_lang_pos",
                    set_={
                        "gender": w.get("gender"),
                        "translations": w.get("translations", {}),
                    },
                )
                .returning(VocabItem.id)
            )
            vocab_id = (await db.execute(voc_stmt)).scalar_one()
            link_stmt = (
                pg_insert(module_vocab)
                .values(module_id=module_id, vocab_item_id=vocab_id)
                .on_conflict_do_nothing()
            )
            await db.execute(link_stmt)
    return len(modules)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "load_modules_is_idempotent"`
Expected: PASS

- [ ] **Step 5: Create the CLI script**

Create `backend/src/klara/scripts/load_de_modules.py`:

```python
"""Seed the curated German A1 module sequence.

Usage:
    uv run python -m klara.scripts.load_de_modules

PR-A seeds ONE module ("En el café") to prove the loop end-to-end. The full
A1 sequence (PR-B) extends MODULES below. Idempotent — safe to re-run.
"""

from __future__ import annotations

import asyncio

from klara.config import get_settings
from klara.curriculum.modules import load_modules
from klara.db import dispose_engine, get_sessionmaker, init_engine

MODULES: list[dict] = [
    {
        "sequence_order": 1,
        "title": "En el café",
        "cefr_level": "A1",
        "can_dos": ["puedo pedir una bebida o un dulce en un café"],
        "grammatical_focus": ["género de sustantivos de comida y bebida (der/die/das)"],
        "vocab": [
            {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translations": {"es": "café"}},
            {"lemma": "Tee", "pos": "noun", "gender": "der", "translations": {"es": "té"}},
            {"lemma": "Wasser", "pos": "noun", "gender": "das", "translations": {"es": "agua"}},
            {"lemma": "Milch", "pos": "noun", "gender": "die", "translations": {"es": "leche"}},
            {"lemma": "Tasse", "pos": "noun", "gender": "die", "translations": {"es": "taza"}},
            {"lemma": "Kuchen", "pos": "noun", "gender": "der", "translations": {"es": "pastel"}},
            {"lemma": "Brot", "pos": "noun", "gender": "das", "translations": {"es": "pan"}},
            {"lemma": "Zucker", "pos": "noun", "gender": "der", "translations": {"es": "azúcar"}},
            {"lemma": "bestellen", "pos": "verb", "translations": {"es": "pedir/ordenar"}},
            {"lemma": "trinken", "pos": "verb", "translations": {"es": "beber"}},
        ],
    }
]


async def _run() -> None:
    settings = get_settings()
    init_engine(settings)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            n = await load_modules(db, language="de", modules=MODULES)
            await db.commit()
        print(f"Sembrados {n} módulo(s) de alemán.")
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/curriculum/modules.py backend/src/klara/scripts/load_de_modules.py backend/tests/test_modules.py
git commit -m "feat(curriculum): module seed loader + load_de_modules script (1 module)"
```

---

## Task 8: Frontend — type + client method

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`

- [ ] **Step 1: Add the type**

Append to `frontend/src/api/types.ts`:

```typescript
export interface ModuleCurrent {
  id: string;
  title: string;
  cefr_level: string;
  can_dos: string[];
  grammatical_focus: string[];
  encountered: number;
  mastered: number;
  total: number;
}
```

- [ ] **Step 2: Add the client method**

Modify `frontend/src/api/client.ts`. Add `ModuleCurrent` to the type import block (lines 3-26):

```typescript
  ModuleCurrent,
```

Add the method to the `api` object (after `dueCards`, around line 189):

```typescript
  currentModule: () => request<ModuleCurrent | null>("/modules/current"),
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: PASS (no type errors)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat(frontend): ModuleCurrent type + api.currentModule()"
```

---

## Task 9: Frontend — Home module panel + empty state + i18n

**Files:**
- Modify: `frontend/src/routes/Home.tsx`
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`

- [ ] **Step 1: Add i18n keys (source = es)**

In `frontend/src/locales/es/common.json`, inside the `"home"` object (after the `"sub"` key near line 32), add:

```json
    "module": {
      "kicker": "Tu módulo",
      "progress_one": "Has encontrado {{count}} de {{total}} palabra.",
      "progress_other": "Has encontrado {{count}} de {{total}} palabras.",
      "empty": "Aún sin módulo. Genera tu primera historia para empezar."
    },
```

Add the same `"module"` block (translated) to the other 5 locales' `"home"` object:

`en/common.json`:
```json
    "module": {
      "kicker": "Your module",
      "progress_one": "You've met {{count}} of {{total}} word.",
      "progress_other": "You've met {{count}} of {{total}} words.",
      "empty": "No module yet. Generate your first story to start."
    },
```

`de/common.json`:
```json
    "module": {
      "kicker": "Dein Modul",
      "progress_one": "Du kennst {{count}} von {{total}} Wort.",
      "progress_other": "Du kennst {{count}} von {{total}} Wörtern.",
      "empty": "Noch kein Modul. Erstelle deine erste Geschichte."
    },
```

`fr/common.json`:
```json
    "module": {
      "kicker": "Ton module",
      "progress_one": "Tu as rencontré {{count}} mot sur {{total}}.",
      "progress_other": "Tu as rencontré {{count}} mots sur {{total}}.",
      "empty": "Pas encore de module. Génère ta première histoire."
    },
```

`pt/common.json`:
```json
    "module": {
      "kicker": "Seu módulo",
      "progress_one": "Você encontrou {{count}} de {{total}} palavra.",
      "progress_other": "Você encontrou {{count}} de {{total}} palavras.",
      "empty": "Ainda sem módulo. Gere sua primeira história."
    },
```

`ja/common.json`:
```json
    "module": {
      "kicker": "あなたのモジュール",
      "progress_one": "{{total}} 語中 {{count}} 語に出会いました。",
      "progress_other": "{{total}} 語中 {{count}} 語に出会いました。",
      "empty": "まだモジュールがありません。最初のストーリーを作成してください。"
    },
```

- [ ] **Step 2: Render the panel in Home**

Modify `frontend/src/routes/Home.tsx`.

Add to the type import (line 5):

```typescript
import type { CardOut, ModuleCurrent, Story, StoryListItem } from "../api/types";
```

Add state (after line 43, `const [dueCount, ...]`):

```typescript
  const [module, setModule] = useState<ModuleCurrent | null>(null);
```

Inside the existing `useEffect`'s async IIFE, after the `due` fetch block (after line 69), add:

```typescript
      try {
        const mod = await api.currentModule();
        if (!cancelled) setModule(mod);
      } catch {
        if (!cancelled) setModule(null);
      }
```

Render the panel after the masthead rule (after line 93, the first `<hr className="k-rule home__rule" />`), before the loading/feature block:

```tsx
      {!loading && (
        <section className="home__module">
          <span className="k-mono home__module-kicker">{t("home.module.kicker")}</span>
          {module ? (
            <>
              <h2 className="home__module-title">{module.title}</h2>
              <p className="home__module-progress k-mono">
                {t("home.module.progress", {
                  count: module.encountered,
                  total: module.total,
                })}
              </p>
            </>
          ) : (
            <p className="home__module-empty">{t("home.module.empty")}</p>
          )}
        </section>
      )}
```

(Note: `t("home.module.progress", { count, total })` resolves `progress_one`/`progress_other` via i18next pluralization on `count`.)

- [ ] **Step 3: i18n parity + typecheck + build**

Run: `cd frontend && npm run i18n:check && npm run typecheck && npm run build`
Expected: i18n:check reports all 6 locales aligned; typecheck clean; build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/Home.tsx frontend/src/locales
git commit -m "feat(frontend): Home current-module panel + empty state + i18n"
```

---

## Task 10: Full verification

**Files:** none (verification + any fixups)

- [ ] **Step 1: Backend — tests, lint, format**

Run:
```bash
cd backend
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
```
Expected: all tests pass; ruff clean; format clean. Fix any issues and re-run.

- [ ] **Step 2: Migration round-trip (final)**

Run:
```bash
cd backend
uv run alembic upgrade head && uv run alembic downgrade base && uv run alembic upgrade head
```
Expected: success (matches CI `migration roundtrip`).

- [ ] **Step 3: Frontend — i18n, typecheck, build**

Run:
```bash
cd frontend
npm run i18n:check && npm run typecheck && npm run build
```
Expected: all green.

- [ ] **Step 4: Commit any fixups**

```bash
git add -A
git commit -m "chore(curriculum): fixups from full verification"
```

(Skip if nothing changed.)

---

## Notes for the implementer

- **Test isolation:** `vocab_items` is NOT truncated between tests (conftest), but `modules`/`module_vocab` now ARE (Task 1, Step 7). Use a **unique fake `language` code per test** (`modt1`, `modt2`, …) for vocab and modules so rows from other tests can't bleed into queries — this mirrors the convention in `test_curriculum_selection.py`.
- **Why auto-enroll on coverage, not on module-activation:** the "encountered" signal must move with *reading*, so a module word becomes a card only when it actually appears in a generated story (`result.target_words` = covered words). Front-loading all module vocab as cards on activation would make "encountered" jump to 100% immediately and stop being a reading signal.
- **The fallback path is unchanged:** when no module is active (unseeded DB, e.g. CI), `create_story` calls `next_target_words` exactly as before and does not enroll. All pre-existing story tests must stay green (Task 6, Step 6).
- **PR-B (separate plan):** the advancement gate in `submit_review` (forward-only pointer advance when `module_progress` mastered/total ≥ `mastery_threshold`, with a no-op guard when the reviewed card isn't in the active module), the full ~8-module A1 authoring, and the mastery/gamification surface.
