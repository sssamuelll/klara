# Gender SRS — Slice B2a (backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the backend for a dedicated, LLM-independent gender review queue — a cross-module weak-noun selector, a layer-clean shared grading helper, and a new `/gender` router (`GET /gender/review` + `POST /gender/attempts`) — all derived on-read from the existing `GenderAttempt` ledger.

**Architecture:** Gender gets its own router and schema home (no longer bolted onto `/srs`). Grading is extracted from the story-scoped handler into one framework-free service helper that returns `GenderAttemptOut | None`; routers map `None` to a localized 404. The review list is the weak set computed by a column-projected selector (no JSONB loaded, no SQL LIMIT).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, Postgres, pytest (`asyncio_mode = "auto"`), ruff. Spec: `docs/superpowers/specs/2026-06-23-gender-srs-b2-design.md`.

## Global Constraints

- **Branch:** `feat/gender-srs-b2a` (exists; the spec is committed there).
- **Tests:** `cd backend && uv run pytest <path> -v`. Async tests use `@pytest.mark.asyncio` (suite is `asyncio_mode = "auto"`).
- **Lint/format every commit, two SEPARATE commands** (a uv stderr warning can flip `$?`): `uv run ruff check --fix src tests` then `uv run ruff format src tests`. CI runs `ruff check` + `ruff format --check`.
- **No new table / migration / scheduling column / conftest TRUNCATE entry** (derived on-read).
- **`services/` stays framework-free:** `grade_gender_attempt` must NOT import `fastapi` / raise `HTTPException` / take `locale`. It returns `GenderAttemptOut | None`; the router does the 404.
- **Column projection is load-bearing:** `weak_gender_nouns` selects 4 columns and uses `.all()` (NOT `.scalars()`) so the JSONB `detail` is never loaded. A code comment marks this; do not "simplify" to `select(GenderAttempt)`.
- **Membership-before-gate order preserved:** the rewritten `record_gender_attempt` keeps its `target_vocab_item_ids` 404 BEFORE delegating to the helper.
- **Integrity = oracle gate only:** any authenticated user may grade any oracle-gradable noun as their own evidence (self-reported; gender is display-only / never gates). Cross-user isolation is via server-derived `user_id`; an IDOR-isolation test enforces it.
- **New router mounts at `/api/v1/gender`** (so endpoints are `/api/v1/gender/review` and `/api/v1/gender/attempts`).
- **B2b (frontend) is a separate later plan** — not in scope here.

---

### Task 1: Consolidate gender schemas into `schemas/gender.py`

Move the gender request/response schemas out of `schemas/finish.py` into a new gender-axis home, and add `GenderReviewItem`. Behavior-preserving for the existing story endpoint; the existing gender-attempt tests are the safety net.

**Files:**
- Create: `backend/src/klara/schemas/gender.py`
- Modify: `backend/src/klara/schemas/finish.py` (remove the 3 moved classes, lines 109-124)
- Modify: `backend/src/klara/routers/stories.py` (import the 3 from `schemas.gender`, lines 45-62 block)
- Test: `backend/tests/test_gender_grading.py` (new — a tiny schema test here; the file grows in Task 2)

**Interfaces:**
- Consumes: nothing.
- Produces (in `klara.schemas.gender`): `GenderAttemptIn{vocab_item_id: UUID, picked_article: Literal["der","die","das"]}`, `GenderRuleOut{suffix, suffix_class, rule_gender, is_exception}`, `GenderAttemptOut{was_correct: bool, correct_gender: str, rule: GenderRuleOut | None = None}`, `GenderReviewItem{vocab_item_id: UUID, lemma: str, en: str | None = None}`.

- [ ] **Step 1: Confirm the existing gender-attempt tests pass (baseline)**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -q`
Expected: PASS — these exercise the story gender endpoint and are the refactor safety net.

- [ ] **Step 2: Write the failing test for the new module + new schema**

Create `backend/tests/test_gender_grading.py`:

```python
"""grade_gender_attempt (shared gender grading) + the consolidated gender schemas."""

import uuid

import pytest

from klara.models.enums import CEFRLevel, PartOfSpeech


def test_gender_schemas_live_in_gender_module():
    from klara.schemas.gender import (
        GenderAttemptIn,
        GenderAttemptOut,
        GenderReviewItem,
        GenderRuleOut,
    )

    item = GenderReviewItem(vocab_item_id=uuid.uuid4(), lemma="Tisch", en="mesa")
    assert item.en == "mesa"
    assert GenderAttemptIn(vocab_item_id=uuid.uuid4(), picked_article="der").picked_article == "der"
    out = GenderAttemptOut(was_correct=True, correct_gender="der", rule=None)
    assert out.rule is None
    assert GenderRuleOut(
        suffix="ung", suffix_class="hard", rule_gender="die", is_exception=False
    ).rule_gender == "die"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/test_gender_grading.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.schemas.gender'`.

- [ ] **Step 4: Create `schemas/gender.py`**

Create `backend/src/klara/schemas/gender.py`:

```python
"""Gender-axis API contracts (der/die/das), shared by the in-story grading path
(routers/stories.py) and the standalone gender review path (routers/gender.py).
Moved here from schemas/finish.py so the gender router's dependency cone stays
within the gender subsystem."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class GenderAttemptIn(BaseModel):
    vocab_item_id: UUID
    picked_article: Literal["der", "die", "das"]


class GenderRuleOut(BaseModel):
    suffix: str
    suffix_class: Literal["hard", "tendency"]
    rule_gender: Literal["der", "die", "das"]
    is_exception: bool


class GenderAttemptOut(BaseModel):
    was_correct: bool
    correct_gender: str
    rule: GenderRuleOut | None = None  # showable suffix rule (Case A/C); None otherwise


class GenderReviewItem(BaseModel):
    vocab_item_id: UUID
    lemma: str
    en: str | None = None  # native-language gloss for context; NOT the answer
```

- [ ] **Step 5: Remove the 3 moved classes from `schemas/finish.py`**

Delete lines 109-124 of `backend/src/klara/schemas/finish.py` (the `GenderAttemptIn`, `GenderRuleOut`, `GenderAttemptOut` class definitions — the block from `class GenderAttemptIn(BaseModel):` through the `rule: GenderRuleOut | None ...` line). Leave `GenderL1NoteItem` and everything else. Do NOT remove `finish.py`'s `Literal`/`UUID` imports — other classes (`GenderL1NoteItem`, `QuizAttemptOut`, etc.) still use them; `ruff check --fix` (Step 8) will confirm.

- [ ] **Step 6: Update the `stories.py` import**

In `backend/src/klara/routers/stories.py`, the `from klara.schemas.finish import (...)` block (lines 45-62) currently includes `GenderAttemptIn`, `GenderAttemptOut`, `GenderRuleOut`. Remove those three names from that block, and add a new import:

```python
from klara.schemas.gender import GenderAttemptIn, GenderAttemptOut, GenderRuleOut
```

(Keep `GenderL1NoteItem`, `GenderL1NotesOut`, `InsightOut`, `KlaraNoteOut`, `MCResolveOut`, `PronunciationAttemptIn`, `PronunciationAttemptOut`, `QuizAttemptIn`, `QuizAttemptOut`, `QuizOut`, `ScheduleBucket`, `ScheduleEntry`, `ScheduleOut` importing from `schemas.finish`.)

- [ ] **Step 7: Run tests to verify green**

Run: `cd backend && uv run pytest tests/test_gender_grading.py tests/test_gender_cloze.py tests/test_l1_notes_endpoint.py -q`
Expected: PASS — the new schema test plus the existing story gender-attempt + L1-notes suites (proving the move didn't break the live endpoint).

- [ ] **Step 8: Lint, format, commit**

```bash
cd backend && uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/schemas/gender.py backend/src/klara/schemas/finish.py backend/src/klara/routers/stories.py backend/tests/test_gender_grading.py
git commit -m "refactor(curriculum): consolidate gender schemas into schemas/gender.py + add GenderReviewItem"
```

---

### Task 2: `grade_gender_attempt` — the shared, framework-free grading helper

**Files:**
- Create: `backend/src/klara/services/gender_grading.py`
- Test: `backend/tests/test_gender_grading.py` (append)

**Interfaces:**
- Consumes: `GenderAttemptOut`, `GenderRuleOut` from `schemas.gender` (Task 1); `detect_gender_rule`, `reconcile_rule` from `curriculum.gender_rules`; `GenderAttempt`, `VocabItem` from `models`.
- Produces: `async grade_gender_attempt(db: AsyncSession, *, user_id: UUID, vocab_item_id: UUID, picked_article: str) -> GenderAttemptOut | None` — grades vs the oracle, writes a `GenderAttempt`, returns the result; `None` when the vocab is not oracle-gradable. NO `HTTPException`, NO `locale`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_gender_grading.py`:

```python
async def _user(db):
    from klara.models import User

    u = User(
        id=uuid.uuid4(),
        email=f"gg-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GG",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def _oracle_noun(db, *, lemma, gender):
    from klara.models import VocabItem

    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=lemma,
        pos=PartOfSpeech.NOUN,
        gender=gender,
        gender_source="oracle",
    )
    db.add(v)
    await db.flush()
    return v


@pytest.mark.asyncio
async def test_grade_gender_attempt_correct_and_wrong(db_session):
    from sqlalchemy import select

    from klara.models import GenderAttempt
    from klara.services.gender_grading import grade_gender_attempt

    u = await _user(db_session)
    v = await _oracle_noun(db_session, lemma=f"Tisch{uuid.uuid4().hex[:6]}", gender="der")
    await db_session.commit()

    ok = await grade_gender_attempt(
        db_session, user_id=u.id, vocab_item_id=v.id, picked_article="der"
    )
    assert ok is not None and ok.was_correct is True and ok.correct_gender == "der"

    bad = await grade_gender_attempt(
        db_session, user_id=u.id, vocab_item_id=v.id, picked_article="die"
    )
    assert bad is not None and bad.was_correct is False and bad.correct_gender == "der"

    rows = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalars().all()
    assert len(rows) == 2  # both attempts recorded


@pytest.mark.asyncio
async def test_grade_gender_attempt_none_when_not_oracle(db_session):
    from klara.models import VocabItem
    from klara.services.gender_grading import grade_gender_attempt

    u = await _user(db_session)
    llm = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=f"Llm{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="llm",
    )
    db_session.add(llm)
    await db_session.commit()

    assert await grade_gender_attempt(
        db_session, user_id=u.id, vocab_item_id=llm.id, picked_article="die"
    ) is None
    assert await grade_gender_attempt(
        db_session, user_id=u.id, vocab_item_id=uuid.uuid4(), picked_article="die"
    ) is None  # missing vocab


@pytest.mark.asyncio
async def test_grade_gender_attempt_show_gates_rule(db_session):
    from klara.services.gender_grading import grade_gender_attempt

    u = await _user(db_session)
    # "-ung" is a hard rule for die; an agreeing oracle gender shows the rule.
    v = await _oracle_noun(db_session, lemma=f"Zeitung{uuid.uuid4().hex[:6]}", gender="die")
    await db_session.commit()
    out = await grade_gender_attempt(
        db_session, user_id=u.id, vocab_item_id=v.id, picked_article="die"
    )
    assert out is not None and out.rule is not None
    assert out.rule.rule_gender == "die"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/test_gender_grading.py -k grade_gender_attempt -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.services.gender_grading'`.

(Note: the `-ung` lemma is suffixed with uuid hex; `detect_gender_rule` matches on the `-ung` suffix regardless of the hex tail since it is a longest-suffix match on the stem. If the show-gate test is brittle in your environment, the implementer may substitute any lemma whose `detect_gender_rule` agrees with its oracle gender — but `-ung`→die is a documented hard rule.)

- [ ] **Step 3: Create `services/gender_grading.py`**

Create `backend/src/klara/services/gender_grading.py`:

```python
"""Shared gender grading — the single source of truth for grading a der/die/das
pick against the oracle and recording the diadic evidence. Framework-free: it
returns GenderAttemptOut | None (None = not oracle-gradable) and never raises an
HTTP error; routers map None to a localized 404. Called by both the in-story
finish path (routers/stories.py) and the standalone review path
(routers/gender.py)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.gender_rules import detect_gender_rule, reconcile_rule
from klara.models import GenderAttempt, VocabItem
from klara.schemas.gender import GenderAttemptOut, GenderRuleOut


async def grade_gender_attempt(
    db: AsyncSession, *, user_id: UUID, vocab_item_id: UUID, picked_article: str
) -> GenderAttemptOut | None:
    """Grade the pick against the oracle gender and record the evidence. Returns
    None when the vocab is not oracle-gradable (missing / gender_source != 'oracle'
    / no gender) — an LLM/user guess is never certified as evidence (the curriculum
    invariant). The returned value is a function of inputs + oracle (no read-back of
    the committed row); single commit, no refresh — matching the prior handler."""
    vocab = await db.get(VocabItem, vocab_item_id)
    if vocab is None or vocab.gender_source != "oracle" or not vocab.gender:
        return None
    was_correct = picked_article == vocab.gender
    rule = detect_gender_rule(vocab.lemma)
    detail = reconcile_rule(rule, vocab.gender, vocab.lemma) if rule is not None else None
    rule_out = None
    if detail is not None and (detail["agreement"] or detail["is_exception"]):
        rule_out = GenderRuleOut(
            suffix=detail["suffix"],
            suffix_class=detail["suffix_class"],
            rule_gender=detail["rule_gender"],
            is_exception=detail["is_exception"],
        )
    db.add(
        GenderAttempt(
            user_id=user_id,
            vocab_item_id=vocab.id,
            picked_article=picked_article,
            was_correct=was_correct,
            detail=detail,
        )
    )
    await db.commit()
    return GenderAttemptOut(was_correct=was_correct, correct_gender=vocab.gender, rule=rule_out)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_gender_grading.py -v`
Expected: PASS (the schema test from Task 1 + the three grading tests).

- [ ] **Step 5: Update the `GenderAttempt.detail` model docstring**

In `backend/src/klara/models/gender.py`, the `detail` column comment says it is "written by `record_gender_attempt`". Update that phrase to "written by `grade_gender_attempt`" (it is now the shared writer). Make only this wording change.

- [ ] **Step 6: Lint, format, commit**

```bash
cd backend && uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/services/gender_grading.py backend/src/klara/models/gender.py backend/tests/test_gender_grading.py
git commit -m "feat(curriculum): grade_gender_attempt — shared framework-free gender grading helper"
```

---

### Task 3: Rewire `record_gender_attempt` to delegate to the helper

The story endpoint keeps its story-coupled lines (load + membership 404), then delegates grading to the shared helper, mapping `None` to its 404. Behavior-preserving — the membership 404 still fires BEFORE the oracle gate.

**Files:**
- Modify: `backend/src/klara/routers/stories.py:512-537` (`record_gender_attempt` body)
- Test: `backend/tests/test_gender_cloze.py` (regression — stays green)

**Interfaces:**
- Consumes: `grade_gender_attempt` (Task 2).
- Produces: no new symbols; the endpoint's external behavior is unchanged.

- [ ] **Step 1: Confirm the existing endpoint tests pass (baseline)**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -q`
Expected: PASS — `test_gender_attempt_endpoint_grades_against_oracle` and `test_gender_attempt_roundtrips` are the regression guard.

- [ ] **Step 2: Replace the grading body with a delegation**

In `backend/src/klara/routers/stories.py`, replace lines 512-537 (everything AFTER the membership check at 510-511, i.e. from `vocab = await db.get(VocabItem, payload.vocab_item_id)` through the final `return`) with:

```python
    out = await grade_gender_attempt(
        db,
        user_id=user.id,
        vocab_item_id=payload.vocab_item_id,
        picked_article=payload.picked_article,
    )
    if out is None:
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))
    return out
```

Keep lines 509-511 unchanged (the `_load_or_404` + the `payload.vocab_item_id not in (story.target_vocab_item_ids or [])` 404 — membership stays BEFORE the helper). Add the import near the other service imports (after line 78):

```python
from klara.services.gender_grading import grade_gender_attempt
```

Then remove now-unused imports from `stories.py`: `detect_gender_rule`, `reconcile_rule` (line 22) and `GenderRuleOut` (the `schemas.gender` import from Task 1) are no longer used here (they moved into the helper). Let `ruff check --fix` (Step 4) drop whatever is genuinely unused; if `GenderAttemptOut` is still referenced by the `response_model=GenderAttemptOut` decorator (line 494) keep it, and `GenderAttemptIn` is still the body type (keep it).

- [ ] **Step 3: Run the regression suite**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v`
Expected: PASS — identical behavior. The wrong-pick grading, the `correct_gender` in the response, and the persisted `GenderAttempt` row are unchanged; a non-member vocab still 404s at line 510-511 before the helper.

- [ ] **Step 4: Lint, format, commit**

```bash
cd backend && uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/routers/stories.py
git commit -m "refactor(stories): record_gender_attempt delegates to grade_gender_attempt"
```

`ruff check --fix` drops `detect_gender_rule`/`reconcile_rule`/`GenderRuleOut` if they are now unused in stories.py. If ruff reports any of them still used elsewhere in the file, leave them.

---

### Task 4: `weak_gender_nouns` — cross-module weak-set selector

**Files:**
- Modify: `backend/src/klara/curriculum/competence.py` (append after `gender_weakness_order`)
- Test: `backend/tests/test_curriculum_competence.py` (append; reuse the file's `_user`, `_de_oracle_noun`, `_attempt` helpers)

**Interfaces:**
- Consumes: `select`, `UUID`, `AsyncSession`, `GenderAttempt`, `VocabItem`, `gender_eligible_clause`, `_gender_noun_state`, `_GENDER_TIER`, `_GENDER_WEAK_STATES`, `GENDER_MASTERY_STREAK_N` (all already imported / in-module in competence.py).
- Produces: `async weak_gender_nouns(db: AsyncSession, *, user_id: UUID, limit: int = 20) -> list[UUID]` — the user's encountered-but-not-mastered eligible gender nouns, cross-module, priority-ordered, capped after sort.

- [ ] **Step 1: Write the failing tests**

Extend the import at the top of `backend/tests/test_curriculum_competence.py` to add `weak_gender_nouns`:

```python
from klara.curriculum.competence import (
    GENDER_MASTERY_STREAK_N,
    MASTERY_INTERVAL_DAYS,
    _gender_noun_state,
    _streak_mastered,
    gender_weakness_order,
    is_mastered_gender,
    is_mastered_lexical,
    known_set,
    module_gender_progress,
    module_progress,
    weak_gender_nouns,
)
```

Append these tests (reuse the file's existing `_user`, `_de_oracle_noun`, and `_attempt` helpers; `UTC`/`datetime`/`timedelta` are imported there):

```python
@pytest.mark.asyncio
async def test_weak_gender_nouns_only_weak_cross_module(db_session):
    uid = await _user(db_session)
    mastered = await _de_oracle_noun(db_session, gender="der")  # 3 correct → excluded
    wrong = await _de_oracle_noun(db_session, gender="die")  # newest wrong → included
    progressing = await _de_oracle_noun(db_session, gender="das")  # 1 correct, <N → included
    for _ in range(3):
        await _attempt(db_session, uid=uid, vid=mastered.id, correct=True)
    await _attempt(db_session, uid=uid, vid=wrong.id, correct=False)
    await _attempt(db_session, uid=uid, vid=progressing.id, correct=True)
    await db_session.commit()

    ids = await weak_gender_nouns(db_session, user_id=uid)
    assert set(ids) == {wrong.id, progressing.id}  # mastered excluded; unseen never appears
    assert ids[0] == wrong.id  # wrong_recent (tier 0) before in_progress (tier 1)


@pytest.mark.asyncio
async def test_weak_gender_nouns_excludes_ineligible(db_session):
    uid = await _user(db_session)
    verb = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"V{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.VERB, gender=None, gender_source="oracle",
    )
    llm = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"L{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN, gender="der", gender_source="llm",
    )
    db_session.add_all([verb, llm])
    await db_session.flush()
    await _attempt(db_session, uid=uid, vid=verb.id, correct=False)
    await _attempt(db_session, uid=uid, vid=llm.id, correct=False)
    await db_session.commit()
    assert await weak_gender_nouns(db_session, user_id=uid) == []  # predicate filters both


@pytest.mark.asyncio
async def test_weak_gender_nouns_limit_after_sort(db_session):
    uid = await _user(db_session)
    a = await _de_oracle_noun(db_session, gender="der")
    b = await _de_oracle_noun(db_session, gender="die")
    await _attempt(db_session, uid=uid, vid=a.id, correct=False)
    await _attempt(db_session, uid=uid, vid=b.id, correct=False)
    await db_session.commit()
    ids = await weak_gender_nouns(db_session, user_id=uid, limit=1)
    assert len(ids) == 1  # capped after sort/filter


@pytest.mark.asyncio
async def test_weak_gender_nouns_empty_when_caught_up(db_session):
    uid = await _user(db_session)
    v = await _de_oracle_noun(db_session, gender="der")
    for _ in range(3):
        await _attempt(db_session, uid=uid, vid=v.id, correct=True)  # mastered
    await db_session.commit()
    assert await weak_gender_nouns(db_session, user_id=uid) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -k weak_gender_nouns -v`
Expected: FAIL — `ImportError: cannot import name 'weak_gender_nouns'`.

- [ ] **Step 3: Implement `weak_gender_nouns`**

Append to `backend/src/klara/curriculum/competence.py` (after `gender_weakness_order`):

```python
async def weak_gender_nouns(db: AsyncSession, *, user_id: UUID, limit: int = 20) -> list[UUID]:
    """The user's encountered-but-not-mastered eligible gender nouns, CROSS-MODULE,
    ordered by remediation priority (wrong_recent before in_progress; within a tier,
    least-recently-attempted first). Derived on-read from the GenderAttempt ledger —
    no scheduling state. `limit` caps the result AFTER sort (a SQL LIMIT would
    truncate per-noun streaks and corrupt mastery classification).

    LOAD-BEARING: this selects 4 COLUMNS and uses .all() (NOT .scalars() /
    select(GenderAttempt)) so the JSONB `detail` is never loaded. Do not change to
    full ORM rows — that reintroduces the JSONB-hydration cost on a hot path."""
    stmt = (
        select(
            GenderAttempt.vocab_item_id,
            GenderAttempt.was_correct,
            GenderAttempt.attempted_at,
            GenderAttempt.id,
        )
        .join(VocabItem, VocabItem.id == GenderAttempt.vocab_item_id)
        .where(GenderAttempt.user_id == user_id, *gender_eligible_clause())
        .order_by(GenderAttempt.attempted_at.desc(), GenderAttempt.id.desc())
    )
    rows = (await db.execute(stmt)).all()
    by_noun: dict[UUID, list] = {}
    for r in rows:
        by_noun.setdefault(r.vocab_item_id, []).append(r)

    weak: list[tuple[int, float, UUID]] = []
    for vid, attempts in by_noun.items():
        state = _gender_noun_state(attempts, GENDER_MASTERY_STREAK_N)
        if state in _GENDER_WEAK_STATES:
            weak.append((_GENDER_TIER[state], attempts[0].attempted_at.timestamp(), vid))
    weak.sort(key=lambda t: (t[0], t[1], str(t[2])))
    return [vid for _, _, vid in weak[:limit]]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -v`
Expected: PASS (the four new tests + all pre-existing competence tests).

- [ ] **Step 5: Lint, format, commit**

```bash
cd backend && uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/curriculum/competence.py backend/tests/test_curriculum_competence.py
git commit -m "feat(curriculum): weak_gender_nouns — cross-module column-projected weak-set selector"
```

---

### Task 5: `routers/gender.py` — the gender review queue + standalone grade

**Files:**
- Create: `backend/src/klara/routers/gender.py`
- Modify: `backend/src/klara/main.py` (mount the router, near line 223)
- Test: `backend/tests/test_gender_review.py` (new — authed endpoint tests)

**Interfaces:**
- Consumes: `weak_gender_nouns` (Task 4), `grade_gender_attempt` (Task 2), `GenderReviewItem`/`GenderAttemptIn`/`GenderAttemptOut` (Task 1), `DBSession`/`CurrentUser`/`LocaleDep`, `t`, `VocabItem`.
- Produces: `GET /api/v1/gender/review?limit=20 -> list[GenderReviewItem]`; `POST /api/v1/gender/attempts -> GenderAttemptOut` (201).

- [ ] **Step 1: Write the failing endpoint tests**

Create `backend/tests/test_gender_review.py`:

```python
"""GET /gender/review (weak set, answer hidden) + POST /gender/attempts (standalone
oracle-gated grade). Authed via dependency overrides; lemmas uuid-suffixed."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from klara.auth.users import current_active_user
from klara.dependencies import db_session as db_session_dep
from klara.main import create_app
from klara.models import GenderAttempt, User, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


async def _user(db, *, native_language="es"):
    u = User(
        id=uuid.uuid4(),
        email=f"gr-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GR",
        level=CEFRLevel.A1,
        native_language=native_language,
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def _oracle_noun(db, *, lemma, gender, translations=None):
    v = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=lemma,
        pos=PartOfSpeech.NOUN,
        gender=gender,
        gender_source="oracle",
        translations=translations or {},
    )
    db.add(v)
    await db.flush()
    return v


def _client(db, user):
    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: user
    app.dependency_overrides[db_session_dep] = lambda: db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_review_returns_weak_only_answer_hidden(db_session):
    u = await _user(db_session)
    mastered = await _oracle_noun(db_session, lemma=f"Tisch{uuid.uuid4().hex[:6]}", gender="der")
    weak = await _oracle_noun(
        db_session, lemma=f"Lampe{uuid.uuid4().hex[:6]}", gender="die",
        translations={"es": "lámpara"},
    )
    for _ in range(3):
        db_session.add(GenderAttempt(
            id=uuid.uuid4(), user_id=u.id, vocab_item_id=mastered.id,
            picked_article="der", was_correct=True,
        ))
    db_session.add(GenderAttempt(
        id=uuid.uuid4(), user_id=u.id, vocab_item_id=weak.id,
        picked_article="der", was_correct=False,
    ))
    await db_session.commit()

    async with _client(db_session, u) as ac:
        resp = await ac.get("/api/v1/gender/review")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert [i["vocab_item_id"] for i in items] == [str(weak.id)]  # mastered excluded
    assert items[0]["lemma"] == weak.lemma and items[0]["en"] == "lámpara"
    assert "gender" not in items[0] and "correct_gender" not in items[0]  # answer hidden


@pytest.mark.asyncio
async def test_review_empty_when_caught_up(db_session):
    u = await _user(db_session)
    async with _client(db_session, u) as ac:
        resp = await ac.get("/api/v1/gender/review")
    assert resp.status_code == 200 and resp.json() == []


@pytest.mark.asyncio
async def test_grade_endpoint_records_and_grades(db_session):
    from sqlalchemy import select

    u = await _user(db_session)
    v = await _oracle_noun(db_session, lemma=f"Mond{uuid.uuid4().hex[:6]}", gender="der")
    await db_session.commit()
    async with _client(db_session, u) as ac:
        resp = await ac.post(
            "/api/v1/gender/attempts",
            json={"vocab_item_id": str(v.id), "picked_article": "die"},
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["was_correct"] is False and body["correct_gender"] == "der"
    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.user_id == u.id  # written to the caller's ledger


@pytest.mark.asyncio
async def test_grade_endpoint_404_for_non_oracle(db_session):
    u = await _user(db_session)
    llm = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"Llm{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN, gender="die", gender_source="llm",
    )
    db_session.add(llm)
    await db_session.commit()
    async with _client(db_session, u) as ac:
        resp = await ac.post(
            "/api/v1/gender/attempts",
            json={"vocab_item_id": str(llm.id), "picked_article": "die"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_grade_endpoint_is_user_isolated(db_session):
    """IDOR isolation: a grade always lands on the CALLER's ledger, never another
    user's. The vocab is shared; the attempt's user_id is server-derived."""
    from sqlalchemy import select

    owner = await _user(db_session)
    other = await _user(db_session)
    v = await _oracle_noun(db_session, lemma=f"Haus{uuid.uuid4().hex[:6]}", gender="das")
    await db_session.commit()
    async with _client(db_session, other) as ac:  # `other` is the authed caller
        resp = await ac.post(
            "/api/v1/gender/attempts",
            json={"vocab_item_id": str(v.id), "picked_article": "das"},
        )
    assert resp.status_code == 201
    rows = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalars().all()
    assert len(rows) == 1 and rows[0].user_id == other.id  # never owner.id
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && uv run pytest tests/test_gender_review.py -v`
Expected: FAIL — 404s on `/api/v1/gender/review` and `/api/v1/gender/attempts` (router not mounted yet).

- [ ] **Step 3: Create `routers/gender.py`**

Create `backend/src/klara/routers/gender.py`:

```python
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from klara.curriculum.competence import weak_gender_nouns
from klara.dependencies import CurrentUser, DBSession, LocaleDep
from klara.i18n import t
from klara.models import VocabItem
from klara.schemas.gender import GenderAttemptIn, GenderAttemptOut, GenderReviewItem
from klara.services.gender_grading import grade_gender_attempt

router = APIRouter(prefix="/gender", tags=["gender"])


async def _load_words_ordered(db: DBSession, ids: list[UUID]) -> list[VocabItem]:
    """Load VocabItems for `ids`, preserving the input order."""
    rows = (await db.execute(select(VocabItem).where(VocabItem.id.in_(ids)))).scalars().all()
    by_id = {w.id: w for w in rows}
    return [by_id[i] for i in ids if i in by_id]


@router.get("/review", response_model=list[GenderReviewItem])
async def gender_review(
    db: DBSession, user: CurrentUser, limit: int = Query(20, ge=1, le=100)
) -> list[GenderReviewItem]:
    """The user's weak der/die/das nouns, priority-ordered. The answer is never
    in the payload — revealed only on grading. Empty when the user has no weak
    nouns (caught up, or never started)."""
    ids = await weak_gender_nouns(db, user_id=user.id, limit=limit)
    if not ids:
        return []
    words = await _load_words_ordered(db, ids)
    return [
        GenderReviewItem(
            vocab_item_id=w.id,
            lemma=w.lemma,
            en=(w.translations or {}).get(user.native_language),
        )
        for w in words
    ]


@router.post("/attempts", response_model=GenderAttemptOut, status_code=status.HTTP_201_CREATED)
async def grade(
    payload: GenderAttemptIn, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> GenderAttemptOut:
    """Grade a standalone der/die/das pick (no story scope). Oracle-gated: 404 if
    the noun is not oracle-gradable. The attempt is recorded for the caller."""
    out = await grade_gender_attempt(
        db, user_id=user.id, vocab_item_id=payload.vocab_item_id, picked_article=payload.picked_article
    )
    if out is None:
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))
    return out
```

- [ ] **Step 4: Mount the router in `main.py`**

In `backend/src/klara/main.py`: add `gender` to the routers import block (the `from klara.routers import (...)` near the top — match the existing style), and add this line after the srs mount (line 223):

```python
    app.include_router(gender.router, prefix="/api/v1")
```

- [ ] **Step 5: Run the endpoint tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_gender_review.py -v`
Expected: PASS (all five: weak-only/answer-hidden, empty, grade-records, 404-non-oracle, IDOR-isolation).

- [ ] **Step 6: Full backend suite + lint/format, commit**

```bash
cd backend && uv run pytest -q
uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/routers/gender.py backend/src/klara/main.py backend/tests/test_gender_review.py
git commit -m "feat(gender): /gender router — review queue + standalone oracle-gated grade"
```

Expected: full suite green (the prior ~286 + the new B2a tests).

---

## Definition of done (before opening the PR)

- [ ] **Full backend suite green:** `cd backend && uv run pytest -q`
- [ ] **Lint + format check clean (as CI):** `cd backend && uv run ruff check src tests && uv run ruff format --check src tests`
- [ ] No new migration/table/conftest TRUNCATE entry; `services/gender_grading.py` imports no `fastapi`.
- [ ] `weak_gender_nouns` still uses `.all()` (4 columns), not `.scalars()`.
- [ ] `record_gender_attempt`'s membership 404 still fires before the helper; its existing tests pass.
- [ ] PR targets `main` from `feat/gender-srs-b2a`; the spec commits + the five task commits are present. PR description notes B2b (frontend) is the follow-up and that the endpoints are dormant until then.

## Self-review notes (spec coverage)

- weak_gender_nouns (column-projected, limit-after-sort) → Task 4. ✓
- grade_gender_attempt (framework-free, None-not-404) → Task 2; rewire → Task 3. ✓
- `/gender` router, honest naming, answer hidden, IDOR test → Task 5. ✓
- schemas/gender.py consolidation + GenderReviewItem → Task 1. ✓
- Oracle-gate-only integrity + IDOR isolation test → Task 5. ✓
- Cost ceiling / projection load-bearing → enforced by code comment + the `.all()` constraint (no public-API test can catch a `.scalars()` regression; noted honestly). ✓
- model docstring update → Task 2 Step 5. ✓
- Deferred to B2b: picker extraction, screen, client/types, Home tile, i18n, CSS. ✓ (not in this plan)
