# Gender SRS — Slice B1: weak-gender remediation core + in-story delivery

**Status:** approved design (brainstorm complete)
**Date:** 2026-06-23
**Axis:** German grammatical gender (der/die/das)

## Goal

Make weak (recently-wrong, not-yet-mastered) German gender nouns resurface for
remediation, **without** introducing decay or any new persisted state. B1 ships
the shared **selector** (derived on-read from the existing `GenderAttempt`
ledger) plus its first two consumers: a **reliable** in-story consumer (the
gender-cloze picks the weakest noun already present) and a **best-effort**
generation consumer (weak past-module nouns are softly suggested to the story
LLM).

## Decisions locked during brainstorming

These framed the whole design and are **not** re-opened in B1:

1. **Fork = parallel/derived, not UserCard-with-axis.** The codebase already
   votes parallel: `GenderAttempt`/`GenderLexicon`/`GenderL1Note` are separate
   tables; `models/gender.py` says gender is *"deliberately NOT folded into the
   monadic UserCard (lexical SRS)."* Reusing `UserCard` with an axis column
   would cost ~11 silent-correctness touch points (6 read filters, 3 write tags,
   the unique constraint, the due index, a backfill migration).
2. **Model = asymmetric remediation.** Per the R3 design (*"el género por
   sufijo se internaliza, no decae"*), nothing decays. Only **failed** genders
   resurface; **correct** ones are never re-tested on a forgetting curve. So
   there is no `ease`, no interval growth, no `next_review_at`.
3. **Storage = derived projection, no new table.** "Weak" is computed on-read
   from `GenderAttempt`, exactly as `is_mastered_gender` already computes
   mastery. Zero migration, zero new write-path.
4. **Three delivery surfaces, built B1 → B2 → B3 (risk-ascending).** B1
   (this spec) = core selector + in-story delivery (backend-only). B2 = a
   dedicated `/srs/gender/due` queue + screen (the *reliable* cross-module
   resurfacing path). B3 = polymorphic merge into `/practice/queue`.
5. **Mastery stays the N=3 streak.** `GENDER_MASTERY_STREAK_N = 3` and
   `_streak_mastered` remain the single source of truth; B1 reuses them, does
   not replace them.

## Why generation is the wrong primary seam (the recon finding)

Story generation does **not** control which nouns become cloze targets:

- `target_lemmas` is only a **soft prompt suggestion** to the LLM
  (`routers/stories.py:155-167` → `services/story_gen.py:219-225`).
- The LLM emits `target_words` non-deterministically (`temperature=0.8`).
- `verify_coverage` then keeps only the words that **actually appear in the
  prose**: `Story.target_vocab_item_ids = kept_ids`
  (`services/story_gen.py:284-313`). A suggested noun the LLM omits is dropped
  and logged as `story.coverage.dropped`.
- For German users the **module path** is taken almost always, and
  `module_target_lemmas` returns the **entire current module's vocab**
  (`curriculum/modules.py:54-60`) — current-module-scoped, so it **cannot** pull
  a weak noun from an earlier module.
- `build_gender_cloze` returns on the **first** eligible noun
  (`services/finish_lessons.py:160`) — **one** gender cloze per story.

Therefore the **reliable** seam is the cloze builder (deterministic, no LLM/
coverage dependency): among the nouns that *did* land in the story, remediate
the weakest. Generation bias is kept only as a best-effort nudge; guaranteed
cross-module resurfacing is deferred to B2.

## Architecture

```
GenderAttempt (existing ledger)
        │
        ▼
_gender_noun_state(attempts_desc, N) → UNSEEN | WRONG_RECENT | IN_PROGRESS | MASTERED   (pure)
        │
        ├─► weak_gender_nouns(db, user_id) → list[UUID]      (cross-module selector, Shape A)
        │        └─► Consumer B: soft generation bias (create_story)
        │
        └─► gender_weakness_order(db, user_id, ids) → list[UUID]   (per-noun ordering)
                 └─► Consumer A: build_gender_cloze picks the weakest (finish path)

is_gender_eligible(w) / gender_eligible_clause()  → canonical predicate, replaces 4 copies
```

No new tables, models, migrations, endpoints, or schemas. All new logic lives in
`curriculum/` plus edits to two existing call paths.

## Components

### 1. Canonical eligibility predicate — `curriculum/gender_eligibility.py` (NEW)

The recon found the gender-eligibility predicate **copied by hand in four
places** that must agree forever:

- `services/finish_lessons.py:160-166` (cloze builder, Python)
- `curriculum/competence.py:128-134` (`module_gender_progress`, SQL clause)
- `routers/stories.py:326-333` (L1-notes endpoint, Python)
- `routers/stories.py:516` (`record_gender_attempt` gate — deliberately
  *looser*: oracle + non-empty gender only)

B1 adds a fifth consumer (the selector) and modifies the cloze builder, so it
extracts one source of truth:

```python
from klara.models import VocabItem
from klara.models.enums import PartOfSpeech

GENDER_ARTICLES: tuple[str, ...] = ("der", "die", "das")


def is_gender_eligible(w: VocabItem) -> bool:
    """A noun is gender-gradable iff it is a German NOUN whose gender is
    oracle-sourced and one of der/die/das. The single source of truth — replaces
    four hand-maintained copies."""
    return (
        w.language == "de"
        and w.pos == PartOfSpeech.NOUN
        and w.gender_source == "oracle"
        and w.gender in GENDER_ARTICLES
    )


def gender_eligible_clause() -> tuple:
    """The same predicate as a tuple of SQLAlchemy conditions, to splat into
    `.where(*gender_eligible_clause())` for VocabItem queries."""
    return (
        VocabItem.language == "de",
        VocabItem.gender_source == "oracle",
        VocabItem.pos == PartOfSpeech.NOUN,
        VocabItem.gender.in_(list(GENDER_ARTICLES)),
    )
```

**Migration of the four sites:**
- `finish_lessons.py`, `competence.py` (`module_gender_progress`), and the
  `stories.py` L1-notes comprehension switch to `is_gender_eligible` /
  `gender_eligible_clause()`.
- `record_gender_attempt`'s gate (`stories.py:516`) is migrated too. This is a
  **deliberate, safe tightening**: it gains the `pos == NOUN`, `language == de`,
  and `gender in der/die/das` checks. A forged/stale POST for a non-eligible
  vocab item now 404s instead of grading — items that should never have been
  gradable. Documented here so it is not mistaken for a regression.

### 2. The classifier — `curriculum/competence.py` (NEW, pure)

```python
def _gender_noun_state(attempts_desc: list, n: int) -> str:
    """Classify one noun's gender evidence. attempts_desc[0] is newest.
    Returns 'unseen' | 'wrong_recent' | 'in_progress' | 'mastered'.
    Reuses _streak_mastered as the mastery source of truth."""
    if not attempts_desc:
        return "unseen"
    if _streak_mastered(attempts_desc, n):
        return "mastered"
    if not attempts_desc[0].was_correct:
        return "wrong_recent"
    return "in_progress"
```

State table (N=3): mastered = newest 3 all correct; else wrong_recent = newest
attempt wrong; else in_progress = newest correct but streak incomplete; unseen =
no attempts. The four states are mutually exclusive and total.

### 3. The selector — `weak_gender_nouns` in `curriculum/competence.py` (NEW)

Cross-module (no `module_vocab` join — mirrors the cross-module
`is_mastered_gender`, not the module-scoped `module_gender_progress`).
**Shape A**: a never-attempted noun is *not* weak (you cannot "resurface" the
unseen).

```python
async def weak_gender_nouns(db: AsyncSession, *, user_id: UUID) -> list[UUID]:
    """Cross-module set of the user's gender nouns that are encountered but not
    mastered, ordered by remediation priority. Derived on-read from the
    GenderAttempt ledger — no stored schedule. weak = state in
    {wrong_recent, in_progress}. Order: wrong_recent before in_progress;
    within a tier, least-recently-attempted first (cycle, don't hammer)."""
    rows = (
        (
            await db.execute(
                select(GenderAttempt)
                .join(VocabItem, VocabItem.id == GenderAttempt.vocab_item_id)
                .where(GenderAttempt.user_id == user_id, *gender_eligible_clause())
                .order_by(GenderAttempt.attempted_at.desc(), GenderAttempt.id.desc())
            )
        )
        .scalars()
        .all()
    )
    by_noun: dict[UUID, list] = {}
    for r in rows:
        by_noun.setdefault(r.vocab_item_id, []).append(r)

    tier = {"wrong_recent": 0, "in_progress": 1}
    weak: list[tuple[int, object, UUID]] = []
    for vid, attempts in by_noun.items():
        state = _gender_noun_state(attempts, GENDER_MASTERY_STREAK_N)
        if state in tier:
            # attempts[0].attempted_at is the most-recent attempt; ascending sort
            # surfaces the least-recently-seen first.
            weak.append((tier[state], attempts[0].attempted_at, vid))
    weak.sort(key=lambda t: (t[0], t[1]))
    return [vid for _, _, vid in weak]
```

Indexed by `ix_gender_attempt_user_vocab (user_id, vocab_item_id)`. One query,
Python-side bucketing — no N+1, matching `module_gender_progress`'s style.

### 4. The ordering helper — `gender_weakness_order` in `competence.py` (NEW)

Used by the cloze to rank the nouns already in a story. Unlike the selector this
ranks **all** the passed ids (including unseen and mastered) so the cloze always
has a deterministic pick.

```python
async def gender_weakness_order(
    db: AsyncSession, *, user_id: UUID, vocab_item_ids: list[UUID]
) -> list[UUID]:
    """Order the given nouns by cloze-pick priority for this user:
    wrong_recent > in_progress > unseen > mastered; within a tier,
    least-recently-attempted first (unseen have no attempts → stable input
    order). Returns every input id exactly once."""
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

    tier = {"wrong_recent": 0, "in_progress": 1, "unseen": 2, "mastered": 3}

    def key(idx_vid: tuple[int, UUID]):
        idx, vid = idx_vid
        attempts = by_noun.get(vid, [])
        state = _gender_noun_state(attempts, GENDER_MASTERY_STREAK_N)
        recency = attempts[0].attempted_at if attempts else None
        # within tier: those with a timestamp sort ascending (least-recent first);
        # unseen (no timestamp) fall back to stable input order via idx.
        return (tier[state], recency is None, recency, idx)

    return [vid for _, vid in sorted(enumerate(vocab_item_ids), key=key)]
```

(The `recency is None` term keeps `None` from being compared against datetimes;
unseen items are ordered among themselves by input index.)

### 5. Consumer A — cloze picks the weakest (RELIABLE)

`services/finish_lessons.py` `build_gender_cloze` stays **sync and pure**; it
gains an optional `prefer_order`:

```python
def build_gender_cloze(words, native_language, *, prefer_order=None):
    eligible = [w for w in words if is_gender_eligible(w)]
    if not eligible:
        return None
    if prefer_order:
        rank = {vid: i for i, vid in enumerate(prefer_order)}
        eligible.sort(key=lambda w: rank.get(w.id, len(prefer_order)))
    chosen = eligible[0]
    return {
        "type": "gender_cloze",
        "cap": "gender",
        "lemma": chosen.lemma,
        "vocab_item_id": str(chosen.id),
        "en": (chosen.translations or {}).get(native_language),
    }
```

`is_gender_eligible` remains the **sole** eligibility authority; `prefer_order`
is only a hint. A stable sort means ties keep target order — so with
`prefer_order=None` (or all-mastered), behavior is identical to today
(first eligible noun).

**The finish-path caller** (`routers/stories.py:267-272`, the quiz builder)
computes the order and passes it:

```python
words = await _load_words(db, list(story.target_vocab_item_ids or []))
prefer = await gender_weakness_order(
    db, user_id=user.id, vocab_item_ids=[w.id for w in words]
)
gender_item = build_gender_cloze(words, native_language, prefer_order=prefer)
```

### 6. Consumer B — soft generation bias (BEST-EFFORT)

In `create_story` (`routers/stories.py`), after `target_lemmas` is assembled by
**either** branch, append up to `K` weak past-module lemmas not already present:

```python
GENDER_REMEDIATION_K = 2  # tunable; small so it nudges, not floods

weak_ids = await weak_gender_nouns(db, user_id=user.id)
if weak_ids:
    existing = {lemma.casefold() for lemma in target_lemmas}
    weak_words = await _load_words(db, weak_ids)  # preserves weakness order
    extra = [w.lemma for w in weak_words if w.lemma.casefold() not in existing]
    target_lemmas = target_lemmas + extra[:GENDER_REMEDIATION_K]
```

Inserted once, after the module/fallback `if/else`, so it covers both paths.
The appended nouns are **not** added to `mod_vids`, so they do not get enrolled
as current-module cards (`enroll_cards` still uses `kept ∩ mod_vids`). They only
re-test via the cloze *if* the LLM weaves them in and coverage keeps them —
accepted as best-effort.

## Data flow

1. **Finish a story →** quiz builder loads the story's target words →
   `gender_weakness_order` ranks them → `build_gender_cloze` emits a cloze for
   the weakest eligible noun → learner answers → `record_gender_attempt` grades
   vs the oracle and appends a `GenderAttempt` row (unchanged write path).
2. **Generate next story →** `weak_gender_nouns` returns the cross-module weak
   set → top-K lemmas appended to `target_lemmas` → LLM may include them → if
   covered, they become targets → step 1 can then remediate them.

The loop closes deterministically via step 1 for any weak noun already in a
story; step 2 is the soft attempt to drag fading nouns back into stories.

## Error handling & edge cases

- **No gender attempts:** `weak_gender_nouns → []`; no bias; cloze falls back to
  first eligible noun (today's behavior). No error.
- **Story with no eligible nouns:** `build_gender_cloze → None` (today's
  behavior).
- **All eligible nouns mastered:** all land in the MASTERED tier; stable sort
  keeps target order → first eligible chosen (today's behavior).
- **Weak noun the LLM ignores / coverage drops:** simply not remediated this
  story; no error, no broken cloze (the cloze only ever shows nouns present in
  `target_vocab_item_ids`).
- **`None` timestamp comparison:** guarded in `gender_weakness_order` via the
  `recency is None` sort term so datetimes are never compared with `None`.

## Testing strategy

Mirror `tests/test_curriculum_competence.py` (async, `db_session`,
`_de_oracle_noun`, direct `GenderAttempt` seeding with explicit `attempted_at`).
No clock-freezing in the suite — advance time with explicit `attempted_at`
offsets. `vocab_items` is not truncated per-test, so seed helpers suffix lemmas
with uuid hex (existing convention).

New / changed tests:

- **`_gender_noun_state` (pure):** all four states — 3 correct → mastered;
  newest wrong → wrong_recent; <3 attempts all correct → in_progress; empty →
  unseen; newest wrong after a mastered streak → wrong_recent.
- **`weak_gender_nouns`:** includes wrong_recent and in_progress; excludes
  mastered and unseen; spans two modules (cross-module — seed nouns via
  `_de_oracle_noun`, no `Module` needed, plus one explicit two-module case);
  ordering: wrong_recent before in_progress; least-recently-attempted first
  within a tier; excludes `llm`-source / VERB / non-de nouns via the predicate.
- **`gender_weakness_order`:** full ranking wrong_recent > in_progress > unseen
  > mastered; unseen ordered by input index; returns every id once; empty input
  → `[]`.
- **`is_gender_eligible` / `gender_eligible_clause`:** der/die/das oracle NOUN
  passes; llm-source, VERB, non-de, non-canonical gender each fail. (Co-locate
  with the competence tests or a small `test_gender_eligibility.py`.)
- **`build_gender_cloze` weakest-pick** (update `tests/test_gender_cloze.py`):
  with two eligible nouns where B is weaker than A and A is first in target
  order, `prefer_order` makes the cloze pick B; with `prefer_order=None` it
  still picks the first (back-compat).
- **Generation bias** (story-gen / stories test with a stub `LLMClient`): weak
  lemmas are appended to `target_lemmas` passed into `generate_story`, capped at
  K=2, deduped case-insensitively against the module list; empty weak set leaves
  `target_lemmas` unchanged.
- **Predicate migration regression:** the existing L1-notes, module-progress,
  and gender-cloze tests must stay green after switching to the shared
  predicate; add one test that `record_gender_attempt` now 404s for a
  non-eligible (e.g. VERB) vocab id in a story's targets (the tightening).

## Non-goals (explicitly out of B1)

- No new table, model, migration, endpoint, schema, or `conftest` TRUNCATE
  change.
- No change to module advancement — it stays lexical-only and single-writer
  (`advance_module_if_mastered` untouched).
- No new frontend surface and no client changes (the cloze payload shape is
  unchanged).
- Still **one** gender cloze per story — B1 reprioritizes the single slot; it
  does not increase gender throughput.
- No *guaranteed* cross-module resurfacing — that is B2 (the dedicated queue,
  which does not depend on the LLM or coverage).
- No decay, ease, interval, or `next_review_at` for gender.
```
