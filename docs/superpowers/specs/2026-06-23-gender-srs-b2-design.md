# Gender SRS — Slice B2: dedicated gender review queue + screen

**Status:** approved design, revised after adversarial roster review (2026-06-23)
**Date:** 2026-06-23
**Axis:** German grammatical gender (der/die/das)
**Builds on:** B1 (`gender_eligibility`, `_gender_noun_state`, `gender_weakness_order`, the shared predicate), merged on main.

## Goal

Give the learner a reliable, LLM-independent way to resurface weak German
genders: a dedicated der/die/das review screen. Its list is the **weak set**
(encountered-but-not-mastered eligible nouns) computed on-read from the
`GenderAttempt` ledger — no new table, no scheduling column. B1 reprioritizes the
in-story cloze; B2 is the standalone cross-module remediation path.

## What the roster changed (and why this is not on /srs)

The adversarial review converged on one insight: **gender competence is a
stateless projection over an immutable evidence ledger, not a time-scheduled
deck.** It has no `next_review_at`, no clock, no decay. Dressing it as an SRS
"due queue" (the original `/srs/gender/due` plan) borrowed a scheduling ontology
it does not have — which surfaced as a false cost claim, a category-error name,
and a junction router. The resolution:

1. **Own router, honest naming.** Gender's standalone endpoints live in a new
   `routers/gender.py` mounted at `/api/v1/gender`: `GET /gender/review` (the
   weak list — NOT "due"; nothing is time-due) and `POST /gender/attempts`. This
   gives the gender axis a home instead of making `/srs` a junction reaching
   into three subsystems.
2. **No HTTP in the service layer.** The grading helper returns a value
   (`GenderAttemptOut | None`); the router maps `None` to a localized 404. No
   `HTTPException` and no `locale` leak into `services/`.
3. **Integrity = oracle gate only, documented as such.** Any authenticated user
   may grade any oracle-gradable noun as **their own** evidence. Mastery is
   **self-reported evidence**, not an anti-cheat signal — acceptable precisely
   because gender mastery is display-only and never gates module advancement
   (so self-inflation only misleads the learner about their own progress, never
   the curriculum and never another user). The dropped story-membership check is
   a *scoping* check, not an authorization one; cross-user isolation is enforced
   by `user_id = user.id` (server-derived) and is covered by a test.
4. **Cost ceiling, stated honestly.** `GET /gender/review` is NOT a "mirror of
   `due_cards`" in cost. The `ix_gender_attempt_user_vocab` index serves the
   `user_id` filter but NOT the `ORDER BY attempted_at`, so each call sorts the
   user's whole eligible gender history — O(K log K) in their lifetime attempts.
   Bounded per-user (the B1 global-scan defect is fixed) and fine at current
   scale; it degrades for very heavy users. The Home badge must NOT trigger this
   sort on every Home load (see B2b).
5. **B3 note:** because gender has no temporal due-ness, B3 (merging gender into
   the lexical practice queue) must explicitly reconcile two different axes —
   "how overdue (time)" vs "how weak (evidence)" — not pretend gender is
   time-due. B2's honest naming keeps that reconciliation visible instead of
   hiding it behind a shared "due" word.

## Decisions locked

- Derived / no new table; "weak" computed on-read from `GenderAttempt`.
- Remediation-pure list (weak set only; empty → a neutral "nothing to review"
  state — NOT "you mastered everything", since an empty set also means "never
  started"). New gender exposure stays in stories (B1).
- Asymmetric remediation, no decay, no temporal spacing — a weakness worklist.
- Minimal Home entry (a tile; the mastery tri-state stays parked — "D").
- Oracle grading gate preserved; gender never gates advancement.

## Scope split — two sequenced PRs

- **B2a (backend):** the selector, the grading helper (layer-clean), the gender
  router with its two endpoints, the consolidated gender schemas, and tests.
  Independently testable and mergeable.
- **B2b (frontend):** the extracted presentational picker, the review screen,
  the client/types, the Home tile, the 6-locale microcopy, and the CSS.

This document is the shared design; each PR gets its own plan.

## B2a — Backend

### 1. `weak_gender_nouns` — `curriculum/competence.py` (NEW)

Cross-module, **column-projected** (no ORM rows, no JSONB `detail`). The
VocabItem join applies the eligibility predicate without materializing VocabItem.

```python
async def weak_gender_nouns(
    db: AsyncSession, *, user_id: UUID, limit: int = 20
) -> list[UUID]:
    """The user's encountered-but-not-mastered eligible gender nouns, cross-module,
    ordered by remediation priority (wrong_recent before in_progress; within a
    tier, least-recently-attempted first). Derived on-read; no scheduling state.
    Column-projected — does NOT load the JSONB `detail`. `limit` caps the result
    AFTER sort (a SQL LIMIT would truncate per-noun streaks and corrupt mastery
    classification)."""
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
    rows = (await db.execute(stmt)).all()  # list[Row] — do NOT .scalars() (would load ORM rows + JSONB)
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

Rows expose `.was_correct`/`.attempted_at` by attribute, so `_gender_noun_state`
/ `_streak_mastered` work unchanged. The `.all()` (NOT `.scalars()`) keeping the
projection light is a correctness property — a test asserts the JSONB is not
loaded (see tests). The `str(vid)` final tiebreak only breaks exact (tier,
timestamp) ties — rare given microsecond `attempted_at`; the recency term does
the real cycling.

**Cost:** O(K log K) per call in the user's lifetime eligible attempts (the
index serves the `user_id` filter, not the `attempted_at` order). Bounded
per-user, accepted at current scale; documented as the known ceiling.

### 2. `grade_gender_attempt` — `services/gender_grading.py` (NEW, layer-clean)

The story-independent core of `record_gender_attempt`
(`routers/stories.py:512-537`), extracted as ONE shared async helper. It does
NOT raise `HTTPException` and does NOT take `locale` — it returns `None` when the
noun isn't oracle-gradable; each router maps `None` to its own localized 404.

```python
async def grade_gender_attempt(
    db: AsyncSession, *, user_id: UUID, vocab_item_id: UUID, picked_article: str
) -> GenderAttemptOut | None:
    """Grade a der/die/das pick against the oracle gender and record the evidence.
    The single source of truth for gender grading. Returns None when the vocab is
    not oracle-gradable (missing / gender_source != 'oracle' / no gender) — the
    caller turns that into a 404. Oracle-gated: an LLM/user guess is never
    certified as evidence."""
    vocab = await db.get(VocabItem, vocab_item_id)
    if vocab is None or vocab.gender_source != "oracle" or not vocab.gender:
        return None
    was_correct = picked_article == vocab.gender
    rule = detect_gender_rule(vocab.lemma)
    detail = reconcile_rule(rule, vocab.gender, vocab.lemma) if rule is not None else None
    rule_out = None
    if detail is not None and (detail["agreement"] or detail["is_exception"]):
        rule_out = GenderRuleOut(
            suffix=detail["suffix"], suffix_class=detail["suffix_class"],
            rule_gender=detail["rule_gender"], is_exception=detail["is_exception"],
        )
    db.add(GenderAttempt(
        user_id=user_id, vocab_item_id=vocab.id,
        picked_article=picked_article, was_correct=was_correct, detail=detail,
    ))
    await db.commit()
    return GenderAttemptOut(was_correct=was_correct, correct_gender=vocab.gender, rule=rule_out)
```

No `fastapi` import (services/ stays framework-free, as it is today). The
returned `GenderAttemptOut` is a function of inputs + oracle (not a read-back of
the committed row — `GenderAttemptOut` exposes no server-generated fields, so
this is fine and matches the prior handler's single-commit/no-refresh behavior).
`detect_gender_rule`/`reconcile_rule` are unchanged (pure). **Also update
`GenderAttempt.detail`'s model docstring**, which currently says "written by
`record_gender_attempt`" — it is now written by `grade_gender_attempt`.

`record_gender_attempt` (`stories.py`) is rewritten to keep ONLY its story-coupled
lines (`_load_or_404` + the `vocab_item_id not in story.target_vocab_item_ids`
404 — **this 404 must stay BEFORE the helper call**, preserving the existing
membership-then-grade order), then:

```python
out = await grade_gender_attempt(db, user_id=user.id, vocab_item_id=payload.vocab_item_id, picked_article=payload.picked_article)
if out is None:
    raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))
return out
```

### 3. `routers/gender.py` (NEW) — mounted at `/api/v1/gender`

```python
router = APIRouter(prefix="/gender", tags=["gender"])  # include_router(prefix="/api/v1") in main.py

@router.get("/review", response_model=list[GenderReviewItem])
async def gender_review(
    db: DBSession, user: CurrentUser, limit: int = Query(20, ge=1, le=100)
) -> list[GenderReviewItem]:
    ids = await weak_gender_nouns(db, user_id=user.id, limit=limit)
    if not ids:
        return []
    words = await _load_words_ordered(db, ids)  # order-preserving SELECT … WHERE id IN (…)
    return [
        GenderReviewItem(vocab_item_id=w.id, lemma=w.lemma,
                         en=(w.translations or {}).get(user.native_language))
        for w in words
    ]

@router.post("/attempts", response_model=GenderAttemptOut, status_code=201)
async def grade(
    payload: GenderAttemptIn, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> GenderAttemptOut:
    out = await grade_gender_attempt(
        db, user_id=user.id, vocab_item_id=payload.vocab_item_id, picked_article=payload.picked_article
    )
    if out is None:
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))
    return out
```

`_load_words_ordered` = the order-preserving id-IN load (the `stories._load_words`
shape; add a small local helper in `routers/gender.py`). The answer
(`vocab.gender`) is **never** in the review payload — revealed only on grading.
`GET /gender/review` needs no `LocaleDep` (uses `user.native_language` for `en`,
like `due_cards`); the gloss is `str | None` and the screen renders the lemma
alone when it is `None`.

### 4. Schemas — consolidate into `schemas/gender.py` (NEW)

Give the gender axis a schema home (so the gender router's dependency cone stays
within the gender subsystem): **move** `GenderAttemptIn`, `GenderAttemptOut`,
`GenderRuleOut` from `schemas/finish.py` into `schemas/gender.py`, and add:

```python
class GenderReviewItem(BaseModel):
    vocab_item_id: UUID
    lemma: str
    en: str | None = None
```

Update importers (`routers/stories.py`, any tests) to import from
`schemas/gender.py`. `finish.py` keeps `GenderClozeQuizItem` (the in-story quiz
shape, genuinely story-flow). This is a mechanical move guarded by the suites.

### B2a tests

- `weak_gender_nouns`: wrong_recent + in_progress only (excludes mastered &
  unseen); cross-module; priority order; `limit` caps after sort; empty when no
  weak nouns; excludes llm/VERB/non-de via the predicate. **Plus a projection
  guard**: assert the query does not load the JSONB `detail` (e.g. the returned
  rows are `Row`, not `GenderAttempt`, or assert on the compiled column set) so a
  future `.scalars()` regression is caught.
- `grade_gender_attempt`: correct/wrong grading; returns `None` for missing /
  non-oracle / no-gender vocab (the gate, proven once here — not re-proven at
  each caller); writes a GenderAttempt row; returns the show-gated rule.
- `record_gender_attempt` regression: still behaves identically after the
  extraction (membership 404 before the gate; existing tests stay green).
- `GET /gender/review`: authed — only weak ids, ordered, answer absent, empty
  when caught up, respects `limit`.
- `POST /gender/attempts`: authed — grades vs oracle, 201, writes evidence, 404
  for non-eligible vocab. **IDOR-isolation test**: a user's attempt writes to
  *their* ledger (`user_id == caller`), never another user's.

## B2b — Frontend

### 5. Extract the presentational picker — `components/GenderPicker.tsx` (NEW)

Lift only the **dumb core** of `GenderClozeQuestion` (`StoryFinish.tsx:898-1006`):
the 3-button der/die/das picker (`GENDER_OPTIONS`) and the prompt. **Keep grading
orchestration, result-shaping, and failure policy at each call site** (per the
roster: the story-finish and review contexts will diverge — story swallows
failures as "couldn't check, advance"; the review screen may differ). The picker
takes a graded result + an `onPick` callback and renders the verdict/`ruleNote`
from a `GenderAttemptOut`-shaped result the parent supplies. `StoryFinish`'s
`GenderClozeQuestion` becomes a thin wrapper owning `recordGenderAttempt`; the
review screen owns `gradeGender`. One presentational picker; orchestration stays
local.

### 6. `routes/GenderReview.tsx` (NEW) — route `/gender`

Modeled on `Practice.tsx` (`setup|session|summary`): fetch `api.genderReview()`
once on mount → empty → a **neutral** "nothing to review right now" state (not
"you mastered everything") → iterate items through `GenderPicker` with per-item
feedback → summary (reviewed / correct) → "again" (refetch) / "home". New
protected `<Route path="/gender">` in `App.tsx`.

### 7. Client + types — `api/client.ts`, `api/types.ts`

- `api.genderReview(limit = 20)` → `GET /gender/review` → `GenderReviewItem[]`.
- `api.gradeGender(payload: GenderAttemptIn)` → `POST /gender/attempts` →
  `GenderAttemptOut`.
- `interface GenderReviewItem { vocab_item_id: string; lemma: string; en?: string | null }`.

### 8. Home entry — `routes/Home.tsx`

A new `home__secondary` tile "gender review" → `navigate('/gender')`. **The
count badge must not trigger the O(K log K) review sort on every Home load**
(Halberg): either show the tile without a live count, or fetch the count lazily
/ cheaply — decided in the B2b plan. Keys `home.sec.genderReview.*`.

### 9. i18n + CSS

- New top-level **`genderReview`** group (es source, mirrored identically to
  en/de/fr/ja/pt — `npm run i18n:check` enforces leaf-key parity): `title`,
  `empty` (neutral), `progress`, `done`, summary CTAs. Per-item feedback reuses
  `story.finish.quiz.genderCloze.*`. Add `home.sec.genderReview.{title,subtitle}`.
- **CSS:** style the `qcard__gender-btn`/`qcard__gender-opts` picker buttons
  (currently unstyled) + the review screen shell.

### B2b verification

`npm run typecheck`, `npm run build`, `npm run i18n:check` green (the frontend's
CI gates are type + build + i18n parity, not unit tests).

## Data flow

Open `/gender` → `GET /gender/review` (weak set, priority-ordered, answer
hidden) → iterate, each pick `POST /gender/attempts` → graded vs oracle, evidence
appended → summary → "again" refetches (now-mastered nouns gone). A wrong answer
re-opens the noun (asymmetric remediation). The story finish path is unchanged
except its grader now delegates to the shared helper.

## Error handling & edge cases

- **Empty weak set** → `[]` → neutral empty state. Covers both "caught up" and
  "never started" honestly (no congratulation).
- **Non-gradable vocab** → helper returns `None` → router 404. The review
  endpoint never serves such nouns; a 404 here only arises from a forged/stale id.
- **Grade failure mid-session** → the screen advances without recording (mirror
  the story picker's resilience); the noun stays weak and reappears next fetch.
- **`limit`** clamped 1..100 (Query), default 20.
- **Mastery is self-reported** (oracle-gate-only): a client could grind 3 correct
  picks to mark a noun mastered. Accepted — gender is display-only / never gates;
  no cross-user impact (enforced by server-derived `user_id` + the IDOR test).

## Non-goals

- No table, migration, scheduling column, or temporal spacing.
- No backfill with unseen nouns (remediation-pure).
- No surfacing of the gender mastery tri-state on Home (parked "D").
- No anti-gaming/throttle on self-graded attempts (out of scope; self-only).
- No change to module advancement; `advance_module_if_mastered` untouched.
- No solving B3's queue-merge reconciliation (named, deferred).
