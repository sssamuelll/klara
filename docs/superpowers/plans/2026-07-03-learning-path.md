# Learning Path + Story Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Duolingo-style module path UI backed by a shared per-module story library served via copy-on-claim, so starting a story is instant and generation cost is shared.

**Architecture:** New `story_library` table keyed by (module, native_language); claiming clones an entry into the user's `stories` row so every downstream flow (finish, quiz, SRS, attempts) works untouched. Two-signal gating: *completar* (3 finished stories → pointer advances) and *dominar* (existing SRS 85% gate, unchanged). The pool grows by recycling coverage-clean, non-personal live generations.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (backend), React 18 + react-router 6 + i18next (frontend), pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-07-03-learning-path-design.md`

## Global Constraints

- Branch: `feat/learning-path` (already exists, spec committed).
- Backend tests: `cd backend && uv run pytest tests/<file> -v` — requires the dev Postgres from `docker compose up db` (conftest points at `german_app_test`).
- Frontend checks: `cd frontend && npm run typecheck && npm test && npm run i18n:check`.
- i18n: every new key must land in ALL SIX locales (`es`, `en`, `de`, `fr`, `ja`, `pt`) in the same commit — `npm run i18n:check` fails otherwise. `es` is source of truth.
- `STORIES_TO_COMPLETE = 3` (constant, not a column). `POOL_CAP_PER_PAIR = 50`.
- Module stays a predicate: NO FK from `modules` to stories/library content. Story→Module provenance FK is allowed.
- No streaks/lives/leagues/XP anywhere (owner constraint from the June spec).
- Pointer (`users.current_module_id`) gates advance forward-only; starting a story in module M sets the pointer to M (any direction).
- Claim path must never call an LLM — it is a DB clone, milliseconds.
- Pool recycle is best-effort: a pool failure must never fail story creation.
- Commit after every task with the trailer:
  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01NZA6P3qYsv8AcC4aZTocW8
  ```

---

### Task 1: StoryLibrary model + migration

**Files:**
- Create: `backend/src/klara/models/library.py`
- Modify: `backend/src/klara/models/story.py` (two new nullable columns)
- Modify: `backend/src/klara/models/__init__.py` (export `StoryLibrary`)
- Create: `backend/alembic/versions/20260703_0010_story_library.py`
- Test: `backend/tests/test_story_library_model.py`

**Interfaces:**
- Produces: `StoryLibrary` model (fields below), `Story.module_id: UUID | None`, `Story.library_source_id: UUID | None`. Every later backend task imports `StoryLibrary` from `klara.models`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_story_library_model.py
"""StoryLibrary rows persist and stories accept module/library provenance."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from klara.models import Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel


async def _seed_module(db_session) -> Module:
    module = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=1,
        title="En el café",
        can_dos=["puedo pedir una bebida"],
        grammatical_focus=["género de sustantivos"],
    )
    db_session.add(module)
    await db_session.commit()
    return module


async def _seed_user(db_session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"lib-{uuid.uuid4().hex[:6]}@klara.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Test",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_story_library_roundtrip(db_session):
    module = await _seed_module(db_session)
    entry = StoryLibrary(
        module_id=module.id,
        language="de",
        native_language="es",
        level=CEFRLevel.A1,
        title="Der Kaffee",
        content={"sentences": [{"target": "Ich trinke Kaffee.", "native": "Bebo café.", "new_words": []}], "comprehension_questions": []},
        target_vocab_item_ids=[],
        topic="pedir un café",
        source="seed",
        content_hash="a" * 64,
    )
    db_session.add(entry)
    await db_session.commit()

    row = (await db_session.execute(select(StoryLibrary))).scalar_one()
    assert row.times_served == 0
    assert row.is_active is True
    assert row.source == "seed"
    assert row.module_id == module.id


@pytest.mark.asyncio
async def test_story_accepts_module_and_library_provenance(db_session):
    module = await _seed_module(db_session)
    user = await _seed_user(db_session)
    story = Story(
        user_id=user.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="Test",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[],
        module_id=module.id,
        library_source_id=None,
    )
    db_session.add(story)
    await db_session.commit()
    await db_session.refresh(story)
    assert story.module_id == module.id
    assert story.library_source_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_story_library_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'StoryLibrary'`

- [ ] **Step 3: Write the model**

```python
# backend/src/klara/models/library.py
"""Shared per-module story catalog, served by copy-on-claim (spec 2026-07-03).

NOT a container relationship: Module never references this table; the library
references the module. Claiming clones a row into `stories`, so downstream
flows (finish, quiz, SRS, attempts) never see a library row."""

from uuid import UUID

from sqlalchemy import ARRAY, Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, pg_enum, uuid_pk
from klara.models.enums import CEFRLevel


class StoryLibrary(Base):
    __tablename__ = "story_library"
    __table_args__ = (
        Index("ix_library_module_native", "module_id", "native_language", "is_active"),
    )

    id: Mapped[uuid_pk]
    module_id: Mapped[UUID] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    native_language: Mapped[str] = mapped_column(String(8), nullable=False)
    level: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, name="cefr_level", create_type=False), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_vocab_item_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), default=list, nullable=False
    )
    quiz_items: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    insight_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    insight_body: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 'seed' (curated batch) | 'pool' (recycled live generation). Plain string,
    # not a PG enum — two values don't earn a type. ponytail: string, enum if a
    # third source ever appears.
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    source_story_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("stories.id", ondelete="SET NULL"), nullable=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    times_served: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    generated_by_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generated_by_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    generation_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[created_ts]
```

Add to `backend/src/klara/models/story.py`, after `generation_cost_usd` (line 36):

```python
    # Provenance: which module conditioned this story (Story→Module — the June
    # invariant forbids the opposite direction). Basis for "N stories of this
    # module finished". NULL for pre-path stories and module-less generation.
    module_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("modules.id", ondelete="SET NULL"), nullable=True
    )
    # Which library entry this story was claimed from; doubles as the
    # "don't re-serve this entry to this user" filter.
    library_source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("story_library.id", ondelete="SET NULL"), nullable=True
    )
```

In `backend/src/klara/models/__init__.py`: add `from klara.models.library import StoryLibrary` and `"StoryLibrary"` to `__all__` (mirror how `Story` is exported).

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/20260703_0010_story_library.py
"""story_library + stories.module_id/library_source_id

Revision ID: 20260703_0010
Revises: 20260616_0009
Create Date: 2026-07-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from alembic import op

revision: str = "20260703_0010"
down_revision: str | None = "20260616_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

cefr_level = PG_ENUM("A0", "A1", "A2", "B1", "B2", "C1", name="cefr_level", create_type=False)


def upgrade() -> None:
    op.create_table(
        "story_library",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "module_id",
            UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("native_language", sa.String(8), nullable=False),
        sa.Column("level", cefr_level, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column(
            "target_vocab_item_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column("quiz_items", JSONB, nullable=True),
        sa.Column("insight_title", sa.String(200), nullable=True),
        sa.Column("insight_body", sa.String(2000), nullable=True),
        sa.Column("topic", sa.String(200), nullable=True),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column(
            "source_story_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("times_served", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("generated_by_provider", sa.String(50), nullable=True),
        sa.Column("generated_by_model", sa.String(120), nullable=True),
        sa.Column("generation_cost_usd", sa.Float, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_library_module_native", "story_library", ["module_id", "native_language", "is_active"]
    )
    op.add_column(
        "stories",
        sa.Column(
            "module_id",
            UUID(as_uuid=True),
            sa.ForeignKey("modules.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "stories",
        sa.Column(
            "library_source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("story_library.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_story_user_module", "stories", ["user_id", "module_id"])


def downgrade() -> None:
    op.drop_index("ix_story_user_module", table_name="stories")
    op.drop_column("stories", "library_source_id")
    op.drop_column("stories", "module_id")
    op.drop_index("ix_library_module_native", table_name="story_library")
    op.drop_table("story_library")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_story_library_model.py -v`
Expected: 2 PASSED (conftest runs alembic upgrade against the test DB).

- [ ] **Step 6: Run the full backend suite (migration must not break anything)**

Run: `cd backend && uv run pytest -x -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/src/klara/models/library.py backend/src/klara/models/story.py backend/src/klara/models/__init__.py backend/alembic/versions/20260703_0010_story_library.py backend/tests/test_story_library_model.py
git commit -m "feat(path): story_library table + story module/library provenance (#spec 2026-07-03)"
```

---

### Task 2: Extract the generation core from `generate_story`

**Files:**
- Modify: `backend/src/klara/services/story_gen.py`
- Test: `backend/tests/test_story_gen_draft.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(slots=True)
  class StoryDraft:
      title: str
      content: dict                     # {"sentences": [...], "comprehension_questions": [...]}
      target_words: list[VocabItem]     # coverage-kept only
      dropped_lemmas: list[str]         # declared target words the text didn't use
      quiz_items: list[dict] | None
      insight_title: str | None
      insight_body: str | None
      provider: str | None
      model: str | None
      cost_usd: float | None

  async def generate_story_draft(
      db: AsyncSession, llm: LLMClient, *,
      level: CEFRLevel, target_language: str, native_language: str,
      learning_context: str | None, topic: str | None, model: str | None,
      target_lemmas: list[str] | None = None, module_objective: str | None = None,
      avoid_lemmas: list[str] | None = None,
  ) -> StoryDraft
  ```
  `GeneratedStory` gains `dropped_lemmas: list[str]`. `generate_story` keeps its exact signature and behavior (router + existing tests untouched); internally it computes `avoid_lemmas = await _recent_vocab_lemmas(db, user_id)` and delegates to `generate_story_draft`, then builds the `Story` row.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_story_gen_draft.py
"""generate_story_draft: the user-less generation core (library build + create_story share it)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from klara.llm.base import LLMResponse
from klara.models import Story
from klara.models.enums import CEFRLevel
from klara.services.story_gen import generate_story_draft

STORY_JSON = {
    "title": "Der Kaffee am Morgen",
    "sentences": [
        {
            "target": "Ich trinke Kaffee mit Milch.",
            "native": "Bebo café con leche.",
            "new_words": ["Kaffee", "Milch"],
            "breakdown": [
                {"word": "Ich", "translation": "yo"},
                {"word": "trinke", "translation": "bebo"},
                {"word": "Kaffee", "translation": "café"},
                {"word": "mit", "translation": "con"},
                {"word": "Milch", "translation": "leche"},
            ],
        }
    ],
    "comprehension_questions": [],
    "target_words": [
        {"lemma": "Kaffee", "pos": "noun", "gender": "der", "translation": "café"},
        {"lemma": "Milch", "pos": "noun", "gender": "die", "translation": "leche"},
        {"lemma": "Zucker", "pos": "noun", "gender": "der", "translation": "azúcar"},
    ],
    "quiz_items": None,
}


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def complete(
        self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None
    ):
        self.calls += 1
        return LLMResponse(content=self.content, model="fake", provider="fake", cost_usd=0.001)

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_draft_creates_no_story_row_and_reports_dropped(db_session):
    llm = FakeLLM(json.dumps(STORY_JSON))
    draft = await generate_story_draft(
        db_session,
        llm,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        learning_context=None,
        topic="pedir un café",
        model=None,
        target_lemmas=["Kaffee", "Milch", "Zucker"],
        module_objective=None,
        avoid_lemmas=[],
    )
    assert draft.title == "Der Kaffee am Morgen"
    # Zucker was declared but never appears in the text → coverage drops it.
    assert "Zucker" in draft.dropped_lemmas
    kept = {w.lemma for w in draft.target_words}
    assert kept == {"Kaffee", "Milch"}
    assert draft.provider == "fake"
    n_stories = (await db_session.execute(select(func.count()).select_from(Story))).scalar_one()
    assert n_stories == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_story_gen_draft.py -v`
Expected: FAIL — `ImportError: cannot import name 'generate_story_draft'`

- [ ] **Step 3: Refactor `story_gen.py`**

Add the dataclass after `GeneratedStory` (and extend `GeneratedStory`):

```python
@dataclass(slots=True)
class GeneratedStory:
    story: Story
    target_words: list[VocabItem]
    dropped_lemmas: list[str]


@dataclass(slots=True)
class StoryDraft:
    title: str
    content: dict
    target_words: list[VocabItem]
    dropped_lemmas: list[str]
    quiz_items: list[dict] | None
    insight_title: str | None
    insight_body: str | None
    provider: str | None
    model: str | None
    cost_usd: float | None
```

Move the body of `generate_story` from the prompt build through the coverage check into:

```python
async def generate_story_draft(
    db: AsyncSession,
    llm: LLMClient,
    *,
    level: CEFRLevel,
    target_language: str,
    native_language: str,
    learning_context: str | None,
    topic: str | None,
    model: str | None,
    target_lemmas: list[str] | None = None,
    module_objective: str | None = None,
    avoid_lemmas: list[str] | None = None,
) -> StoryDraft:
    target_label = language_label(target_language)
    native_label = language_label(native_language)
    recent = avoid_lemmas or []
    system = build_story_system_prompt(
        target_label=target_label,
        native_label=native_label,
        level=level.value,
        target_language=target_language,
        learning_context=learning_context,
    )
    user = build_story_user_prompt(
        topic=topic or "libre — algo cotidiano",
        target_label=target_label,
        recent_vocab=", ".join(recent) if recent else "(ninguno)",
        target_lemmas=target_lemmas or [],
        module_objective=module_objective,
    )
    # MOVE VERBATIM from the current generate_story body: everything from
    # `data: dict[str, Any] | None = None` (the retry loop) through the
    # `if missed:` / `log.info("story.curriculum.missed", ...)` block —
    # i.e. current story_gen.py lines 249-315. This code is already
    # user-agnostic; only the surrounding function changes.
    return StoryDraft(
        title=title,
        content=content,
        target_words=kept_words,
        dropped_lemmas=dropped,
        quiz_items=quiz_items_raw if isinstance(quiz_items_raw, list) else None,
        insight_title=insight_title,
        insight_body=insight_body,
        provider=response.provider,
        model=response.model,
        cost_usd=response.cost_usd,
    )
```

`generate_story` keeps its signature and becomes:

```python
async def generate_story(
    db: AsyncSession,
    llm: LLMClient,
    *,
    user_id: UUID,
    level: CEFRLevel,
    target_language: str,
    native_language: str,
    learning_context: str | None,
    topic: str | None,
    model: str | None,
    target_lemmas: list[str] | None = None,
    module_objective: str | None = None,
) -> GeneratedStory:
    log.info(
        "story.generate.request",
        user_id=str(user_id),
        level=level.value,
        target_language=target_language,
        native_language=native_language,
        topic=topic,
    )
    avoid = await _recent_vocab_lemmas(db, user_id)
    draft = await generate_story_draft(
        db,
        llm,
        level=level,
        target_language=target_language,
        native_language=native_language,
        learning_context=learning_context,
        topic=topic,
        model=model,
        target_lemmas=target_lemmas,
        module_objective=module_objective,
        avoid_lemmas=avoid,
    )
    story = Story(
        user_id=user_id,
        level=level,
        target_language=target_language,
        native_language=native_language,
        title=draft.title,
        content=draft.content,
        target_vocab_item_ids=[w.id for w in draft.target_words],
        generated_by_provider=draft.provider,
        generated_by_model=draft.model,
        generation_cost_usd=draft.cost_usd,
        quiz_items=draft.quiz_items,
        insight_title=draft.insight_title,
        insight_body=draft.insight_body,
    )
    db.add(story)
    await db.flush()
    await db.refresh(story)
    # NOTE: no commit here — the caller (create_story) owns the commit so the
    # story and its module card-enrollment land in a single transaction.
    log.info(
        "story.generate.done",
        story_id=str(story.id),
        n_sentences=len(draft.content.get("sentences") or []),
        n_target_words=len(draft.target_words),
        cost_usd=draft.cost_usd,
    )
    return GeneratedStory(story=story, target_words=draft.target_words, dropped_lemmas=draft.dropped_lemmas)
```

- [ ] **Step 4: Run the new test and the existing story tests**

Run: `cd backend && uv run pytest tests/test_story_gen_draft.py tests/test_story_gen_extract.py tests/test_story_curriculum.py tests/test_story_prompt.py -v`
Expected: all PASS (existing tests prove the refactor preserved behavior).

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/services/story_gen.py backend/tests/test_story_gen_draft.py
git commit -m "refactor(story-gen): extract user-less generate_story_draft core"
```

---

### Task 3: Library service — pick, claim, count, completion, pool recycle

**Files:**
- Create: `backend/src/klara/curriculum/library.py`
- Test: `backend/tests/test_library_service.py`

**Interfaces:**
- Produces (all consumed by Tasks 4-7):
  ```python
  STORIES_TO_COMPLETE = 3
  POOL_CAP_PER_PAIR = 50

  def library_content_hash(content: dict) -> str
  async def pick_library_entry(db, *, user_id: UUID, module_id: UUID, native_language: str) -> StoryLibrary | None
  async def claim_library_entry(db, *, user: User, entry: StoryLibrary, module: Module) -> Story   # caller commits
  async def count_available(db, *, user_id: UUID, module_id: UUID, native_language: str) -> int
  async def stories_finished_count(db, *, user_id: UUID, module_id: UUID) -> int
  async def advance_module_if_completed(db, *, user: User) -> bool                                  # caller commits
  async def maybe_recycle_to_library(db, *, story: Story, dropped_lemmas: list[str], topic: str | None, topic_origin: str) -> bool
  ```
- Consumes: `enroll_cards`, `module_vocab_ids` from `klara.curriculum.modules`; `StoryLibrary` from Task 1.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_library_service.py
"""curriculum.library: pick/claim/count, completion gate, pool recycle rules."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from klara.curriculum.library import (
    STORIES_TO_COMPLETE,
    advance_module_if_completed,
    claim_library_entry,
    count_available,
    library_content_hash,
    maybe_recycle_to_library,
    pick_library_entry,
    stories_finished_count,
)
from klara.models import Module, Story, StoryLibrary, StoryView, User
from klara.models.enums import CEFRLevel

CONTENT = {
    "sentences": [{"target": "Ich trinke Kaffee.", "native": "Bebo café.", "new_words": []}],
    "comprehension_questions": [],
}


async def _user(db) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"lib-{uuid.uuid4().hex[:6]}@klara.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="T",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.commit()
    return u


async def _module(db, seq: int = 1) -> Module:
    m = Module(
        id=uuid.uuid4(),
        language="de",
        cefr_level=CEFRLevel.A1,
        sequence_order=seq,
        title=f"M{seq}",
        can_dos=[],
        grammatical_focus=[],
    )
    db.add(m)
    await db.commit()
    return m


def _entry(module: Module, *, served: int = 0, hash_suffix: str = "0") -> StoryLibrary:
    return StoryLibrary(
        module_id=module.id,
        language="de",
        native_language="es",
        level=CEFRLevel.A1,
        title="T",
        content=CONTENT,
        target_vocab_item_ids=[],
        source="seed",
        content_hash=(hash_suffix * 64)[:64],
        times_served=served,
    )


@pytest.mark.asyncio
async def test_pick_prefers_least_served_and_skips_claimed(db_session):
    user = await _user(db_session)
    module = await _module(db_session)
    fresh = _entry(module, served=0, hash_suffix="a")
    worn = _entry(module, served=5, hash_suffix="b")
    db_session.add_all([fresh, worn])
    await db_session.commit()

    picked = await pick_library_entry(
        db_session, user_id=user.id, module_id=module.id, native_language="es"
    )
    assert picked is not None and picked.id == fresh.id

    story = await claim_library_entry(db_session, user=user, entry=picked, module=module)
    await db_session.commit()
    assert story.library_source_id == fresh.id
    assert story.module_id == module.id
    assert user.current_module_id == module.id
    assert fresh.times_served == 1

    # Already claimed → next pick returns the other entry; count drops to 1.
    second = await pick_library_entry(
        db_session, user_id=user.id, module_id=module.id, native_language="es"
    )
    assert second is not None and second.id == worn.id
    assert await count_available(
        db_session, user_id=user.id, module_id=module.id, native_language="es"
    ) == 1


@pytest.mark.asyncio
async def test_completion_gate_advances_pointer(db_session):
    user = await _user(db_session)
    m1 = await _module(db_session, seq=1)
    m2 = await _module(db_session, seq=2)
    user.current_module_id = m1.id
    for i in range(STORIES_TO_COMPLETE):
        s = Story(
            user_id=user.id,
            level=CEFRLevel.A1,
            target_language="de",
            native_language="es",
            title=f"S{i}",
            content=CONTENT,
            target_vocab_item_ids=[],
            module_id=m1.id,
        )
        db_session.add(s)
        await db_session.flush()
        db_session.add(
            StoryView(story_id=s.id, user_id=user.id, finished_at=datetime.now(UTC))
        )
    await db_session.commit()

    assert await stories_finished_count(db_session, user_id=user.id, module_id=m1.id) == 3
    assert await advance_module_if_completed(db_session, user=user) is True
    assert user.current_module_id == m2.id
    # Idempotent / forward-only: m2 has no finished stories → no advance.
    assert await advance_module_if_completed(db_session, user=user) is False


@pytest.mark.asyncio
async def test_pool_recycle_rules(db_session):
    user = await _user(db_session)
    module = await _module(db_session)
    story = Story(
        user_id=user.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="P",
        content=CONTENT,
        target_vocab_item_ids=[],
        module_id=module.id,
    )
    db_session.add(story)
    await db_session.commit()

    # free topic → rejected
    assert await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=[], topic="mi perra Luna", topic_origin="free"
    ) is False
    # dropped lemmas → rejected
    assert await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=["Zucker"], topic=None, topic_origin="none"
    ) is False
    # clean → accepted once, hash-deduped after
    assert await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=[], topic=None, topic_origin="none"
    ) is True
    await db_session.commit()
    assert await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=[], topic=None, topic_origin="none"
    ) is False


def test_content_hash_is_stable_and_target_only():
    h1 = library_content_hash(CONTENT)
    h2 = library_content_hash(
        {"sentences": [{"target": "Ich trinke Kaffee.", "native": "OTRA traducción", "new_words": []}]}
    )
    assert h1 == h2
    assert len(h1) == 64
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_library_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum.library'`

- [ ] **Step 3: Implement `curriculum/library.py`**

```python
# backend/src/klara/curriculum/library.py
"""Story library: shared per-module catalog served by copy-on-claim, the
completar gate (finished stories), and pool recycling (spec 2026-07-03)."""

from __future__ import annotations

import hashlib
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.modules import enroll_cards, module_vocab_ids
from klara.models import Module, Story, StoryLibrary, StoryView, User

log = structlog.get_logger(__name__)

# Fast gate: N finished stories complete a module (the slow SRS "dominar" gate
# in modules.advance_module_if_mastered stays untouched). ponytail: constant,
# promote to a Module column if per-module tuning is ever needed.
STORIES_TO_COMPLETE = 3
POOL_CAP_PER_PAIR = 50


def library_content_hash(content: dict) -> str:
    """Dedup key: target-language sentence texts only (translations vary per
    native language pair without changing what the learner reads)."""
    targets = [(s.get("target") or "").strip() for s in (content.get("sentences") or [])]
    return hashlib.sha256("\n".join(targets).encode("utf-8")).hexdigest()


def _claimed_by_user(user_id: UUID):
    return select(Story.library_source_id).where(
        Story.user_id == user_id, Story.library_source_id.is_not(None)
    )


async def pick_library_entry(
    db: AsyncSession, *, user_id: UUID, module_id: UUID, native_language: str
) -> StoryLibrary | None:
    """Least-served active entry the user hasn't claimed; ties → oldest."""
    stmt = (
        select(StoryLibrary)
        .where(
            StoryLibrary.module_id == module_id,
            StoryLibrary.native_language == native_language,
            StoryLibrary.is_active.is_(True),
            StoryLibrary.id.not_in(_claimed_by_user(user_id)),
        )
        .order_by(StoryLibrary.times_served.asc(), StoryLibrary.created_at.asc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def count_available(
    db: AsyncSession, *, user_id: UUID, module_id: UUID, native_language: str
) -> int:
    stmt = (
        select(func.count())
        .select_from(StoryLibrary)
        .where(
            StoryLibrary.module_id == module_id,
            StoryLibrary.native_language == native_language,
            StoryLibrary.is_active.is_(True),
            StoryLibrary.id.not_in(_claimed_by_user(user_id)),
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def claim_library_entry(
    db: AsyncSession, *, user: User, entry: StoryLibrary, module: Module
) -> Story:
    """Clone the entry into the user's stories (copy-on-claim: every downstream
    flow works on a normal owned story), enroll module vocab, move the pointer.
    Caller commits."""
    story = Story(
        user_id=user.id,
        level=entry.level,
        target_language=entry.language,
        native_language=entry.native_language,
        title=entry.title,
        content=entry.content,
        target_vocab_item_ids=list(entry.target_vocab_item_ids or []),
        generated_by_provider=entry.generated_by_provider,
        generated_by_model=entry.generated_by_model,
        # The claimer didn't pay a generation — cost stays on the library row.
        generation_cost_usd=None,
        quiz_items=entry.quiz_items,
        insight_title=entry.insight_title,
        insight_body=entry.insight_body,
        module_id=module.id,
        library_source_id=entry.id,
    )
    db.add(story)
    entry.times_served += 1
    # Starting a story in module M moves the pointer to M (gated-suave skip and
    # replay are the same gesture; the gates push forward from wherever it is).
    user.current_module_id = module.id
    mod_vids = await module_vocab_ids(db, module)
    enrolled = [vid for vid in (entry.target_vocab_item_ids or []) if vid in mod_vids]
    await enroll_cards(db, user_id=user.id, vocab_item_ids=enrolled)
    await db.flush()
    await db.refresh(story)
    return story


async def stories_finished_count(db: AsyncSession, *, user_id: UUID, module_id: UUID) -> int:
    stmt = (
        select(func.count(func.distinct(Story.id)))
        .select_from(Story)
        .join(StoryView, (StoryView.story_id == Story.id) & (StoryView.user_id == user_id))
        .where(
            Story.user_id == user_id,
            Story.module_id == module_id,
            StoryView.finished_at.is_not(None),
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def advance_module_if_completed(db: AsyncSession, *, user: User) -> bool:
    """Completar gate: N finished stories in the ACTIVE module advance the
    pointer to the next sequence_order. Forward-only. Caller commits."""
    if user.current_module_id is None:
        return False
    module = await db.get(Module, user.current_module_id)
    if module is None or module.language != user.target_language:
        return False
    finished = await stories_finished_count(db, user_id=user.id, module_id=module.id)
    if finished < STORIES_TO_COMPLETE:
        return False
    nxt = (
        await db.execute(
            select(Module)
            .where(
                Module.language == user.target_language,
                Module.sequence_order > module.sequence_order,
            )
            .order_by(Module.sequence_order.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if nxt is None:
        return False  # last module — stay
    user.current_module_id = nxt.id
    await db.flush()
    return True


async def maybe_recycle_to_library(
    db: AsyncSession,
    *,
    story: Story,
    dropped_lemmas: list[str],
    topic: str | None,
    topic_origin: str,
) -> bool:
    """Pool growth: copy a clean live generation into the library. Rules
    (spec §7): no free-text topics (privacy), full coverage only (quality),
    module-conditioned only, hash-deduped, capped per (module, native).
    Best-effort — callers must never let a failure here break story creation."""
    if topic_origin == "free" or story.module_id is None or dropped_lemmas:
        return False
    content = story.content or {}
    h = library_content_hash(content)
    exists = (
        await db.execute(select(StoryLibrary.id).where(StoryLibrary.content_hash == h))
    ).first()
    if exists is not None:
        return False
    n = (
        await db.execute(
            select(func.count())
            .select_from(StoryLibrary)
            .where(
                StoryLibrary.module_id == story.module_id,
                StoryLibrary.native_language == story.native_language,
                StoryLibrary.is_active.is_(True),
            )
        )
    ).scalar_one()
    if n >= POOL_CAP_PER_PAIR:
        return False
    db.add(
        StoryLibrary(
            module_id=story.module_id,
            language=story.target_language,
            native_language=story.native_language,
            level=story.level,
            title=story.title,
            content=content,
            target_vocab_item_ids=list(story.target_vocab_item_ids or []),
            quiz_items=story.quiz_items,
            insight_title=story.insight_title,
            insight_body=story.insight_body,
            topic=topic,
            source="pool",
            source_story_id=story.id,
            content_hash=h,
            generated_by_provider=story.generated_by_provider,
            generated_by_model=story.generated_by_model,
            generation_cost_usd=story.generation_cost_usd,
        )
    )
    log.info("library.pool.recycled", story_id=str(story.id), module_id=str(story.module_id))
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_library_service.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/curriculum/library.py backend/tests/test_library_service.py
git commit -m "feat(path): library service — pick/claim/count, completar gate, pool recycle"
```

---

### Task 4: GET /modules — the path endpoint

**Files:**
- Modify: `backend/src/klara/schemas/module.py`
- Modify: `backend/src/klara/routers/modules.py`
- Test: `backend/tests/test_modules_path.py`

**Interfaces:**
- Produces: `GET /api/v1/modules` → `list[ModulePathItemOut]`:
  ```python
  class ModulePathItemOut(BaseModel):
      id: UUID
      sequence_order: int
      title: str
      cefr_level: CEFRLevel
      can_dos: list[str]
      grammatical_focus: list[str]
      encountered: int
      mastered: int
      total: int
      gender_encountered: int
      gender_mastered: int
      gender_total: int
      stories_finished: int
      stories_to_complete: int
      completed: bool
      is_current: bool
      unlocked: bool
      library_available: int
  ```
- Consumes: `module_progress`, `module_gender_progress` (existing), `stories_finished_count`, `count_available`, `STORIES_TO_COMPLETE` (Task 3), `read_active_module` (existing).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_modules_path.py
"""GET /modules: full path with derived completed/unlocked/is_current states."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from klara.curriculum.library import STORIES_TO_COMPLETE
from klara.models import Module, Story, StoryLibrary, StoryView, User
from klara.models.enums import CEFRLevel

CONTENT = {"sentences": [{"target": "Hallo.", "native": "Hola.", "new_words": []}], "comprehension_questions": []}


@pytest.mark.asyncio
async def test_list_modules_states(client, db_session):
    # client fixture: authenticated httpx AsyncClient (follow the pattern used
    # by tests that already call protected endpoints, e.g. test_modules.py —
    # reuse ITS login/user fixture verbatim).
    # Arrange three modules; user finished 3 stories in m1 and is current on m2.
    from sqlalchemy import select

    user = (await db_session.execute(select(User).limit(1))).scalar_one()  # the client fixture's user
    mods = []
    for seq in (1, 2, 3):
        m = Module(
            id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1,
            sequence_order=seq, title=f"M{seq}", can_dos=[], grammatical_focus=[],
        )
        db_session.add(m)
        mods.append(m)
    await db_session.flush()
    for i in range(STORIES_TO_COMPLETE):
        s = Story(
            user_id=user.id, level=CEFRLevel.A1, target_language="de",
            native_language="es", title=f"S{i}", content=CONTENT,
            target_vocab_item_ids=[], module_id=mods[0].id,
        )
        db_session.add(s)
        await db_session.flush()
        db_session.add(StoryView(story_id=s.id, user_id=user.id, finished_at=datetime.now(UTC)))
    db_session.add(StoryLibrary(
        module_id=mods[1].id, language="de", native_language="es", level=CEFRLevel.A1,
        title="L", content=CONTENT, target_vocab_item_ids=[], source="seed",
        content_hash="c" * 64,
    ))
    user.current_module_id = mods[1].id
    await db_session.commit()

    resp = await client.get("/api/v1/modules")
    assert resp.status_code == 200
    items = resp.json()
    assert [it["sequence_order"] for it in items] == [1, 2, 3]
    m1, m2, m3 = items
    assert m1["completed"] is True and m1["unlocked"] is True
    assert m2["is_current"] is True and m2["unlocked"] is True
    assert m2["library_available"] == 1
    assert m3["completed"] is False and m3["unlocked"] is False
    assert m2["stories_to_complete"] == STORIES_TO_COMPLETE
```

**Implementation note for the test:** before writing it, open an existing endpoint test (e.g. `backend/tests/test_modules.py`) and copy its authenticated-client + user fixture arrangement exactly — the sketch above marks the two places that depend on it (getting the client's `User` row, and the auth setup). Everything else is literal.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_modules_path.py -v`
Expected: FAIL — 404/405 (route doesn't exist) or schema import error.

- [ ] **Step 3: Implement schema + endpoint**

Append to `backend/src/klara/schemas/module.py`:

```python
class ModulePathItemOut(BaseModel):
    id: UUID
    sequence_order: int
    title: str
    cefr_level: CEFRLevel
    can_dos: list[str]
    grammatical_focus: list[str]
    encountered: int
    mastered: int
    total: int
    gender_encountered: int
    gender_mastered: int
    gender_total: int
    stories_finished: int
    stories_to_complete: int
    completed: bool
    is_current: bool
    unlocked: bool
    library_available: int
```

Append to `backend/src/klara/routers/modules.py` (add imports: `select` from sqlalchemy, `Module` from klara.models, `count_available`, `stories_finished_count`, `STORIES_TO_COMPLETE` from `klara.curriculum.library`, `ModulePathItemOut`):

```python
@router.get("", response_model=list[ModulePathItemOut])
async def list_modules(db: DBSession, user: CurrentUser) -> list[ModulePathItemOut]:
    """The full path for the user's target language, ordered. Locked/completed
    are derived on read — no completion-history table (accepted debt, spec §5).
    ponytail: ~5 queries per module × 8 modules; fine at this scale, batch if a
    language ever ships 50 modules."""
    modules = (
        (
            await db.execute(
                select(Module)
                .where(Module.language == user.target_language)
                .order_by(Module.sequence_order.asc())
            )
        )
        .scalars()
        .all()
    )
    active = await read_active_module(db, user)
    out: list[ModulePathItemOut] = []
    prev_completed = True  # first module is always unlocked
    for m in modules:
        encountered, mastered, total = await module_progress(db, user_id=user.id, module_id=m.id)
        g_enc, g_mast, g_total = await module_gender_progress(db, user_id=user.id, module_id=m.id)
        finished = await stories_finished_count(db, user_id=user.id, module_id=m.id)
        completed = finished >= STORIES_TO_COMPLETE
        unlocked = prev_completed or (active is not None and m.sequence_order <= active.sequence_order)
        available = await count_available(
            db, user_id=user.id, module_id=m.id, native_language=user.native_language
        )
        out.append(
            ModulePathItemOut(
                id=m.id,
                sequence_order=m.sequence_order,
                title=m.title,
                cefr_level=m.cefr_level,
                can_dos=m.can_dos or [],
                grammatical_focus=m.grammatical_focus or [],
                encountered=encountered,
                mastered=mastered,
                total=total,
                gender_encountered=g_enc,
                gender_mastered=g_mast,
                gender_total=g_total,
                stories_finished=finished,
                stories_to_complete=STORIES_TO_COMPLETE,
                completed=completed,
                is_current=active is not None and m.id == active.id,
                unlocked=unlocked,
                library_available=available,
            )
        )
        prev_completed = completed
    return out
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_modules_path.py tests/test_modules.py -v`
Expected: all PASS (existing /modules/current tests stay green).

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/schemas/module.py backend/src/klara/routers/modules.py backend/tests/test_modules_path.py
git commit -m "feat(path): GET /modules — full path with derived states"
```

---

### Task 5: POST /modules/{id}/story — the instant claim

**Files:**
- Modify: `backend/src/klara/routers/modules.py`
- Test: `backend/tests/test_claim_story.py`

**Interfaces:**
- Produces: `POST /api/v1/modules/{module_id}/story` → 201 `StoryOut` (same shape the reader already renders). 404 `detail="module.not_found"` for bad module; 404 `detail="library.empty"` when no entry is available (the frontend switches its CTA on this code).
- Consumes: `pick_library_entry`, `claim_library_entry` (Task 3); `_serialize_story`, `_load_words` imported from `klara.routers.stories`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_claim_story.py
"""POST /modules/{id}/story: clone-on-claim, pointer move, 404 codes."""

from __future__ import annotations

import uuid

import pytest

from klara.models import Module, StoryLibrary
from klara.models.enums import CEFRLevel

CONTENT = {
    "sentences": [{"target": "Ich trinke Kaffee.", "native": "Bebo café.", "new_words": []}],
    "comprehension_questions": [],
}


@pytest.mark.asyncio
async def test_claim_clones_and_moves_pointer(client, db_session):
    module = Module(
        id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1,
        sequence_order=1, title="En el café", can_dos=[], grammatical_focus=[],
    )
    db_session.add(module)
    await db_session.flush()
    db_session.add(StoryLibrary(
        module_id=module.id, language="de", native_language="es", level=CEFRLevel.A1,
        title="Der Kaffee", content=CONTENT, target_vocab_item_ids=[],
        source="seed", content_hash="d" * 64,
    ))
    await db_session.commit()

    resp = await client.post(f"/api/v1/modules/{module.id}/story")
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Der Kaffee"
    assert body["content"]["sentences"][0]["target"] == "Ich trinke Kaffee."

    # Second claim: entry already seen by this user → library.empty.
    resp2 = await client.post(f"/api/v1/modules/{module.id}/story")
    assert resp2.status_code == 404
    assert resp2.json()["detail"] == "library.empty"


@pytest.mark.asyncio
async def test_claim_unknown_module_404(client):
    resp = await client.post(f"/api/v1/modules/{uuid.uuid4()}/story")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "module.not_found"
```

(Same note as Task 4: reuse the repo's existing authenticated `client` fixture pattern.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_claim_story.py -v`
Expected: FAIL — 405/404 route not found.

- [ ] **Step 3: Implement the endpoint**

Append to `backend/src/klara/routers/modules.py` (add imports: `HTTPException`, `status` from fastapi; `UUID` from uuid; `pick_library_entry`, `claim_library_entry` from `klara.curriculum.library`; `Module` already imported in Task 4; `StoryOut` from `klara.schemas.story`; `_load_words`, `_serialize_story` from `klara.routers.stories`):

```python
@router.post("/{module_id}/story", response_model=StoryOut, status_code=status.HTTP_201_CREATED)
async def claim_module_story(module_id: UUID, db: DBSession, user: CurrentUser) -> StoryOut:
    """Instant story: clone the next unseen library entry for this module into
    the user's stories. No LLM in this path — milliseconds, audio already warm
    from library-build precache. detail codes ('module.not_found',
    'library.empty') are contracts with the frontend, not display strings."""
    module = await db.get(Module, module_id)
    if module is None or module.language != user.target_language:
        raise HTTPException(status_code=404, detail="module.not_found")
    entry = await pick_library_entry(
        db, user_id=user.id, module_id=module.id, native_language=user.native_language
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="library.empty")
    story = await claim_library_entry(db, user=user, entry=entry, module=module)
    await db.commit()
    words = await _load_words(db, list(story.target_vocab_item_ids or []))
    return _serialize_story(story, words, user.native_language)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_claim_story.py -v`
Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/routers/modules.py backend/tests/test_claim_story.py
git commit -m "feat(path): POST /modules/{id}/story — copy-on-claim instant story"
```

---

### Task 6: POST /stories/{id}/finish — the completion event

**Files:**
- Modify: `backend/src/klara/schemas/finish.py` (add `StoryFinishOut`)
- Modify: `backend/src/klara/routers/stories.py`
- Test: `backend/tests/test_story_finish.py`

**Interfaces:**
- Produces: `POST /api/v1/stories/{story_id}/finish` → `StoryFinishOut {finished_at: datetime, module_advanced: bool}`. Idempotent (re-finish keeps the first timestamp). Activates the dormant `StoryView` table.
- Consumes: `advance_module_if_completed` (Task 3), `_load_or_404` (existing), `Story.module_id` (Task 1).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_story_finish.py
"""POST /stories/{id}/finish: StoryView write + completar advancement."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from klara.curriculum.library import STORIES_TO_COMPLETE
from klara.models import Module, Story, StoryView, User
from klara.models.enums import CEFRLevel

CONTENT = {"sentences": [{"target": "Hallo.", "native": "Hola.", "new_words": []}], "comprehension_questions": []}


@pytest.mark.asyncio
async def test_finish_is_idempotent_and_advances_on_third(client, db_session):
    user = (await db_session.execute(select(User).limit(1))).scalar_one()
    m1 = Module(id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1,
                sequence_order=1, title="M1", can_dos=[], grammatical_focus=[])
    m2 = Module(id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1,
                sequence_order=2, title="M2", can_dos=[], grammatical_focus=[])
    db_session.add_all([m1, m2])
    await db_session.flush()
    user.current_module_id = m1.id
    stories = []
    for i in range(STORIES_TO_COMPLETE):
        s = Story(user_id=user.id, level=CEFRLevel.A1, target_language="de",
                  native_language="es", title=f"S{i}", content=CONTENT,
                  target_vocab_item_ids=[], module_id=m1.id)
        db_session.add(s)
        stories.append(s)
    await db_session.commit()

    r1 = await client.post(f"/api/v1/stories/{stories[0].id}/finish")
    assert r1.status_code == 200
    assert r1.json()["module_advanced"] is False
    first_ts = r1.json()["finished_at"]

    # Idempotent: same timestamp, still one view row.
    r1b = await client.post(f"/api/v1/stories/{stories[0].id}/finish")
    assert r1b.json()["finished_at"] == first_ts

    await client.post(f"/api/v1/stories/{stories[1].id}/finish")
    r3 = await client.post(f"/api/v1/stories/{stories[2].id}/finish")
    assert r3.json()["module_advanced"] is True

    await db_session.refresh(user)
    assert user.current_module_id == m2.id
    views = (await db_session.execute(select(StoryView).where(StoryView.user_id == user.id))).scalars().all()
    assert len(views) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_story_finish.py -v`
Expected: FAIL — 405/404 route not found.

- [ ] **Step 3: Implement schema + endpoint**

Append to `backend/src/klara/schemas/finish.py`:

```python
class StoryFinishOut(BaseModel):
    finished_at: datetime
    module_advanced: bool
```

(Add `from datetime import datetime` if not already imported.)

In `backend/src/klara/routers/stories.py`: import `StoryView` (extend the existing `klara.models` import), `advance_module_if_completed` from `klara.curriculum.library`, `StoryFinishOut` from `klara.schemas.finish`. Append:

```python
@router.post("/{story_id}/finish", response_model=StoryFinishOut)
async def finish_story(
    story_id: UUID, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> StoryFinishOut:
    """The 'historia completada' event (fires when the reader reaches the
    Finish summary). Idempotent. Feeds the completar gate."""
    story = await _load_or_404(db, story_id, user.id, locale)
    view = (
        await db.execute(
            select(StoryView)
            .where(StoryView.story_id == story.id, StoryView.user_id == user.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if view is None:
        view = StoryView(story_id=story.id, user_id=user.id)
        db.add(view)
    if view.finished_at is None:
        view.finished_at = datetime.now(UTC)
    advanced = False
    if story.module_id is not None and story.module_id == user.current_module_id:
        await db.flush()  # the new view must be visible to the count
        advanced = await advance_module_if_completed(db, user=user)
    await db.commit()
    return StoryFinishOut(finished_at=view.finished_at, module_advanced=advanced)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && uv run pytest tests/test_story_finish.py -v`
Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/schemas/finish.py backend/src/klara/routers/stories.py backend/tests/test_story_finish.py
git commit -m "feat(path): POST /stories/{id}/finish — StoryView write + completar advance"
```

---

### Task 7: create_story extensions — module_id, topic_origin, pool recycle, module list filter

**Files:**
- Modify: `backend/src/klara/schemas/story.py`
- Modify: `backend/src/klara/routers/stories.py`
- Modify: `backend/src/klara/services/finish_lessons.py` (one prompt line)
- Test: `backend/tests/test_create_story_module.py`

**Interfaces:**
- Produces:
  - `StoryCreateRequest` gains `module_id: UUID | None = None` and `topic_origin: Literal["chip", "free", "none"] = "none"`.
  - `StoryOut` gains `module_id: UUID | None = None` (frontend uses it for "next story in module").
  - `GET /stories` gains optional `module_id` query filter.
  - Successful module-conditioned generations recycle into the pool per Task 3 rules.
- Consumes: `maybe_recycle_to_library` (Task 3), `GeneratedStory.dropped_lemmas` (Task 2).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_create_story_module.py
"""create_story: explicit module conditioning, provenance, pool recycle."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from klara.dependencies import get_story_llm
from klara.llm.base import LLMResponse
from klara.main import app
from klara.models import Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel

STORY_JSON = json.dumps({
    "title": "Der Kaffee",
    "sentences": [{
        "target": "Ich trinke Kaffee.",
        "native": "Bebo café.",
        "new_words": ["Kaffee"],
        "breakdown": [{"word": "Kaffee", "translation": "café"}],
    }],
    "comprehension_questions": [],
    "target_words": [{"lemma": "Kaffee", "pos": "noun", "gender": "der", "translation": "café"}],
    "quiz_items": None,
})


class FakeLLM:
    async def complete(self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None):
        return LLMResponse(content=STORY_JSON, model="fake", provider="fake", cost_usd=0.001)

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_create_with_module_sets_provenance_and_recycles(client, db_session):
    app.dependency_overrides[get_story_llm] = lambda: FakeLLM()
    try:
        module = Module(id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1,
                        sequence_order=1, title="En el café", can_dos=[], grammatical_focus=[])
        db_session.add(module)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/stories",
            json={"topic": "pedir un café", "module_id": str(module.id), "topic_origin": "chip"},
        )
        assert resp.status_code == 201
        assert resp.json()["module_id"] == str(module.id)

        story = (await db_session.execute(select(Story))).scalar_one()
        assert story.module_id == module.id

        user = (await db_session.execute(select(User).limit(1))).scalar_one()
        assert user.current_module_id == module.id  # explicit module moves the pointer

        # chip topic + full coverage → recycled into the pool
        entry = (await db_session.execute(select(StoryLibrary))).scalar_one()
        assert entry.source == "pool"
        assert entry.source_story_id == story.id
    finally:
        app.dependency_overrides.pop(get_story_llm, None)


@pytest.mark.asyncio
async def test_free_topic_is_not_recycled(client, db_session):
    app.dependency_overrides[get_story_llm] = lambda: FakeLLM()
    try:
        module = Module(id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1,
                        sequence_order=1, title="M", can_dos=[], grammatical_focus=[])
        db_session.add(module)
        await db_session.commit()
        resp = await client.post(
            "/api/v1/stories",
            json={"topic": "mi perra Luna", "module_id": str(module.id), "topic_origin": "free"},
        )
        assert resp.status_code == 201
        n = (await db_session.execute(select(StoryLibrary))).scalars().all()
        assert n == []
    finally:
        app.dependency_overrides.pop(get_story_llm, None)
```

(If existing endpoint tests already override the story LLM differently — check `test_story_curriculum.py` first and copy its override idiom instead.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_create_story_module.py -v`
Expected: FAIL — 422 (unknown fields rejected? pydantic ignores extras by default — then the module assertion fails) or `module_id` missing from response.

- [ ] **Step 3: Implement**

`backend/src/klara/schemas/story.py`:

```python
from typing import Literal  # add to imports

class StoryCreateRequest(BaseModel):
    topic: str | None = None
    level: CEFRLevel | None = None
    # Explicit module conditioning (path module screen). None → active module.
    module_id: UUID | None = None
    # The backend can't distinguish a suggestion chip from free text; the pool
    # must never serve personal free-text topics to other users (spec §7).
    topic_origin: Literal["chip", "free", "none"] = "none"
```

`StoryOut` gains (after `curriculum_note`):

```python
    module_id: UUID | None = None
```

In `backend/src/klara/routers/stories.py`:

1. Add imports: `structlog`; `Module` (extend the `klara.models` import); `maybe_recycle_to_library` from `klara.curriculum.library`. Add `log = structlog.get_logger(__name__)` after the router definition.
2. In `_serialize_story`, add `module_id=story.module_id,` to the `StoryOut(...)` construction.
3. In `create_story`, replace the module-resolution block:

```python
    level = payload.level or user.level
    if payload.module_id is not None:
        active = await db.get(Module, payload.module_id)
        if active is None or active.language != user.target_language:
            raise HTTPException(status_code=404, detail="module.not_found")
        # Starting a story in module M moves the pointer to M (gated suave).
        user.current_module_id = active.id
    else:
        active = await ensure_active_module(db, user)
    if active is not None:
        target_lemmas = await module_target_lemmas(db, active)
        mod_vids = await module_vocab_ids(db, active)
        objective = _module_objective(active)
    else:
        ...  # (unchanged fallback branch)
```

4. After the `enroll_cards` block and before `await db.commit()`:

```python
    result.story.module_id = active.id if active is not None else None
    # Pool growth is best-effort: never let it break story creation.
    try:
        await maybe_recycle_to_library(
            db,
            story=result.story,
            dropped_lemmas=result.dropped_lemmas,
            topic=payload.topic,
            topic_origin=payload.topic_origin,
        )
    except Exception:
        log.warning("library.pool.recycle_failed", story_id=str(result.story.id))
    await db.commit()
```

5. `list_stories` gains the filter — add parameter `module_id: UUID | None = Query(None)` and:

```python
    if module_id is not None:
        stmt = stmt.where(Story.module_id == module_id)
```

6. `backend/src/klara/services/finish_lessons.py` line 90 — replace:

```
- NO reveles una historia específica de mañana (no hay ninguna en cola). El tono es vibe-set, no spoiler.
```

with:

```
- NO reveles una historia específica de mañana. El tono es vibe-set, no spoiler.
```

- [ ] **Step 4: Run the new test + neighbors**

Run: `cd backend && uv run pytest tests/test_create_story_module.py tests/test_story_curriculum.py tests/test_klara_note.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && uv run pytest -x -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/schemas/story.py backend/src/klara/routers/stories.py backend/src/klara/services/finish_lessons.py backend/tests/test_create_story_module.py
git commit -m "feat(path): module-conditioned create_story + pool recycle + module list filter"
```

---

### Task 8: Seed script — build_story_library

**Files:**
- Create: `backend/src/klara/scripts/build_story_library.py`
- Test: `backend/tests/test_build_library.py`

**Interfaces:**
- Produces: `uv run python -m klara.scripts.build_story_library` — seeds 8 modules × 5 es→de stories into `story_library`, idempotent by content_hash, TTS-warmed. Testable core:
  ```python
  async def build_library(
      db, llm, *, language: str, native: str, per_module: int,
      warm_audio: Callable[[list[str]], Awaitable[None]] | None = None,
      max_attempts: int = 3,
  ) -> int   # number of entries inserted
  ```
- Consumes: `generate_story_draft` (Task 2), `library_content_hash` (Task 3), `precache_texts`/`collect_story_texts` (existing), `_module_objective` idiom (reimplemented locally to avoid importing a router).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_build_library.py
"""build_library: coverage gate, idempotency, per-module counts (FakeLLM)."""

from __future__ import annotations

import json
import uuid

import pytest

from klara.llm.base import LLMResponse
from klara.models import Module, StoryLibrary
from klara.models.enums import CEFRLevel
from klara.scripts.build_story_library import build_library
from sqlalchemy import func, select


def _story_json(sentence: str, lemma: str) -> str:
    return json.dumps({
        "title": f"Geschichte {lemma}",
        "sentences": [{"target": sentence, "native": "x", "new_words": [lemma],
                       "breakdown": [{"word": lemma, "translation": "x"}]}],
        "comprehension_questions": [],
        "target_words": [{"lemma": lemma, "pos": "noun", "gender": "der", "translation": "x"}],
        "quiz_items": None,
    })


class SequenceLLM:
    """Returns a different story per call so content hashes differ."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None):
        self.calls += 1
        return LLMResponse(
            content=_story_json(f"Der Kaffee Nummer {self.calls} ist gut. Kaffee!", "Kaffee"),
            model="fake", provider="fake", cost_usd=0.001,
        )

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_build_inserts_per_module_and_is_idempotent(db_session):
    # Seed the module + its vocab via the real loader (same path prod uses).
    from klara.curriculum.modules import load_modules

    await load_modules(db_session, language="de", modules=[{
        "sequence_order": 1, "title": "En el café", "cefr_level": "A1",
        "can_dos": ["pedir"], "grammatical_focus": ["género"],
        "vocab": [{"lemma": "Kaffee", "pos": "noun", "gender": "der", "translations": {"es": "café"}}],
    }])
    await db_session.commit()

    warmed: list[list[str]] = []

    async def warm(texts: list[str]) -> None:
        warmed.append(texts)

    n = await build_library(db_session, SequenceLLM(), language="de", native="es",
                            per_module=2, warm_audio=warm)
    await db_session.commit()
    assert n == 2
    assert len(warmed) == 2
    count = (await db_session.execute(select(func.count()).select_from(StoryLibrary))).scalar_one()
    assert count == 2
    row = (await db_session.execute(select(StoryLibrary).limit(1))).scalar_one()
    assert row.source == "seed"
    assert row.native_language == "es"

    # Re-run: hashes differ per call BUT the per-module target count is already
    # met, so nothing new is inserted.
    n2 = await build_library(db_session, SequenceLLM(), language="de", native="es",
                             per_module=2, warm_audio=warm)
    assert n2 == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_build_library.py -v`
Expected: FAIL — `ModuleNotFoundError: klara.scripts.build_story_library`

- [ ] **Step 3: Implement the script**

```python
# backend/src/klara/scripts/build_story_library.py
"""Build the curated seed story library (spec 2026-07-03 §8).

Usage:
    uv run python -m klara.scripts.build_story_library

Generates PER_MODULE stories per German A1 module for native_language=es using
the real generation pipeline (coverage-gated), inserts them as source='seed',
and pre-warms the global TTS audio cache. Idempotent: modules that already
have >= PER_MODULE active seed entries for the pair are skipped, and duplicate
content hashes are never inserted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.config import get_settings
from klara.curriculum.library import library_content_hash
from klara.curriculum.modules import module_target_lemmas
from klara.db import dispose_engine, get_sessionmaker, init_engine
from klara.llm.base import LLMClient
from klara.llm.litellm_impl import LiteLLMClient
from klara.models import Module, StoryLibrary
from klara.services.story_gen import StoryGenerationError, generate_story_draft
from klara.services.tts_precache import collect_story_texts, precache_texts

log = structlog.get_logger(__name__)

PER_MODULE = 5
MAX_ATTEMPTS = 3

# Curated topics per module sequence_order. Each varies scene/protagonist so
# the module's stories don't read as clones (module-level substitute for the
# per-user recent-vocab dedup, spec §8).
TOPICS: dict[int, list[str]] = {
    1: [
        "pedir un café y un pastel",
        "una tarde de lluvia en el café",
        "el primer día de trabajo de una mesera",
        "dos amigos comparten una tarta",
        "un turista pide en alemán por primera vez",
    ],
    2: [
        "conocer a un vecino nuevo",
        "presentarse el primer día de clase",
        "un encuentro en el tren",
        "una llamada telefónica formal",
        "presentar a un amigo en una fiesta",
    ],
    3: [
        "una cena familiar de domingo",
        "mostrar fotos de la familia",
        "la visita de la abuela",
        "un hermano pequeño curioso",
        "planear un cumpleaños en familia",
    ],
    4: [
        "llegar tarde a una cita",
        "comprar entradas de cine",
        "preguntar la hora en la calle",
        "el horario del tren",
        "contar el dinero del mercado",
    ],
    5: [
        "comprar fruta en el mercado",
        "buscar un regalo",
        "una oferta en el supermercado",
        "devolver una camisa",
        "la lista de compras olvidada",
    ],
    6: [
        "mudanza a un apartamento nuevo",
        "buscar las llaves perdidas",
        "ordenar la sala",
        "una visita sorpresa",
        "arreglar la cocina",
    ],
    7: [
        "una mañana con prisa",
        "la rutina de un estudiante",
        "el desayuno perfecto",
        "una noche tranquila",
        "el despertador que no sonó",
    ],
    8: [
        "perderse en el U-Bahn",
        "preguntar por una dirección",
        "el autobús equivocado",
        "un paseo en bicicleta",
        "comprar un billete de tren",
    ],
}


def _module_objective(module: Module) -> str:
    can_dos = "; ".join(module.can_dos or [])
    focus = "; ".join(module.grammatical_focus or [])
    parts = ["OBJETIVO DEL MÓDULO (la historia debe servir este objetivo, sin forzar):"]
    if can_dos:
        parts.append(f"Can-do: {can_dos}.")
    if focus:
        parts.append(f"Foco gramatical: {focus}.")
    return " ".join(parts)


async def _seed_count(db: AsyncSession, module_id, native: str) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(StoryLibrary)
            .where(
                StoryLibrary.module_id == module_id,
                StoryLibrary.native_language == native,
                StoryLibrary.is_active.is_(True),
                StoryLibrary.source == "seed",
            )
        )
    ).scalar_one()


async def build_library(
    db: AsyncSession,
    llm: LLMClient,
    *,
    language: str,
    native: str,
    per_module: int,
    warm_audio: Callable[[list[str]], Awaitable[None]] | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> int:
    modules = (
        (
            await db.execute(
                select(Module)
                .where(Module.language == language)
                .order_by(Module.sequence_order.asc())
            )
        )
        .scalars()
        .all()
    )
    inserted = 0
    for module in modules:
        have = await _seed_count(db, module.id, native)
        if have >= per_module:
            log.info("library.build.skip_full", module=module.title, have=have)
            continue
        topics = TOPICS.get(module.sequence_order, [])[: per_module]
        lemmas = await module_target_lemmas(db, module)
        objective = _module_objective(module)
        for topic in topics[have:]:
            draft = None
            for attempt in range(max_attempts):
                try:
                    candidate = await generate_story_draft(
                        db,
                        llm,
                        level=module.cefr_level,
                        target_language=language,
                        native_language=native,
                        learning_context=None,
                        topic=topic,
                        model=None,
                        target_lemmas=lemmas,
                        module_objective=objective,
                        avoid_lemmas=[],
                    )
                except StoryGenerationError as exc:
                    log.warning("library.build.gen_failed", topic=topic, attempt=attempt, error=str(exc))
                    continue
                if candidate.dropped_lemmas:
                    log.info(
                        "library.build.coverage_retry",
                        topic=topic,
                        attempt=attempt,
                        dropped=candidate.dropped_lemmas,
                    )
                    continue
                draft = candidate
                break
            if draft is None:
                log.warning("library.build.skipped", module=module.title, topic=topic)
                continue
            h = library_content_hash(draft.content)
            dup = (
                await db.execute(select(StoryLibrary.id).where(StoryLibrary.content_hash == h))
            ).first()
            if dup is not None:
                log.info("library.build.dup_hash", topic=topic)
                continue
            db.add(
                StoryLibrary(
                    module_id=module.id,
                    language=language,
                    native_language=native,
                    level=module.cefr_level,
                    title=draft.title,
                    content=draft.content,
                    target_vocab_item_ids=[w.id for w in draft.target_words],
                    quiz_items=draft.quiz_items,
                    insight_title=draft.insight_title,
                    insight_body=draft.insight_body,
                    topic=topic,
                    source="seed",
                    content_hash=h,
                    generated_by_provider=draft.provider,
                    generated_by_model=draft.model,
                    generation_cost_usd=draft.cost_usd,
                )
            )
            await db.flush()
            inserted += 1
            if warm_audio is not None:
                words = [
                    {"lemma": w.lemma, "example_target": w.example_target}
                    for w in draft.target_words
                ]
                texts = collect_story_texts(draft.content, words)
                if draft.title:
                    texts = [draft.title] + [t for t in texts if t != draft.title]
                await warm_audio(texts)
            log.info("library.build.inserted", module=module.title, topic=topic, cost=draft.cost_usd)
    return inserted


async def _run() -> None:
    settings = get_settings()
    init_engine(settings)
    try:
        llm = LiteLLMClient(
            settings,
            default_model=settings.llm_story_model,
            default_extra_body=settings.llm_story_extra_body,
        )

        async def warm(texts: list[str]) -> None:
            await precache_texts(settings, texts, "de")

        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            n = await build_library(
                db, llm, language="de", native="es", per_module=PER_MODULE, warm_audio=warm
            )
            await db.commit()
        print(f"Insertadas {n} historia(s) en la librería.")
    finally:
        await dispose_engine()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test**

Run: `cd backend && uv run pytest tests/test_build_library.py -v`
Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/scripts/build_story_library.py backend/tests/test_build_library.py
git commit -m "feat(path): build_story_library seed script (8 modules x 5, es->de)"
```

---

### Task 9: Frontend API client + types

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Produces (consumed by Tasks 10-12):
  ```ts
  export interface ModulePathItem {
    id: string; sequence_order: number; title: string; cefr_level: string;
    can_dos: string[]; grammatical_focus: string[];
    encountered: number; mastered: number; total: number;
    gender_encountered: number; gender_mastered: number; gender_total: number;
    stories_finished: number; stories_to_complete: number;
    completed: boolean; is_current: boolean; unlocked: boolean;
    library_available: number;
  }
  // Story gains: module_id?: string | null;
  api.listModules(): Promise<ModulePathItem[]>
  api.claimModuleStory(moduleId: string): Promise<Story>
  api.finishStory(storyId: string): Promise<{ finished_at: string; module_advanced: boolean }>
  api.listModuleStories(moduleId: string, limit?: number): Promise<StoryListItem[]>
  api.createStory(topic?: string, opts?: { moduleId?: string; topicOrigin?: "chip" | "free" | "none" })
  ```

- [ ] **Step 1: Add the type + extend Story**

In `frontend/src/api/types.ts`: append `ModulePathItem` (exact shape above) after `ModuleCurrent`, and add `module_id?: string | null;` to the `Story` interface.

- [ ] **Step 2: Extend the client**

In `frontend/src/api/client.ts`, replace `createStory` and add the new calls next to `currentModule`:

```ts
  createStory: (
    topic?: string,
    opts?: { moduleId?: string; topicOrigin?: "chip" | "free" | "none" }
  ) =>
    request<Story>("/stories", {
      method: "POST",
      body: JSON.stringify({
        topic: topic ?? null,
        module_id: opts?.moduleId ?? null,
        topic_origin: opts?.topicOrigin ?? "none",
      }),
    }),

  listModules: () => request<ModulePathItem[]>("/modules"),

  claimModuleStory: (moduleId: string) =>
    request<Story>(`/modules/${moduleId}/story`, { method: "POST" }),

  finishStory: (storyId: string) =>
    request<{ finished_at: string; module_advanced: boolean }>(
      `/stories/${storyId}/finish`,
      { method: "POST" }
    ),

  listModuleStories: (moduleId: string, limit = 20) =>
    request<StoryListItem[]>(`/stories?limit=${limit}&module_id=${moduleId}`),
```

Add `ModulePathItem` to the types import at the top of `client.ts`.

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run typecheck`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat(path): frontend API client for modules path + claim + finish"
```

---

### Task 10: i18n — `path` and `module` key groups in all 6 locales

**Files:**
- Modify: `frontend/src/locales/es/common.json`, `en/common.json`, `de/common.json`, `fr/common.json`, `ja/common.json`, `pt/common.json`

**Interfaces:**
- Produces the keys consumed by Tasks 11-12: `path.*`, `module.*`, `story.end.cta.nextInModule`, `story.end.cta.backToPath`.

- [ ] **Step 1: Add the key groups**

Add as NEW top-level groups (after `"home"`) in each locale, plus two keys inside the existing `story.end.cta` group. **es** (source of truth):

```json
"path": {
  "kicker": "Tu ruta",
  "continue": "Continuar aquí",
  "completedTag": "Completado",
  "lockedTag": "Bloqueado",
  "startAnyway": "Empezar aquí igual",
  "stories": "{{count}} de {{total}} historias",
  "words": "{{count}} de {{total}} palabras",
  "empty": "Aún no hay ruta para este idioma. Mientras tanto, genera historias libres."
},
"module": {
  "back": "Volver a la ruta",
  "canDo": "Vas a poder",
  "grammarFocus": "Foco gramatical",
  "readStory": "Leer una historia",
  "createStory": "Crear mi propia historia",
  "noLibrary": "No hay historias listas — crea la tuya",
  "yourStories": "Tus historias de este módulo",
  "storiesDone": "{{count}} de {{total}} historias completadas",
  "mastered": "{{count}} de {{total}} palabras dominadas",
  "gender": "der·die·das {{count}} de {{total}}",
  "claimError": "No se pudo abrir la historia. Intenta otra vez."
}
```

`story.end.cta` additions (es): `"nextInModule": "Siguiente historia del módulo"`, `"backToPath": "Volver a la ruta"`.

**en**:

```json
"path": {
  "kicker": "Your path",
  "continue": "Continue here",
  "completedTag": "Completed",
  "lockedTag": "Locked",
  "startAnyway": "Start here anyway",
  "stories": "{{count}} of {{total}} stories",
  "words": "{{count}} of {{total}} words",
  "empty": "No path for this language yet. Meanwhile, generate free stories."
},
"module": {
  "back": "Back to the path",
  "canDo": "You will be able to",
  "grammarFocus": "Grammar focus",
  "readStory": "Read a story",
  "createStory": "Create my own story",
  "noLibrary": "No ready stories — create your own",
  "yourStories": "Your stories in this module",
  "storiesDone": "{{count}} of {{total}} stories completed",
  "mastered": "{{count}} of {{total}} words mastered",
  "gender": "der·die·das {{count}} of {{total}}",
  "claimError": "Couldn't open the story. Try again."
}
```

`story.end.cta`: `"nextInModule": "Next story in this module"`, `"backToPath": "Back to the path"`.

**de**:

```json
"path": {
  "kicker": "Dein Weg",
  "continue": "Hier weitermachen",
  "completedTag": "Abgeschlossen",
  "lockedTag": "Gesperrt",
  "startAnyway": "Trotzdem hier anfangen",
  "stories": "{{count}} von {{total}} Geschichten",
  "words": "{{count}} von {{total}} Wörtern",
  "empty": "Für diese Sprache gibt es noch keinen Weg. Erzeuge derweil freie Geschichten."
},
"module": {
  "back": "Zurück zum Weg",
  "canDo": "Du wirst können",
  "grammarFocus": "Grammatikfokus",
  "readStory": "Eine Geschichte lesen",
  "createStory": "Meine eigene Geschichte erstellen",
  "noLibrary": "Keine fertigen Geschichten — erstelle deine eigene",
  "yourStories": "Deine Geschichten in diesem Modul",
  "storiesDone": "{{count}} von {{total}} Geschichten abgeschlossen",
  "mastered": "{{count}} von {{total}} Wörtern gemeistert",
  "gender": "der·die·das {{count}} von {{total}}",
  "claimError": "Geschichte konnte nicht geöffnet werden. Versuch es noch einmal."
}
```

`story.end.cta`: `"nextInModule": "Nächste Geschichte im Modul"`, `"backToPath": "Zurück zum Weg"`.

**fr**:

```json
"path": {
  "kicker": "Ton parcours",
  "continue": "Continuer ici",
  "completedTag": "Terminé",
  "lockedTag": "Verrouillé",
  "startAnyway": "Commencer ici quand même",
  "stories": "{{count}} sur {{total}} histoires",
  "words": "{{count}} sur {{total}} mots",
  "empty": "Pas encore de parcours pour cette langue. En attendant, génère des histoires libres."
},
"module": {
  "back": "Retour au parcours",
  "canDo": "Tu sauras",
  "grammarFocus": "Point de grammaire",
  "readStory": "Lire une histoire",
  "createStory": "Créer ma propre histoire",
  "noLibrary": "Pas d'histoires prêtes — crée la tienne",
  "yourStories": "Tes histoires de ce module",
  "storiesDone": "{{count}} sur {{total}} histoires terminées",
  "mastered": "{{count}} sur {{total}} mots maîtrisés",
  "gender": "der·die·das {{count}} sur {{total}}",
  "claimError": "Impossible d'ouvrir l'histoire. Réessaie."
}
```

`story.end.cta`: `"nextInModule": "Histoire suivante du module"`, `"backToPath": "Retour au parcours"`.

**ja**:

```json
"path": {
  "kicker": "学習ルート",
  "continue": "ここから続ける",
  "completedTag": "完了",
  "lockedTag": "ロック中",
  "startAnyway": "ここから始める",
  "stories": "ストーリー {{count}} / {{total}}",
  "words": "単語 {{count}} / {{total}}",
  "empty": "この言語のルートはまだありません。今は自由にストーリーを作りましょう。"
},
"module": {
  "back": "ルートに戻る",
  "canDo": "できるようになること",
  "grammarFocus": "文法フォーカス",
  "readStory": "ストーリーを読む",
  "createStory": "自分のストーリーを作る",
  "noLibrary": "用意されたストーリーがありません — 自分で作りましょう",
  "yourStories": "このモジュールのストーリー",
  "storiesDone": "完了ストーリー {{count}} / {{total}}",
  "mastered": "習得単語 {{count}} / {{total}}",
  "gender": "der·die·das {{count}} / {{total}}",
  "claimError": "ストーリーを開けませんでした。もう一度お試しください。"
}
```

`story.end.cta`: `"nextInModule": "このモジュールの次のストーリー"`, `"backToPath": "ルートに戻る"`.

**pt**:

```json
"path": {
  "kicker": "Sua trilha",
  "continue": "Continuar aqui",
  "completedTag": "Concluído",
  "lockedTag": "Bloqueado",
  "startAnyway": "Começar aqui mesmo assim",
  "stories": "{{count}} de {{total}} histórias",
  "words": "{{count}} de {{total}} palavras",
  "empty": "Ainda não há trilha para este idioma. Enquanto isso, gere histórias livres."
},
"module": {
  "back": "Voltar à trilha",
  "canDo": "Você vai conseguir",
  "grammarFocus": "Foco gramatical",
  "readStory": "Ler uma história",
  "createStory": "Criar minha própria história",
  "noLibrary": "Nenhuma história pronta — crie a sua",
  "yourStories": "Suas histórias deste módulo",
  "storiesDone": "{{count}} de {{total}} histórias concluídas",
  "mastered": "{{count}} de {{total}} palavras dominadas",
  "gender": "der·die·das {{count}} de {{total}}",
  "claimError": "Não foi possível abrir a história. Tente de novo."
}
```

`story.end.cta`: `"nextInModule": "Próxima história do módulo"`, `"backToPath": "Voltar à trilha"`.

- [ ] **Step 2: Verify parity**

Run: `cd frontend && npm run i18n:check`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/locales
git commit -m "feat(path): i18n path/module key groups in all 6 locales"
```

---

### Task 11: Home = the path + path.css

**Files:**
- Modify: `frontend/src/routes/Home.tsx`
- Create: `frontend/src/styles/path.css`
- Modify: `frontend/src/main.tsx` (import path.css)

**Interfaces:**
- Consumes: `api.listModules()`, `ModulePathItem` (Task 9), i18n keys (Task 10).
- Produces: path node click navigates to `/module/:id` (route added in Task 12).

- [ ] **Step 1: Replace the module widget with the path**

In `frontend/src/routes/Home.tsx`:

1. Imports: drop `ModuleCurrent`, add `ModulePathItem`.
2. State: replace `currentModule` with `const [modules, setModules] = useState<ModulePathItem[] | null | undefined>(undefined);`
3. In the fetch effect, replace the `api.currentModule()` block with:

```ts
      try {
        const mods = await api.listModules();
        if (!cancelled) setModules(mods);
      } catch {
        if (!cancelled) setModules(null);
      }
```

4. Replace the whole `home__module` section (lines 102-119) with:

```tsx
      {!loading && modules !== undefined && (
        <section className="path">
          <span className="k-mono path__kicker">{t("path.kicker")}</span>
          {modules && modules.length > 0 ? (
            <ol className="path__list">
              {modules.map((m) => (
                <li key={m.id}>
                  <button
                    className={[
                      "path__node",
                      m.is_current ? "path__node--current" : "",
                      m.completed ? "path__node--completed" : "",
                      !m.unlocked && !m.completed ? "path__node--locked" : "",
                    ].join(" ")}
                    onClick={() => navigate(`/module/${m.id}`)}
                  >
                    <span className="k-mono path__num">
                      {String(m.sequence_order).padStart(2, "0")}
                    </span>
                    <span className="path__body">
                      <span className="path__title">
                        {m.title}
                        {m.completed && <span className="path__check" aria-hidden> ✓</span>}
                      </span>
                      <span className="path__meta k-mono">
                        {m.completed
                          ? t("path.completedTag")
                          : m.is_current
                          ? t("path.stories", { count: m.stories_finished, total: m.stories_to_complete })
                          : !m.unlocked
                          ? t("path.lockedTag")
                          : t("path.words", { count: m.encountered, total: m.total })}
                      </span>
                      <span className="path__bar" aria-hidden>
                        <span
                          className="path__bar-fast"
                          style={{ width: `${m.total ? (m.encountered / m.total) * 100 : 0}%` }}
                        />
                        <span
                          className="path__bar-slow"
                          style={{ width: `${m.total ? (m.mastered / m.total) * 100 : 0}%` }}
                        />
                      </span>
                    </span>
                    <span className="path__cta k-mono">
                      {m.is_current
                        ? t("path.continue")
                        : !m.unlocked && !m.completed
                        ? t("path.startAnyway")
                        : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <p className="path__empty">{t("path.empty")}</p>
          )}
        </section>
      )}
```

- [ ] **Step 2: Write `path.css`**

```css
/* frontend/src/styles/path.css — the learning path on Home + module screen.
   Editorial idiom: k-mono counters, hairline rules, no gamification chrome. */

.path {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 18px 0;
}
.path__kicker {
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--ink-3);
}
.path__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.path__node {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  width: 100%;
  text-align: left;
  background: none;
  border: 0;
  border-bottom: 1px solid var(--rule);
  padding: 14px 2px;
  cursor: pointer;
  color: inherit;
}
.path__node:hover .path__title { color: var(--accent); }
.path__num { font-size: 12px; color: var(--ink-3); padding-top: 3px; }
.path__body { flex: 1; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.path__title { font-family: var(--font-serif); font-size: 18px; }
.path__check { color: var(--accent); }
.path__meta { font-size: 11px; color: var(--ink-3); }
.path__cta { font-size: 11px; color: var(--accent); padding-top: 4px; white-space: nowrap; }
.path__empty { color: var(--ink-3); }

/* Dual progress: fast visible signal (encountered) under slow fill (mastered). */
.path__bar {
  position: relative;
  height: 2px;
  background: var(--rule);
  margin-top: 4px;
  overflow: hidden;
}
.path__bar-fast,
.path__bar-slow {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
}
.path__bar-fast { background: var(--ink-3); opacity: 0.5; }
.path__bar-slow { background: var(--accent); }

.path__node--locked { opacity: 0.55; }
.path__node--current .path__title { font-style: italic; }
.path__node--completed .path__meta { color: var(--accent); }

/* Module screen */
.mod__head { display: flex; flex-direction: column; gap: 8px; margin: 12px 0 18px; }
.mod__title { font-family: var(--font-serif); font-size: 26px; }
.mod__list { list-style: none; margin: 0; padding: 0; }
.mod__facts { display: flex; flex-direction: column; gap: 4px; }
.mod__fact { font-size: 12px; color: var(--ink-3); }
.mod__actions { display: flex; gap: 10px; margin: 18px 0; flex-wrap: wrap; }
.mod__stories { display: flex; flex-direction: column; margin-top: 10px; }
.mod__story {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  background: none;
  border: 0;
  border-bottom: 1px solid var(--rule);
  padding: 10px 2px;
  text-align: left;
  cursor: pointer;
  color: inherit;
}
.mod__story:hover { color: var(--accent); }
```

In `frontend/src/main.tsx`, add `import "./styles/path.css";` next to the other style imports.

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm test`
Expected: clean. (`/module/:id` navigation 404s until Task 12 — fine.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/Home.tsx frontend/src/styles/path.css frontend/src/main.tsx
git commit -m "feat(path): Home renders the module path with dual progress"
```

---

### Task 12: Module screen, route, NewStory + StoryFinish wiring

**Files:**
- Create: `frontend/src/routes/Module.tsx`
- Modify: `frontend/src/App.tsx` (route)
- Modify: `frontend/src/routes/NewStory.tsx` (module param + topic_origin)
- Modify: `frontend/src/routes/Story.tsx` (finish call + next-in-module)
- Modify: `frontend/src/components/StoryFinish.tsx` (NextSteps buttons)

**Interfaces:**
- Consumes: everything from Tasks 9-11.
- Produces: `/module/:id` route; claim flow; finish event fires on summary.

- [ ] **Step 1: Write `Module.tsx`**

```tsx
// frontend/src/routes/Module.tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../api/client";
import type { ModulePathItem, StoryListItem } from "../api/types";

export default function Module() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [mod, setMod] = useState<ModulePathItem | null | undefined>(undefined);
  const [stories, setStories] = useState<StoryListItem[]>([]);
  const [claiming, setClaiming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // ponytail: 8 modules — fetch the list and find; a by-id endpoint can
        // come when a language ships enough modules to matter.
        const mods = await api.listModules();
        if (cancelled) return;
        setMod(mods.find((m) => m.id === id) ?? null);
      } catch {
        if (!cancelled) setMod(null);
      }
      try {
        if (id) {
          const list = await api.listModuleStories(id);
          if (!cancelled) setStories(list);
        }
      } catch {
        /* list stays empty */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function readStory() {
    if (!id || claiming) return;
    setClaiming(true);
    setError(null);
    try {
      const story = await api.claimModuleStory(id);
      navigate(`/story/${story.id}`);
    } catch (e) {
      if (e instanceof ApiError && e.message === "library.empty") {
        navigate(`/story/new?module=${id}`);
      } else {
        setError(t("module.claimError"));
      }
    } finally {
      setClaiming(false);
    }
  }

  if (mod === undefined) {
    return (
      <main className="k-page">
        <div className="story-loading">
          <span className="k-mono">{t("common.loading")}</span>
        </div>
      </main>
    );
  }
  if (mod === null) {
    return (
      <main className="k-page">
        <button className="k-mono k-link" onClick={() => navigate("/")}>{t("module.back")}</button>
        <div className="k-error" role="alert">{t("module.claimError")}</div>
      </main>
    );
  }

  const hasLibrary = mod.library_available > 0;
  return (
    <main className="k-page">
      <button className="k-mono k-link" onClick={() => navigate("/")}>← {t("module.back")}</button>
      <div className="mod__head">
        <span className="k-level">{mod.cefr_level}</span>
        <h1 className="mod__title">{mod.title}</h1>
        <div className="mod__facts">
          {mod.can_dos.length > 0 && (
            <span className="mod__fact">
              <strong>{t("module.canDo")}:</strong> {mod.can_dos.join(" · ")}
            </span>
          )}
          {mod.grammatical_focus.length > 0 && (
            <span className="mod__fact">
              <strong>{t("module.grammarFocus")}:</strong> {mod.grammatical_focus.join(" · ")}
            </span>
          )}
          <span className="mod__fact k-mono">
            {t("module.storiesDone", { count: mod.stories_finished, total: mod.stories_to_complete })}
          </span>
          <span className="mod__fact k-mono">
            {t("module.mastered", { count: mod.mastered, total: mod.total })}
          </span>
          {mod.gender_total > 0 && (
            <span className="mod__fact k-mono">
              {t("module.gender", { count: mod.gender_mastered, total: mod.gender_total })}
            </span>
          )}
        </div>
      </div>

      {error && <div className="k-error" role="alert">{error}</div>}

      <div className="mod__actions">
        <button className="k-btn" onClick={readStory} disabled={claiming}>
          {claiming ? (
            <span className="k-spinner" />
          ) : hasLibrary ? (
            <>{t("module.readStory")} →</>
          ) : (
            <>{t("module.noLibrary")} →</>
          )}
        </button>
        <button
          className="k-btn k-btn--ghost"
          onClick={() => navigate(`/story/new?module=${mod.id}`)}
          disabled={claiming}
        >
          {t("module.createStory")}
        </button>
      </div>

      {stories.length > 0 && (
        <section className="mod__stories">
          <span className="k-mono path__kicker">{t("module.yourStories")}</span>
          {stories.map((s) => (
            <button key={s.id} className="mod__story" onClick={() => navigate(`/story/${s.id}`)}>
              <span>{s.title}</span>
              <span className="k-mono">→</span>
            </button>
          ))}
        </section>
      )}
    </main>
  );
}
```

(Confirm `ApiError` is exported from `client.ts` — it is per `client.ts:51-90`; if the export name differs, match it.)

- [ ] **Step 2: Add the route**

In `frontend/src/App.tsx`: `import Module from "./routes/Module";` and after the `/story/:id` route:

```tsx
          <Route
            path="/module/:id"
            element={
              <ProtectedRoute>
                <Module />
              </ProtectedRoute>
            }
          />
```

- [ ] **Step 3: NewStory — module param + topic_origin**

In `frontend/src/routes/NewStory.tsx`:

1. `import { useNavigate, useSearchParams } from "react-router-dom";` and inside the component: `const [params] = useSearchParams(); const moduleId = params.get("module") ?? undefined;`
2. `generate` gains the origin:

```ts
  async function generate(text: string, origin: "chip" | "free" | "none") {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const story = await api.createStory(text.trim() || undefined, {
        moduleId,
        topicOrigin: text.trim() ? origin : "none",
      });
      navigate(`/story/${story.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    } finally {
      setLoading(false);
    }
  }
```

3. Call sites: form submit → `generate(topic, selected === topic ? "chip" : "free")`; the main button the same; the surprise button → `generate("", "none")`.
4. **Bidirectional fallback (spec §10)**: live generation failing must offer the instant story when one exists. In the `catch` of `generate`, when the request failed with a 502 and we have a module context, claim instead of dead-ending:

```ts
    } catch (e) {
      if (e instanceof ApiError && e.status === 502 && moduleId) {
        try {
          const ready = await api.claimModuleStory(moduleId);
          navigate(`/story/${ready.id}`);
          return;
        } catch {
          /* fall through to the normal error */
        }
      }
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    } finally {
```

(Add `ApiError` to the imports from `../api/client`; confirm the exported error class exposes `status` — it does per `client.ts` — and match its actual name if it differs.)

- [ ] **Step 4: Story finish wiring**

In `frontend/src/routes/Story.tsx`:

1. Fire the finish event when the summary appears — add an effect near the `finished` state:

```tsx
  useEffect(() => {
    if (finished && story) {
      api.finishStory(story.id).catch(() => {});
    }
  }, [finished, story?.id]);
```

2. Pass the module continuation to `StoryFinish` (inside the `finished` render):

```tsx
        onNextInModule={
          story.module_id
            ? async () => {
                try {
                  const next = await api.claimModuleStory(story.module_id!);
                  navigate(`/story/${next.id}`);
                  setFinished(false);
                  practice.reset();
                } catch {
                  navigate(`/story/new?module=${story.module_id}`);
                }
              }
            : undefined
        }
```

In `frontend/src/components/StoryFinish.tsx`:

1. Add `onNextInModule?: () => void;` to BOTH prop interfaces (the outer component at ~line 53 and the NextSteps section at ~line 930), thread it through like `onNew` (~lines 71, 117, 944).
2. In the NextSteps render (~line 1274), before the existing "another" button:

```tsx
        {onNextInModule && (
          <button type="button" className="fin-btn fin-btn--primary" onClick={onNextInModule}>
            {t("story.end.cta.nextInModule")} <span className="fin-arr">→</span>
          </button>
        )}
```

and demote the existing `onNew` button to `fin-btn` (non-primary) when `onNextInModule` is present:

```tsx
        <button
          type="button"
          className={onNextInModule ? "fin-btn" : "fin-btn fin-btn--primary"}
          onClick={onNew}
        >
          {t("story.end.cta.another")} <span className="fin-arr">→</span>
        </button>
```

- [ ] **Step 5: Verify**

Run: `cd frontend && npm run typecheck && npm test && npm run i18n:check && npm run build`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/Module.tsx frontend/src/App.tsx frontend/src/routes/NewStory.tsx frontend/src/routes/Story.tsx frontend/src/components/StoryFinish.tsx
git commit -m "feat(path): module screen, claim flow, finish event, next-in-module"
```

---

### Task 13: End-to-end verification + PR

**Files:** none (verification only).

- [ ] **Step 1: Full backend suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass.

- [ ] **Step 2: Full frontend checks**

Run: `cd frontend && npm run typecheck && npm test && npm run i18n:check && npm run build`
Expected: all clean.

- [ ] **Step 3: Manual e2e against the dev stack**

```bash
docker compose build frontend backend
docker compose up -d
cd backend && uv run alembic upgrade head
uv run python -m klara.scripts.load_de_modules
```

Then with a real LLM key configured, seed a couple of library entries (cheap smoke, not the full 40):
`uv run python -m klara.scripts.build_story_library` (or temporarily set `PER_MODULE = 1` locally for the smoke run — do not commit that change).

In the browser (dev frontend):
- Home shows the path with 8 nodes, node 1 current.
- Tap node 1 → module screen shows can-dos, both CTAs.
- "Leer una historia" opens a story instantly (no "Klara está escribiendo…" wait).
- Finish the story → summary shows "Siguiente historia del módulo"; Home now shows 1/3.
- "Crear mi propia historia" still generates live with the spinner.
- Claim until the library empties → CTA falls back to create.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feat/learning-path
gh pr create --title "feat(path): learning path + per-module story library (copy-on-claim)" --body "$(cat <<'EOF'
## Summary
Guided module path (soft-gated, two signals: completar = 3 finished stories → unlock; dominar = existing SRS 85% gate as the slow ring) + shared per-module story library served by copy-on-claim, so starting a story is instant and generation cost is shared. Hybrid sourcing: curated seed (8 modules × 5, es→de) + pool recycling of coverage-clean, non-personal live generations (cap 50/pair, hash-deduped).

Spec: docs/superpowers/specs/2026-07-03-learning-path-design.md
Plan: docs/superpowers/plans/2026-07-03-learning-path.md

## Heads-up for dev environments
docker-compose bind-mounts source over baked node_modules/deps — run `docker compose build frontend backend` after pulling.

## Prod rollout
1. Deploy runs `alembic upgrade head` (new story_library table + 2 nullable story columns — zero impact on existing rows).
2. One-time on the box: `uv run python -m klara.scripts.build_story_library` inside the backend container (≈40 generations + TTS precache; cost recorded per row in generation_cost_usd).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01NZA6P3qYsv8AcC4aZTocW8
EOF
)"
```

Do NOT merge — the owner merges.

**Prod rollout note (goes in the PR body):** after merge+deploy, SSH to prod and run `uv run python -m klara.scripts.build_story_library` inside the backend container once (≈40 LLM generations + TTS precache; cost is recorded per row in `generation_cost_usd`).
