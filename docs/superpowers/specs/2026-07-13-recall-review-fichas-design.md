# Recall review — "la caja de fichas" — Design

**The SRS recall-review screen.** A postcard flashcard flow for vocab cards that are due: see the target word, recall its meaning, flip, self-rate. Ships as a third mode of the `/review` hub. Closes the dead-`elapsed_seconds` bug on the way.

## Problem

Klara has a full SRS recall backend — `schedule_next_review` (SM-2 lite, `backend/src/klara/services/srs_engine.py`), `GET /srs/cards/due`, `POST /srs/cards/{id}/review` — but **no UI drives it**. `api.reviewCard` (`frontend/src/api/client.ts:225`) has zero callers; `api.dueCards` is used only to render a count on Home (`routes/Home.tsx:67`). So:

1. **There is no recall-review surface.** The cards a user adds from stories (`+ Repaso`) become due and never resurface for recall.
2. **`Review.elapsed_seconds` is dead** (`models/srs.py:56`). The column, the schema field (`schemas/srs.py:29`), and the write (`routers/srs.py:118`) all exist, but the client sends only `{ rating }` — and nothing calls it anyway. The "hesitation" signal the SRS was built to capture is always NULL. (This is the second of the two junta-flagged bugs; the first, the Finish-quiz `sentence_index=-1` 422, is fixed separately in PR #114.)

The visual/UX design is approved (Claude Design project `klara`, `handoff-repaso-fichas/`): a filed index card, one big word, flip to the meaning, four editorial ratings, an anti-Duolingo close. This spec is the implementation of that design into the React app + the two small backend touches it needs.

## Decision

**A third segment in the existing `/review` hub, not a new route.** `Practice.tsx` is already a segment chooser (`pronunciation` | `gender`, `routes/Practice.tsx:207-230`); recall flashcards are the missing third review mode. Add `"cards"` and relabel the hub from "Pronunciar" to **"Repaso"** — the three modes (Fichas / Pronunciar / Género) are all repaso.

The recall session is a **self-contained component** mirroring `GenderReviewSession` (`components/GenderReviewSession.tsx`): it owns its queue, flip state, timing, and rating, and takes a single `onExit` prop. `Practice.tsx` gains ~6 lines (union member, chooser button, render branch); everything else is new and isolated.

## Architecture

### Frontend

- **`frontend/src/components/RecallReviewSession.tsx`** (new) — the whole flow. Props: `{ onExit: () => void; exitLabel: string }` (same shape as `GenderReviewSession`). State: `cards: CardOut[]` (fetched once via `api.dueCards(limit)`), `index`, `phase: "prompt" | "revealed" | "done"`, and a `shownAt` timestamp per card for elapsed timing. Renders the ficha markup inside its own `<main>` — the app masthead is global (`App.tsx` renders it before `<Routes>`), so the session omits it and renders only its header bar + progress pips + ficha + rate row + done. On rating: compute `elapsed = round((now - shownAt) / 1000)`, call `api.reviewCard(card.id, rating, elapsed)` optimistically, advance; when the queue is exhausted → `phase = "done"`. `Space` flips, `1`–`4` rate (keyboard, guarded to the active phase).
- **`frontend/src/lib/srsProjection.ts`** (new) — `projectIntervals(card): Record<Rating, string>`, a small pure mirror of `schedule_next_review`'s branch table, humanized via existing `lib/srsTime.ts`. Renders the honest next-interval under each rating **per card** (a NEW card shows ~10 min / ~1 h / 1 día / 4 días; a REVIEWING card shows its own multipliers). Commented as a mirror of `srs_engine.py`; if it must become authoritative, move the projection server-side onto `CardOut`.
- **`frontend/src/api/client.ts`** — `reviewCard(cardId, rating, elapsedSeconds?)`: add the optional third arg, send `JSON.stringify({ rating, elapsed_seconds: elapsedSeconds })` (omit the key when undefined). **This is the `elapsed_seconds` fix.**
- **`frontend/src/api/types.ts`** — extend `CardOut` with `gender: string | null` (the article for oracle nouns; see backend).
- **TTS** — the "Escuchar" button calls `speak(card.lemma, targetLanguage)` from `lib/tts.ts` (existing playback; same path Story/Practice use).
- **CSS** — port the `handoff-repaso-fichas/styles.css` `.k-ficha` / `.k-rate` / `.k-done` rules into the app (new `frontend/src/styles/recall-review.css`, imported by the component). The handoff tokens ARE the app tokens, so no token work. Reuse existing hub chrome (`kp-*` back button, `k-mono`, hairlines) for the frame.

### Backend

- **`CardOut` (`schemas/srs.py`)** — add `gender: str | None = None`.
- **`_card_to_out` (`routers/srs.py:26`)** — set `gender = vocab.gender if (vocab.pos == PartOfSpeech.NOUN and vocab.gender_source == "oracle") else None`. Only oracle-known genders are surfaced (never an LLM guess), consistent with the gender-axis honesty discipline. `vocab.gender` holds the article (`der`/`die`/`das`). No migration — it is a response field over existing columns.
- Everything else already exists: `due_cards` returns the queue, `submit_review` persists `rating` + `elapsed_seconds`.

### Data flow

`/review` → hub → "Fichas" → `RecallReviewSession` mounts → `api.dueCards()` →
render card: front = `lemma` (article hidden when `gender` present), gender cue, "Escuchar"; flip → back = `gender` (bermellón) + `lemma` + `translation` + `example_target` + source; four ratings with `projectIntervals(card)` →
rate → `api.reviewCard(id, rating, elapsed)` → advance → (queue empty) → done summary (count; "vuelven pronto" = # rated `again`; next-due line) → `onExit()`.

## Out of scope (v1 limits, documented)

- **No card-source line beyond what `CardOut` carries.** The mockup's *"de tu historia «…»"* needs the origin story title, which `CardOut` does not include. v1 omits the source line; wiring the real title is a later `CardOut` addition.
- **No "listen on the back" auto-play, no waveform.** Escuchar is a manual tap; no audio visualizer (that belongs to the pronunciation mode).
- **No filtering chips / partial queues.** The whole due set, in due order (`due_cards` order). No "solo las difíciles" subset.
- **No new nav item** and no change to Home's due-count tile target beyond the hub (the tile already routes to `/review`).
- **Projection stays client-side** (mirror of SM-2 lite). Not moved onto `CardOut` unless it drifts.

## Testing

**Backend (pytest, test DB):**
- `_card_to_out` / `GET /srs/cards/due`: a NOUN with `gender_source="oracle"` and `gender="die"` surfaces `gender="die"`; a NOUN with `gender_source="llm"`, a non-noun, or `gender=None` surfaces `gender=None`.
- **Bug-2 regression:** `POST /srs/cards/{id}/review` with `elapsed_seconds` persists it on the `Review` row (asserts the column is no longer dead once a client sends it).

**Frontend (vitest):**
- `api.reviewCard(id, "good", 7)` builds a request body with `elapsed_seconds: 7`; `reviewCard(id, "good")` omits the key.
- `projectIntervals`: a NEW card yields the four expected buckets; a REVIEWING card scales off its `interval_days`. (Pure fn, no DOM.)
- `RecallReviewSession`: flips on rate-phase transition and, on a rating, calls `api.reviewCard` with the card id, the rating, and a numeric elapsed; advances to the next card; shows the done summary when the queue empties. (Component test with a mocked `api`.)
