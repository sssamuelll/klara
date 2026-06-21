# Slice 3 PR-C — gender pedagogy (suffix-rule feedback + gender mastery) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add authoritative, deterministic gender-suffix feedback at grade time (persisted + returned, never less authoritative than the oracle) and a display-only gender-mastery tri-state on the module — backend-only.

**Architecture:** A pure suffix detector (`detect_gender_rule`) + reconciler (`reconcile_rule`) compute a der/die/das rule from a lemma and reconcile it against the per-word oracle gender (oracle always wins; the rule is shown only when it agrees or the lemma is a curated closed-exception). The result persists to the reserved `GenderAttempt.detail` JSONB and returns via a new optional field on `GenderAttemptOut`. A shared pure streak helper feeds both `is_mastered_gender` (per-noun contract predicate) and `module_gender_progress` (the live consumer), surfaced as a `gender_encountered/mastered/total` tri-state on `ModuleCurrentOut` — never into the advancement gate.

**Tech Stack:** FastAPI, SQLAlchemy async, Postgres, Pydantic, pytest. No new deps. No migration (the `detail` JSONB column already exists; no table change).

**Spec:** `docs/superpowers/specs/2026-06-21-learning-sequence-slice3-prc-gender-pedagogy-design.md` (twice roster-reviewed). PR-A (#67) and PR-B (#68) are merged.

## Global Constraints

- Backend package `klara` under `backend/src/klara`; run all commands from `backend/`.
- ruff `select = E,F,I,B,UP,RUF`. After editing ANY python file (src AND tests), run `uv run ruff check --fix` AND `uv run ruff format` on it before committing. Imports: third-party before first-party `klara.*`, alphabetical; no mid-file (E402) module imports; no re-import (F811).
- Postgres test DB `german_app_test` at localhost:5432 (container `klara_postgres`). conftest manages the schema (session fixture: `alembic downgrade base` + `upgrade head`) and per-test TRUNCATEs `... module_vocab, modules, gender_attempts, gender_lexicon, users` but NOT `vocab_items` — so tests use unique (uuid-suffixed) lemmas for vocab. `modules`/`module_vocab`/`gender_attempts` ARE truncated.
- **Curriculum invariant (non-negotiable):** the per-word oracle gender (`VocabItem.gender`, only when `gender_source == 'oracle'`) is ALWAYS the displayed truth. A suffix rule is shown only when it AGREES with the oracle, or the lemma is in a hand-curated closed-exception list. `agreement` is the sole show-gate.
- **No answer leak:** the suffix payload goes ONLY on `GenderAttemptOut` (post-answer). `GenderClozeQuizItem` (pre-answer) MUST stay byte-identical — adding any field there breaks the hardened no-leak contract.
- Gender is German-only by contract: the detector is invoked only inside the existing `gender_source == 'oracle'` guard in `record_gender_attempt`.
- `GENDER_MASTERY_STREAK_N = 3`. Gender mastery is **display-only** — never wired into `advance_module_if_mastered`.

---

## File Structure

**Backend (create):**
- `backend/src/klara/curriculum/gender_rules.py` — pure detector + reconciler + curated-exception list + `GenderRule`/`GenderRuleDetail` types.
- `backend/tests/test_gender_rules.py` — pure unit tests (no DB, no async).

**Backend (modify):**
- `backend/src/klara/schemas/finish.py` — `GenderRuleOut`; add optional `rule` field to `GenderAttemptOut`.
- `backend/src/klara/routers/stories.py` — `record_gender_attempt`: compute rule/detail, persist `detail`, project the showable rule into the response.
- `backend/src/klara/curriculum/competence.py` — `GENDER_MASTERY_STREAK_N`, `_streak_mastered`, `is_mastered_gender`, `module_gender_progress`.
- `backend/src/klara/schemas/module.py` — `ModuleCurrentOut`: add `gender_encountered/gender_mastered/gender_total`.
- `backend/src/klara/routers/modules.py` — `get_current_module`: wire `module_gender_progress`.
- `backend/tests/test_gender_cloze.py` — append endpoint tests (detail persistence + response projection + no-leak).
- `backend/tests/test_curriculum_competence.py` — append `_streak_mastered`/`is_mastered_gender`/`module_gender_progress` tests.
- `backend/tests/test_modules.py` — append the `GET /modules/current` gender-tri-state test.

---

## Task 1: Pure suffix detector + reconciler (`gender_rules.py`)

**Files:**
- Create: `backend/src/klara/curriculum/gender_rules.py`
- Test: `backend/tests/test_gender_rules.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) GenderRule(suffix: str, rule_gender: str, suffix_class: str)` — `rule_gender ∈ {der,die,das}`, `suffix_class ∈ {hard,tendency}`.
  - `GenderRuleDetail` TypedDict: `{suffix: str, suffix_class: str, rule_gender: str, oracle_gender: str, agreement: bool, is_exception: bool}`.
  - `detect_gender_rule(lemma: str) -> GenderRule | None` — pure, longest-match (hard before tendency on ties), ≥2-codepoint stem guard.
  - `reconcile_rule(rule: GenderRule, oracle_gender: str, lemma: str) -> GenderRuleDetail` — only called with a non-None rule.
  - `_CURATED_EXCEPTIONS: dict[str, str]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_gender_rules.py`:

```python
"""Pure gender-suffix detector + oracle reconciliation (no DB, no async)."""

from klara.curriculum.gender_rules import (
    detect_gender_rule,
    reconcile_rule,
)


def test_detect_hard_suffixes_map_to_article_and_class():
    cases = {
        "Wohnung": ("ung", "die"),
        "Mädchen": ("chen", "das"),
        "Häuslein": ("lein", "das"),
        "Freiheit": ("heit", "die"),
        "Möglichkeit": ("keit", "die"),
        "Mannschaft": ("schaft", "die"),
        "Nation": ("ion", "die"),
        "Lehrling": ("ling", "der"),
        "Kapitalismus": ("ismus", "der"),
        "Dokument": ("ment", "das"),
        "Reichtum": ("tum", "das"),
    }
    for lemma, (suffix, gender) in cases.items():
        r = detect_gender_rule(lemma)
        assert r is not None, lemma
        assert (r.suffix, r.rule_gender, r.suffix_class) == (suffix, gender, "hard"), lemma


def test_detect_longest_match_wins():
    # -ität (4) beats -tät (3); both → die, but the longer suffix is reported.
    assert detect_gender_rule("Universität").suffix == "ität"


def test_detect_tendency_suffixes():
    r = detect_gender_rule("Mutter")  # the classic -er trap
    assert (r.rule_gender, r.suffix_class) == ("der", "tendency")
    assert detect_gender_rule("Blume").suffix_class == "tendency"  # -e → die (tendency)


def test_detect_none_when_no_suffix_or_stem_too_short():
    assert detect_gender_rule("Tisch") is None  # no matching suffix
    assert detect_gender_rule("xe") is None  # -e matches but stem "x" < 2 codepoints
    assert detect_gender_rule("") is None


def test_detect_nis_is_excluded():
    # -nis is genuinely two-gendered (die/das) → not a detector rule at all.
    assert detect_gender_rule("Ergebnis") is None
    assert detect_gender_rule("Erlaubnis") is None


def test_detect_schwung_still_detects_ung():
    # The detector is deliberately simple — Schwung detects -ung; suppression is
    # the reconciler's job (Case B), not the detector's.
    assert detect_gender_rule("Schwung").rule_gender == "die"


def test_reconcile_case_a_agreement():
    rule = detect_gender_rule("Wohnung")  # -ung → die
    d = reconcile_rule(rule, "die", "Wohnung")
    assert d == {
        "suffix": "ung",
        "suffix_class": "hard",
        "rule_gender": "die",
        "oracle_gender": "die",
        "agreement": True,
        "is_exception": False,
    }


def test_reconcile_case_b_tendency_disagrees_is_the_invariant():
    # -er → der but oracle die (die Mutter): disagreement, NOT curated → suppress.
    rule = detect_gender_rule("Mutter")
    d = reconcile_rule(rule, "die", "Mutter")
    assert d["agreement"] is False and d["is_exception"] is False


def test_reconcile_case_b_hard_false_positive():
    rule = detect_gender_rule("Schwung")  # -ung → die
    d = reconcile_rule(rule, "der", "Schwung")
    assert d["agreement"] is False and d["is_exception"] is False


def test_reconcile_case_c_curated_exception():
    rule = detect_gender_rule("Reichtum")  # -tum → das
    d = reconcile_rule(rule, "der", "Reichtum")  # oracle der; curated der
    assert d["agreement"] is False and d["is_exception"] is True


def test_reconcile_curated_only_when_value_matches_oracle():
    # Reichtum is curated 'der'; a nonsensical oracle 'die' must NOT be treated
    # as a curated exception (cross-check) → falls to Case B.
    rule = detect_gender_rule("Reichtum")
    d = reconcile_rule(rule, "die", "Reichtum")
    assert d["agreement"] is False and d["is_exception"] is False


def test_reconcile_uncurated_compound_falls_to_case_b():
    rule = detect_gender_rule("Privatreichtum")  # -tum → das, NOT in the curated list
    d = reconcile_rule(rule, "der", "Privatreichtum")
    assert d["agreement"] is False and d["is_exception"] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_gender_rules.py -v`
Expected: FAIL — `ImportError: cannot import name 'detect_gender_rule'`.

- [ ] **Step 3: Create the module**

Create `backend/src/klara/curriculum/gender_rules.py`:

```python
"""Deterministic German gender-suffix rules — a generalization OVER the oracle,
so the per-word oracle gender always wins; a rule surfaces only when it AGREES
with the oracle (or the lemma is a curated closed-exception). Pure, no DB."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

# Hard suffixes: ~100% reliable, teachable AS a rule. (suffix, article)
_HARD: list[tuple[str, str]] = [
    ("chen", "das"),
    ("lein", "das"),
    ("ung", "die"),
    ("heit", "die"),
    ("keit", "die"),
    ("schaft", "die"),
    ("ität", "die"),
    ("tät", "die"),
    ("tion", "die"),
    ("sion", "die"),
    ("ion", "die"),
    ("ling", "der"),
    ("ismus", "der"),
    ("ment", "das"),
    ("tum", "das"),
]
# Tendency suffixes: softened ("usually"), never absolute. Shown only on oracle
# agreement; suppressed (Case B) on disagreement, exactly like a hard suffix.
_TENDENCY: list[tuple[str, str]] = [
    ("e", "die"),
    ("er", "der"),
    ("el", "der"),
    ("en", "der"),
    ("ie", "die"),
    ("ik", "die"),
    ("ur", "die"),
]
# -nis is deliberately ABSENT: it is genuinely two-gendered (die/das), which a
# scalar rule_gender cannot represent, and it is "never a rule" pedagogically.

# Closed, enumerable exceptions to a hard suffix (Case C). Exact-lemma keys only.
_CURATED_EXCEPTIONS: dict[str, str] = {
    "Reichtum": "der",
    "Irrtum": "der",
}

# Stem remaining after stripping the suffix must be at least this many codepoints,
# to avoid firing on absurdly short words.
_MIN_STEM = 2


@dataclass(frozen=True, slots=True)
class GenderRule:
    suffix: str
    rule_gender: str  # der | die | das
    suffix_class: str  # hard | tendency


class GenderRuleDetail(TypedDict):
    suffix: str
    suffix_class: str
    rule_gender: str
    oracle_gender: str
    agreement: bool
    is_exception: bool


def detect_gender_rule(lemma: str) -> GenderRule | None:
    """Longest matching suffix → der/die/das + class. Among equal-length matches,
    hard beats tendency. Returns None when nothing matches with a ≥2-codepoint
    stem. Deliberately simple: false positives (der Schwung vs -ung) are caught
    by reconcile_rule against the oracle, not here."""
    lemma = (lemma or "").strip()
    # candidate key = (suffix_length, hard_priority); pick the max.
    best: tuple[int, int, GenderRule] | None = None
    for table, priority, cls in ((_HARD, 1, "hard"), (_TENDENCY, 0, "tendency")):
        for suffix, article in table:
            if lemma.endswith(suffix) and len(lemma) - len(suffix) >= _MIN_STEM:
                key = (len(suffix), priority)
                if best is None or key > best[:2]:
                    best = (key[0], key[1], GenderRule(suffix, article, cls))
    return best[2] if best is not None else None


def reconcile_rule(rule: GenderRule, oracle_gender: str, lemma: str) -> GenderRuleDetail:
    """Reconcile a detected rule against the authoritative oracle gender. Only
    invoked with a non-None rule (the no-suffix → None guard lives at the call
    site). agreement is the sole show-gate; is_exception is true only when the
    rule disagrees AND the lemma is curated with a value matching the oracle."""
    agreement = rule.rule_gender == oracle_gender
    is_exception = not agreement and _CURATED_EXCEPTIONS.get(lemma) == oracle_gender
    return {
        "suffix": rule.suffix,
        "suffix_class": rule.suffix_class,
        "rule_gender": rule.rule_gender,
        "oracle_gender": oracle_gender,
        "agreement": agreement,
        "is_exception": is_exception,
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_gender_rules.py -v`
Expected: PASS (all). Then `uv run ruff check --fix src/klara/curriculum/gender_rules.py tests/test_gender_rules.py` and `uv run ruff format src/klara/curriculum/gender_rules.py tests/test_gender_rules.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/curriculum/gender_rules.py backend/tests/test_gender_rules.py
git commit -m "feat(curriculum): pure German gender-suffix detector + oracle reconciler"
```

---

## Task 2: Persist `detail` + return the showable rule on `GenderAttemptOut`

**Files:**
- Modify: `backend/src/klara/schemas/finish.py`, `backend/src/klara/routers/stories.py`
- Test: `backend/tests/test_gender_cloze.py` (append)

**Interfaces:**
- Consumes (Task 1): `detect_gender_rule`, `reconcile_rule`, `GenderRuleDetail`.
- Produces:
  - `GenderRuleOut` (Pydantic): `{suffix: str, suffix_class: Literal["hard","tendency"], rule_gender: Literal["der","die","das"], is_exception: bool}`.
  - `GenderAttemptOut.rule: GenderRuleOut | None = None` (the showable projection; `None` on Case B / no-suffix).
  - `record_gender_attempt` now writes `GenderAttempt.detail` (the 6-key dict or `None`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_gender_cloze.py` (the file already imports `uuid`, `pytest`, `GenderAttempt`, `VocabItem`, `PartOfSpeech` at module top):

```python
async def _gender_story_user(db_session, *, lemma, gender, gender_source="oracle"):
    """Create a user + an oracle-gendered de NOUN + a story targeting it. Returns
    (user, vocab, story). Lemmas are unique-prefixed so the real German suffix
    stays at the END (the detector matches the suffix), while vocab_items (not
    truncated) stays collision-free."""
    import uuid as _uuid

    from klara.models import Story, User
    from klara.models.enums import CEFRLevel

    u = User(
        id=_uuid.uuid4(), email=f"gp-{_uuid.uuid4().hex[:6]}@k.app", hashed_password="x",
        is_active=True, is_verified=True, is_superuser=False, display_name="GP",
        level=CEFRLevel.A1, native_language="es", target_language="de",
    )
    v = VocabItem(
        id=_uuid.uuid4(), language="de", lemma=lemma,
        pos=PartOfSpeech.NOUN, gender=gender, gender_source=gender_source,
    )
    db_session.add_all([u, v])
    await db_session.flush()
    story = Story(
        id=_uuid.uuid4(), user_id=u.id, level=CEFRLevel.A1, target_language="de",
        native_language="es", title="t",
        content={"sentences": [], "comprehension_questions": []},
        target_vocab_item_ids=[v.id],
    )
    db_session.add(story)
    await db_session.commit()
    return u, v, story


async def _post_gender(db_session, u, story, vocab_id, picked):
    from httpx import ASGITransport, AsyncClient

    from klara.auth.users import current_active_user
    from klara.dependencies import db_session as db_session_dep
    from klara.main import create_app

    app = create_app()
    app.dependency_overrides[current_active_user] = lambda: u
    app.dependency_overrides[db_session_dep] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        return await ac.post(
            f"/api/v1/stories/{story.id}/gender/attempts",
            json={"vocab_item_id": str(vocab_id), "picked_article": picked},
        )


@pytest.mark.asyncio
async def test_gender_attempt_case_a_returns_rule_and_persists_detail(db_session):
    from sqlalchemy import select

    lemma = f"q{uuid.uuid4().hex[:8]}heit"  # ends in -heit (hard die)
    u, v, story = await _gender_story_user(db_session, lemma=lemma, gender="die")
    resp = await _post_gender(db_session, u, story, v.id, "die")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["was_correct"] is True
    assert body["rule"] == {
        "suffix": "heit", "suffix_class": "hard", "rule_gender": "die", "is_exception": False,
    }
    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.detail == {
        "suffix": "heit", "suffix_class": "hard", "rule_gender": "die",
        "oracle_gender": "die", "agreement": True, "is_exception": False,
    }


@pytest.mark.asyncio
async def test_gender_attempt_case_b_suppresses_rule_but_persists_detail(db_session):
    from sqlalchemy import select

    lemma = f"q{uuid.uuid4().hex[:8]}er"  # ends in -er (tendency der); oracle die → disagree
    u, v, story = await _gender_story_user(db_session, lemma=lemma, gender="die")
    resp = await _post_gender(db_session, u, story, v.id, "die")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["rule"] is None  # suppressed on the wire
    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.detail["agreement"] is False and row.detail["is_exception"] is False
    assert set(row.detail.keys()) == {
        "suffix", "suffix_class", "rule_gender", "oracle_gender", "agreement", "is_exception",
    }


@pytest.mark.asyncio
async def test_gender_attempt_no_suffix_null_detail_and_rule(db_session):
    lemma = f"klotz{uuid.uuid4().hex[:6]}x"  # ends in 'x' → no suffix match
    u, v, story = await _gender_story_user(db_session, lemma=lemma, gender="der")
    resp = await _post_gender(db_session, u, story, v.id, "der")
    assert resp.status_code == 201, resp.text
    assert resp.json()["rule"] is None
    from sqlalchemy import select

    row = (
        await db_session.execute(select(GenderAttempt).where(GenderAttempt.vocab_item_id == v.id))
    ).scalar_one()
    assert row.detail is None


def test_gender_cloze_quiz_item_has_no_rule_field():
    # No-leak contract: the PRE-answer quiz item must never carry the rule/answer.
    from klara.schemas.finish import GenderClozeQuizItem

    assert "rule" not in GenderClozeQuizItem.model_fields
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v -k "case_a or case_b or no_suffix or has_no_rule"`
Expected: FAIL — `body["rule"]` KeyError / `GenderAttemptOut` has no `rule` (and detail is never written).

- [ ] **Step 3: Add the `GenderRuleOut` schema + the optional field**

Modify `backend/src/klara/schemas/finish.py`. Add `GenderRuleOut` immediately before `GenderAttemptOut`, and add the `rule` field to `GenderAttemptOut` (`Literal` and `BaseModel` are already imported):

```python
class GenderRuleOut(BaseModel):
    suffix: str
    suffix_class: Literal["hard", "tendency"]
    rule_gender: Literal["der", "die", "das"]
    is_exception: bool


class GenderAttemptOut(BaseModel):
    was_correct: bool
    correct_gender: str
    rule: GenderRuleOut | None = None  # showable suffix rule (Case A/C); None otherwise
```

(Replace the existing `GenderAttemptOut` class — keep `was_correct`/`correct_gender`, add `rule`.)

- [ ] **Step 4: Wire the detector into `record_gender_attempt`**

Modify `backend/src/klara/routers/stories.py`. Add a new import line `from klara.curriculum.gender_rules import detect_gender_rule, reconcile_rule` (ruff `--fix` will place it in first-party alphabetical order), and add `GenderRuleOut` to the existing `from klara.schemas.finish import ...` line (which already imports `GenderAttemptIn, GenderAttemptOut`). Then change the body of `record_gender_attempt` from `was_correct = ...` through the `return` to:

```python
    was_correct = payload.picked_article == vocab.gender
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
            user_id=user.id,
            vocab_item_id=vocab.id,
            picked_article=payload.picked_article,
            was_correct=was_correct,
            detail=detail,
        )
    )
    await db.commit()
    return GenderAttemptOut(was_correct=was_correct, correct_gender=vocab.gender, rule=rule_out)
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_gender_cloze.py -v` then `uv run pytest -q` (full suite — no regression). Then `uv run ruff check --fix src tests` and `uv run ruff format src tests` (apply on touched files).

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/schemas/finish.py backend/src/klara/routers/stories.py backend/tests/test_gender_cloze.py
git commit -m "feat(stories): suffix-rule feedback on gender attempts (oracle wins, persisted to detail)"
```

---

## Task 3: Gender mastery — `_streak_mastered`, `is_mastered_gender`, `module_gender_progress`

**Files:**
- Modify: `backend/src/klara/curriculum/competence.py`
- Test: `backend/tests/test_curriculum_competence.py` (append)

**Interfaces:**
- Produces:
  - `GENDER_MASTERY_STREAK_N: int = 3`.
  - `_streak_mastered(attempts_desc: list, n: int) -> bool` — pure: `len >= n and all(a.was_correct for a in attempts_desc[:n])`. `attempts_desc` is ordered most-recent-first.
  - `is_mastered_gender(db, *, user_id: UUID, vocab_item_id: UUID) -> bool` (async).
  - `module_gender_progress(db, *, user_id: UUID, module_id: UUID) -> tuple[int, int, int]` → `(gender_encountered, gender_mastered, gender_total)`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_curriculum_competence.py`. Add these imports to the existing top-of-file import blocks: extend `from klara.curriculum.competence import (...)` with `GENDER_MASTERY_STREAK_N, _streak_mastered, is_mastered_gender, module_gender_progress`; extend `from klara.models import ...` with `GenderAttempt`. Then append:

```python
def test_streak_mastered_pure():
    class _A:
        def __init__(self, c):
            self.was_correct = c

    assert _streak_mastered([_A(True), _A(True), _A(True)], 3) is True
    assert _streak_mastered([_A(True), _A(True)], 3) is False  # < N attempts
    # Most recent (index 0) is a fail → streak broken.
    assert _streak_mastered([_A(False), _A(True), _A(True), _A(True)], 3) is False
    # The fail is OLDER than the last N → still mastered.
    assert _streak_mastered([_A(True), _A(True), _A(True), _A(False)], 3) is True
    assert GENDER_MASTERY_STREAK_N == 3


async def _de_oracle_noun(db, *, gender):
    v = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"N{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN, gender=gender, gender_source="oracle",
    )
    db.add(v)
    await db.flush()
    return v


@pytest.mark.asyncio
async def test_is_mastered_gender_streak_and_recency(db_session):
    from datetime import datetime, timedelta, timezone

    uid = await _user(db_session)
    v = await _de_oracle_noun(db_session, gender="der")
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, correct in enumerate([True, True, True]):  # 3 correct → mastered
        db_session.add(GenderAttempt(
            id=uuid.uuid4(), user_id=uid, vocab_item_id=v.id,
            picked_article="der", was_correct=correct, attempted_at=base + timedelta(minutes=i),
        ))
    await db_session.commit()
    assert await is_mastered_gender(db_session, user_id=uid, vocab_item_id=v.id) is True

    # A newer failed attempt breaks the most-recent-3 streak.
    db_session.add(GenderAttempt(
        id=uuid.uuid4(), user_id=uid, vocab_item_id=v.id,
        picked_article="die", was_correct=False, attempted_at=base + timedelta(minutes=9),
    ))
    await db_session.commit()
    assert await is_mastered_gender(db_session, user_id=uid, vocab_item_id=v.id) is False


@pytest.mark.asyncio
async def test_is_mastered_gender_false_below_floor(db_session):
    uid = await _user(db_session)
    v = await _de_oracle_noun(db_session, gender="die")
    for _ in range(2):  # only 2 attempts < N=3
        db_session.add(GenderAttempt(
            id=uuid.uuid4(), user_id=uid, vocab_item_id=v.id,
            picked_article="die", was_correct=True,
        ))
    await db_session.commit()
    assert await is_mastered_gender(db_session, user_id=uid, vocab_item_id=v.id) is False


@pytest.mark.asyncio
async def test_module_gender_progress_tristate(db_session):
    from klara.models import Module

    uid = await _user(db_session)
    mastered = await _de_oracle_noun(db_session, gender="der")  # 3 correct
    encountered = await _de_oracle_noun(db_session, gender="die")  # 2 attempts (< N)
    untouched = await _de_oracle_noun(db_session, gender="das")  # 0 attempts
    verb = VocabItem(  # not a NOUN → excluded
        id=uuid.uuid4(), language="de", lemma=f"V{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.VERB, gender=None, gender_source="oracle",
    )
    llm_noun = VocabItem(  # not oracle → excluded
        id=uuid.uuid4(), language="de", lemma=f"L{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN, gender="der", gender_source="llm",
    )
    db_session.add_all([verb, llm_noun])
    await db_session.flush()
    m = Module(
        id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1, sequence_order=1,
        title="g", can_dos=["x"], grammatical_focus=["y"],
    )
    m.vocab_items = [mastered, encountered, untouched, verb, llm_noun]
    db_session.add(m)
    await db_session.flush()
    for _ in range(3):
        db_session.add(GenderAttempt(
            id=uuid.uuid4(), user_id=uid, vocab_item_id=mastered.id,
            picked_article="der", was_correct=True,
        ))
    for _ in range(2):
        db_session.add(GenderAttempt(
            id=uuid.uuid4(), user_id=uid, vocab_item_id=encountered.id,
            picked_article="die", was_correct=True,
        ))
    await db_session.commit()

    enc, mast, total = await module_gender_progress(db_session, user_id=uid, module_id=m.id)
    assert (enc, mast, total) == (2, 1, 3)  # total: 3 oracle nouns; verb+llm excluded


@pytest.mark.asyncio
async def test_module_gender_progress_zero_when_no_eligible(db_session):
    from klara.models import Module

    uid = await _user(db_session)
    llm_noun = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"L{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN, gender="der", gender_source="llm",
    )
    db_session.add(llm_noun)
    await db_session.flush()
    m = Module(
        id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1, sequence_order=1,
        title="g", can_dos=["x"], grammatical_focus=["y"],
    )
    m.vocab_items = [llm_noun]
    db_session.add(m)
    await db_session.commit()
    assert await module_gender_progress(db_session, user_id=uid, module_id=m.id) == (0, 0, 0)
```

(`_user` already exists in this file and returns a `uuid.UUID`.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -v -k "streak or gender"`
Expected: FAIL — `cannot import name '_streak_mastered'`.

- [ ] **Step 3: Implement in `competence.py`**

Modify `backend/src/klara/curriculum/competence.py`. Add `GenderAttempt` to the `from klara.models import ...` line and `PartOfSpeech` to the `from klara.models.enums import CardState` line. Append at the end of the file:

```python
# Gender-axis mastery (R3). The competence interface's gender implementation,
# sibling of is_mastered_lexical. Mastery is read off historical GenderAttempt
# evidence (the frozen was_correct), never re-graded. Display-only (never gates).
GENDER_MASTERY_STREAK_N = 3


def _streak_mastered(attempts_desc: list, n: int) -> bool:
    """Pure: mastered iff there are at least n attempts and the most recent n
    (attempts_desc[0] is newest) are all correct. The single source of truth for
    the streak rule — both per-noun and per-module paths call it."""
    return len(attempts_desc) >= n and all(a.was_correct for a in attempts_desc[:n])


async def is_mastered_gender(db: AsyncSession, *, user_id: UUID, vocab_item_id: UUID) -> bool:
    """Per-noun gender mastery: the most recent GENDER_MASTERY_STREAK_N attempts
    for this (user, noun) are all correct. Deterministic order via
    (attempted_at DESC, id DESC)."""
    rows = (
        await db.execute(
            select(GenderAttempt)
            .where(
                GenderAttempt.user_id == user_id,
                GenderAttempt.vocab_item_id == vocab_item_id,
            )
            .order_by(GenderAttempt.attempted_at.desc(), GenderAttempt.id.desc())
            .limit(GENDER_MASTERY_STREAK_N)
        )
    ).scalars().all()
    return _streak_mastered(list(rows), GENDER_MASTERY_STREAK_N)


async def module_gender_progress(
    db: AsyncSession, *, user_id: UUID, module_id: UUID
) -> tuple[int, int, int]:
    """(gender_encountered, gender_mastered, gender_total) for the module's
    gender-gradable nouns — the parallel of module_progress for the gender axis.
    Eligible = de + oracle + NOUN + gender in der/die/das (same predicate as
    build_gender_cloze). Two queries, no N+1; bucket the globally-ordered
    attempts in Python and apply the shared _streak_mastered."""
    eligible = (
        await db.execute(
            select(VocabItem.id)
            .select_from(module_vocab)
            .join(VocabItem, VocabItem.id == module_vocab.c.vocab_item_id)
            .where(
                module_vocab.c.module_id == module_id,
                VocabItem.language == "de",
                VocabItem.gender_source == "oracle",
                VocabItem.pos == PartOfSpeech.NOUN,
                VocabItem.gender.in_(["der", "die", "das"]),
            )
        )
    ).scalars().all()
    total = len(eligible)
    if total == 0:
        return (0, 0, 0)
    rows = (
        await db.execute(
            select(GenderAttempt)
            .where(
                GenderAttempt.user_id == user_id,
                GenderAttempt.vocab_item_id.in_(eligible),
            )
            .order_by(GenderAttempt.attempted_at.desc(), GenderAttempt.id.desc())
        )
    ).scalars().all()
    by_noun: dict[UUID, list] = {}
    for r in rows:
        by_noun.setdefault(r.vocab_item_id, []).append(r)
    encountered = len(by_noun)
    mastered = sum(
        1 for attempts in by_noun.values() if _streak_mastered(attempts, GENDER_MASTERY_STREAK_N)
    )
    return (encountered, mastered, total)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -v` then `uv run pytest -q`. Then `uv run ruff check --fix src tests` + `uv run ruff format src tests`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/curriculum/competence.py backend/tests/test_curriculum_competence.py
git commit -m "feat(curriculum): gender mastery — _streak_mastered, is_mastered_gender, module_gender_progress"
```

---

## Task 4: Surface the gender tri-state on `ModuleCurrentOut`

**Files:**
- Modify: `backend/src/klara/schemas/module.py`, `backend/src/klara/routers/modules.py`
- Test: `backend/tests/test_modules.py` (append)

**Interfaces:**
- Consumes (Task 3): `module_gender_progress`.
- Produces: `ModuleCurrentOut.gender_encountered/gender_mastered/gender_total: int`, populated by `get_current_module`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_modules.py` (the helpers `_user`, `_module` and the `Module/User/VocabItem/CardState/CEFRLevel/PartOfSpeech` imports already exist; the GET pattern mirrors `test_get_current_module_endpoint`):

```python
@pytest.mark.asyncio
async def test_get_current_module_reports_gender_tristate(db_session):
    from klara.models import GenderAttempt

    u = await _user(db_session)
    u.target_language = "de"
    # Two oracle de NOUNs: one mastered (3 correct), one only encountered (2 attempts).
    mastered = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"N{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN, gender="der", gender_source="oracle",
    )
    seen = VocabItem(
        id=uuid.uuid4(), language="de", lemma=f"N{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN, gender="die", gender_source="oracle",
    )
    db_session.add_all([mastered, seen])
    await db_session.flush()
    m = await _module(db_session, language="de", order=1, title="Género", vocab=[mastered, seen])
    u.current_module_id = m.id
    for _ in range(3):
        db_session.add(GenderAttempt(
            id=uuid.uuid4(), user_id=u.id, vocab_item_id=mastered.id,
            picked_article="der", was_correct=True,
        ))
    for _ in range(2):
        db_session.add(GenderAttempt(
            id=uuid.uuid4(), user_id=u.id, vocab_item_id=seen.id,
            picked_article="die", was_correct=True,
        ))
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
    assert body["gender_total"] == 2
    assert body["gender_encountered"] == 2
    assert body["gender_mastered"] == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/test_modules.py -v -k "gender_tristate"`
Expected: FAIL — `KeyError: 'gender_total'` (field not on the response model).

- [ ] **Step 3: Add the fields + wire the call**

Modify `backend/src/klara/schemas/module.py` — add three fields to `ModuleCurrentOut` after `total`:

```python
    encountered: int
    mastered: int
    total: int
    gender_encountered: int
    gender_mastered: int
    gender_total: int
```

Modify `backend/src/klara/routers/modules.py` — add `module_gender_progress` to the `from klara.curriculum.competence import module_progress` import, call it, and pass the three fields:

```python
from klara.curriculum.competence import module_gender_progress, module_progress
```

```python
    encountered, mastered, total = await module_progress(db, user_id=user.id, module_id=module.id)
    g_enc, g_mast, g_total = await module_gender_progress(db, user_id=user.id, module_id=module.id)
    return ModuleCurrentOut(
        id=module.id,
        title=module.title,
        cefr_level=module.cefr_level,
        can_dos=module.can_dos or [],
        grammatical_focus=module.grammatical_focus or [],
        encountered=encountered,
        mastered=mastered,
        total=total,
        gender_encountered=g_enc,
        gender_mastered=g_mast,
        gender_total=g_total,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && uv run pytest tests/test_modules.py -v` then `uv run pytest -q`. Then `uv run ruff check --fix src tests` + `uv run ruff format src tests`.

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/schemas/module.py backend/src/klara/routers/modules.py backend/tests/test_modules.py
git commit -m "feat(modules): gender mastery tri-state on GET /modules/current (display-only)"
```

---

## Task 5: Full verification

- [ ] **Step 1: Backend suite + lint**

Run (from `backend/`): `uv run pytest -q` (all pass), `uv run ruff check src tests` (clean), `uv run ruff format --check src tests` (clean).
Expected: green. No migration round-trip needed (no schema change — `GenderAttempt.detail` already exists; `ModuleCurrentOut` is a response model).

- [ ] **Step 2: Confirm the no-leak + invariant contracts hold**

Confirm via the suite: `test_gender_cloze_quiz_item_has_no_rule_field` passes (the quiz item gained no field), `test_gender_attempt_case_b_*` passes (a disagreeing rule is suppressed), and the PR-B no-leak key-set assertion on `gender_cloze` still passes.

- [ ] **Step 3: Commit any fixups** (skip if none).

---

## Notes for the implementer

- **No migration, no frontend.** PR-C is backend-only. The rendered suffix note + 6-locale microcopy is a deliberate follow-up (PR-C.1); the optional `rule` field is added now so that follow-up is pure frontend.
- **The invariant is the whole point.** The oracle gender is always the displayed truth; a rule appears only on `agreement` (Case A) or a curated closed-exception (Case C). A disagreeing rule (Case B — incl. detector false positives like *Schwung*, and tendency traps like *die Mutter*) is suppressed on the wire but its 6-key `detail` is still persisted for offline audit. Never surface a rule the specific word violates.
- **Detector is intentionally simple.** Longest suffix match (hard before tendency on ties), ≥2-codepoint stem guard. It does NOT do morphology — false positives are caught by `reconcile_rule` against the oracle. Do not add cleverness.
- **Gender mastery is display-only.** `module_gender_progress` is the live consumer (Home reads `GET /modules/current`). Do NOT call it from `advance_module_if_mastered`. `is_mastered_gender` is the per-noun contract sibling of `is_mastered_lexical` (which also has no direct caller — `module_progress` and the gate inline the lexical predicate); it's not dead code, it's the gender implementation of the competence interface.
- **`gender_total` is the curriculum denominator, not a learner-driven %.** Mirrors the lexical `total`. PR-C.1 Home copy frames it as progress ("3 of 8"), never as a self-driven percentage.
- **Test isolation:** `vocab_items` is NOT truncated — use unique uuid-prefixed lemmas, keeping any real German suffix at the END so the detector still matches it. `modules`/`module_vocab`/`gender_attempts` ARE truncated. `attempted_at` is explicitly set in the recency test to control ordering.
- **Oracle-mutation-after-mastery** is a known, accepted v1 limit (mastery rests on historical `was_correct`; a post-mastery lexicon reseed is not reconciled). No code needed.
