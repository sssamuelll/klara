# Slice 3 PR-B — gender cloze (correction surface) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Put the gender correction in front of the user: a deterministic `gender_cloze` quiz item (tap der/die/das) appended to the story Finish quiz, **graded server-side against the oracle**, with each answer recorded as diadic evidence in a new `gender_attempt` table.

**Architecture:** A new `gender_attempt(user, vocab_item, picked_article, was_correct)` table is the diadic evidence store (NOT QuizAttempt — different arity). `get_story_quiz` appends — at serve time, never persisted — a `gender_cloze` item built deterministically from the story's target nouns whose `gender_source == 'oracle'`. The frontend renders a 3-button picker; on pick it POSTs `{vocab_item_id, picked_article}` to a new `POST /stories/{id}/gender/attempts`, which **grades against `VocabItem.gender` (the oracle)**, writes a `GenderAttempt`, and returns `{was_correct, correct_gender}` — so the answer is never shipped to the client and grading is authoritative. The generic quiz-attempt record is skipped for gender items (the gender_attempt is the record).

**Tech Stack:** FastAPI, SQLAlchemy async, Postgres, Alembic, pytest; React + Vite + TS, react-i18next (6 locales). No new deps.

**Spec:** `docs/superpowers/specs/2026-06-16-learning-sequence-slice3-gender-correction-design.md` (PR-B of 3). PR-A (oracle + provenance) is merged.

**Out of scope (deferred):** `is_mastered_gender` (no consumer yet — it's a trivial read over `gender_attempt` added when a gate/map needs it; building it now is dead code the roster warned against). Suffix-rule feedback + ES→DE incongruence = PR-C. Practice/SRS integration of gender = later.

---

## File Structure

**Backend (create):**
- `backend/src/klara/models/gender.py` — `GenderAttempt` model.
- `backend/alembic/versions/20260616_0011_gender_attempts.py` — table migration.
- `backend/tests/test_gender_cloze.py` — build_gender_cloze, quiz serve, attempt endpoint.

**Backend (modify):**
- `backend/src/klara/models/__init__.py` — export `GenderAttempt`.
- `backend/alembic/env.py` — import `gender` model.
- `backend/src/klara/schemas/finish.py` — `GenderClozeQuizItem` in the `QuizItem` union; `GenderAttemptIn`/`GenderAttemptOut`; add `"gender_cloze"` to `QuizAttemptIn.question_type`.
- `backend/src/klara/services/finish_lessons.py` — `build_gender_cloze(words)`.
- `backend/src/klara/routers/stories.py` — append the gender_cloze in `get_story_quiz`; new `POST /{id}/gender/attempts`.
- `backend/tests/conftest.py` — add `gender_attempts` to the TRUNCATE list.

**Frontend (modify):**
- `frontend/src/api/types.ts` — `GenderClozeQuizItem` (+ union), `GenderAttemptIn`/`GenderAttemptOut`, `"gender_cloze"` in `QuizAttemptIn`.
- `frontend/src/api/client.ts` — `recordGenderAttempt`.
- `frontend/src/components/StoryFinish.tsx` — `GenderClozeQuestion` renderer + dispatch case + skip generic quiz-attempt for gender.
- `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` — `story.finish.quiz.genderCloze` keys.

---

## Task 1: GenderAttempt model + migration

**Files:**
- Create: `backend/src/klara/models/gender.py`, `backend/alembic/versions/20260616_0011_gender_attempts.py`
- Modify: `backend/src/klara/models/__init__.py`, `backend/alembic/env.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_gender_cloze.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_gender_cloze.py`:

```python
"""Gender cloze: evidence table, deterministic build, serve, server-side grading."""

import uuid

import pytest

from klara.models import GenderAttempt, VocabItem
from klara.models.enums import PartOfSpeech


@pytest.mark.asyncio
async def test_gender_attempt_roundtrips(db_session):
    from klara.models import User
    from klara.models.enums import CEFRLevel

    u = User(
        id=uuid.uuid4(), email=f"ga-{uuid.uuid4().hex[:6]}@k.app", hashed_password="x",
        is_active=True, is_verified=True, is_superuser=False, display_name="GA",
        level=CEFRLevel.A1, native_language="es", target_language="de",
    )
    v = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"Tisch{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN, gender="der", gender_source="oracle",
    )
    db_session.add_all([u, v])
    await db_session.flush()
    db_session.add(
        GenderAttempt(
            id=uuid.uuid4(), user_id=u.id, vocab_item_id=v.id,
            picked_article="die", was_correct=False,
        )
    )
    await db_session.commit()

    from sqlalchemy import select

    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.user_id == u.id))
    ).scalar_one()
    assert row.picked_article == "die" and row.was_correct is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py::test_gender_attempt_roundtrips -v`
Expected: FAIL — `ImportError: cannot import name 'GenderAttempt'`.

- [ ] **Step 3: Create the model**

Create `backend/src/klara/models/gender.py`:

```python
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, uuid_pk


class GenderAttempt(Base):
    """Diadic gender evidence: which article the user picked for a given noun,
    and whether it matched the oracle. The per-noun binding `assigns(user, noun,
    article)` — deliberately NOT folded into the monadic UserCard (lexical SRS).
    A future is_mastered_gender derives mastery from these rows."""

    __tablename__ = "gender_attempts"
    __table_args__ = (
        Index("ix_gender_attempt_user_vocab", "user_id", "vocab_item_id"),
        CheckConstraint("picked_article IN ('der', 'die', 'das')", name="ck_gender_attempt_picked"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vocab_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("vocab_items.id", ondelete="CASCADE"), nullable=False
    )
    picked_article: Mapped[str] = mapped_column(String(8), nullable=False)  # der | die | das
    was_correct: Mapped[bool] = mapped_column(nullable=False)
    # Forward-compat for PR-C (e.g. the detected suffix rule); unused in v1.
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attempted_at: Mapped[created_ts]
```

- [ ] **Step 4: Export + register**

Modify `backend/src/klara/models/__init__.py` — add `from klara.models.gender import GenderAttempt` and `"GenderAttempt"` to `__all__`.

Modify `backend/alembic/env.py` — add `gender` to the model-import tuple (alphabetical: `... audio, gender, gender_lexicon, module, ...`).

- [ ] **Step 5: Write the migration**

Create `backend/alembic/versions/20260616_0011_gender_attempts.py`:

```python
"""gender_attempts evidence table

Revision ID: 20260616_0011
Revises: 20260616_0010
Create Date: 2026-06-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "20260616_0011"
down_revision: str | None = "20260616_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gender_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vocab_item_id", UUID(as_uuid=True),
            sa.ForeignKey("vocab_items.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("picked_article", sa.String(8), nullable=False),
        sa.Column("was_correct", sa.Boolean, nullable=False),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column(
            "attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("picked_article IN ('der', 'die', 'das')", name="ck_gender_attempt_picked"),
    )
    op.create_index("ix_gender_attempt_user_vocab", "gender_attempts", ["user_id", "vocab_item_id"])


def downgrade() -> None:
    op.drop_index("ix_gender_attempt_user_vocab", table_name="gender_attempts")
    op.drop_table("gender_attempts")
```

- [ ] **Step 6: Add to conftest TRUNCATE**

Modify `backend/tests/conftest.py` — add `gender_attempts` to the TRUNCATE list (it FKs users + vocab_items; CASCADE handles order, but list it before users):

```python
                "story_views, study_sessions, stories, module_vocab, modules, "
                "gender_attempts, gender_lexicon, users RESTART IDENTITY CASCADE"
```

- [ ] **Step 7: Verify migration round-trip (use the TEST db URL)**

Run (from `backend/`):
```bash
DATABASE_URL="postgresql+asyncpg://german:german_dev_pw@localhost:5432/german_app_test" uv run alembic upgrade head
DATABASE_URL="postgresql+asyncpg://german:german_dev_pw@localhost:5432/german_app_test" uv run alembic downgrade base
DATABASE_URL="postgresql+asyncpg://german:german_dev_pw@localhost:5432/german_app_test" uv run alembic upgrade head
```
Expected: all succeed. (Important: set `DATABASE_URL` to the **test** DB — a bare `alembic` command targets the dev DB.)

- [ ] **Step 8: Run the test**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v` then `uv run pytest -q` (full suite — new table, no regression). Then `uv run ruff check src tests` and `uv run ruff format --check src tests`. Run `ruff format` on any file you touched before committing.

- [ ] **Step 9: Commit**

```bash
git add backend/src/klara/models/gender.py backend/src/klara/models/__init__.py backend/alembic/env.py backend/alembic/versions/20260616_0011_gender_attempts.py backend/tests/conftest.py backend/tests/test_gender_cloze.py
git commit -m "feat(curriculum): gender_attempts diadic evidence table"
```

---

## Task 2: GenderClozeQuizItem schema + build_gender_cloze + serve it

**Files:**
- Modify: `backend/src/klara/schemas/finish.py`, `backend/src/klara/services/finish_lessons.py`, `backend/src/klara/routers/stories.py`
- Test: `backend/tests/test_gender_cloze.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_gender_cloze.py`:

```python
def test_build_gender_cloze_picks_oracle_noun():
    from klara.services.finish_lessons import build_gender_cloze

    verb = VocabItem(id=uuid.uuid4(), language="de", lemma="laufen", pos=PartOfSpeech.VERB)
    llm_noun = VocabItem(
        id=uuid.uuid4(), language="de", lemma="Quux", pos=PartOfSpeech.NOUN,
        gender="die", gender_source="llm",
    )
    oracle_noun = VocabItem(
        id=uuid.uuid4(), language="de", lemma="Tisch", pos=PartOfSpeech.NOUN,
        gender="der", gender_source="oracle", translations={"es": "mesa"},
    )
    # Only the oracle-sourced noun qualifies; verbs and llm-gender nouns are skipped.
    item = build_gender_cloze([verb, llm_noun, oracle_noun], native_language="es")
    assert item is not None
    assert item["type"] == "gender_cloze"
    assert item["lemma"] == "Tisch"
    assert item["vocab_item_id"] == str(oracle_noun.id)
    assert item["en"] == "mesa"
    assert "correct_gender" not in item  # answer is NOT shipped to the client


def test_build_gender_cloze_none_when_no_oracle_noun():
    from klara.services.finish_lessons import build_gender_cloze

    only_llm = VocabItem(
        id=uuid.uuid4(), language="de", lemma="Quux", pos=PartOfSpeech.NOUN,
        gender="die", gender_source="llm",
    )
    assert build_gender_cloze([only_llm], native_language="es") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v -k "build_gender_cloze"`
Expected: FAIL — `cannot import name 'build_gender_cloze'`.

- [ ] **Step 3: Add the schema**

Modify `backend/src/klara/schemas/finish.py`. Add the item type after `ShadowQuizItem` (line 41):

```python
class GenderClozeQuizItem(BaseModel):
    type: Literal["gender_cloze"]
    cap: str
    lemma: str
    vocab_item_id: str
    en: str | None = None  # native-language gloss for context; NOT the answer
```

Extend the union (line 44):

```python
QuizItem = MCQuizItem | ClozeQuizItem | ShadowQuizItem | GenderClozeQuizItem
```

Add `"gender_cloze"` to `QuizAttemptIn.question_type` (line 83):

```python
    question_type: Literal["mc", "cloze", "shadow", "gender_cloze"]
```

- [ ] **Step 4: Implement build_gender_cloze**

Modify `backend/src/klara/services/finish_lessons.py`. Add imports at the top (alphabetical within their groups): `from klara.models import VocabItem` (if not present) and `from klara.models.enums import PartOfSpeech`. Add the function (near `ensure_quiz_items`):

```python
def build_gender_cloze(words: list[VocabItem], *, native_language: str) -> dict | None:
    """Deterministically build a der/die/das cloze from the first story target
    noun whose gender comes from the oracle (authoritative). Returns the quiz
    item dict, or None when no oracle-gendered noun is available (e.g. the oracle
    isn't loaded yet) — in which case the quiz is served unchanged. The correct
    article is NOT included: grading is server-side (POST /gender/attempts)."""
    for w in words:
        if w.pos == PartOfSpeech.NOUN and w.gender_source == "oracle" and w.gender:
            return {
                "type": "gender_cloze",
                "cap": "gender",  # frontend localizes the caption
                "lemma": w.lemma,
                "vocab_item_id": str(w.id),
                "en": (w.translations or {}).get(native_language),
            }
    return None
```

- [ ] **Step 5: Serve it in get_story_quiz**

Modify `backend/src/klara/routers/stories.py`. Import `build_gender_cloze` alongside `ensure_quiz_items` (the existing `from klara.services.finish_lessons import ...` line). Change `get_story_quiz`'s body so the deterministic gender cloze is appended (at serve time, never persisted):

```python
    story = await _load_or_404(db, story_id, user.id, locale)
    words = await _load_words(db, list(story.target_vocab_item_ids or []))
    lemmas = [w.lemma for w in words]
    items = list(await ensure_quiz_items(db, story, llm, lemmas=lemmas) or [])
    gender_cloze = build_gender_cloze(words, native_language=user.native_language)
    if gender_cloze is not None:
        items.append(gender_cloze)
    return QuizOut(items=items)
```

- [ ] **Step 6: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v -k "build_gender_cloze"`
Expected: PASS. Then `uv run ruff check ...` + `ruff format` the touched files.

- [ ] **Step 7: Commit**

```bash
git add backend/src/klara/schemas/finish.py backend/src/klara/services/finish_lessons.py backend/src/klara/routers/stories.py backend/tests/test_gender_cloze.py
git commit -m "feat(stories): serve a deterministic gender_cloze (oracle nouns) in the Finish quiz"
```

---

## Task 3: POST /gender/attempts — server-side grading + evidence

**Files:**
- Modify: `backend/src/klara/schemas/finish.py`, `backend/src/klara/routers/stories.py`
- Test: `backend/tests/test_gender_cloze.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_gender_cloze.py`:

```python
@pytest.mark.asyncio
async def test_gender_attempt_endpoint_grades_against_oracle(db_session):
    import uuid as _uuid

    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app
    from klara.models import GenderAttempt, Story, User
    from klara.models.enums import CEFRLevel
    from sqlalchemy import select

    u = User(
        id=_uuid.uuid4(), email=f"ge-{_uuid.uuid4().hex[:6]}@k.app", hashed_password="x",
        is_active=True, is_verified=True, is_superuser=False, display_name="GE",
        level=CEFRLevel.A1, native_language="es", target_language="de",
    )
    v = VocabItem(
        id=_uuid.uuid4(), language="de", lemma=f"Mond{_uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN, gender="der", gender_source="oracle",
    )
    db_session.add_all([u, v])
    await db_session.flush()
    story = Story(
        id=_uuid.uuid4(), user_id=u.id, level=CEFRLevel.A1, target_language="de",
        native_language="es", title="t", content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[v.id],
    )
    db_session.add(story)
    await db_session.commit()

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Wrong pick "die" (the ES "la luna" trap) — oracle says "der".
        resp = await ac.post(
            f"/api/v1/stories/{story.id}/gender/attempts",
            json={"vocab_item_id": str(v.id), "picked_article": "die"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["was_correct"] is False
    assert body["correct_gender"] == "der"  # the answer arrives only after picking
    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.picked_article == "die" and row.was_correct is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v -k "endpoint_grades"`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Add the schemas**

Modify `backend/src/klara/schemas/finish.py` — add after `QuizAttemptOut` (line 95):

```python
class GenderAttemptIn(BaseModel):
    vocab_item_id: UUID
    picked_article: Literal["der", "die", "das"]


class GenderAttemptOut(BaseModel):
    was_correct: bool
    correct_gender: str
```

- [ ] **Step 4: Add the endpoint**

Modify `backend/src/klara/routers/stories.py`. Add the imports: `GenderAttempt` to the `from klara.models import ...` line; `GenderAttemptIn, GenderAttemptOut` to the `from klara.schemas.finish import ...` line. Add the endpoint (near `record_quiz_attempt`):

```python
@router.post(
    "/{story_id}/gender/attempts",
    response_model=GenderAttemptOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_gender_attempt(
    story_id: UUID,
    payload: GenderAttemptIn,
    db: DBSession,
    user: CurrentUser,
    locale: LocaleDep,
) -> GenderAttemptOut:
    """Grade a der/die/das pick against the oracle (VocabItem.gender) and record
    the diadic evidence. The story scopes which words are answerable."""
    story = await _load_or_404(db, story_id, user.id, locale)
    if payload.vocab_item_id not in (story.target_vocab_item_ids or []):
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))
    vocab = await db.get(VocabItem, payload.vocab_item_id)
    if vocab is None or not vocab.gender:
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))

    was_correct = payload.picked_article == vocab.gender
    db.add(
        GenderAttempt(
            user_id=user.id,
            vocab_item_id=vocab.id,
            picked_article=payload.picked_article,
            was_correct=was_correct,
        )
    )
    await db.commit()
    return GenderAttemptOut(was_correct=was_correct, correct_gender=vocab.gender)
```

(`HTTPException`, `status`, `t`, `VocabItem`, `_load_or_404` are already imported/defined in `stories.py`. `GenderAttempt.id` has a Python `uuid_pk` default, so `db.add` with a single row populates it — matching the existing `record_quiz_attempt` pattern that omits `id`.)

- [ ] **Step 5: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v` then `uv run pytest -q` (full suite). Then `uv run ruff check src tests` + `ruff format` the touched files.

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/schemas/finish.py backend/src/klara/routers/stories.py backend/tests/test_gender_cloze.py
git commit -m "feat(stories): POST /gender/attempts — grade der/die/das vs oracle, record evidence"
```

---

## Task 4: Frontend — types + client

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`

- [ ] **Step 1: Add types**

Modify `frontend/src/api/types.ts`. Add the item type after `ShadowQuizItem` and extend the union:

```typescript
export interface GenderClozeQuizItem {
  type: "gender_cloze";
  cap: string;
  lemma: string;
  vocab_item_id: string;
  en?: string | null;
}

export type QuizItem =
  | MCQuizItem
  | ClozeQuizItem
  | ShadowQuizItem
  | GenderClozeQuizItem;

export interface GenderAttemptIn {
  vocab_item_id: string;
  picked_article: "der" | "die" | "das";
}

export interface GenderAttemptOut {
  was_correct: boolean;
  correct_gender: string;
}
```

Update `QuizAttemptIn.question_type`:

```typescript
  question_type: "mc" | "cloze" | "shadow" | "gender_cloze";
```

(Replace the existing `QuizItem` type alias and `QuizAttemptIn` interface with these versions — do not leave the old ones.)

- [ ] **Step 2: Add the client method**

Modify `frontend/src/api/client.ts`. Add `GenderAttemptIn, GenderAttemptOut` to the `./types` import block. Add the method after `recordQuizAttempt`:

```typescript
  recordGenderAttempt: (storyId: string, payload: GenderAttemptIn) =>
    request<GenderAttemptOut>(`/stories/${storyId}/gender/attempts`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
```

- [ ] **Step 3: Typecheck + commit**

Run: `cd frontend && npm run typecheck` (expect clean).

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat(frontend): GenderCloze quiz item type + recordGenderAttempt"
```

---

## Task 5: Frontend — GenderClozeQuestion renderer + dispatch + i18n

**Files:**
- Modify: `frontend/src/components/StoryFinish.tsx`, `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`

- [ ] **Step 1: Add i18n keys (es source, then all 6 locales)**

In each `frontend/src/locales/<loc>/common.json`, inside `story.finish.quiz` (after the `shadow` block), add a `genderCloze` block. es:

```json
    "genderCloze": {
      "cap": "El artículo",
      "prompt": "¿der, die o das?",
      "correct": "Correcto.",
      "wrong": "Era «{{correct}}»."
    },
```

en:
```json
    "genderCloze": {
      "cap": "The article",
      "prompt": "der, die or das?",
      "correct": "Correct.",
      "wrong": "It was «{{correct}}»."
    },
```

de:
```json
    "genderCloze": {
      "cap": "Der Artikel",
      "prompt": "der, die oder das?",
      "correct": "Richtig.",
      "wrong": "Es war «{{correct}}»."
    },
```

fr:
```json
    "genderCloze": {
      "cap": "L'article",
      "prompt": "der, die ou das ?",
      "correct": "Correct.",
      "wrong": "C'était «{{correct}}»."
    },
```

pt:
```json
    "genderCloze": {
      "cap": "O artigo",
      "prompt": "der, die ou das?",
      "correct": "Correto.",
      "wrong": "Era «{{correct}}»."
    },
```

ja:
```json
    "genderCloze": {
      "cap": "冠詞",
      "prompt": "der・die・das？",
      "correct": "正解。",
      "wrong": "正解は「{{correct}}」。"
    },
```

- [ ] **Step 2: Add the renderer + dispatch + skip generic record**

Modify `frontend/src/components/StoryFinish.tsx`.

(a) Add `GenderClozeQuizItem` to the `../api/types` import block.

(b) In the `Quiz()` component's `onAnswered`, skip the generic quiz-attempt POST for gender items (the gender attempt is recorded by the renderer). Change the `void api.recordQuizAttempt(...)` call so it is guarded:

```typescript
    // Best-effort persistence — failures don't block the UX. Gender items
    // record their own diadic evidence (recordGenderAttempt), so skip the
    // generic quiz-attempt record for them.
    if (q.type !== "gender_cloze") {
      void api
        .recordQuizAttempt(story.id, {
          question_index: idx,
          question_type: q.type,
          was_correct: full.correct,
          was_revealed: full.revealed,
        })
        .catch(() => undefined);
    }
```

(c) Add the dispatch case in the `Quiz()` render, after the `shadow` block:

```tsx
        {q.type === "gender_cloze" && (
          <GenderClozeQuestion
            q={q}
            story={story}
            onAnswered={onAnswered}
            onNext={onNext}
            isLast={isLast}
          />
        )}
```

(d) Add the renderer component (near `ClozeQuestion`). It uses tap, not the mic; grading is server-side:

```tsx
interface GenderClozeProps {
  q: GenderClozeQuizItem;
  story: Story;
  onAnswered: (r: { correct: boolean; revealed: boolean }) => void;
  onNext: () => void;
  isLast: boolean;
}

const GENDER_OPTIONS = ["der", "die", "das"] as const;

function GenderClozeQuestion({
  q,
  story,
  onAnswered,
  onNext,
  isLast,
}: GenderClozeProps): JSX.Element {
  const { t } = useTranslation();
  const [picked, setPicked] = useState<string | null>(null);
  const [result, setResult] = useState<{ correct: boolean; correctGender: string } | null>(null);

  const onPick = (article: string) => {
    if (picked) return;
    setPicked(article);
    void api
      .recordGenderAttempt(story.id, {
        vocab_item_id: q.vocab_item_id,
        picked_article: article as "der" | "die" | "das",
      })
      .then((r) => {
        setResult({ correct: r.was_correct, correctGender: r.correct_gender });
        onAnswered({ correct: r.was_correct, revealed: false });
      })
      .catch(() => {
        // On failure, grade optimistically as wrong-unknown but still advance.
        setResult({ correct: false, correctGender: "" });
        onAnswered({ correct: false, revealed: false });
      });
  };

  return (
    <article className="qcard" data-type="gender_cloze">
      <header className="qcard__head">
        <span className="fin-cap">{t("story.finish.quiz.genderCloze.cap")}</span>
      </header>
      <div className="qcard__body">
        <p className="qcard__cloze">
          <span className="qcard__blank" data-state={picked ? (result?.correct ? "correct" : "revealed") : "empty"}>
            {result ? result.correctGender || "—" : "___"}
          </span>{" "}
          <span>{q.lemma}</span>
        </p>
        {q.en && <p className="qcard__en">{q.en}</p>}
        <p className="qcard__hint">{t("story.finish.quiz.genderCloze.prompt")}</p>
      </div>
      <footer className="qcard__foot">
        {!picked && (
          <div className="qcard__actions qcard__gender-opts">
            {GENDER_OPTIONS.map((a) => (
              <button key={a} type="button" className="qcard__gender-btn" onClick={() => onPick(a)}>
                {a}
              </button>
            ))}
          </div>
        )}
        {result && (
          <div className="qcard__result">
            <span className="qcard__verdict">
              {result.correct ? (
                <em>{t("story.finish.quiz.genderCloze.correct")}</em>
              ) : (
                t("story.finish.quiz.genderCloze.wrong", { correct: result.correctGender })
              )}
            </span>
            <button type="button" className="fin-btn fin-btn--primary qcard__next" onClick={onNext}>
              {isLast ? t("story.finish.quiz.toSummary") : t("story.finish.quiz.next")}{" "}
              <span className="fin-arr">→</span>
            </button>
          </div>
        )}
      </footer>
    </article>
  );
}
```

(The renderer takes `story` via props and uses `story.id` for the POST — the gender_cloze item itself carries no story id.)

- [ ] **Step 3: i18n parity + typecheck + build**

Run: `cd frontend && npm run i18n:check && npm run typecheck && npm run build`
Expected: 6 locales aligned; typecheck clean; build OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/StoryFinish.tsx frontend/src/locales
git commit -m "feat(frontend): gender_cloze tap picker in Finish (server-graded der/die/das)"
```

---

## Task 6: Full verification

- [ ] **Step 1: Backend**

Run (from `backend/`): `uv run pytest -q` (all pass), `uv run ruff check src tests`, `uv run ruff format --check src tests`, and the migration round-trip with the **test** DATABASE_URL (Task 1 Step 7).

- [ ] **Step 2: Frontend**

Run (from `frontend/`): `npm run i18n:check && npm run typecheck && npm run build` (all green).

- [ ] **Step 3: Commit any fixups** (skip if none).

---

## Notes for the implementer

- **ruff hygiene (every task):** run `uv run ruff check --fix` AND `uv run ruff format` on every file touched (tests + scripts included); imports alphabetical in the top block, never mid-file. Migration `alembic` commands must set `DATABASE_URL` to the test DB — a bare command hits the dev DB.
- **Test isolation:** `gender_attempts` IS truncated between tests; `vocab_items` is NOT — use unique (uuid-suffixed) lemmas in tests.
- **Server-side grading is the contract:** the gender_cloze item never carries the correct article; the client sends the pick and the backend grades against `VocabItem.gender` (the oracle) and returns the verdict. Keep it that way — it's authoritative and prevents peeking.
- **Graceful when the oracle is empty:** `build_gender_cloze` returns `None` if no target noun has `gender_source == 'oracle'`, so until the prod oracle is loaded (PR-A's `load_de_gender`), the quiz is served unchanged — no gender_cloze appears. No regression.
- **Deferred:** `is_mastered_gender` (no consumer yet), suffix-rule feedback + ES→DE incongruence (PR-C), Practice/SRS gender integration. `GenderAttempt.detail` (JSONB) is reserved for PR-C's suffix signal; unused in v1.
- **CSS:** `qcard__gender-opts` / `qcard__gender-btn` are new classes; minimal styling (3 inline buttons) is fine — match the existing `qcard__*` look. If the existing stylesheet uses a different convention, follow it; styling is not behavior-critical.
