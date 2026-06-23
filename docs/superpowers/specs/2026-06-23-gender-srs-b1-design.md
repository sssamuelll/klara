# Gender SRS — Slice B1: in-story gender-cloze reprioritization + remediation classifier

**Status:** approved design, revised after adversarial roster review (2026-06-23)
**Date:** 2026-06-23
**Axis:** German grammatical gender (der/die/das)

## Goal

When a learner opens a story's quiz, the single gender cloze targets the
**weakest** der/die/das noun **already present in that story** instead of the
first one — derived on-read from the existing `GenderAttempt` ledger, with no
new state. B1 also lands the reusable pieces (a canonical eligibility predicate
and a pure mastery-state classifier) that the later slices consume.

B1 **reprioritizes** the in-context gender slot; it does not **resurface** nouns
from other stories. Guaranteed cross-module resurfacing is B2's job (a
deterministic `/srs/gender/due` queue that does not depend on the LLM).

## Decisions locked during brainstorming

1. **Fork = parallel/derived, not UserCard-with-axis.** The codebase already
   votes parallel (`GenderAttempt`/`GenderLexicon`/`GenderL1Note` are separate
   tables; `models/gender.py`: gender is *"deliberately NOT folded into the
   monadic UserCard"*). A UserCard axis would cost ~11 silent-correctness touch
   points.
2. **Model = asymmetric remediation.** Nothing decays on a time/forgetting
   curve. A **demonstrated error** re-opens remediation; a correct noun is never
   re-tested on an interval. (See *Curriculum-invariant reconciliation*.)
3. **Storage = derived projection, no new table.** Weakness is computed on-read
   from `GenderAttempt`, like `is_mastered_gender` already computes mastery.
4. **Three delivery surfaces, built B1 → B2 → B3.** B1 (this spec) = in-story
   cloze reprioritization + the classifier. B2 = the dedicated, LLM-independent
   `/srs/gender/due` queue (the reliable cross-module resurfacing path). B3 =
   polymorphic merge into `/practice/queue`.
5. **Mastery stays the N=3 streak.** `GENDER_MASTERY_STREAK_N = 3` and
   `_streak_mastered` remain the single source of truth.

## Scope revision after roster review

The roster (Stride, Richter, Null Vale) converged: the originally-approved
"soft generation bias" (Consumer B) and the cross-module selector
`weak_gender_nouns` it fed are **deferred to B2**, and the `record_gender_attempt`
gate is **left untouched**. Rationale:

- The generation bias is best-effort, LLM- and coverage-gated, unmeasurable, and
  strictly dominated by B2's deterministic queue. Shipping it now would also
  pollute the `story.curriculum.missed` telemetry channel and create a
  cardless-target phantom in the schedule UI.
- `weak_gender_nouns` (cross-module, unbounded) exists only to feed that bias in
  B1; Halberg flagged it as a full-ledger scan with full-ORM/JSONB hydration on
  every `create_story`. It is B2's engine, not B1's.
- Deferring both removes, in one cut, the unbounded scan, a `casefold(None)`
  crash, a `casefold` vs `canonical_lemma` normalization mismatch on ß/umlaut, a
  schedule-UI phantom, and a remediation livelock.

What remains is the deterministic seam that teaches whether reprioritization
helps, plus the reusable classifier B2 will consume.

## Why generation is the wrong primary seam (recon finding)

Story generation does **not** control which nouns become cloze targets:
`target_lemmas` is only a soft prompt suggestion; the LLM emits `target_words`
non-deterministically (`temperature=0.8`); `verify_coverage` keeps only words
that appear in the prose (`story_gen.py:284-313`); for German users the module
path returns the **entire current module** vocab and cannot pull earlier-module
nouns; and `build_gender_cloze` returns on the **first** eligible noun
(`finish_lessons.py:160`) — one cloze per story. The reliable seam is therefore
the cloze builder, not generation.

## Curriculum-invariant reconciliation (forced by Voronov)

Two doctrine points are made explicit so they are not hand-waved:

1. **"No decae" (R3) vs windowed mastery.** `_streak_mastered` evaluates the
   newest N attempts — it is a sliding window, not a permanent latch, so it
   already "un-masters" a noun on the next wrong answer. B1 is the first feature
   to *act* on the `mastered → wrong_recent` transition. This is **exactly** the
   asymmetric remediation chosen in decision 2: gender does not decay on a
   *time* curve (no interval, no forgetting), but a **demonstrated error
   re-opens** it. The R3 phrase "el género se internaliza, no decae" is hereby
   refined to "does not decay with time; a wrong answer re-opens remediation."
2. **Axiom-0 and the scheduling signal.** Axiom-0 ("an intervention is
   legitimate only while its source of truth outranks the learner") governs
   **truth-assertions** — i.e. grading. The grading gate
   (`record_gender_attempt`, `gender_source == "oracle"`) is untouched, so the
   *answer's* authority still outranks the learner. Deciding *which* noun to
   re-test from the learner's own error history is **pedagogical sequencing**,
   not a truth-assertion — and it is exactly how the lexical axis already works
   (`is_mastered_lexical` derives from the learner's own reviews). Gender mirrors
   that pattern **minus the advancement gate** (gender still never gates module
   advancement). No Axiom-0 violation.

## Architecture

```
GenderAttempt (existing ledger)
        │
        ▼
_gender_noun_state(attempts_desc, N) → unseen | wrong_recent | in_progress | mastered   (pure)
        │
        └─► gender_weakness_order(db, user_id, ids) → list[UUID]   (story-scoped, bounded)
                 └─► Consumer A: build_gender_cloze picks the weakest (get_story_quiz)

is_gender_eligible(w) / gender_eligible_clause()  → canonical predicate, replaces 3 read copies
```

No new tables, models, migrations, endpoints, or schemas. New logic lives in a
small `curriculum/gender_eligibility.py`, additions to `competence.py`, and an
edit to one read path (`get_story_quiz`) plus the cloze builder.

## Components

### 1. Canonical eligibility predicate — `curriculum/gender_eligibility.py` (NEW)

The gender-eligibility predicate is copied by hand in four places. B1 extracts
one source of truth and migrates the **three read sites**:

- `services/finish_lessons.py:160-166` (cloze builder)
- `curriculum/competence.py:128-134` (`module_gender_progress` SQL clause)
- `routers/stories.py:326-333` (L1-notes endpoint)

The fourth site — `record_gender_attempt`'s gate (`stories.py:516`, a
deliberately looser "oracle + non-empty gender" write gate) — is **left
unchanged** in B1. Tightening it is a write-contract behavior change and is out
of scope; it relies on the cloze only ever being built from an eligible item,
which still holds.

```python
from klara.models import VocabItem
from klara.models.enums import PartOfSpeech

GENDER_ARTICLES: tuple[str, ...] = ("der", "die", "das")


def is_gender_eligible(w: VocabItem) -> bool:
    """A noun is gender-gradable iff it is a German NOUN whose gender is
    oracle-sourced and one of der/die/das. The single source of truth for the
    three read sites that previously hand-copied this predicate."""
    return (
        w.language == "de"
        and w.pos == PartOfSpeech.NOUN
        and w.gender_source == "oracle"
        and w.gender in GENDER_ARTICLES
    )


def gender_eligible_clause() -> tuple:
    """The same predicate as SQLAlchemy conditions, to splat into
    `.where(*gender_eligible_clause())` for VocabItem queries."""
    return (
        VocabItem.language == "de",
        VocabItem.gender_source == "oracle",
        VocabItem.pos == PartOfSpeech.NOUN,
        VocabItem.gender.in_(list(GENDER_ARTICLES)),
    )
```

`competence.py`'s `module_gender_progress` keeps its `module_vocab` join and
swaps its inline conjuncts for `*gender_eligible_clause()`. The L1-notes
comprehension and the cloze builder switch to `is_gender_eligible`.

### 2. The classifier — `_gender_noun_state` in `competence.py` (NEW, pure)

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

The four states are mutually exclusive and total **over a fixed attempt list**.
Note (per Voronov): the state is a function of `(attempts, N, read-time)`, not a
permanent property of the noun — a once-mastered noun answered wrong becomes
`wrong_recent`. That transition is the remediation trigger, by design.

### 3. The ordering helper — `gender_weakness_order` in `competence.py` (NEW)

Ranks the nouns of a single story for the cloze pick. Bounded by the story's
target ids (a handful) and index-friendly (`vocab_item_id IN (...)` uses
`ix_gender_attempt_user_vocab`). Returns every input id exactly once.

**Tie-break rule (the back-compat fix):** within the **weak** tiers
(`wrong_recent`, `in_progress`) cycle by least-recently-attempted first; within
the **non-weak** tiers (`unseen`, `mastered`) preserve **input order**. So when
no noun is weak, the order is the caller's target order and the cloze picks the
first eligible noun — identical to today's behavior.

```python
async def gender_weakness_order(
    db: AsyncSession, *, user_id: UUID, vocab_item_ids: list[UUID]
) -> list[UUID]:
    """Order the given nouns by cloze-pick priority for this user:
    wrong_recent > in_progress > unseen > mastered. Within the weak tiers,
    least-recently-attempted first (cycle). Within unseen/mastered, preserve the
    caller's input order (back-compat with the old first-eligible pick)."""
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
    weak = {"wrong_recent", "in_progress"}

    def key(idx_vid: tuple[int, UUID]) -> tuple[int, float, int]:
        idx, vid = idx_vid
        attempts = by_noun.get(vid, [])
        state = _gender_noun_state(attempts, GENDER_MASTERY_STREAK_N)
        if state in weak:
            # attempts[0] is the most-recent attempt; ascending epoch surfaces
            # the noun whose most-recent attempt is oldest (cycle, don't hammer).
            return (tier[state], attempts[0].attempted_at.timestamp(), idx)
        # non-weak: constant recency term so idx (target order) decides → back-compat
        return (tier[state], 0.0, idx)

    return [vid for _, vid in sorted(enumerate(vocab_item_ids), key=key)]
```

Using `.timestamp()` (a float) for the recency term removes both the
`None`-vs-`datetime` and naive-vs-aware comparison hazards a roster reviewer
flagged. `GenderAttempt.attempted_at` is a `created_ts` column
(`DateTime(timezone=True)`), so it is uniformly tz-aware and `.timestamp()` is
well-defined; only the weak tiers (which always have attempts) read it.

### 4. Consumer A — cloze picks the weakest (the reliable seam)

`services/finish_lessons.py` `build_gender_cloze` stays **sync and pure** and
keeps `native_language` **keyword-only** (its current signature); it gains an
optional `prefer_order`:

```python
def build_gender_cloze(words, *, native_language, prefer_order=None):
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

`is_gender_eligible` remains the sole eligibility authority; `prefer_order` is
only a hint. With `prefer_order=None` (or when it preserves target order),
`list.sort` stability yields today's first-eligible pick exactly.

**Caller** — `get_story_quiz` (`GET /{story_id}/quiz`, `routers/stories.py:258-273`;
`user: CurrentUser` is in scope, so `user.id` and `user.native_language` are
available). This is the quiz-render endpoint, **not** the attempt-grading
endpoint `record_gender_attempt`:

```python
words = await _load_words(db, list(story.target_vocab_item_ids or []))
prefer = await gender_weakness_order(
    db, user_id=user.id, vocab_item_ids=[w.id for w in words]
)
gender_cloze = build_gender_cloze(words, native_language=user.native_language, prefer_order=prefer)
```

`gender_weakness_order` runs on every quiz fetch (which can exceed once per
finish); the query is target-id-bounded and index-served, so the cost is a
handful of rows.

## Data flow

Open a story's quiz → `_load_words` loads targets in stored order →
`gender_weakness_order` ranks them for this user → `build_gender_cloze` emits a
cloze for the weakest eligible noun → learner answers → `record_gender_attempt`
grades vs the oracle and appends a `GenderAttempt` row (unchanged write path).
A wrong answer makes that noun `wrong_recent`, so a future quiz containing it
re-tests it first. Pulling a faded noun into a *new* story is B2.

## Error handling & edge cases

- **No attempts at all (every noun unseen):** all land in the `unseen` tier,
  ordered by input index → first eligible chosen (today's behavior). No error.
- **All eligible nouns mastered:** all land in the `mastered` tier, ordered by
  input index → first eligible chosen (today's behavior). No error. *(This is
  the steady state for a long-term user; the tie-break-by-index rule makes the
  back-compat guarantee genuinely hold here — the bug the roster caught in the
  previous draft.)*
- **Story with no eligible nouns:** `build_gender_cloze → None` (today's
  behavior).
- **Empty target list:** `gender_weakness_order → []`; cloze `None`.
- **Mixed weakness:** weakest eligible noun chosen; within the weak tier the
  least-recently-attempted one wins.

## Testing strategy

Mirror `tests/test_curriculum_competence.py` (async, `db_session`,
`_de_oracle_noun`, direct `GenderAttempt` seeding with explicit `attempted_at`;
no clock-freezing — advance time via `attempted_at` offsets; uuid-suffixed
lemmas since `vocab_items` is not truncated).

- **`_gender_noun_state` (pure):** 3 correct → mastered; newest wrong →
  wrong_recent; <3 attempts all correct → in_progress; empty → unseen;
  mastered-streak then one newer wrong → wrong_recent.
- **`gender_weakness_order`:** full ranking wrong_recent > in_progress > unseen >
  mastered; within the weak tier, least-recently-attempted first; **all-mastered
  preserves input/target order** (back-compat); **all-unseen preserves input
  order**; returns every id once; empty input → `[]`.
- **`is_gender_eligible` / `gender_eligible_clause`:** der/die/das oracle NOUN
  passes; llm-source, VERB, non-de, non-canonical gender each fail.
- **`build_gender_cloze` weakest-pick** (update `tests/test_gender_cloze.py`):
  with two eligible nouns where B is weaker than A and A is first in target
  order, `prefer_order` makes the cloze pick B; with `prefer_order=None` it still
  picks the first (back-compat); all-mastered story still picks the first.
- **Predicate-migration regression:** the existing L1-notes, module-progress,
  and gender-cloze suites stay green after switching the three read sites to the
  shared predicate.

## Non-goals (explicitly out of B1)

- No new table, model, migration, endpoint, schema, or `conftest` TRUNCATE
  change.
- **No `weak_gender_nouns` cross-module selector and no generation bias** — both
  deferred to B2 (see *Scope revision*).
- **No change to `record_gender_attempt`'s gate** — left as-is.
- No change to module advancement — it stays lexical-only and single-writer.
- No new frontend surface and no client changes (the cloze payload is unchanged).
- Still **one** gender cloze per story — B1 reprioritizes the single slot.
- No *guaranteed* cross-module resurfacing — that is B2.
- No decay, ease, interval, or `next_review_at` for gender.

## Deferred to B2 (recorded so they are not lost)

- `weak_gender_nouns(db, *, user_id)` — cross-module Shape A selector. When
  built, it must select only `(vocab_item_id, was_correct, attempted_at, id)`
  (not full ORM rows / JSONB `detail`) and be bounded, to avoid the full-ledger
  scan Halberg flagged. The classifier `_gender_noun_state` from B1 is its core.
- The soft generation bias (Consumer B). If revisited, dedup against
  `canonical_lemma`, not `casefold`, and guard `None` lemmas.
- The remediation livelock and the `not_in_srs` schedule phantom are properties
  of cross-module resurfacing and must be addressed in B2's design.
