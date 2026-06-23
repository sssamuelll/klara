# Gender SRS — Slice B3 (final): gender as a chooser segment in Practice

**Status:** approved design (brainstorm complete)
**Date:** 2026-06-23
**Axis:** German grammatical gender (der/die/das)
**Builds on:** B2a (backend `/gender/review` + `/gender/attempts`), B2b (`GenderPicker`, the `/gender` route + `GenderReview.tsx`), and #88 (the GenderReview polish: the empty/failed split + the `genderReview.failed` key). **All frontend; no backend change.**

## Goal

Surface gender review inside the Practice ("Pronunciar") screen as a **second
segment the learner can choose at setup**, reusing the existing gender flow. The
pronunciation session is untouched; the gender segment is the existing
`/gender` review, composed into Practice.

## Why this shape (roster-settled)

The Practice queue is **two concatenated typed lanes** (struggled → review) with
no shared ordering key, and the session loop is **monolithically
pronunciation** (`useSentencePractice` owns iteration AND assumes every item is
mic-scored). A *true interleave* of gender cards into that stream would require
hoisting iteration out of the hook, kind-dispatching the render, and forking the
summary/submit — high blast radius, and it would tempt a fake `next_review_at`
the locked invariants forbid. The chosen shape avoids all of that: gender is a
**separate, independently-looped segment** under the Practice screen, not mixed
into the pronunciation stream.

## Decisions locked (brainstorm)

- **Frontend-only.** Reuses `GET /gender/review` + `POST /gender/attempts` (B2a)
  and `GenderPicker` (B2b). **No backend change**; `/practice/queue` is NOT
  extended with a gender lane (the segment calls `/gender/review` directly).
- **Tab/choice at setup.** The Practice setup offers two segments — "Pronunciar"
  and "Género". The learner picks one; each runs its own independent loop.
- **No live count on the gender segment.** The "Género" entry is static — it does
  NOT pre-fetch `/gender/review` on Practice load (the same O(K log K) cost
  ceiling that kept the Home tile static). `/gender/review` is fetched **lazily,
  only when the learner enters the gender segment**.
- **Pronunciation loop untouched.** `useSentencePractice`, `SentenceView`,
  `tallySummary`, and the `/srs/cards/review-batch` submit are not modified.
- **DRY via extraction.** The gender session+summary is extracted from
  `GenderReview.tsx` into a reusable `GenderReviewSession` so the standalone
  `/gender` route and the Practice gender segment share one component.

## Architecture / Components

### 1. Extract `components/GenderReviewSession.tsx` (NEW)

Lift the loading / failed / empty / session / summary flow out of
`routes/GenderReview.tsx` into a reusable component that owns its own state
(items, phase, idx, correct), self-fetches via `api.genderReview()`, runs the
`GenderPicker` idx-loop, tallies, and renders the summary with an internal
"otra vez" (refetch). The only thing it does NOT own is where "exit" goes:

```ts
function GenderReviewSession(props: {
  onExit: () => void;     // where the home/back button goes
  exitLabel: string;      // the already-translated label for that button
}): JSX.Element
```

The empty, failed, and summary states render the exit button as
`<button onClick={onExit}>{exitLabel}</button>`. "Otra vez" (restart/refetch)
stays internal.

`routes/GenderReview.tsx` becomes a thin wrapper:
`<GenderReviewSession onExit={() => navigate("/")} exitLabel={t("genderReview.home")} />`.
Its behavior at `/gender` is unchanged.

### 2. Practice setup → segment chooser (`routes/Practice.tsx`)

Add a `segment` choice to the setup phase. On mount, Practice fetches ONLY the
pronunciation queue as today (no gender fetch — cost ceiling). The setup phase
renders two choices:
- **Pronunciar** — with its existing struggled/review counts; entering it runs
  the existing pronunciation session (unchanged).
- **Género** — a static entry with NO count; entering it renders
  `<GenderReviewSession onExit={backToSetup} exitLabel={t("practice.segment.backToSetup")} />`,
  which lazily fetches `/gender/review` on mount.

Concretely: a `segment: "pronunciation" | "gender" | null` state. `null` → the
chooser. Picking "pronunciation" → the existing setup→session→summary flow.
Picking "gender" → the `GenderReviewSession`. Each segment's "exit" returns to
the chooser (`setSegment(null)`), so the learner can do one then the other.

### 3. i18n + CSS

- New keys for the chooser (es source, 6 locales, parity): `practice.segment.title`
  (the chooser heading, if any), `practice.segment.pronunciation` (label),
  `practice.segment.gender` (label), `practice.segment.backToSetup` (the gender
  segment's exit button). The gender session itself reuses the existing
  `genderReview.*` keys. **All new copy drafted via solace-wren.**
- **CSS:** style the segment chooser (two cards/tabs at setup), harmonizing with
  the existing Practice setup (`kp-*`) markup and the design tokens.

## Data flow

Open `/review` (Practice) → fetch pronunciation queue → setup shows the chooser
(Pronunciar with counts; Género static). Pick Pronunciar → existing session.
Pick Género → `GenderReviewSession` lazily fetches `/gender/review` → cards via
`GenderPicker` (grades through `api.gradeGender`) → summary → "otra vez" (refetch)
or back to the chooser. The standalone `/gender` route still works (Home tile),
sharing `GenderReviewSession`.

## Edge cases

- **Gender segment empty / fetch fails** → `GenderReviewSession`'s neutral
  empty / failed states (from B2b + #88), with the exit button returning to the
  Practice chooser.
- **No pronunciation items** → the Pronunciar choice can still be shown (it leads
  to the existing empty-queue handling) or de-emphasized; keep the existing
  empty-queue behavior for that segment.
- **Lazy gender fetch** → entering the gender segment shows
  `GenderReviewSession`'s loading state while `/gender/review` resolves.

## Non-goals

- No backend change; no gender lane in `/practice/queue`; no new endpoint.
- No fake `next_review_at`; no true interleave of gender into the pronunciation
  stream; no modification of `useSentencePractice` / the pronunciation session.
- No live gender count anywhere on load (cost ceiling).
- No change to module advancement; gender still never gates.

## Dependency / sequencing

B3's code touches `routes/GenderReview.tsx`, the locale files, and the gender
CSS — the same files as **#88** (the GenderReview polish). **Execute B3 on a
`main` that already includes #88** (rebase the branch onto post-#88 main before
the code tasks) to avoid conflicts. The spec/plan (docs) carry no conflict.

## Verification

Frontend gates (no unit runner): `npm run typecheck`, `npm run build`,
`npm run i18n:check` (parity). Manual: `/review` shows the chooser; Pronunciar
runs the unchanged pronunciation session; Género runs the gender review
(lazily-fetched), identical to `/gender`; `/gender` standalone still works.
