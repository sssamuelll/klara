# Gender SRS — Slice B3 (frontend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface gender review inside the Practice (`/review`) screen as a second segment the learner chooses at setup, reusing the existing gender flow — frontend-only, pronunciation session untouched.

**Architecture:** Extract the gender session+summary from `routes/GenderReview.tsx` into a reusable `components/GenderReviewSession.tsx` (the `/gender` route becomes a thin wrapper). Add a `segment` chooser to `Practice.tsx`: two early-return branches at the top of render (`segment === "gender"` → `GenderReviewSession`; `segment === null` → a chooser) leave the existing pronunciation render textually untouched (reached only when `segment === "pronunciation"`). The gender segment lazily fetches `/gender/review` on entry (no live count). No backend change.

**Tech Stack:** React + Vite + TypeScript, react-router-dom v6, react-i18next (6 locales, es source).
Spec: `docs/superpowers/specs/2026-06-23-gender-srs-b3-design.md`.

## Global Constraints

- **Branch:** `feat/gender-srs-b3`. **Execute on a `main` that already includes #88** (the GenderReview polish: the empty/failed split + the `genderReview.failed` key). Before starting Task 1, rebase: `git fetch origin && git rebase origin/main` (resolve any GenderReview.tsx / locale / gender-css overlap in #88's favor, then layer B3 on top). This plan's Task 1 code already reflects the post-#88 GenderReview.tsx (the empty/failed conditional string).
- **No unit-test runner.** Gates from `frontend/`: `npm run typecheck`, `npm run build`, `npm run i18n:check` (6-locale leaf-key parity, es source).
- **Frontend-only.** No backend change; `/practice/queue` is NOT modified; no new endpoint. Reuses `api.genderReview()` / `api.gradeGender()` (B2a) + `GenderPicker` (B2b).
- **Pronunciation flow untouched.** The existing `Practice.tsx` setup/session/summary branches, `useSentencePractice`, `SentenceView`, `tallySummary`, and the `/srs/cards/review-batch` submit are NOT edited — they are only preceded by two new early-return branches.
- **No live gender count on load** (the O(K log K) cost ceiling). The "Género" choice is static; `/gender/review` is fetched only when the gender segment mounts.
- **Per-card feedback reuses** `genderReview.*` / `story.finish.quiz.genderCloze.*`; only the chooser gets new `practice.segment.*` keys.
- **`GenderPicker` per-card `key={vocab_item_id}`** must be preserved in the extracted session (resets picker state per card).

---

### Task 1: Extract `GenderReviewSession` from `GenderReview.tsx`

**Files:**
- Create: `frontend/src/components/GenderReviewSession.tsx`
- Modify: `frontend/src/routes/GenderReview.tsx` (becomes a thin wrapper)

**Interfaces:**
- Consumes: `api.genderReview` / `api.gradeGender` + `GenderReviewItem` (B2a); `GenderPicker` (B2b); the `genderReview.*` i18n keys (incl. `genderReview.failed` from #88).
- Produces: `GenderReviewSession(props: { onExit: () => void; exitLabel: string }): JSX.Element` (default export) — owns items/phase/idx/correct, self-fetches, runs the GenderPicker loop, renders loading/failed/empty/session/summary; "otra vez" (refetch) is internal; the failed/empty/summary exit button calls `onExit` with text `exitLabel`.

- [ ] **Step 1: Create `GenderReviewSession.tsx`**

Move the session machinery out of `GenderReview.tsx` into `frontend/src/components/GenderReviewSession.tsx` (this reflects the post-#88 GenderReview, where empty/failed pick the string by phase):

```tsx
import "../styles/gender-review.css";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { GenderReviewItem } from "../api/types";
import GenderPicker from "./GenderPicker";

type Phase = "loading" | "failed" | "empty" | "session" | "summary";

interface GenderReviewSessionProps {
  onExit: () => void;
  exitLabel: string;
}

export default function GenderReviewSession({
  onExit,
  exitLabel,
}: GenderReviewSessionProps): JSX.Element {
  const { t } = useTranslation();

  const [items, setItems] = useState<GenderReviewItem[]>([]);
  const [phase, setPhase] = useState<Phase>("loading");
  const [idx, setIdx] = useState(0);
  const [correct, setCorrect] = useState(0);

  // Initial fetch (alive-guarded).
  useEffect(() => {
    let alive = true;
    api
      .genderReview()
      .then((rows) => {
        if (!alive) return;
        setItems(rows);
        setPhase(rows.length === 0 ? "empty" : "session");
      })
      .catch(() => {
        if (alive) setPhase("failed");
      });
    return () => {
      alive = false;
    };
  }, []);

  // "Another round" — refetch. User action; no alive guard.
  const restart = () => {
    setPhase("loading");
    setIdx(0);
    setCorrect(0);
    api
      .genderReview()
      .then((rows) => {
        setItems(rows);
        setPhase(rows.length === 0 ? "empty" : "session");
      })
      .catch(() => setPhase("failed"));
  };

  if (phase === "loading") {
    return (
      <main className="gr">
        <p className="gr__loading">{t("genderReview.title")}</p>
      </main>
    );
  }

  if (phase === "failed" || phase === "empty") {
    return (
      <main className="gr">
        <h1 className="gr__title">{t("genderReview.title")}</h1>
        <p className="gr__empty">
          {t(phase === "failed" ? "genderReview.failed" : "genderReview.empty")}
        </p>
        <button type="button" className="fin-btn fin-btn--primary" onClick={onExit}>
          {exitLabel}
        </button>
      </main>
    );
  }

  if (phase === "summary") {
    return (
      <main className="gr">
        <h1 className="gr__title">{t("genderReview.title")}</h1>
        <p className="gr__summary">{t("genderReview.summary", { correct, total: items.length })}</p>
        <div className="gr__actions">
          <button type="button" className="fin-btn fin-btn--primary" onClick={restart}>
            {t("genderReview.again")}
          </button>
          <button type="button" className="fin-btn" onClick={onExit}>
            {exitLabel}
          </button>
        </div>
      </main>
    );
  }

  // phase === "session"
  const item = items[idx];
  return (
    <main className="gr">
      <header className="gr__head">
        <h1 className="gr__title">{t("genderReview.title")}</h1>
        <span className="gr__progress k-mono">
          {t("genderReview.progress", { done: idx + 1, total: items.length })}
        </span>
      </header>
      <GenderPicker
        key={item.vocab_item_id}
        lemma={item.lemma}
        en={item.en}
        onGrade={(article) =>
          api.gradeGender({ vocab_item_id: item.vocab_item_id, picked_article: article })
        }
        onResult={(c) => {
          if (c) setCorrect((n) => n + 1);
        }}
        onNext={() => {
          if (idx + 1 < items.length) setIdx(idx + 1);
          else setPhase("summary");
        }}
        isLast={idx + 1 === items.length}
      />
    </main>
  );
}
```

- [ ] **Step 2: Reduce `routes/GenderReview.tsx` to a thin wrapper**

Replace the whole of `frontend/src/routes/GenderReview.tsx` with:

```tsx
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import GenderReviewSession from "../components/GenderReviewSession";

export default function GenderReview(): JSX.Element {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return <GenderReviewSession onExit={() => navigate("/")} exitLabel={t("genderReview.home")} />;
}
```

(The `../styles/gender-review.css` import now lives in `GenderReviewSession.tsx`; the `/gender` route's behavior is unchanged — loads, iterates, summary, "otra vez"/"Volver al inicio".)

- [ ] **Step 3: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS. `/gender` renders identically (the session moved into the reused component; the route just supplies `onExit`/`exitLabel`).

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/components/GenderReviewSession.tsx frontend/src/routes/GenderReview.tsx
git commit -m "refactor(gender): extract reusable GenderReviewSession; /gender route wraps it"
```

---

### Task 2: i18n — `practice.segment.*` chooser keys, 6 locales

**Files:**
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`

**Interfaces:**
- Produces the keys Task 3 consumes: `practice.segment.{title, back}`, `practice.segment.pron.{title, dek}`, `practice.segment.gender.{title, dek}` (6 leaf keys), nested inside the existing top-level `practice` object.

- [ ] **Step 1: Add the `segment` block to each locale's `practice` object**

Inside the existing `"practice"` object in each `common.json`, add a `"segment"` child with these exact values (es is source; all 6 must have the identical 6 leaf keys):

**es:** `"segment": { "title": "¿Qué repasas?", "pron": { "title": "Pronunciar", "dek": "Las frases que se te traban, otra vez en voz alta." }, "gender": { "title": "Géneros", "dek": "Los der, die, das que fallas." }, "back": "Elegir otro" }`

**en:** `"segment": { "title": "What do you review?", "pron": { "title": "Speaking", "dek": "The sentences that trip you up, out loud again." }, "gender": { "title": "Genders", "dek": "The der, die, das you miss." }, "back": "Pick another" }`

**de:** `"segment": { "title": "Was wiederholst du?", "pron": { "title": "Sprechen", "dek": "Die Sätze, die dir schwerfallen, noch einmal laut." }, "gender": { "title": "Genus", "dek": "Die der, die, das, die du verfehlst." }, "back": "Anderes wählen" }`

**fr:** `"segment": { "title": "Que révises-tu ?", "pron": { "title": "Prononcer", "dek": "Les phrases qui coincent, à voix haute encore." }, "gender": { "title": "Genres", "dek": "Les der, die, das que tu rates." }, "back": "Choisir l'autre" }`

**ja:** `"segment": { "title": "何を復習する？", "pron": { "title": "発音", "dek": "つまずいた文を、もう一度声に出して。" }, "gender": { "title": "性", "dek": "間違える der, die, das。" }, "back": "別のを選ぶ" }`

**pt:** `"segment": { "title": "O que revês?", "pron": { "title": "Pronunciar", "dek": "As frases que te travam, outra vez em voz alta." }, "gender": { "title": "Géneros", "dek": "Os der, die, das que erras." }, "back": "Escolher outro" }`

Mind JSON comma discipline (the `practice` object already has siblings like `setup`, `loading`, `summary` — add `segment` alongside, no trailing commas).

- [ ] **Step 2: Verify parity + typecheck**

Run: `cd frontend && npm run i18n:check && npm run typecheck`
Expected: PASS — all 6 locales gain the identical 6 new leaf keys.

- [ ] **Step 3: Commit**

```bash
cd .. && git add frontend/src/locales
git commit -m "i18n(practice): segment chooser (Pronunciar | Género) across 6 locales"
```

---

### Task 3: Practice segment chooser

**Files:**
- Modify: `frontend/src/routes/Practice.tsx`

**Interfaces:**
- Consumes: `GenderReviewSession` (Task 1), the `practice.segment.*` keys (Task 2).
- Produces: no new exports; `/review` now opens with a segment chooser.

- [ ] **Step 1: Add the `segment` state + the two early-return branches**

In `frontend/src/routes/Practice.tsx`:

1. Add the import (with the other component imports):
```tsx
import GenderReviewSession from "../components/GenderReviewSession";
```
2. Add state near the existing `const [phase, setPhase] = useState<Phase>("setup");`:
```tsx
const [segment, setSegment] = useState<"pronunciation" | "gender" | null>(null);
```
3. Insert these TWO branches at the very TOP of the render (immediately after the existing hooks/derivations and BEFORE the existing `if (phase === "setup" && (queue === null || loadFailed || total === 0))` block):

```tsx
  // ---- SEGMENT: gender (reuses the standalone /gender session) -----------
  if (segment === "gender") {
    return (
      <GenderReviewSession onExit={() => setSegment(null)} exitLabel={t("practice.segment.back")} />
    );
  }

  // ---- SEGMENT CHOOSER ---------------------------------------------------
  if (segment === null) {
    return (
      <main className="k-page kp-setup">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("common.back")}
        </button>
        <header className="kp-setup__head">
          <h1 className="kp-setup__title">{t("practice.segment.title")}</h1>
        </header>
        <section className="kp-segments">
          <button className="kp-segment" onClick={() => setSegment("pronunciation")}>
            <span className="kp-segment__title">{t("practice.segment.pron.title")}</span>
            <span className="kp-segment__dek">{t("practice.segment.pron.dek")}</span>
            <span className="kp-segment__arrow k-serif">→</span>
          </button>
          <button className="kp-segment" onClick={() => setSegment("gender")}>
            <span className="kp-segment__title">{t("practice.segment.gender.title")}</span>
            <span className="kp-segment__dek">{t("practice.segment.gender.dek")}</span>
            <span className="kp-segment__arrow k-serif">→</span>
          </button>
        </section>
      </main>
    );
  }

  // segment === "pronunciation" → the existing pronunciation flow (below, unchanged)
```

Everything below (the `if (phase === "setup" && …)` guard, `if (queue === null) return null`, the setup render, the summary render, and the session render) is **left exactly as-is** — it now runs only when `segment === "pronunciation"`. Do NOT edit those branches (their `navigate("/")` back-buttons keep their current behavior; the asymmetry — pronunciation back→home, gender back→chooser — is accepted to keep the pronunciation flow untouched).

(Note: the pronunciation queue still fetches on mount as today; the chooser does not show a pron count, and the gender choice triggers no fetch until `GenderReviewSession` mounts — honoring the cost ceiling.)

- [ ] **Step 2: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS. `/review` opens on the chooser; "Pronunciar" → the unchanged pronunciation setup/session/summary; "Géneros" → `GenderReviewSession` (lazy fetch), whose exit returns to the chooser.

- [ ] **Step 3: Commit**

```bash
cd .. && git add frontend/src/routes/Practice.tsx
git commit -m "feat(practice): segment chooser — Pronunciar | Géneros (gender reuses GenderReviewSession)"
```

---

### Task 4: CSS — the segment chooser

**Files:**
- Modify: `frontend/src/styles/` — the stylesheet that defines the `kp-setup` / `kp-*` Practice classes (find it: grep `kp-setup` under `frontend/src/styles/`; likely `practice.css` or similar). Add the `.kp-segments` / `.kp-segment*` rules there.

**Interfaces:** Consumes the existing Practice `kp-*` design tokens/classes.

- [ ] **Step 1: Style the chooser**

Find the stylesheet with the existing `.kp-setup` rules (`grep -rl "kp-setup" frontend/src/styles/`). Add a two-card chooser that harmonizes with the existing `kp-setup`/`kp-source`/`kp-chip` aesthetic and the design tokens (read the file for the real `var(--…)` tokens — paper/ink/rule/radius/spacing — and reuse them; the block below shows intended structure):

```css
.kp-segments {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin: 1.5rem 0;
}

.kp-segment {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-areas: "title arrow" "dek arrow";
  align-items: center;
  gap: 0.15rem 1rem;
  width: 100%;
  text-align: left;
  padding: 1rem 1.25rem;
  background: var(--paper);
  border: 1px solid var(--ink-3);
  border-radius: var(--r-md);
  color: inherit;
  cursor: pointer;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease;
}

.kp-segment:hover {
  border-color: var(--ink);
}

.kp-segment__title {
  grid-area: title;
  font-family: var(--font-serif);
  font-size: 1.125rem;
}

.kp-segment__dek {
  grid-area: dek;
  color: var(--ink-2);
  font-size: 0.9rem;
}

.kp-segment__arrow {
  grid-area: arrow;
  opacity: 0.6;
}
```

Substitute the real token names found in the file. Match the existing border/hover idiom (the gender buttons from #88 use `--ink-3` resting border + `--ink` hover — mirror that for consistency).

- [ ] **Step 2: Build + visual check**

Run: `cd frontend && npm run build`
Expected: PASS. Manually confirm the two choices read as clear, tappable cards consistent with the Practice setup aesthetic.

- [ ] **Step 3: Commit**

```bash
cd .. && git add frontend/src/styles/
git commit -m "style(practice): segment chooser cards"
```

---

## Definition of done (before opening the PR)

- [ ] `cd frontend && npm run typecheck && npm run build && npm run i18n:check` — all green.
- [ ] `/review` opens on the chooser; "Pronunciar" runs the **unchanged** pronunciation session; "Géneros" runs `GenderReviewSession` (lazy `/gender/review` fetch), whose exit returns to the chooser.
- [ ] `/gender` standalone still works (Home tile), sharing `GenderReviewSession`.
- [ ] No backend change; no live gender count on load; pronunciation flow untouched.
- [ ] Branch rebased on post-#88 main; PR targets `main` from `feat/gender-srs-b3`.

## Self-review notes (spec coverage)

- Extract reusable `GenderReviewSession`; `/gender` wraps it → Task 1. ✓
- `practice.segment.*` i18n, 6 locales (solace-wren copy) → Task 2. ✓
- Practice chooser (segment state + two early-return branches; pronunciation untouched; gender lazy, no count) → Task 3. ✓
- Chooser CSS → Task 4. ✓
- Frontend-only, no `/practice/queue` change, no fake key → honored across all tasks. ✓
- #88 rebase dependency → Global Constraints. ✓
