# Gender SRS — Slice B2b (frontend): dedicated der/die/das review screen

**Status:** approved design (brainstorm complete)
**Date:** 2026-06-23
**Axis:** German grammatical gender (der/die/das)
**Builds on:** B2a (backend), merged on main — `GET /api/v1/gender/review → GenderReviewItem[]{vocab_item_id, lemma, en}` and `POST /api/v1/gender/attempts → GenderAttemptOut{was_correct, correct_gender, rule}`.

## Goal

Ship the learner-facing surface for the gender review queue: a dedicated screen
that drills the user's weak der/die/das nouns one card at a time, grading each
against the oracle, then a short summary. Reuses the existing in-story gender
cloze look; reachable from a Home tile.

## Decisions locked (B2 spec + this brainstorm)

- **Extract a presentational `GenderPicker`** from `StoryFinish.GenderClozeQuestion`; the grading call is **injected** via an `onGrade` prop (story binds `recordGenderAttempt`, review binds `gradeGender`). The shared `genderRuleNote` rule-string logic moves to a pure helper.
- **Direct flow** `session → summary` — NO setup phase. Fetch on mount → first card immediately (progress header `N/total`) → iterate → summary.
- **Neutral empty state** ("nothing to review right now") — never "you mastered everything" (an empty weak set also means "never started").
- **Home tile, NO live count badge** (the `GET /gender/review` O(K log K) cost ceiling — never full-sort on Home load).
- Route `/gender` (ProtectedRoute). New `genderReview` i18n group across all 6 locales; per-card feedback reuses `story.finish.quiz.genderCloze.*`.
- **All new copy is drafted via the solace-wren skill** (microcopy mandate) during the implementation plan.

## Architecture / Components

### 1. `components/GenderPicker.tsx` (NEW) + `lib/genderRuleNote.ts` (NEW)

Lift the **presentational** core of `GenderClozeQuestion` (`StoryFinish.tsx:898-1006`)
into a reusable component. It owns the common flow (pick → grade → verdict +
rule → next) but the grading call is injected:

```ts
function GenderPicker(props: {
  lemma: string;
  en?: string | null;
  onGrade: (article: "der" | "die" | "das") => Promise<GenderAttemptOut>;
  onResult: (correct: boolean) => void;   // for the parent's tally / quiz tracker
  onNext: () => void;
  isLast: boolean;
}): JSX.Element
```

Internals (moved verbatim from `GenderClozeQuestion`): `GENDER_OPTIONS`, the
`picked`/`result` state, the qcard markup (the `qcard__blank` revealing
`correctGender`, the lemma, the optional `en` gloss, the `prompt` hint, the
three `qcard__gender-btn` buttons, the verdict, the `ruleNote`, the next button).
The pick handler calls `props.onGrade(article)` instead of `recordGenderAttempt`
directly; on success it sets the result + calls `onResult(was_correct)`; on
failure it grades as "couldn't check" and advances (identical for both callers —
never strand the user). Per-card strings stay on `story.finish.quiz.genderCloze.*`.

`genderRuleNote(t, rule: GenderRule | null, correctGender: string | null, lemma: string) -> string | null`
in `lib/genderRuleNote.ts` is the pure extraction of the existing `ruleNote` IIFE
(`StoryFinish.tsx:933-949`) — the hard/tendency/exception key selection. Both the
picker and (transitively) StoryFinish use it, so the rule-localization logic is
single-sourced.

### 2. `StoryFinish.tsx` refactor (behavior-preserving)

`GenderClozeQuestion` becomes a thin wrapper around `GenderPicker`:
`onGrade={(a) => api.recordGenderAttempt(story.id, {vocab_item_id: q.vocab_item_id, picked_article: a})}`,
`onResult={(correct) => onAnswered({correct, revealed: false})}`, forwarding
`onNext`/`isLast`. The in-story quiz behavior is unchanged.

### 3. `routes/GenderReview.tsx` (NEW) — route `/gender`

Two phases, `session → summary` (no setup). On mount, fetch `api.genderReview()`
once (mirror `Practice.tsx`'s alive-guarded effect). States:
- **loading** → a minimal spinner/placeholder.
- **load failed** → a neutral error line (mirror Practice's `loadFailed`).
- **empty** (`items.length === 0`) → the neutral "nothing to review" state with a
  "back home" CTA.
- **session** → `idx` state; render `GenderPicker` for `items[idx]` with a
  `N/total` progress header; `onNext` advances `idx` or, when `isLast`, switches
  to summary; `onResult` accumulates a `correct` tally.
- **summary** → counts (reviewed / correct), an **"otra vez"** CTA (refetch:
  reset to session with a fresh `api.genderReview()` — now-mastered nouns are
  gone) and an **"inicio"** CTA (`navigate('/')`).

Registered in `App.tsx` as `<Route path="/gender" element={<ProtectedRoute><GenderReview/></ProtectedRoute>}/>`.

### 4. Client + types — `api/client.ts`, `api/types.ts`

- `interface GenderReviewItem { vocab_item_id: string; lemma: string; en?: string | null }` (next to the existing gender types).
- `api.genderReview = (limit = 20) => request<GenderReviewItem[]>(\`/gender/review?limit=${limit}\`)`.
- `api.gradeGender = (payload: GenderAttemptIn) => request<GenderAttemptOut>("/gender/attempts", { method: "POST", body: JSON.stringify(payload) })`.

(`GenderAttemptIn`/`GenderAttemptOut`/`GenderRule` types already exist in `types.ts`.)

### 5. Home tile — `routes/Home.tsx`

A new `home__secondary` item (a sibling of the `/review` and `/chat` items) that
`navigate('/gender')`. **No live count badge** — a static tile (unlike the
`/review` item's `dueCount`), because `GET /gender/review` is O(K log K) in the
user's lifetime attempts and must not run on every Home load. Copy: `home.sec.genderReview.{title,subtitle}`.

### 6. i18n + CSS

- New top-level **`genderReview`** group, es as source, mirrored to en/de/fr/ja/pt
  (`npm run i18n:check` enforces identical leaf-key sets). Keys + their roles:
  - `genderReview.title` — screen title.
  - `genderReview.progress` — the `N/total` header (interpolated `{{done}}`/`{{total}}`).
  - `genderReview.empty` — the neutral "nothing to review right now" state body.
  - `genderReview.summary` — the summary headline (interpolated reviewed/correct counts).
  - `genderReview.again` — the refetch CTA ("otra vez").
  - `genderReview.home` — the back-home CTA.
  - `home.sec.genderReview.title` / `home.sec.genderReview.subtitle` — the Home tile.
  - Per-card feedback (cap/prompt/correct/wrong/failed/rule.*) **reuses the
    existing `story.finish.quiz.genderCloze.*`** — no new keys.
  - **The strings for every new key are drafted with the solace-wren skill**
    (microcopy mandate); es first (source), then mirrored to the five others.
- **CSS:** `qcard__gender-btn` / `qcard__gender-opts` are currently unstyled
  (they inherit generic qcard layout). Style the three article buttons (a clear
  three-up choice) and the review screen shell (progress header, summary). Add to
  the existing styles or a small `gender-review.css`.

## Data flow

Home tile → `/gender` → `GenderReview` fetches `api.genderReview()` → if empty,
neutral state; else iterate `GenderPicker` per item: pick → `api.gradeGender()` →
verdict + `genderRuleNote` → next → … → summary (reviewed/correct) → "otra vez"
(refetch) or "inicio". The same `GenderPicker` renders in-story (via the
`StoryFinish` wrapper, `onGrade` bound to `recordGenderAttempt`).

## Edge cases

- **Empty weak set** → neutral "nothing to review" + home CTA (no congratulation).
- **Fetch fails** → neutral error line + home CTA (mirror Practice's `loadFailed`).
- **Grade fails mid-card** → the picker grades "couldn't check" and advances
  (the existing in-story behavior, now shared) — never strands the session.
- **Single noun** → one card, then summary.
- **`en` gloss is null** → render the lemma alone (the picker already guards `q.en`).

## Verification

The frontend CI gates are `npm run typecheck`, `npm run build`, and
`npm run i18n:check` (6-locale leaf-key parity) — all must pass. No unit-test
runner is wired; correctness beyond types is confirmed by build + a manual/visual
pass of the screen and the unchanged in-story cloze.

## Non-goals

- No live count badge on Home (cost ceiling).
- No setup phase; no auto-advance (manual next preserves the rule-reading moment).
- No surfacing of the gender mastery tri-state (parked "D").
- No change to the backend (B2a is the contract); no new endpoint.
- No B3 practice-queue merge.
- Gender still never gates advancement.
