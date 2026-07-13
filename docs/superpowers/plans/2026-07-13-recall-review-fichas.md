# Recall Review — "la caja de fichas" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the SRS recall-review screen ("Fichas") as a third mode of the `/review` hub, driving the existing dueCards + reviewCard + SM-2 backend, and wire `reviewCard` to send `elapsed_seconds` (closes the Bug-2 dead column).

**Architecture:** A self-contained `RecallReviewSession` React component (mirrors `GenderReviewSession`) rendered as a new `"cards"` segment in `routes/Practice.tsx`. Two small backend touches expose `gender` (article, for the hide/reveal) and `ease` (for honest per-card interval projection) on `CardOut`. A pure `lib/srsProjection.ts` mirrors `schedule_next_review` to label each rating's next interval.

**Tech Stack:** Backend FastAPI + SQLAlchemy async + pytest. Frontend React + Vite + TypeScript + vitest + react-i18next (6 locales, `es` source).

## Global Constraints

- **i18n parity is a CI gate.** `scripts/check-i18n.mjs` requires all 6 locales (`es, en, de, fr, ja, pt`) to have the exact same leaf keys as `es` (source). Every key added to `es/common.json` MUST be added to the other 5, or `npm run i18n:check` (and CI) fails. Copy is authored in `es`; the other 5 are translated.
- **Backend tests need Postgres.** `conftest.py` defaults `TEST_DATABASE_URL` to the compose DB (`postgresql+asyncpg://german:german_dev_pw@localhost:5432/german_app_test`). Bring it up with `docker compose up -d postgres` before running pytest, or run against CI.
- **Commands run from the sub-tree:** backend commands from `backend/`, frontend from `frontend/`.
- **No new runtime dependencies.** Everything uses libraries already in the repo.
- **`CardState` values** (frontend union / backend enum): `new | learning | reviewing | relearning | suspended`.
- **`ReviewRating` values:** `again | hard | good | easy` (already in `frontend/src/api/types.ts:19`).

---

## File Structure

**Backend**
- Modify `backend/src/klara/schemas/srs.py` — add `gender` + `ease` to `CardOut`.
- Modify `backend/src/klara/routers/srs.py` — `_card_to_out` populates them.
- Create `backend/tests/test_srs_recall.py` — gender exposure + `elapsed_seconds` regression.

**Frontend**
- Modify `frontend/src/api/types.ts` — add `gender`, `ease` to `CardOut`.
- Modify `frontend/src/api/client.ts` — `reviewCard(cardId, rating, elapsedSeconds?)`.
- Create `frontend/src/api/client.reviewCard.test.ts` — request body includes `elapsed_seconds`.
- Create `frontend/src/lib/srsProjection.ts` — `projectIntervals` + `formatInterval`.
- Create `frontend/src/lib/srsProjection.test.ts`.
- Create `frontend/src/styles/recall-review.css` — ported ficha/rate/done styles.
- Create `frontend/src/components/RecallReviewSession.tsx`.
- Create `frontend/src/components/RecallReviewSession.test.tsx`.
- Modify `frontend/src/routes/Practice.tsx` — `"cards"` segment + chooser button.
- Modify `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` — `nav.review` value, `practice.segment.cards`, `recall.*`.

---

## Task 1: Backend — expose `gender` + `ease` on `CardOut`

**Files:**
- Modify: `backend/src/klara/schemas/srs.py` (`CardOut`, ~lines 14-24)
- Modify: `backend/src/klara/routers/srs.py` (`_card_to_out`, lines 26-38)
- Test: `backend/tests/test_srs_recall.py` (create)

**Interfaces:**
- Produces: `CardOut` now carries `gender: str | None` (the article `der`/`die`/`das`, only for nouns with `gender_source == "oracle"`, else `None`) and `ease: float`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_srs_recall.py`. Mirror the register/login helper from `tests/test_story_finish.py`.

```python
"""GET /srs/cards/due exposes gender (oracle nouns only) + ease; review persists elapsed_seconds."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from klara.models import UserCard, VocabItem, Review, User
from klara.models.enums import PartOfSpeech, CardState


async def _register_and_login(client, seed_invite, email: str) -> str:
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def _add_due_card(db, user_id, *, lemma, pos, gender, gender_source):
    vocab = VocabItem(
        language="de", lemma=lemma, pos=pos, gender=gender,
        gender_source=gender_source, translations={"es": "x"}, example_target="Ein Satz.",
    )
    db.add(vocab)
    await db.flush()
    card = UserCard(user_id=user_id, vocab_item_id=vocab.id, next_review_at=None, state=CardState.NEW)
    db.add(card)
    await db.commit()
    return card


@pytest.mark.asyncio
async def test_due_exposes_gender_for_oracle_nouns_only(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite, "recall1@example.com")
    user = (await db_session.execute(select(User).where(User.email == "recall1@example.com"))).scalar_one()
    await _add_due_card(db_session, user.id, lemma="Bäckerei", pos=PartOfSpeech.NOUN, gender="die", gender_source="oracle")
    await _add_due_card(db_session, user.id, lemma="Haus", pos=PartOfSpeech.NOUN, gender="das", gender_source="llm")
    await _add_due_card(db_session, user.id, lemma="gehen", pos=PartOfSpeech.VERB, gender=None, gender_source="llm")

    r = await client.get("/api/v1/srs/cards/due", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    by_lemma = {c["lemma"]: c for c in r.json()}
    assert by_lemma["Bäckerei"]["gender"] == "die"   # oracle noun → article
    assert by_lemma["Haus"]["gender"] is None          # llm noun → hidden
    assert by_lemma["gehen"]["gender"] is None          # non-noun → null
    assert isinstance(by_lemma["Bäckerei"]["ease"], (int, float))


@pytest.mark.asyncio
async def test_review_persists_elapsed_seconds(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite, "recall2@example.com")
    user = (await db_session.execute(select(User).where(User.email == "recall2@example.com"))).scalar_one()
    card = await _add_due_card(db_session, user.id, lemma="lesen", pos=PartOfSpeech.VERB, gender=None, gender_source="llm")

    r = await client.post(
        f"/api/v1/srs/cards/{card.id}/review",
        json={"rating": "good", "elapsed_seconds": 7},
        headers={"Cookie": cookie},
    )
    assert r.status_code == 200, r.text
    review = (await db_session.execute(select(Review).where(Review.user_card_id == card.id))).scalar_one()
    assert review.elapsed_seconds == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose up -d postgres` (once), then from `backend/`:
`uv run pytest tests/test_srs_recall.py -v`
Expected: `test_due_exposes_gender_for_oracle_nouns_only` FAILS (KeyError `'gender'` / response has no gender). The elapsed test may already pass (backend already persists it) — that's the regression guard; keep it.

- [ ] **Step 3: Add the fields to `CardOut`**

In `backend/src/klara/schemas/srs.py`, add to `CardOut` (after `example_target`):

```python
    gender: str | None = None
    ease: float
```

- [ ] **Step 4: Populate them in `_card_to_out`**

In `backend/src/klara/routers/srs.py`, add the import at the top:

```python
from klara.models.enums import PartOfSpeech
```

Replace `_card_to_out` (lines 26-38) with:

```python
def _card_to_out(card: UserCard, vocab: VocabItem, native_language: str) -> CardOut:
    # Only surface an oracle-known article (der/die/das). An LLM-guessed gender is
    # never shown as fact — same honesty gate as the gender-cloze axis.
    gender = (
        vocab.gender
        if vocab.pos == PartOfSpeech.NOUN and vocab.gender_source == "oracle"
        else None
    )
    return CardOut(
        id=card.id,
        vocab_item_id=vocab.id,
        lemma=vocab.lemma,
        pos=vocab.pos,
        translation=(vocab.translations or {}).get(native_language),
        example_target=vocab.example_target,
        gender=gender,
        state=card.state,
        interval_days=card.interval_days,
        next_review_at=card.next_review_at,
        repetitions=card.repetitions,
        ease=card.ease,
    )
```

- [ ] **Step 5: Run tests + lint**

From `backend/`:
`uv run pytest tests/test_srs_recall.py -v` → Expected: PASS (both tests)
`uv run ruff check src tests && uv run ruff format --check src tests` → Expected: clean

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/schemas/srs.py backend/src/klara/routers/srs.py backend/tests/test_srs_recall.py
git commit -m "feat(srs): expose gender (oracle nouns) + ease on CardOut; regression-test elapsed_seconds"
```

---

## Task 2: Frontend — `reviewCard` sends `elapsed_seconds` (closes Bug 2) + `CardOut` type

**Files:**
- Modify: `frontend/src/api/types.ts` (`CardOut`, lines 85-96)
- Modify: `frontend/src/api/client.ts` (`reviewCard`, lines 225-229)
- Test: `frontend/src/api/client.reviewCard.test.ts` (create)

**Interfaces:**
- Produces: `api.reviewCard(cardId: string, rating: ReviewRating, elapsedSeconds?: number) => Promise<unknown>`. Body: `{ rating }` or `{ rating, elapsed_seconds }`. `CardOut` type gains `gender: string | null` and `ease: number`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api/client.reviewCard.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

function mockFetch() {
  const spy = vi.fn(async () => new Response("{}", { status: 200, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => vi.unstubAllGlobals());

describe("reviewCard", () => {
  it("sends elapsed_seconds when provided", async () => {
    const fetchSpy = mockFetch();
    await api.reviewCard("card-1", "good", 7);
    const [, init] = fetchSpy.mock.calls[0];
    expect(JSON.parse(init.body as string)).toEqual({ rating: "good", elapsed_seconds: 7 });
  });

  it("omits elapsed_seconds when not provided", async () => {
    const fetchSpy = mockFetch();
    await api.reviewCard("card-1", "again");
    const [, init] = fetchSpy.mock.calls[0];
    expect(JSON.parse(init.body as string)).toEqual({ rating: "again" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

From `frontend/`: `npx vitest run src/api/client.reviewCard.test.ts`
Expected: FAIL — the "sends elapsed_seconds" case gets `{ rating: "good" }` (no elapsed_seconds), and `reviewCard` rejects a 3rd arg type.

- [ ] **Step 3: Update `reviewCard`**

In `frontend/src/api/client.ts`, replace `reviewCard` (lines 225-229) with:

```ts
  reviewCard: (cardId: string, rating: ReviewRating, elapsedSeconds?: number) =>
    request(`/srs/cards/${cardId}/review`, {
      method: "POST",
      body: JSON.stringify(
        elapsedSeconds === undefined ? { rating } : { rating, elapsed_seconds: elapsedSeconds },
      ),
    }),
```

Ensure `ReviewRating` is imported in `client.ts` (it is exported from `./types`). If the file imports types via `import type { ... } from "./types"`, add `ReviewRating` to that import.

- [ ] **Step 4: Add `gender` + `ease` to the `CardOut` type**

In `frontend/src/api/types.ts`, inside `CardOut` (lines 85-96), add after `example_target`:

```ts
  gender: string | null;
```

and after `repetitions`:

```ts
  ease: number;
```

- [ ] **Step 5: Run test + typecheck**

From `frontend/`:
`npx vitest run src/api/client.reviewCard.test.ts` → Expected: PASS
`npm run typecheck` → Expected: clean

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/types.ts frontend/src/api/client.reviewCard.test.ts
git commit -m "fix(srs): reviewCard sends elapsed_seconds; CardOut gains gender + ease"
```

---

## Task 3: Frontend — `lib/srsProjection.ts` (honest per-rating intervals)

**Files:**
- Create: `frontend/src/lib/srsProjection.ts`
- Test: `frontend/src/lib/srsProjection.test.ts`

**Interfaces:**
- Consumes: `CardOut` (`state`, `interval_days`, `ease`), `ReviewRating` from `../api/types`.
- Produces: `projectIntervals(card: Pick<CardOut, "state" | "interval_days" | "ease">) => Record<ReviewRating, number>` (days), and `formatInterval(days: number) => string` (localized short label). Mirrors backend `schedule_next_review` (`services/srs_engine.py`).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/srsProjection.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";

vi.mock("../i18n", () => ({
  default: {
    t: (key: string, opts?: { count?: number }) => `${key.split(".").pop()}:${opts?.count ?? ""}`,
  },
}));

import { projectIntervals, formatInterval } from "./srsProjection";

describe("projectIntervals", () => {
  it("uses fixed learning steps for a new card (ease is ignored)", () => {
    const p = projectIntervals({ state: "new", interval_days: 0, ease: 2.5 });
    expect(p.again).toBeCloseTo(0.0069, 4);
    expect(p.hard).toBeCloseTo(0.04, 4);
    expect(p.good).toBe(1);
    expect(p.easy).toBe(4);
  });

  it("scales off the current interval and ease for a reviewing card", () => {
    const p = projectIntervals({ state: "reviewing", interval_days: 10, ease: 2.5 });
    expect(p.again).toBeCloseTo(0.0069, 4);
    expect(p.hard).toBeCloseTo(12, 2); // 10 * 1.2
    expect(p.good).toBeCloseTo(25, 2); // 10 * 2.5
    expect(p.easy).toBeCloseTo(32.5, 2); // 10 * 2.5 * 1.3
  });

  it("floors the reviewing base interval at 1 day", () => {
    const p = projectIntervals({ state: "reviewing", interval_days: 0, ease: 2.0 });
    expect(p.good).toBeCloseTo(2, 2); // max(0,1) * 2.0
  });
});

describe("formatInterval", () => {
  it("labels sub-hour, sub-day, day, week, month buckets", () => {
    expect(formatInterval(0.0069)).toContain("minutes"); // ~10 min
    expect(formatInterval(0.04)).toContain("hours"); // ~1 h
    expect(formatInterval(1)).toContain("day"); // 1 día
    expect(formatInterval(4)).toContain("days"); // 4 días
    expect(formatInterval(14)).toContain("weeks"); // 2 sem
    expect(formatInterval(60)).toContain("months"); // 2 mes
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

From `frontend/`: `npx vitest run src/lib/srsProjection.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `srsProjection.ts`**

Create `frontend/src/lib/srsProjection.ts`:

```ts
import i18n from "../i18n";
import type { CardOut, ReviewRating } from "../api/types";

/**
 * Client mirror of backend `schedule_next_review` (services/srs_engine.py, SM-2
 * lite). Projects the next interval (in days) each rating would produce for a
 * card, so the review buttons can show honest, per-card costs. If this drifts
 * from the backend, move the projection onto CardOut instead of mirroring here.
 */
const LEARNING_STATES = new Set(["new", "learning", "relearning"]);

export function projectIntervals(
  card: Pick<CardOut, "state" | "interval_days" | "ease">,
): Record<ReviewRating, number> {
  const again = 0.0069; // ~10 min, every state
  if (LEARNING_STATES.has(card.state)) {
    return { again, hard: 0.04, good: 1, easy: 4 };
  }
  const base = Math.max(card.interval_days, 1);
  return {
    again,
    hard: round2(base * 1.2),
    good: round2(base * card.ease),
    easy: round2(base * card.ease * 1.3),
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

/** Short localized label for an interval in days (recall.interval.* keys). */
export function formatInterval(days: number): string {
  const k = (s: string, count: number): string =>
    i18n.t(`recall.interval.${s}`, { count });
  if (days < 1 / 24) return k("minutes", Math.max(1, Math.round(days * 24 * 60)));
  if (days < 1) return k("hours", Math.max(1, Math.round(days * 24)));
  if (days < 7) {
    const d = Math.round(days);
    return k(d === 1 ? "day" : "days", d);
  }
  if (days < 30) return k("weeks", Math.max(1, Math.round(days / 7)));
  return k("months", Math.max(1, Math.round(days / 30)));
}
```

- [ ] **Step 4: Run test to verify it passes**

From `frontend/`: `npx vitest run src/lib/srsProjection.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/srsProjection.ts frontend/src/lib/srsProjection.test.ts
git commit -m "feat(srs): srsProjection — honest per-rating next intervals"
```

---

## Task 4: Frontend — i18n keys (all 6 locales) + CSS port

**Files:**
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`
- Create: `frontend/src/styles/recall-review.css`

**Interfaces:**
- Produces: i18n keys `nav.review` (value → "Repaso"/translated), `practice.segment.cards.{title,dek}`, and the `recall.*` namespace (below). CSS classes `.rr`, `.rr__*` used by Task 5.

- [ ] **Step 1: Add the `es` keys (source of truth)**

In `frontend/src/locales/es/common.json`: change `nav.review` value from `"Pronunciar"` to `"Repaso"`. Add `cards` inside `practice.segment` and a new top-level `recall` block:

```json
"practice": {
  "segment": {
    "cards": { "title": "Fichas", "dek": "Las palabras que guardaste, una a una." }
  }
}
```
(merge `cards` alongside the existing `pron`/`gender`/`title`/`back` keys — do not replace them.)

Add this top-level block:

```json
"recall": {
  "title": "La caja de fichas",
  "kicker": "REPASO · HOY",
  "exit": "← Hoy",
  "loading": "Abriendo la caja…",
  "failed": "No se pudo abrir el repaso. Intenta de nuevo en un momento.",
  "empty": "No hay fichas por repasar hoy. Vuelve mañana.",
  "progress": "{{done}} / {{total}}",
  "cue": "¿Qué significa? Recuérdala, luego voltéala.",
  "listen": "Escuchar",
  "flip": "Voltear",
  "flipHint": "ESPACIO voltear",
  "rateHint": "1–4 calificar · esto agenda el próximo repaso",
  "rate": { "again": "Otra vez", "hard": "Difícil", "good": "Bien", "easy": "Fácil" },
  "interval": {
    "minutes": "~{{count}} min",
    "hours": "~{{count}} h",
    "day": "{{count}} día",
    "days": "{{count}} días",
    "weeks": "{{count}} sem",
    "months": "{{count}} mes"
  },
  "done": {
    "kicker": "REPASO CERRADO",
    "label": "fichas repasadas",
    "again": "vuelven pronto",
    "rest": "descansan",
    "note": "Las que fallaste vuelven en un rato; las demás, cuando estén a punto de olvidarse. No hay racha que romper — la caja te espera mañana.",
    "sign": "— K",
    "home": "Volver a hoy"
  }
}
```

- [ ] **Step 2: Mirror the keys into the other 5 locales (translated)**

Add the SAME keys to `en, de, fr, ja, pt` `common.json` with translations (and set each `nav.review` to the localized "Repaso": en `"Review"`, de `"Wiederholen"`, fr `"Révision"`, ja `"復習"`, pt `"Revisão"`). Keep the `interval` unit style natural per language (en: `~{{count}} min` / `{{count}} day` / `{{count}} days` / `{{count}} wk` / `{{count}} mo`). Use the existing translations in each file as the tone reference.

- [ ] **Step 3: Run the parity gate**

From `frontend/`: `npm run i18n:check`
Expected: PASS (no key drift across the 6 locales). If it lists missing keys, add them to the named locale and re-run.

- [ ] **Step 4: Port the CSS**

Create `frontend/src/styles/recall-review.css` by copying the component rules from the design mockup at `D:\Desktop\klara\klara-finished-handoff\handoff-repaso-fichas\styles.css`. **Rename EVERY `k-*` class in the copied rules to `rr-*`** (`k-ficha`→`rr-ficha`, `k-rate`→`rr-rate`, `k-deck`→`rr-deck`, `k-done`→`rr-done`, `k-head`→`rr-head`, `k-prog`→`rr-prog`, `k-listen`→`rr-listen`, `k-flip`→`rr-flip`, and their `__element`/`--modifier` suffixes) so they match the class names Task 5's component uses. Copy ONLY these rule groups:
- BODY + HEADER + PROGRESS (`k-head`, `k-prog`)
- DECK / ficha / flip faces (`k-deck`, `k-ficha*`, `k-listen`)
- ACTIONS (`k-flip`, `k-rate*`, `k-deck__hint`)
- DONE (`k-done*`)
- STATE VISIBILITY (`[data-show]` rules — keep, but scope the `.kapp[data-state=...]` selectors to `.rr[data-state=...]`)
- REDUCED MOTION + RESPONSIVE

Do NOT copy: the `@import` webfont line (fonts are global in the app), `* { box-sizing }` / `html, body` resets (app provides them), `.state-switch` (handoff only), `.k-mast*` masthead (the app masthead is global). The tokens (`--paper`, `--ink`, `--accent`, `--font-*`, …) already exist app-wide, so the ported rules resolve unchanged.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/locales frontend/src/styles/recall-review.css
git commit -m "feat(recall): i18n (6 locales) + ported ficha styles; relabel /review hub to Repaso"
```

---

## Task 5a: Frontend — `lib/recallSession.ts` (pure session reducer)

**Files:**
- Create: `frontend/src/lib/recallSession.ts`
- Test: `frontend/src/lib/recallSession.test.ts`

**Interfaces:**
- Consumes: `CardOut`, `ReviewRating` from `../api/types`.
- Produces: `RecallState`, `RecallAction`, `initialRecallState`, `recallReducer(state, action)`, `restedCount(state)`. The component (Task 5b) drives this via `useReducer`; all side effects (`api.dueCards`, `api.reviewCard`, `speak`, elapsed timing) stay in the component — the reducer is pure.

Rationale: the repo has no component-test infra and, by convention, keeps testable logic in `lib/` as pure functions (all existing tests are `lib/*.test.ts`). This task extracts the session state machine so it is unit-tested like the rest of `lib/`; Task 5b is a thin, untested view (like `GenderReviewSession`).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/recallSession.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { CardOut } from "../api/types";
import { initialRecallState, recallReducer, restedCount } from "./recallSession";

const card = (id: string): CardOut => ({
  id, vocab_item_id: `v-${id}`, lemma: "Wort", pos: "noun", translation: "palabra",
  example_target: "Ein Wort.", gender: "das", state: "new", interval_days: 0,
  next_review_at: null, repetitions: 0, ease: 2.5,
});

describe("recallReducer", () => {
  it("loaded with cards → prompt at index 0", () => {
    const s = recallReducer(initialRecallState, { type: "loaded", cards: [card("a"), card("b")] });
    expect(s.phase).toBe("prompt");
    expect(s.idx).toBe(0);
    expect(s.cards).toHaveLength(2);
  });

  it("loaded with no cards → empty", () => {
    expect(recallReducer(initialRecallState, { type: "loaded", cards: [] }).phase).toBe("empty");
  });

  it("failed → failed phase", () => {
    expect(recallReducer(initialRecallState, { type: "failed" }).phase).toBe("failed");
  });

  it("flip only advances prompt → revealed; it is a no-op from any other phase", () => {
    const prompt = recallReducer(initialRecallState, { type: "loaded", cards: [card("a")] });
    expect(recallReducer(prompt, { type: "flip" }).phase).toBe("revealed");
    const revealed = recallReducer(prompt, { type: "flip" });
    expect(recallReducer(revealed, { type: "flip" })).toBe(revealed); // no-op returns same ref
  });

  it("rate is a no-op unless revealed", () => {
    const prompt = recallReducer(initialRecallState, { type: "loaded", cards: [card("a")] });
    expect(recallReducer(prompt, { type: "rate", rating: "good" })).toBe(prompt);
  });

  it("rate advances to the next card (back to prompt) and counts 'again'", () => {
    let s = recallReducer(initialRecallState, { type: "loaded", cards: [card("a"), card("b")] });
    s = recallReducer(s, { type: "flip" });
    s = recallReducer(s, { type: "rate", rating: "again" });
    expect(s.phase).toBe("prompt");
    expect(s.idx).toBe(1);
    expect(s.againCount).toBe(1);
  });

  it("rating the last card → done; restedCount = total - again", () => {
    let s = recallReducer(initialRecallState, { type: "loaded", cards: [card("a"), card("b")] });
    s = recallReducer(recallReducer(s, { type: "flip" }), { type: "rate", rating: "good" }); // card a: good
    s = recallReducer(recallReducer(s, { type: "flip" }), { type: "rate", rating: "again" }); // card b: again (last)
    expect(s.phase).toBe("done");
    expect(s.againCount).toBe(1);
    expect(restedCount(s)).toBe(1); // 2 total - 1 again
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

From `frontend/`: `npx vitest run src/lib/recallSession.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `recallSession.ts`**

Create `frontend/src/lib/recallSession.ts`:

```ts
import type { CardOut, ReviewRating } from "../api/types";

/**
 * Pure state machine for a recall-review session. The component (RecallReviewSession)
 * drives this via useReducer and owns all side effects (fetching due cards, POSTing
 * the review with its elapsed time, TTS). Keeping the transitions here makes the
 * session's behaviour unit-testable without a DOM renderer.
 */
export type RecallPhase = "loading" | "failed" | "empty" | "prompt" | "revealed" | "done";

export interface RecallState {
  cards: CardOut[];
  idx: number;
  phase: RecallPhase;
  againCount: number;
}

export type RecallAction =
  | { type: "loaded"; cards: CardOut[] }
  | { type: "failed" }
  | { type: "flip" }
  | { type: "rate"; rating: ReviewRating };

export const initialRecallState: RecallState = {
  cards: [],
  idx: 0,
  phase: "loading",
  againCount: 0,
};

export function recallReducer(state: RecallState, action: RecallAction): RecallState {
  switch (action.type) {
    case "loaded":
      return {
        cards: action.cards,
        idx: 0,
        phase: action.cards.length === 0 ? "empty" : "prompt",
        againCount: 0,
      };
    case "failed":
      return { ...state, phase: "failed" };
    case "flip":
      return state.phase === "prompt" ? { ...state, phase: "revealed" } : state;
    case "rate": {
      if (state.phase !== "revealed") return state;
      const againCount = state.againCount + (action.rating === "again" ? 1 : 0);
      const nextIdx = state.idx + 1;
      return nextIdx < state.cards.length
        ? { ...state, idx: nextIdx, phase: "prompt", againCount }
        : { ...state, phase: "done", againCount };
    }
    default:
      return state;
  }
}

/** Cards that were NOT rated "again" this session — the "descansan" count. */
export function restedCount(state: RecallState): number {
  return state.cards.length - state.againCount;
}
```

- [ ] **Step 4: Run test to verify it passes**

From `frontend/`: `npx vitest run src/lib/recallSession.test.ts` → Expected: PASS (7/7)
`npm run typecheck` → clean

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/recallSession.ts frontend/src/lib/recallSession.test.ts
git commit -m "feat(recall): pure session reducer (recallSession)"
```

---

## Task 5b: Frontend — `RecallReviewSession` component (thin view)

**Files:**
- Create: `frontend/src/components/RecallReviewSession.tsx`
- Modify: `frontend/src/styles/recall-review.css` (add the `.rr` base layout rule)

**Interfaces:**
- Consumes: `recallReducer`/`initialRecallState`/`restedCount` (Task 5a), `api.dueCards`/`api.reviewCard` (Task 2), `projectIntervals`/`formatInterval` (Task 3), `speak` from `../lib/tts`, `recall.*` i18n + `.rr-*` CSS (Task 4), `CardOut`/`ReviewRating` types.
- Produces: `default export RecallReviewSession(props: { onExit: () => void; exitLabel: string })`. Root: `<main className="rr" data-state={phase}>`.

No unit test (the repo does not test components — `GenderReviewSession` has none either; the session's logic is covered by `recallSession.test.ts`, `srsProjection.test.ts`, and `client.reviewCard.test.ts`).

- [ ] **Step 1: Add the `.rr` base layout rule**

The ported CSS (Task 4) excluded the mockup's APP-SHELL group, so `.rr` has no layout of its own and `.rr-deck { flex: 1 }` has no flex parent. Model the frame on the sibling session screen `.gr` (`frontend/src/styles/gender-review.css`: `max-width: 36rem; margin: 0 auto; padding: 2rem 1.25rem;`), but make `.rr` a flex column so the deck can center. Add to the TOP of `frontend/src/styles/recall-review.css` (after the header comment):

```css
.rr {
  display: flex;
  flex-direction: column;
  gap: 22px;
  max-width: 720px;
  min-height: 70vh;
  margin: 0 auto;
  padding: 28px 24px 40px;
}
```

- [ ] **Step 2: Implement the component**

Create `frontend/src/components/RecallReviewSession.tsx`:

```tsx
import "../styles/recall-review.css";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { ReviewRating } from "../api/types";
import { speak } from "../lib/tts";
import { formatInterval, projectIntervals } from "../lib/srsProjection";
import { initialRecallState, recallReducer, restedCount } from "../lib/recallSession";

const RATINGS: ReviewRating[] = ["again", "hard", "good", "easy"];

interface Props {
  onExit: () => void;
  exitLabel: string;
}

export default function RecallReviewSession({ onExit, exitLabel }: Props): JSX.Element {
  const { t } = useTranslation();
  const [state, dispatch] = useReducer(recallReducer, initialRecallState);
  const shownAt = useRef<number>(0);

  useEffect(() => {
    let alive = true;
    api
      .dueCards(50)
      .then((rows) => {
        if (!alive) return;
        dispatch({ type: "loaded", cards: rows });
        shownAt.current = performance.now();
      })
      .catch(() => alive && dispatch({ type: "failed" }));
    return () => {
      alive = false;
    };
  }, []);

  // Reset the per-card timer whenever a new card comes on screen.
  useEffect(() => {
    if (state.phase === "prompt") shownAt.current = performance.now();
  }, [state.idx, state.phase]);

  const card = state.cards[state.idx];

  const rate = useCallback(
    (rating: ReviewRating) => {
      if (!card) return;
      const elapsed = Math.max(0, Math.round((performance.now() - shownAt.current) / 1000));
      void api.reviewCard(card.id, rating, elapsed).catch(() => undefined);
      dispatch({ type: "rate", rating });
    },
    [card],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (state.phase === "prompt" && e.code === "Space") {
        e.preventDefault();
        dispatch({ type: "flip" });
      } else if (state.phase === "revealed" && ["1", "2", "3", "4"].includes(e.key)) {
        rate(RATINGS[Number(e.key) - 1]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state.phase, rate]);

  if (state.phase === "loading") {
    return (
      <main className="rr">
        <p className="rr__loading k-mono">{t("recall.loading")}</p>
      </main>
    );
  }
  if (state.phase === "failed" || state.phase === "empty") {
    return (
      <main className="rr">
        <h1 className="rr__title">{t("recall.title")}</h1>
        <p className="rr__empty">{t(state.phase === "failed" ? "recall.failed" : "recall.empty")}</p>
        <button type="button" className="rr-done__cta" onClick={onExit}>
          {exitLabel}
        </button>
      </main>
    );
  }
  if (state.phase === "done") {
    return (
      <main className="rr" data-state="done">
        <section className="rr-done">
          <span className="rr-done__folio k-mono">{t("recall.done.kicker")}</span>
          <span className="rr-done__count">{state.cards.length}</span>
          <span className="rr-done__label">{t("recall.done.label")}</span>
          <div className="rr-done__ledger">
            <div className="rr-done__stat">
              <span className="rr-done__stat-n rr-done__stat-n--accent">{state.againCount}</span>
              <span className="rr-done__stat-l">{t("recall.done.again")}</span>
            </div>
            <div className="rr-done__stat">
              <span className="rr-done__stat-n">{restedCount(state)}</span>
              <span className="rr-done__stat-l">{t("recall.done.rest")}</span>
            </div>
          </div>
          <p className="rr-done__note">{t("recall.done.note")}</p>
          <span className="rr-done__sign">{t("recall.done.sign")}</span>
          <button type="button" className="rr-done__cta" onClick={onExit}>
            {t("recall.done.home")} →
          </button>
        </section>
      </main>
    );
  }

  // phase === "prompt" | "revealed"
  const intervals = projectIntervals(card);
  return (
    <main className="rr" data-state={state.phase}>
      <header className="rr-head">
        <button type="button" className="rr-head__exit k-mono" onClick={onExit}>
          {t("recall.exit")}
        </button>
        <div className="rr-head__title">
          <span className="rr-head__k">K</span>
          <span className="rr-head__name">{t("recall.title")}</span>
        </div>
        <span className="rr-head__meta k-mono">{t("recall.kicker")}</span>
      </header>

      <div className="rr-prog">
        <span className="rr-prog__count k-mono">
          {t("recall.progress", { done: state.idx + 1, total: state.cards.length })}
        </span>
      </div>

      <section className="rr-deck">
        <div className="rr-ficha">
          <div className="rr-ficha__inner">
            <div className="rr-ficha__face rr-ficha__face--front">
              <span className="rr-ficha__word">{card.lemma}</span>
              {card.gender && (
                <span className="rr-ficha__gender-cue k-mono">
                  <b>der</b> · <b>die</b> · <b>das</b> ?
                </span>
              )}
              <span className="rr-ficha__cue">{t("recall.cue")}</span>
              <button type="button" className="rr-listen k-mono" onClick={() => speak(card.lemma)}>
                <span className="rr-listen__tri" /> {t("recall.listen")}
              </button>
            </div>
            <div className="rr-ficha__face rr-ficha__face--back">
              <div className="rr-ficha__answer">
                {card.gender && <span className="rr-ficha__article">{card.gender}</span>}
                <span className="rr-ficha__answer-word">{card.lemma}</span>
                {card.translation && <span className="rr-ficha__tx">— {card.translation}</span>}
              </div>
              {card.example_target && (
                <>
                  <div className="rr-ficha__rule" />
                  <p className="rr-ficha__eg">{card.example_target}</p>
                </>
              )}
            </div>
          </div>
        </div>

        <div data-show="prompt" className="rr-deck__prompt">
          <button type="button" className="rr-flip" onClick={() => dispatch({ type: "flip" })}>
            {t("recall.flip")} <span className="rr-flip__arrow">↻</span>
          </button>
          <p className="rr-deck__hint">{t("recall.flipHint")}</p>
        </div>

        <div className="rr-rate" data-show="revealed">
          {RATINGS.map((r) => (
            <button
              key={r}
              type="button"
              className={`rr-rate__btn${r === "again" ? " rr-rate__btn--again" : ""}`}
              onClick={() => rate(r)}
            >
              <span className="rr-rate__lbl">{t(`recall.rate.${r}`)}</span>
              <span className="rr-rate__when k-mono">{formatInterval(intervals[r])}</span>
            </button>
          ))}
        </div>
        <p className="rr-deck__hint" data-show="revealed">
          {t("recall.rateHint")}
        </p>
      </section>
    </main>
  );
}
```

- [ ] **Step 3: Verify**

From `frontend/`:
`npm run typecheck` → clean
`npx vitest run` → all existing + new lib tests pass (no component test added)
`npm run build` → succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/RecallReviewSession.tsx frontend/src/styles/recall-review.css
git commit -m "feat(recall): RecallReviewSession view over the session reducer + .rr layout"
```

## Task 6: Frontend — wire `"cards"` segment into `Practice.tsx` + verify

**Files:**
- Modify: `frontend/src/routes/Practice.tsx` (segment union line 103; chooser lines 206-230; import)

**Interfaces:**
- Consumes: `RecallReviewSession` (Task 5), `practice.segment.cards.*` i18n (Task 4).

- [ ] **Step 1: Add the import + segment type**

In `frontend/src/routes/Practice.tsx`, add the import near the other component imports:

```tsx
import RecallReviewSession from "../components/RecallReviewSession";
```

Change the segment state type (line 103) from:

```tsx
const [segment, setSegment] = useState<"pronunciation" | "gender" | null>(null);
```

to:

```tsx
const [segment, setSegment] = useState<"cards" | "pronunciation" | "gender" | null>(null);
```

- [ ] **Step 2: Add the render branch**

Directly above the `if (segment === "gender") {` branch (line ~200), add:

```tsx
  if (segment === "cards") {
    return (
      <RecallReviewSession onExit={() => setSegment(null)} exitLabel={t("practice.segment.back")} />
    );
  }
```

- [ ] **Step 3: Add the chooser button (first — recall is the canonical review)**

In the segment chooser `<section className="kp-segments">` (lines 216-227), add as the FIRST button:

```tsx
          <button className="kp-segment" onClick={() => setSegment("cards")}>
            <span className="kp-segment__title">{t("practice.segment.cards.title")}</span>
            <span className="kp-segment__dek">{t("practice.segment.cards.dek")}</span>
            <span className="kp-segment__arrow k-serif">→</span>
          </button>
```

- [ ] **Step 4: Full verification**

From `frontend/`:
`npm run typecheck` → clean
`npx vitest run` → all pass (new + existing)
`npm run i18n:check` → clean
`npm run build` → succeeds

From `backend/` (Postgres up):
`uv run pytest tests/test_srs_recall.py -v` → pass
`uv run ruff check src tests && uv run ruff format --check src tests` → clean

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/Practice.tsx
git commit -m "feat(recall): add Fichas as the first mode of the /review hub"
```

---

## Self-Review notes (addressed)

- **`ease` addition:** the approved spec listed only `CardOut.gender`; honest per-card projection for REVIEWING cards needs `ease` (backend `schedule_next_review` multiplies by it), so Task 1 adds `ease` too. Minor, additive, same shape as `gender`.
- **`humanizeNextReview` unused:** it only bucketizes by day (`delta <= 1 → dueNow`), so it can't render "~10 min" vs "~1 h". Task 3 ships `formatInterval` with dedicated `recall.interval.*` keys instead.
- **Spec coverage:** third segment (Task 6), RecallReviewSession (Task 5), srsProjection (Task 3), reviewCard elapsed_seconds = Bug 2 (Task 2), CardOut.gender + oracle gate (Task 1), TTS listen (Task 5), CSS port (Task 4), i18n 6-locale parity (Task 4). Out-of-scope items (source line, back-audio, chips) are not implemented, as specified.
