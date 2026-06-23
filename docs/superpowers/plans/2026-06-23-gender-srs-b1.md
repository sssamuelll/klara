# Gender SRS — Slice B1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a learner opens a story's quiz, the single gender cloze targets the *weakest* der/die/das noun already present in that story (not the first), derived on-read from the existing `GenderAttempt` ledger with no new state.

**Architecture:** Extract one canonical gender-eligibility predicate (replacing three hand-copied read sites); add a pure mastery-state classifier and a story-scoped weakness-ordering query in `competence.py`; teach `build_gender_cloze` to honor a `prefer_order`; wire `get_story_quiz` to compute that order. No table, migration, endpoint, or schema changes.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, Postgres, pytest (`asyncio_mode = "auto"`), ruff. Spec: `docs/superpowers/specs/2026-06-23-gender-srs-b1-design.md`.

## Global Constraints

- **Branch:** work on `feat/gender-srs-b1` (already exists; the spec is committed there).
- **Tests:** `uv run pytest <path> -v` from `backend/`. Async tests use `@pytest.mark.asyncio` (the suite is `asyncio_mode = "auto"`, but match the existing files).
- **Lint/format every commit, as two separate commands** (a uv deprecation warning on stderr can flip `$?`, so never gate `ruff format` on `ruff check`'s exit):
  - `uv run ruff check --fix src tests`
  - `uv run ruff format src tests`
  - CI runs both `ruff check` and `ruff format --check`.
- **No new table / migration / endpoint / schema / `conftest` TRUNCATE entry** (derived-on-read).
- **`record_gender_attempt`'s gate (`stories.py:516`) is NOT touched.** Only three read sites are migrated to the shared predicate.
- **`vocab_items` is not truncated per test** → seed lemmas with `uuid.uuid4().hex[:8]` suffixes (existing convention). `gender_attempts` IS truncated.
- **Gender stays display-only / never gates advancement.** `advance_module_if_mastered` is untouched.
- **German-only:** the predicate is `de + oracle NOUN + gender ∈ {der,die,das}`.
- **Deferred to B2 (do NOT build here):** `weak_gender_nouns` cross-module selector and the soft generation bias.

---

### Task 1: Canonical eligibility predicate

**Files:**
- Create: `backend/src/klara/curriculum/gender_eligibility.py`
- Test: `backend/tests/test_gender_eligibility.py`

**Interfaces:**
- Consumes: `klara.models.VocabItem`, `klara.models.enums.PartOfSpeech`.
- Produces:
  - `GENDER_ARTICLES: tuple[str, ...] = ("der", "die", "das")`
  - `is_gender_eligible(w: VocabItem) -> bool`
  - `gender_eligible_clause() -> tuple` (SQLAlchemy conditions over `VocabItem`, to splat into `.where(*gender_eligible_clause())`)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_gender_eligibility.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_gender_eligibility.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum.gender_eligibility'`.

- [ ] **Step 3: Create the module**

Create `backend/src/klara/curriculum/gender_eligibility.py`:

```python
"""Canonical gender-eligibility predicate.

A noun is "gender-gradable" iff it is a German NOUN whose gender is
oracle-sourced and one of der/die/das. This predicate was hand-copied across
several read sites; this module is the single source of truth they share.
"""

from __future__ import annotations

from klara.models import VocabItem
from klara.models.enums import PartOfSpeech

GENDER_ARTICLES: tuple[str, ...] = ("der", "die", "das")


def is_gender_eligible(w: VocabItem) -> bool:
    """In-memory predicate for a loaded VocabItem."""
    return (
        w.language == "de"
        and w.pos == PartOfSpeech.NOUN
        and w.gender_source == "oracle"
        and w.gender in GENDER_ARTICLES
    )


def gender_eligible_clause() -> tuple:
    """The same predicate as SQLAlchemy conditions over VocabItem columns, to
    splat into `.where(*gender_eligible_clause())`."""
    return (
        VocabItem.language == "de",
        VocabItem.gender_source == "oracle",
        VocabItem.pos == PartOfSpeech.NOUN,
        VocabItem.gender.in_(list(GENDER_ARTICLES)),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_gender_eligibility.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Lint, format, commit**

```bash
cd backend && uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/curriculum/gender_eligibility.py backend/tests/test_gender_eligibility.py
git commit -m "feat(curriculum): canonical gender-eligibility predicate"
```

---

### Task 2: Migrate the two read sites to the shared predicate

Behavior-preserving refactor of `module_gender_progress` and the L1-notes endpoint. The existing suites are the safety net; no new behavior.

**Files:**
- Modify: `backend/src/klara/curriculum/competence.py` (the `module_gender_progress` eligible subquery, ~lines 128-134; and the import at line 17)
- Modify: `backend/src/klara/routers/stories.py` (the L1-notes comprehension, ~lines 326-333; and the import at line 40)
- Test (regression only): `backend/tests/test_curriculum_competence.py`, `backend/tests/test_l1_notes_endpoint.py`

**Interfaces:**
- Consumes: `gender_eligible_clause` and `is_gender_eligible` from Task 1.
- Produces: no new symbols (the two functions keep their signatures).

- [ ] **Step 1: Confirm the regression tests currently pass**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py tests/test_l1_notes_endpoint.py -q`
Expected: PASS (these are the safety net before refactoring).

- [ ] **Step 2: Migrate `module_gender_progress` in `competence.py`**

Add the import near the existing curriculum import (after line 15):

```python
from klara.curriculum.gender_eligibility import gender_eligible_clause
```

Change the import at line 17 from:

```python
from klara.models.enums import CardState, PartOfSpeech
```
to (PartOfSpeech becomes unused after this edit — it was only at line 132):
```python
from klara.models.enums import CardState
```

Replace the eligible subquery's `.where(...)` (lines 128-134) — from:

```python
                .where(
                    module_vocab.c.module_id == module_id,
                    VocabItem.language == "de",
                    VocabItem.gender_source == "oracle",
                    VocabItem.pos == PartOfSpeech.NOUN,
                    VocabItem.gender.in_(["der", "die", "das"]),
                )
```
to:
```python
                .where(
                    module_vocab.c.module_id == module_id,
                    *gender_eligible_clause(),
                )
```

- [ ] **Step 3: Migrate the L1-notes comprehension in `stories.py`**

Add the import alongside the other curriculum imports (near lines 20-27):

```python
from klara.curriculum.gender_eligibility import is_gender_eligible
```

Replace the comprehension (lines 326-333) — from:

```python
    eligible: dict[str, str] = {
        w.lemma.lower(): w.gender
        for w in words
        if w.language == "de"
        and w.pos == PartOfSpeech.NOUN
        and w.gender_source == "oracle"
        and w.gender in ("der", "die", "das")
    }
```
to:
```python
    eligible: dict[str, str] = {
        w.lemma.lower(): w.gender for w in words if is_gender_eligible(w)
    }
```

Then remove the now-unused `from klara.models.enums import PartOfSpeech` at line 40 **only if** `ruff check` reports it as unused (Step 5 will catch it; `PartOfSpeech` was used only at line 330).

- [ ] **Step 4: Run the regression suites**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py tests/test_l1_notes_endpoint.py tests/test_gender_cloze.py -q`
Expected: PASS — identical behavior, predicate now shared. (`test_module_gender_progress_tristate`, `test_module_gender_progress_zero_when_no_eligible`, and the L1-notes exclusion tests still pass.)

- [ ] **Step 5: Lint, format, commit**

```bash
cd backend && uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/curriculum/competence.py backend/src/klara/routers/stories.py
git commit -m "refactor(curriculum): module-progress + l1-notes use the shared gender predicate"
```

`ruff check --fix` drops the now-unused `PartOfSpeech` imports. If it does not (e.g. another use remains), leave the import in place — do not force-remove.

---

### Task 3: Mastery-state classifier + story-scoped weakness order

**Files:**
- Modify: `backend/src/klara/curriculum/competence.py` (append after `module_gender_progress`, end of file)
- Test: `backend/tests/test_curriculum_competence.py` (append)

**Interfaces:**
- Consumes: `_streak_mastered`, `GENDER_MASTERY_STREAK_N`, `GenderAttempt`, `select`, `AsyncSession`, `UUID` (all already imported in `competence.py`).
- Produces:
  - `_gender_noun_state(attempts_desc: list, n: int) -> str` — one of `"unseen" | "wrong_recent" | "in_progress" | "mastered"`.
  - `gender_weakness_order(db: AsyncSession, *, user_id: UUID, vocab_item_ids: list[UUID]) -> list[UUID]` — input ids reordered by cloze-pick priority; returns every id exactly once.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_curriculum_competence.py`. First extend the import at lines 9-18 to add the two new names:

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
)
```

Then append these tests (reuse the file's existing `_user`, `_de_oracle_noun`, and `datetime`/`timedelta`/`UTC` patterns):

```python
def test_gender_noun_state_classifies():
    class _A:
        def __init__(self, was_correct):
            self.was_correct = was_correct

    n = GENDER_MASTERY_STREAK_N
    assert _gender_noun_state([], n) == "unseen"
    assert _gender_noun_state([_A(True), _A(True), _A(True)], n) == "mastered"
    assert _gender_noun_state([_A(False), _A(True), _A(True)], n) == "wrong_recent"
    assert _gender_noun_state([_A(True), _A(False)], n) == "in_progress"
    # a mastered streak then a NEWER wrong attempt → wrong_recent (remediation trigger)
    assert _gender_noun_state([_A(False), _A(True), _A(True), _A(True)], n) == "wrong_recent"


async def _attempt(db, *, uid, vid, correct, at=None):
    from datetime import datetime, timedelta

    import uuid as _u

    ga = GenderAttempt(
        id=_u.uuid4(),
        user_id=uid,
        vocab_item_id=vid,
        picked_article="der",
        was_correct=correct,
    )
    if at is not None:
        ga.attempted_at = at
    db.add(ga)


@pytest.mark.asyncio
async def test_gender_weakness_order_ranks_wrong_recent_before_mastered(db_session):
    uid = await _user(db_session)
    a = await _de_oracle_noun(db_session, gender="der")  # will be mastered
    b = await _de_oracle_noun(db_session, gender="die")  # will be wrong_recent
    for _ in range(3):
        await _attempt(db_session, uid=uid, vid=a.id, correct=True)
    await _attempt(db_session, uid=uid, vid=b.id, correct=False)
    await db_session.commit()

    assert await gender_weakness_order(db_session, user_id=uid, vocab_item_ids=[a.id, b.id]) == [
        b.id,
        a.id,
    ]
    # input order does not matter for the weak-vs-mastered ranking
    assert await gender_weakness_order(db_session, user_id=uid, vocab_item_ids=[b.id, a.id]) == [
        b.id,
        a.id,
    ]


@pytest.mark.asyncio
async def test_gender_weakness_order_all_mastered_preserves_input_order(db_session):
    from datetime import datetime, timedelta

    uid = await _user(db_session)
    a = await _de_oracle_noun(db_session, gender="der")
    b = await _de_oracle_noun(db_session, gender="die")
    base = datetime(2026, 1, 1, tzinfo=UTC)
    # a mastered OLDER, b mastered NEWER — recency must be IGNORED for mastered tier
    for i in range(3):
        await _attempt(db_session, uid=uid, vid=a.id, correct=True, at=base + timedelta(minutes=i))
    for i in range(3):
        await _attempt(
            db_session, uid=uid, vid=b.id, correct=True, at=base + timedelta(hours=1, minutes=i)
        )
    await db_session.commit()

    assert await gender_weakness_order(db_session, user_id=uid, vocab_item_ids=[a.id, b.id]) == [
        a.id,
        b.id,
    ]
    assert await gender_weakness_order(db_session, user_id=uid, vocab_item_ids=[b.id, a.id]) == [
        b.id,
        a.id,
    ]


@pytest.mark.asyncio
async def test_gender_weakness_order_all_unseen_preserves_input_order(db_session):
    uid = await _user(db_session)
    a = await _de_oracle_noun(db_session, gender="der")
    b = await _de_oracle_noun(db_session, gender="die")
    await db_session.commit()  # no attempts at all

    assert await gender_weakness_order(db_session, user_id=uid, vocab_item_ids=[a.id, b.id]) == [
        a.id,
        b.id,
    ]


@pytest.mark.asyncio
async def test_gender_weakness_order_cycles_least_recent_first_within_weak_tier(db_session):
    from datetime import datetime, timedelta

    uid = await _user(db_session)
    a = await _de_oracle_noun(db_session, gender="der")  # wrong at minute 1 (older)
    b = await _de_oracle_noun(db_session, gender="die")  # wrong at minute 5 (newer)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    await _attempt(db_session, uid=uid, vid=a.id, correct=False, at=base + timedelta(minutes=1))
    await _attempt(db_session, uid=uid, vid=b.id, correct=False, at=base + timedelta(minutes=5))
    await db_session.commit()

    # both wrong_recent → least-recently-attempted (a) first, regardless of input order
    assert await gender_weakness_order(db_session, user_id=uid, vocab_item_ids=[b.id, a.id]) == [
        a.id,
        b.id,
    ]


@pytest.mark.asyncio
async def test_gender_weakness_order_empty(db_session):
    uid = await _user(db_session)
    assert await gender_weakness_order(db_session, user_id=uid, vocab_item_ids=[]) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -k "gender_weakness_order or gender_noun_state" -v`
Expected: FAIL — `ImportError: cannot import name '_gender_noun_state'` (and `gender_weakness_order`).

- [ ] **Step 3: Implement the classifier and ordering helper**

Append to `backend/src/klara/curriculum/competence.py` (end of file):

```python
def _gender_noun_state(attempts_desc: list, n: int) -> str:
    """Classify one noun's gender evidence (attempts_desc[0] is newest):
    'unseen' (no attempts) | 'mastered' (newest n all correct) |
    'wrong_recent' (newest attempt wrong) | 'in_progress' (otherwise).
    Reuses _streak_mastered as the mastery source of truth. Note: the state is a
    function of (attempts, n, read-time), not a permanent property — a mastered
    noun answered wrong becomes 'wrong_recent', which is the remediation trigger."""
    if not attempts_desc:
        return "unseen"
    if _streak_mastered(attempts_desc, n):
        return "mastered"
    if not attempts_desc[0].was_correct:
        return "wrong_recent"
    return "in_progress"


_GENDER_TIER = {"wrong_recent": 0, "in_progress": 1, "unseen": 2, "mastered": 3}
_GENDER_WEAK_STATES = frozenset({"wrong_recent", "in_progress"})


async def gender_weakness_order(
    db: AsyncSession, *, user_id: UUID, vocab_item_ids: list[UUID]
) -> list[UUID]:
    """Order the given nouns by gender-cloze pick priority for this user:
    wrong_recent > in_progress > unseen > mastered. Within the weak tiers,
    least-recently-attempted first (cycle, don't hammer). Within unseen/mastered,
    preserve the caller's input order (back-compat with the old first-eligible
    pick). Returns every input id exactly once. Bounded by the input id list and
    served by ix_gender_attempt_user_vocab — a handful of rows."""
    if not vocab_item_ids:
        return []
    rows = (
        (
            await db.execute(
                select(GenderAttempt)
                .where(
                    GenderAttempt.user_id == user_id,
                    GenderAttempt.vocab_item_id.in_(vocab_item_ids),
                )
                .order_by(GenderAttempt.attempted_at.desc(), GenderAttempt.id.desc())
            )
        )
        .scalars()
        .all()
    )
    by_noun: dict[UUID, list] = {}
    for r in rows:
        by_noun.setdefault(r.vocab_item_id, []).append(r)

    def _key(idx_vid: tuple[int, UUID]) -> tuple[int, float, int]:
        idx, vid = idx_vid
        attempts = by_noun.get(vid, [])
        state = _gender_noun_state(attempts, GENDER_MASTERY_STREAK_N)
        if state in _GENDER_WEAK_STATES:
            # attempts[0] is the most-recent attempt; ascending epoch surfaces the
            # noun whose most-recent attempt is oldest (cycle). .timestamp() is a
            # float, sidestepping any None/naive-aware datetime comparison.
            return (_GENDER_TIER[state], attempts[0].attempted_at.timestamp(), idx)
        # unseen/mastered: constant recency so idx (input/target order) decides.
        return (_GENDER_TIER[state], 0.0, idx)

    return [vid for _, vid in sorted(enumerate(vocab_item_ids), key=_key)]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -v`
Expected: PASS (the new tests plus all pre-existing competence tests).

- [ ] **Step 5: Lint, format, commit**

```bash
cd backend && uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/curriculum/competence.py backend/tests/test_curriculum_competence.py
git commit -m "feat(curriculum): gender mastery-state classifier + story weakness ordering"
```

---

### Task 4: `build_gender_cloze` honors a weakness order

**Files:**
- Modify: `backend/src/klara/services/finish_lessons.py` (the `build_gender_cloze` function, lines 150-174; imports at lines 19-20)
- Test: `backend/tests/test_gender_cloze.py` (append pure tests)

**Interfaces:**
- Consumes: `is_gender_eligible` from Task 1; `prefer_order` is a `list[UUID]` such as `gender_weakness_order`'s return (Task 3).
- Produces: `build_gender_cloze(words: list[VocabItem], *, native_language: str, prefer_order: list[UUID] | None = None) -> dict | None` — `native_language` stays **keyword-only**; the returned dict keys are unchanged (`type, cap, lemma, vocab_item_id, en`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_gender_cloze.py`:

```python
def test_build_gender_cloze_prefer_order_picks_weakest():
    from klara.services.finish_lessons import build_gender_cloze

    a = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Tisch",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
        translations={"es": "mesa"},
    )
    b = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Lampe",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="oracle",
        translations={"es": "lámpara"},
    )
    # a is first in target order, but prefer_order ranks b ahead → b is chosen.
    item = build_gender_cloze([a, b], native_language="es", prefer_order=[b.id, a.id])
    assert item["vocab_item_id"] == str(b.id)
    assert item["lemma"] == "Lampe"


def test_build_gender_cloze_prefer_order_none_picks_first_eligible():
    from klara.services.finish_lessons import build_gender_cloze

    a = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Tisch",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
        translations={"es": "mesa"},
    )
    b = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma="Lampe",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="oracle",
        translations={"es": "lámpara"},
    )
    # No prefer_order → first eligible in target order (back-compat).
    item = build_gender_cloze([a, b], native_language="es")
    assert item["vocab_item_id"] == str(a.id)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -k "prefer_order" -v`
Expected: FAIL — `TypeError: build_gender_cloze() got an unexpected keyword argument 'prefer_order'`.

- [ ] **Step 3: Update `build_gender_cloze`**

In `backend/src/klara/services/finish_lessons.py`, update the imports. Add to the standard-library import group (alongside `import json` / `import re`, lines 11-12):

```python
from uuid import UUID
```

(`from __future__ import annotations` is already present, so the `list[UUID]` annotation is lazy; the import is for clarity and is recognized by ruff as annotation usage.)

Add (with the other `klara` imports, after line 19):

```python
from klara.curriculum.gender_eligibility import is_gender_eligible
```

Change line 20 from:

```python
from klara.models.enums import PartOfSpeech
```
to nothing — remove it (it was used only inside `build_gender_cloze`; Step 5's `ruff check` confirms it is unused).

Replace the whole function body (lines 150-174):

```python
def build_gender_cloze(
    words: list[VocabItem],
    *,
    native_language: str,
    prefer_order: list[UUID] | None = None,
) -> dict | None:
    """Deterministically build a der/die/das cloze from an oracle-gendered story
    target noun. Returns the quiz item dict, or None when no oracle-gendered noun
    is available (the quiz is served unchanged). The correct article is NOT
    included: grading is server-side (POST /gender/attempts).

    When prefer_order is given (a ranking of vocab ids, e.g. from
    gender_weakness_order), the eligible nouns are ordered by it before the first
    is picked, so the weakest gender noun present is remediated. With
    prefer_order=None the first eligible noun in target order is picked —
    identical to the prior behavior.

    Eligibility (German der/die/das oracle NOUN) is delegated to
    is_gender_eligible so the predicate stays single-sourced."""
    eligible = [w for w in words if is_gender_eligible(w)]
    if not eligible:
        return None
    if prefer_order:
        rank = {vid: i for i, vid in enumerate(prefer_order)}
        eligible.sort(key=lambda w: rank.get(w.id, len(prefer_order)))
    chosen = eligible[0]
    return {
        "type": "gender_cloze",
        "cap": "gender",  # frontend localizes the caption
        "lemma": chosen.lemma,
        "vocab_item_id": str(chosen.id),
        "en": (chosen.translations or {}).get(native_language),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v`
Expected: PASS — the two new `prefer_order` tests plus the existing `test_build_gender_cloze_picks_oracle_noun`, `..._none_when_no_oracle_noun`, `..._skips_non_german_oracle_noun`, and `test_get_quiz_appends_gender_cloze` (the caller still passes only `native_language`, so the default `prefer_order=None` keeps it green).

- [ ] **Step 5: Lint, format, commit**

```bash
cd backend && uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/services/finish_lessons.py backend/tests/test_gender_cloze.py
git commit -m "feat(finish): build_gender_cloze honors a weakness prefer_order"
```

---

### Task 5: Wire `get_story_quiz` to prioritize the weakest noun

**Files:**
- Modify: `backend/src/klara/routers/stories.py` (`get_story_quiz`, lines 258-273; add a `competence` import near lines 20-27)
- Test: `backend/tests/test_gender_cloze.py` (append an endpoint integration test)

**Interfaces:**
- Consumes: `gender_weakness_order` (Task 3) and `build_gender_cloze`'s `prefer_order` (Task 4).
- Produces: no new symbols; `GET /stories/{id}/quiz` now appends the gender cloze for the weakest eligible noun in the story.

- [ ] **Step 1: Write the failing integration test**

Append to `backend/tests/test_gender_cloze.py` (mirrors `test_get_quiz_appends_gender_cloze`):

```python
@pytest.mark.asyncio
async def test_get_quiz_targets_weakest_gender_noun(db_session):
    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app
    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    u = User(
        id=uuid.uuid4(),
        email=f"gw-{uuid.uuid4().hex[:6]}@k.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="GW",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    strong = VocabItem(  # FIRST in target order, but mastered → must NOT be picked
        id=uuid.uuid4(),
        language="de",
        lemma=f"Tisch{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="der",
        gender_source="oracle",
    )
    weak = VocabItem(  # second in target order, recently wrong → must be picked
        id=uuid.uuid4(),
        language="de",
        lemma=f"Lampe{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        gender="die",
        gender_source="oracle",
    )
    db_session.add_all([u, strong, weak])
    await db_session.flush()
    for _ in range(3):  # strong mastered
        db_session.add(
            GenderAttempt(
                id=uuid.uuid4(),
                user_id=u.id,
                vocab_item_id=strong.id,
                picked_article="der",
                was_correct=True,
            )
        )
    db_session.add(  # weak: most recent attempt wrong
        GenderAttempt(
            id=uuid.uuid4(),
            user_id=u.id,
            vocab_item_id=weak.id,
            picked_article="der",
            was_correct=False,
        )
    )
    story = Story(
        id=uuid.uuid4(),
        user_id=u.id,
        level=CEFRLevel.A1,
        target_language="de",
        native_language="es",
        title="t",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[strong.id, weak.id],  # strong first
        quiz_items=[{"type": "shadow", "cap": "x", "sentence": "Hallo.", "en": "Hola."}],
    )
    db_session.add(story)
    await db_session.commit()

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/api/v1/stories/{story.id}/quiz")
    assert resp.status_code == 200, resp.text
    gc = resp.json()["items"][-1]
    assert gc["type"] == "gender_cloze"
    assert gc["vocab_item_id"] == str(weak.id)  # weakest picked, not the first/mastered one
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py::test_get_quiz_targets_weakest_gender_noun -v`
Expected: FAIL — the assertion fails because the unmodified `get_story_quiz` still picks the first eligible noun (`strong.id`), so `gc["vocab_item_id"] == str(weak.id)` is False.

- [ ] **Step 3: Wire the caller**

In `backend/src/klara/routers/stories.py`, add the import alongside the other curriculum imports (near lines 20-27):

```python
from klara.curriculum.competence import gender_weakness_order
```

Replace the body of `get_story_quiz` (lines 266-273) — from:

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
to:
```python
    story = await _load_or_404(db, story_id, user.id, locale)
    words = await _load_words(db, list(story.target_vocab_item_ids or []))
    lemmas = [w.lemma for w in words]
    items = list(await ensure_quiz_items(db, story, llm, lemmas=lemmas) or [])
    prefer = await gender_weakness_order(
        db, user_id=user.id, vocab_item_ids=[w.id for w in words]
    )
    gender_cloze = build_gender_cloze(
        words, native_language=user.native_language, prefer_order=prefer
    )
    if gender_cloze is not None:
        items.append(gender_cloze)
    return QuizOut(items=items)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v`
Expected: PASS — `test_get_quiz_targets_weakest_gender_noun` plus `test_get_quiz_appends_gender_cloze` (single-noun story still appends the cloze).

- [ ] **Step 5: Lint, format, commit**

```bash
cd backend && uv run ruff check --fix src tests
uv run ruff format src tests
cd .. && git add backend/src/klara/routers/stories.py backend/tests/test_gender_cloze.py
git commit -m "feat(stories): quiz gender cloze targets the weakest noun present"
```

---

## Definition of done (run before opening the PR)

- [ ] **Full backend suite green:**
  `cd backend && uv run pytest -q`
- [ ] **Lint + format check clean (as CI runs them):**
  `cd backend && uv run ruff check src tests && uv run ruff format --check src tests`
- [ ] No new migration, table, endpoint, schema, or `conftest` TRUNCATE entry was added.
- [ ] `record_gender_attempt`'s gate is unchanged; `advance_module_if_mastered` is unchanged.
- [ ] PR targets `main` from `feat/gender-srs-b1`; the spec commit + the five task commits are present.

## Self-review notes (spec coverage)

- Canonical predicate + 3 read-site migration → Tasks 1, 2 (cloze site migrated in Task 4). ✓
- `_gender_noun_state` classifier → Task 3. ✓
- `gender_weakness_order` with the weak-tier-recency / non-weak-tier-input-order tie-break (the back-compat fix) → Task 3 (+ tests asserting all-mastered and all-unseen preserve input order). ✓
- `build_gender_cloze` keyword-only `native_language` + `prefer_order` → Task 4. ✓
- `get_story_quiz` wiring (`get_story_quiz`, not a "finish" path) → Task 5. ✓
- Edge cases (no attempts, all mastered, no eligible, empty) → covered by Task 3 and Task 4 tests. ✓
- Deferred (selector, generation bias, gate tightening) → not in any task, by design. ✓
