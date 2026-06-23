# Gender SRS — Slice B2: dedicated /srs/gender/due queue + review screen

**Status:** approved design (brainstorm complete)
**Date:** 2026-06-23
**Axis:** German grammatical gender (der/die/das)
**Builds on:** B1 (`gender_eligibility`, `_gender_noun_state`, `gender_weakness_order`, the shared eligibility predicate), merged on main.

## Goal

Give the learner a **reliable, LLM-independent** way to resurface weak German
genders: a dedicated der/die/das review queue. The queue is the **weak set**
(encountered-but-not-mastered eligible nouns) computed on-read from the
`GenderAttempt` ledger — no new table, no scheduling column. B1 reprioritizes the
in-story cloze; B2 is the standalone cross-module remediation path.

## Decisions locked (brainstorm)

1. **Derived / no new table.** "Due" is not a stored `next_review_at`; it is the
   weak set from a new cross-module `weak_gender_nouns` selector.
2. **Remediation-pure queue.** The queue contains only the weak set
   (encountered-but-not-mastered). When empty → an "all caught up" state. New
   gender exposure stays in stories (B1); B2 does **not** backfill with unseen
   nouns.
3. **Asymmetric remediation, no decay.** A noun stays in the queue until
   mastered (N=3 correct in a row); a wrong answer re-opens it. No temporal
   spacing — a "weakness worklist" you grind down, not a time-spaced deck.
4. **Minimal Home entry.** A `home__secondary` tile "gender review" with a
   pending-count badge. The gender mastery tri-state is NOT surfaced (the parked
   "D" display stays parked).
5. **Oracle grading gate preserved; gender never gates module advancement.**

## Scope split — two sequenced PRs

B2 is one feature, shipped as two reviewable PRs:

- **B2a (backend):** the selector, the extracted grading helper, the two
  endpoints, the schemas, and tests. Independently testable and mergeable
  (dormant until B2b calls it).
- **B2b (frontend):** the extracted picker component, the review screen, the
  client/types, the Home entry, the 6-locale microcopy, and the CSS.

This document is the shared design for both. Each PR gets its own plan.

## Architecture

```
GenderAttempt (existing ledger)
   │
   ▼
weak_gender_nouns(db, *, user_id, limit)  → list[UUID]      (NEW, competence.py; column-projected)
   │
   └─► GET /srs/gender/due → list[GenderDueOut]             (NEW endpoint, /srs router)
            (load VocabItems for the ids → {vocab_item_id, lemma, en})

grade_gender_attempt(db, *, user_id, vocab_item_id, picked_article, locale) → GenderAttemptOut
   (NEW services/gender_grading.py — extracted verbatim from record_gender_attempt's
    story-independent core; the ONE source of truth for gender grading)
   │
   ├─► record_gender_attempt  (stories.py — keeps its story-membership check, then calls it)
   └─► POST /srs/gender/attempts  (NEW endpoint, /srs router — story-less, calls it)

Frontend (B2b):
GenderPicker (extracted from StoryFinish.GenderClozeQuestion, story-less props)
   ├─► StoryFinish  (onGrade = recordGenderAttempt(story.id, …))
   └─► routes/GenderReview.tsx  (onGrade = gradeGender(…)); route /gender; Home tile + badge
```

## B2a — Backend

### 1. `weak_gender_nouns` — `curriculum/competence.py` (NEW)

Cross-module selector, **column-projected** (no ORM rows, no JSONB `detail`
loaded). The VocabItem join applies the eligibility predicate without
materializing VocabItem.

```python
async def weak_gender_nouns(
    db: AsyncSession, *, user_id: UUID, limit: int = 20
) -> list[UUID]:
    """The user's gender nouns that are encountered-but-not-mastered, cross-module,
    ordered by remediation priority (wrong_recent before in_progress; within a
    tier, least-recently-attempted first). Derived on-read from the GenderAttempt
    ledger — no scheduling state. Column-projected (no JSONB detail). `limit` caps
    the returned list (applied AFTER sort, not as a SQL LIMIT — a SQL limit would
    truncate per-noun streaks and corrupt mastery classification)."""
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
    rows = (await db.execute(stmt)).all()  # list[Row]; do NOT .scalars()
    by_noun: dict[UUID, list] = {}
    for r in rows:
        by_noun.setdefault(r.vocab_item_id, []).append(r)

    weak: list[tuple[int, float, UUID]] = []
    for vid, attempts in by_noun.items():
        state = _gender_noun_state(attempts, GENDER_MASTERY_STREAK_N)
        if state in _GENDER_WEAK_STATES:
            weak.append((_GENDER_TIER[state], attempts[0].attempted_at.timestamp(), vid))
    weak.sort(key=lambda t: (t[0], t[1], str(t[2])))  # stable final tiebreak on str(vid)
    return [vid for _, _, vid in weak[:limit]]
```

Rows expose `.was_correct` / `.attempted_at` by attribute, so `_gender_noun_state`
and `_streak_mastered` work unchanged. Served by `ix_gender_attempt_user_vocab`,
bounded by one user's attempt history. All imports already present in
competence.py. (`str(vid)` final tiebreak gives determinism without a
caller-supplied input order.)

### 2. `grade_gender_attempt` — `services/gender_grading.py` (NEW)

Extract the story-independent core of `record_gender_attempt`
(`routers/stories.py:512-537`) verbatim into one shared async helper:

```python
async def grade_gender_attempt(
    db: AsyncSession, *, user_id: UUID, vocab_item_id: UUID, picked_article: str, locale: str
) -> GenderAttemptOut:
    """Grade a der/die/das pick against the oracle gender and record the evidence.
    The single source of truth for gender grading (both the story finish path and
    the SRS review path call this). Oracle-gated: 404 unless the vocab is an
    oracle-sourced German der/die/das noun (never certify an LLM/user guess)."""
    vocab = await db.get(VocabItem, vocab_item_id)
    if vocab is None or vocab.gender_source != "oracle" or not vocab.gender:
        raise HTTPException(status_code=404, detail=t("errors.vocab_not_found", locale))
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

`record_gender_attempt` is rewritten to keep ONLY its story-coupled lines
(`_load_or_404` + the `vocab_item_id not in story.target_vocab_item_ids` 404),
then `return await grade_gender_attempt(db, user_id=user.id, vocab_item_id=…,
picked_article=…, locale=locale)`. Grading, the persisted `detail`, and the
returned `rule` become byte-identical across both paths. `detect_gender_rule` /
`reconcile_rule` are already pure and shared (no change). The helper raising
`HTTPException` is the existing inline behavior, preserved.

### 3. `GET /srs/gender/due` — `routers/srs.py` (NEW)

Mirror of `due_cards`, on the same `/srs` router (→ `/api/v1/srs/gender/due`).
No `LocaleDep` (like `due_cards`); `en` uses `user.native_language`.

```python
@router.get("/gender/due", response_model=list[GenderDueOut])
async def gender_due(
    db: DBSession, user: CurrentUser, limit: int = Query(20, ge=1, le=100)
) -> list[GenderDueOut]:
    ids = await weak_gender_nouns(db, user_id=user.id, limit=limit)
    if not ids:
        return []
    words = await _load_words_ordered(db, ids)  # VocabItem rows preserving id order
    return [
        GenderDueOut(
            vocab_item_id=w.id, lemma=w.lemma,
            en=(w.translations or {}).get(user.native_language),
        )
        for w in words
    ]
```

`_load_words_ordered` = the order-preserving `SELECT … WHERE id IN (…)` pattern
(same shape as `stories._load_words`; add a small local helper in srs.py). The
answer (`vocab.gender`) is **never** included in the payload — revealed only on
grading.

### 4. `POST /srs/gender/attempts` — `routers/srs.py` (NEW)

Story-less grade. Reuses `GenderAttemptIn` / `GenderAttemptOut` (already
story-free). The oracle gate (inside the helper) is the integrity guard — no
story-membership check; grading any oracle noun as the user's own evidence is
harmless.

```python
@router.post("/gender/attempts", response_model=GenderAttemptOut, status_code=201)
async def review_gender(
    payload: GenderAttemptIn, db: DBSession, user: CurrentUser, locale: LocaleDep
) -> GenderAttemptOut:
    return await grade_gender_attempt(
        db, user_id=user.id, vocab_item_id=payload.vocab_item_id,
        picked_article=payload.picked_article, locale=locale,
    )
```

### 5. Schema — `schemas/srs.py` (next to `CardOut` — it is an SRS-due schema)

```python
class GenderDueOut(BaseModel):
    vocab_item_id: UUID
    lemma: str
    en: str | None = None
```

`GenderAttemptIn` / `GenderAttemptOut` / `GenderRuleOut` are reused from
`schemas/finish.py` (already story-free).

### B2a tests

- `weak_gender_nouns`: returns wrong_recent + in_progress (excludes mastered &
  unseen); cross-module (spans two modules / no module needed); priority order
  (wrong_recent first, least-recently-attempted first within tier); `limit` caps
  AFTER sort; empty when no weak nouns; excludes llm-source / VERB / non-de via
  the predicate. Seed via the `test_curriculum_competence.py` patterns.
- `grade_gender_attempt`: correct/wrong grading vs oracle; 404 when vocab missing
  / not oracle / no gender; writes a GenderAttempt row; returns the show-gated
  rule. And: `record_gender_attempt` still behaves identically (its existing
  tests stay green) after the extraction.
- `GET /srs/gender/due`: authed endpoint test — seed weak + mastered nouns,
  assert only weak ids returned, ordered, the answer absent from the payload,
  empty list when caught up, respects `limit`.
- `POST /srs/gender/attempts`: authed — grades vs oracle, 201, writes evidence,
  404 for non-eligible vocab.

## B2b — Frontend

### 6. Extract `GenderPicker` — `components/GenderPicker.tsx` (NEW)

Lift `GenderClozeQuestion` (`StoryFinish.tsx:898-1006`) into an exported
component with story-less props:

```ts
{ lemma: string; vocabItemId: string; en?: string | null;
  onGrade: (article: 'der'|'die'|'das') => Promise<GenderAttemptOut>;
  onNext: () => void; isLast?: boolean }
```

It owns the 3-button der/die/das picker, the graded-result rendering
(`was_correct` / `correct_gender` / the localized `ruleNote` from `GenderRule`),
and `GENDER_OPTIONS`. The screen supplies `onGrade`. `StoryFinish`'s
`GenderClozeQuestion` becomes a thin wrapper: `onGrade={(a) =>
api.recordGenderAttempt(story.id, {vocab_item_id, picked_article: a})}`. One
picker, no duplication. The per-item feedback keeps using the existing
`story.finish.quiz.genderCloze.*` i18n keys.

### 7. `routes/GenderReview.tsx` (NEW) — modeled on `Practice.tsx`

Phase machine `setup|session|summary`: fetch `api.genderDue()` on mount → empty →
"all caught up" state; else iterate items through `GenderPicker` (per-item
graded feedback) → summary (count reviewed / correct) → "again" (refetch — now-
mastered nouns are gone) / "home" CTAs. New protected route `/gender` in
`App.tsx`.

### 8. Client + types — `api/client.ts`, `api/types.ts`

- `api.genderDue(limit = 20)` → `GET /srs/gender/due` → `GenderDueItem[]`.
- `api.gradeGender(payload: GenderAttemptIn)` → `POST /srs/gender/attempts` →
  `GenderAttemptOut`.
- `interface GenderDueItem { vocab_item_id: string; lemma: string; en?: string | null }`.

### 9. Home entry — `routes/Home.tsx`

New `home__secondary` item "gender review" → `navigate('/gender')`, with a badge
count from `api.genderDue()` fetched in Home's mount effect (mirrors the
`dueCards` → `dueCount` pattern). Keys `home.sec.genderReview.*`.

### 10. i18n + CSS

- New top-level **`genderReview`** group (es source, mirrored identically to
  en/de/fr/ja/pt — `npm run i18n:check` enforces leaf-key parity): `title`,
  `empty`, `progress` (e.g. "{{done}} / {{total}}"), `done`, plus the summary
  CTAs. Per-item feedback reuses `story.finish.quiz.genderCloze.*`. Add
  `home.sec.genderReview.{title,subtitle}`.
- **CSS:** the `qcard__gender-btn` / `qcard__gender-opts` classes are currently
  unstyled; style the picker buttons + the review screen shell (new rules,
  likely a `gender-review.css` or additions to the existing styles).

### B2b tests

Frontend has no test runner wired beyond typecheck/build/i18n parity in CI, so
B2b verification is: `npm run typecheck`, `npm run build`, `npm run i18n:check`
all green; manual/visual confirmation of the screen (the project's frontend
gates are type + build + i18n parity, not unit tests).

## Error handling & edge cases

- **Empty weak set** → `GET /srs/gender/due` returns `[]` → screen shows the
  "caught up" state. No error.
- **Non-gradable vocab** (missing / not oracle / no gender) → grade endpoint
  404s (the oracle gate). The due endpoint never serves such nouns, so a
  well-behaved client never hits it.
- **Grade API failure mid-session** → mirror the existing picker behavior
  (StoryFinish grades as "couldn't check" and advances) so a transient failure
  never strands the session.
- **`limit`** clamped 1..100 (Query validation), default 20.

## Non-goals

- No new table, migration, or scheduling column; no temporal spacing.
- No backfill with unseen nouns (remediation-pure).
- No surfacing of the gender mastery tri-state on Home (parked "D").
- No change to module advancement; `advance_module_if_mastered` untouched.
- Gender grading stays oracle-gated; the standalone path does not relax it.
