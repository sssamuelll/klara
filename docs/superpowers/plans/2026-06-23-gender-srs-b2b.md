# Gender SRS — Slice B2b (frontend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the learner-facing gender review screen — a dedicated der/die/das drill over the user's weak nouns — reachable from a Home tile, reusing the in-story cloze look via an extracted presentational picker.

**Architecture:** Extract the presentational `GenderPicker` (+ a pure `genderRuleNote` helper) from `StoryFinish.GenderClozeQuestion`, with the grading call injected via `onGrade`. A new `routes/GenderReview.tsx` (direct `session → summary`, neutral empty state) fetches `GET /gender/review` and grades via `POST /gender/attempts`. New client methods/types, a Home tile, a `genderReview` i18n group across 6 locales, and CSS for the (currently unstyled) gender buttons.

**Tech Stack:** React + Vite + TypeScript, react-router-dom v6, react-i18next (6 locales, es source). Spec: `docs/superpowers/specs/2026-06-23-gender-srs-b2b-design.md`.

## Global Constraints

- **Branch:** `feat/gender-srs-b2b` (exists; spec committed). Backend (B2a) is shipped on `main`.
- **No unit-test runner is wired for the frontend.** Each task's gate is the relevant command, run from `frontend/`:
  - `npm run typecheck` (tsc) — must pass.
  - `npm run build` (vite) — must pass.
  - `npm run i18n:check` — 6-locale leaf-key parity (es is the source of truth); ANY missing/extra key fails.
- **Behavior-preserving:** the in-story gender cloze (`StoryFinish`) must look and behave exactly as before after the extraction.
- **No backend change** — B2a's contract is fixed (`GET /api/v1/gender/review → GenderReviewItem[]`, `POST /api/v1/gender/attempts → GenderAttemptOut`).
- **No live count badge on the Home tile** (the `GET /gender/review` O(K log K) cost ceiling — never fetch it on Home load).
- **Per-card feedback reuses** `story.finish.quiz.genderCloze.*`; only the screen/tile get new (`genderReview.*`, `home.sec.genderReview.*`) keys.
- **The `key` prop on `GenderPicker` per card MUST be the `vocab_item_id`** so the picker's internal `picked`/`result` state resets between cards.

---

### Task 1: Extract `genderRuleNote` helper + `GenderPicker` component

**Files:**
- Create: `frontend/src/lib/genderRuleNote.ts`
- Create: `frontend/src/components/GenderPicker.tsx`

**Interfaces:**
- Consumes: `GenderAttemptOut`, `GenderRule` from `api/types`; the existing `story.finish.quiz.genderCloze.*` i18n keys.
- Produces:
  - `genderRuleNote(t: TFunction, rule: GenderRule | null, correctGender: string | null, lemma: string): string | null`
  - `GenderPicker(props: { lemma: string; en?: string | null; onGrade: (article: "der"|"die"|"das") => Promise<GenderAttemptOut>; onResult: (correct: boolean) => void; onNext: () => void; isLast: boolean }): JSX.Element` (default export)

- [ ] **Step 1: Create the `genderRuleNote` helper**

`frontend/src/lib/genderRuleNote.ts` (extracted verbatim from the `ruleNote` IIFE at `StoryFinish.tsx:933-949`):

```ts
import type { TFunction } from "i18next";

import type { GenderRule } from "../api/types";

/**
 * The localized suffix-rule note for a graded gender attempt, or null when no
 * showable rule applies. Extracted from StoryFinish so the in-story cloze and
 * the standalone review render the rule identically.
 */
export function genderRuleNote(
  t: TFunction,
  rule: GenderRule | null,
  correctGender: string | null,
  lemma: string,
): string | null {
  if (!rule || !correctGender) return null;
  const suffix = `-${rule.suffix}`;
  if (rule.is_exception) {
    return t("story.finish.quiz.genderCloze.rule.exception", {
      suffix,
      ruleGender: rule.rule_gender,
      gender: correctGender,
      lemma,
    });
  }
  if (rule.suffix_class === "hard") {
    return t("story.finish.quiz.genderCloze.rule.hard", { suffix, gender: rule.rule_gender });
  }
  return t("story.finish.quiz.genderCloze.rule.tendency", { suffix, gender: rule.rule_gender });
}
```

- [ ] **Step 2: Create the `GenderPicker` component**

`frontend/src/components/GenderPicker.tsx` (the presentational core lifted from `GenderClozeQuestion`, with `onGrade` injected and `genderRuleNote` reused):

```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { GenderAttemptOut, GenderRule } from "../api/types";
import { genderRuleNote } from "../lib/genderRuleNote";

const GENDER_OPTIONS = ["der", "die", "das"] as const;

interface GenderPickerProps {
  lemma: string;
  en?: string | null;
  onGrade: (article: "der" | "die" | "das") => Promise<GenderAttemptOut>;
  onResult: (correct: boolean) => void;
  onNext: () => void;
  isLast: boolean;
}

export default function GenderPicker({
  lemma,
  en,
  onGrade,
  onResult,
  onNext,
  isLast,
}: GenderPickerProps): JSX.Element {
  const { t } = useTranslation();
  const [picked, setPicked] = useState<string | null>(null);
  const [result, setResult] = useState<{
    correct: boolean;
    correctGender: string | null;
    rule: GenderRule | null;
  } | null>(null);

  const onPick = (article: "der" | "die" | "das") => {
    if (picked) return;
    setPicked(article);
    void onGrade(article)
      .then((r) => {
        setResult({ correct: r.was_correct, correctGender: r.correct_gender, rule: r.rule ?? null });
        onResult(r.was_correct);
      })
      .catch(() => {
        // Couldn't verify: grade as wrong-unknown but still advance — never strand the user.
        setResult({ correct: false, correctGender: null, rule: null });
        onResult(false);
      });
  };

  const ruleNote = result ? genderRuleNote(t, result.rule, result.correctGender, lemma) : null;

  return (
    <article className="qcard" data-type="gender_cloze">
      <header className="qcard__head">
        <span className="fin-cap">{t("story.finish.quiz.genderCloze.cap")}</span>
      </header>
      <div className="qcard__body">
        <p className="qcard__cloze">
          <span
            className="qcard__blank"
            data-state={picked ? (result?.correct ? "correct" : "revealed") : "empty"}
          >
            {result ? result.correctGender || "—" : "___"}
          </span>{" "}
          <span>{lemma}</span>
        </p>
        {en && <p className="qcard__en">{en}</p>}
        <p className="qcard__hint">{t("story.finish.quiz.genderCloze.prompt")}</p>
      </div>
      <footer className="qcard__foot">
        {!picked && (
          <div className="qcard__actions qcard__gender-opts">
            {GENDER_OPTIONS.map((a) => (
              <button key={a} type="button" className="qcard__gender-btn" onClick={() => onPick(a)}>
                {a}
              </button>
            ))}
          </div>
        )}
        {result && (
          <>
            <div className="qcard__result">
              <span className="qcard__verdict">
                {result.correct ? (
                  <em>{t("story.finish.quiz.genderCloze.correct")}</em>
                ) : result.correctGender ? (
                  t("story.finish.quiz.genderCloze.wrong", { correct: result.correctGender })
                ) : (
                  t("story.finish.quiz.genderCloze.failed")
                )}
              </span>
            </div>
            {ruleNote && <p className="qcard__rule">{ruleNote}</p>}
            <button type="button" className="fin-btn fin-btn--primary qcard__next" onClick={onNext}>
              {isLast ? t("story.finish.quiz.toSummary") : t("story.finish.quiz.next")}{" "}
              <span className="fin-arr">→</span>
            </button>
          </>
        )}
      </footer>
    </article>
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: PASS — the two new files compile. (`GenderPicker` is not yet consumed; that's fine.)

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/lib/genderRuleNote.ts frontend/src/components/GenderPicker.tsx
git commit -m "feat(gender): extract presentational GenderPicker + genderRuleNote helper"
```

---

### Task 2: Refactor `StoryFinish.GenderClozeQuestion` to use `GenderPicker`

Behavior-preserving: the in-story cloze renders and grades exactly as before, now via the shared picker.

**Files:**
- Modify: `frontend/src/components/StoryFinish.tsx` (`GenderClozeQuestion`, lines 896-1006; imports)

**Interfaces:**
- Consumes: `GenderPicker` (Task 1). The `GenderClozeProps` (`{q, story, onAnswered, onNext, isLast}`) and the dispatcher call site (`StoryFinish.tsx:222-230`) are UNCHANGED.

- [ ] **Step 1: Replace the `GenderClozeQuestion` body with a thin wrapper**

In `frontend/src/components/StoryFinish.tsx`, replace the entire `GenderClozeQuestion` function and the `GENDER_OPTIONS` const (lines 896-1006) with:

```tsx
function GenderClozeQuestion({
  q,
  story,
  onAnswered,
  onNext,
  isLast,
}: GenderClozeProps): JSX.Element {
  return (
    <GenderPicker
      lemma={q.lemma}
      en={q.en}
      onGrade={(article) =>
        api.recordGenderAttempt(story.id, { vocab_item_id: q.vocab_item_id, picked_article: article })
      }
      onResult={(correct) => onAnswered({ correct, revealed: false })}
      onNext={onNext}
      isLast={isLast}
    />
  );
}
```

Add the import (with the other component imports near the top of `StoryFinish.tsx`):

```tsx
import GenderPicker from "./GenderPicker";
```

The `GenderClozeProps` interface (lines 888-894) stays. The dispatcher (`StoryFinish.tsx:222-230`) is unchanged.

- [ ] **Step 2: Remove now-unused imports/symbols from `StoryFinish.tsx`**

The extracted body no longer uses, *within `GenderClozeQuestion`*: the `GenderRule` type and the local `ruleNote` logic. `GENDER_OPTIONS` is deleted (moved into `GenderPicker`). Run typecheck (Step 3) and the build; if `GenderRule` (or any other symbol) is now unused in `StoryFinish.tsx`, remove it from the imports. Do NOT remove `useState`/`useTranslation`/`api` — they are used by the other quiz components in this file.

- [ ] **Step 3: Typecheck + build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS. The in-story cloze now renders via `GenderPicker` with identical markup, strings, and grading (the `onGrade` binds `recordGenderAttempt(story.id, …)` exactly as before; `onResult` calls `onAnswered({correct, revealed:false})`).

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/components/StoryFinish.tsx
git commit -m "refactor(gender): StoryFinish gender cloze delegates to GenderPicker"
```

---

### Task 3: i18n — `genderReview` group + Home tile keys, 6 locales

Add the new keys (drafted via the solace-wren microcopy skill) to all six locale files. es is the source; the other five must have the identical leaf-key set or `i18n:check` fails.

**Files:**
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`

**Interfaces:**
- Produces the i18n keys consumed by Tasks 5 (screen) and the Home tile: `genderReview.{title,progress,empty,summary,again,home}` (top-level) and `home.sec.genderReview.{title,dek}` (nested under the existing `home.sec`).

- [ ] **Step 1: Add the two blocks to each locale**

In each `common.json`, add a top-level `"genderReview"` object AND a `"genderReview"` object nested inside the existing `home.sec` object (next to `newStory`/`review`/`chat`). Use these exact strings:

**`es/common.json`** — top-level:
```json
"genderReview": {
  "title": "Repaso de género",
  "progress": "{{done}} / {{total}}",
  "empty": "Aquí vuelven los géneros que fallas. Por ahora, ninguno.",
  "summary": "{{correct}} de {{total}} correctos.",
  "again": "Otra ronda",
  "home": "Volver al inicio"
}
```
…and inside `home.sec`: `"genderReview": { "title": "Repasar géneros", "dek": "Repasa los der, die, das que fallas." }`

**`en/common.json`** — top-level:
```json
"genderReview": {
  "title": "Gender review",
  "progress": "{{done}} / {{total}}",
  "empty": "Genders you miss come back here. None for now.",
  "summary": "{{correct}} of {{total}} right.",
  "again": "Another round",
  "home": "Back home"
}
```
…and inside `home.sec`: `"genderReview": { "title": "Review genders", "dek": "Revisit the der, die, das you miss." }`

**`de/common.json`** — top-level:
```json
"genderReview": {
  "title": "Genus-Wiederholung",
  "progress": "{{done}} / {{total}}",
  "empty": "Hier kommen die Genera zurück, die du verfehlst. Im Moment keine.",
  "summary": "{{correct}} von {{total}} richtig.",
  "again": "Noch eine Runde",
  "home": "Zurück zum Start"
}
```
…and inside `home.sec`: `"genderReview": { "title": "Genus üben", "dek": "Wiederhole die der, die, das, die du verfehlst." }`

**`fr/common.json`** — top-level:
```json
"genderReview": {
  "title": "Révision du genre",
  "progress": "{{done}} / {{total}}",
  "empty": "Les genres que tu rates reviennent ici. Aucun pour l'instant.",
  "summary": "{{correct}} sur {{total}} corrects.",
  "again": "Encore un tour",
  "home": "Retour à l'accueil"
}
```
…and inside `home.sec`: `"genderReview": { "title": "Réviser les genres", "dek": "Revois les der, die, das que tu rates." }`

**`ja/common.json`** — top-level:
```json
"genderReview": {
  "title": "性の復習",
  "progress": "{{done}} / {{total}}",
  "empty": "間違えた性はここに戻ってきます。今はありません。",
  "summary": "{{total}}問中{{correct}}問正解。",
  "again": "もう一度",
  "home": "ホームに戻る"
}
```
…and inside `home.sec`: `"genderReview": { "title": "性の復習", "dek": "間違える der, die, das を復習。" }`

**`pt/common.json`** — top-level:
```json
"genderReview": {
  "title": "Revisão de gênero",
  "progress": "{{done}} / {{total}}",
  "empty": "Os gêneros que você erra voltam aqui. Por enquanto, nenhum.",
  "summary": "{{correct}} de {{total}} corretos.",
  "again": "Outra rodada",
  "home": "Voltar ao início"
}
```
…and inside `home.sec`: `"genderReview": { "title": "Revisar gêneros", "dek": "Revise os der, die, das que você erra." }`

Place the top-level `genderReview` object consistently across files (e.g. right after the `story` block, or wherever keeps the diff clean). The exact position does not matter to `i18n:check` — only that the leaf-key SET is identical across all six.

- [ ] **Step 2: Verify parity + typecheck**

Run: `cd frontend && npm run i18n:check && npm run typecheck`
Expected: PASS — `i18n:check` reports no missing/extra keys (all six locales have the identical 8 new leaf keys: 6 under `genderReview`, 2 under `home.sec.genderReview`). If `i18n:check` lists a locale missing a key, you added the blocks unevenly — fix so all six match.

- [ ] **Step 3: Commit**

```bash
cd .. && git add frontend/src/locales
git commit -m "i18n(gender): genderReview screen + Home tile copy across 6 locales"
```

---

### Task 4: Client method + type

**Files:**
- Modify: `frontend/src/api/types.ts` (add `GenderReviewItem`)
- Modify: `frontend/src/api/client.ts` (add `genderReview` + `gradeGender`; extend the type import)

**Interfaces:**
- Consumes: existing `GenderAttemptIn`, `GenderAttemptOut` types (already in `types.ts`).
- Produces: `GenderReviewItem`; `api.genderReview(limit?) => Promise<GenderReviewItem[]>`; `api.gradeGender(payload: GenderAttemptIn) => Promise<GenderAttemptOut>`.

- [ ] **Step 1: Add the `GenderReviewItem` type**

In `frontend/src/api/types.ts`, next to the existing gender types (after `GenderClozeQuizItem`, ~line 201):

```ts
export interface GenderReviewItem {
  vocab_item_id: string;
  lemma: string;
  en?: string | null;
}
```

- [ ] **Step 2: Add the two client methods**

In `frontend/src/api/client.ts`, add `GenderReviewItem` to the `import type { … } from "./types"` block, then add these two methods to the `api` object (e.g. next to `recordGenderAttempt` / `getStoryL1Notes`):

```ts
  genderReview: (limit = 20) => request<GenderReviewItem[]>(`/gender/review?limit=${limit}`),

  gradeGender: (payload: GenderAttemptIn) =>
    request<GenderAttemptOut>("/gender/attempts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
```

(`GenderAttemptIn`/`GenderAttemptOut` are already imported in `client.ts` for `recordGenderAttempt`.)

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat(gender): genderReview + gradeGender client methods + GenderReviewItem type"
```

---

### Task 5: `GenderReview` screen + `/gender` route + Home tile

**Files:**
- Create: `frontend/src/routes/GenderReview.tsx`
- Modify: `frontend/src/App.tsx` (add the `/gender` route + import)
- Modify: `frontend/src/routes/Home.tsx` (add the gender tile, item 04)

**Interfaces:**
- Consumes: `GenderPicker` (Task 1), `api.genderReview`/`api.gradeGender` + `GenderReviewItem` (Task 4), the `genderReview.*` + `home.sec.genderReview.*` i18n keys (Task 3).

- [ ] **Step 1: Create the screen**

`frontend/src/routes/GenderReview.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { GenderReviewItem } from "../api/types";
import GenderPicker from "../components/GenderPicker";

type Phase = "loading" | "failed" | "empty" | "session" | "summary";

export default function GenderReview(): JSX.Element {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [items, setItems] = useState<GenderReviewItem[]>([]);
  const [phase, setPhase] = useState<Phase>("loading");
  const [idx, setIdx] = useState(0);
  const [correct, setCorrect] = useState(0);

  // Initial fetch (alive-guarded, mirrors Practice.tsx).
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

  // "Another round" — refetch (now-mastered nouns are gone). User action; no alive guard.
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

  const goHome = () => navigate("/");

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
        <p className="gr__empty">{t("genderReview.empty")}</p>
        <button type="button" className="fin-btn fin-btn--primary" onClick={goHome}>
          {t("genderReview.home")}
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
          <button type="button" className="fin-btn" onClick={goHome}>
            {t("genderReview.home")}
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

(The `key={item.vocab_item_id}` on `GenderPicker` resets its internal `picked`/`result` per card — essential.)

- [ ] **Step 2: Add the `/gender` route in `App.tsx`**

In `frontend/src/App.tsx`, import the screen (with the other route imports) and add a protected route after the `/review` route (mirror its shape):

```tsx
import GenderReview from "./routes/GenderReview";
```
```tsx
          <Route
            path="/gender"
            element={
              <ProtectedRoute>
                <GenderReview />
              </ProtectedRoute>
            }
          />
```

- [ ] **Step 3: Add the Home tile (item 04)**

In `frontend/src/routes/Home.tsx`, add a fourth `home__sec-item` button after the `/chat` button (after line 197, inside `home__secondary`):

```tsx
        <button className="home__sec-item" onClick={() => navigate("/gender")}>
          <span className="k-mono home__sec-num">04</span>
          <span className="home__sec-body">
            <span className="home__sec-title">{t("home.sec.genderReview.title")}</span>
            <span className="home__sec-dek">{t("home.sec.genderReview.dek")}</span>
          </span>
          <span className="home__sec-arrow k-serif">→</span>
        </button>
```

(No live count fetch — the tile is static, unlike the `/review` item's `dueCount`.)

- [ ] **Step 4: Typecheck + build + i18n parity**

Run: `cd frontend && npm run typecheck && npm run build && npm run i18n:check`
Expected: PASS. Manually confirm (dev server): navigating to `/gender` fetches the queue; an empty queue shows the neutral empty state + home button; a non-empty queue shows cards one at a time with a `N / total` header, grades each pick (verdict + rule), advances, and ends on a summary with "Otra ronda" (refetch) / "Volver al inicio".

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/routes/GenderReview.tsx frontend/src/App.tsx frontend/src/routes/Home.tsx
git commit -m "feat(gender): /gender review screen + route + Home tile"
```

---

### Task 6: CSS — gender buttons + review screen shell

**Files:**
- Modify: `frontend/src/styles/finish.css` (the `qcard__gender-btn` / `qcard__gender-opts` rules — shared by the in-story cloze AND the review screen)
- Create: `frontend/src/styles/gender-review.css` (the screen shell)
- Modify: `frontend/src/routes/GenderReview.tsx` (import the screen stylesheet)

**Interfaces:**
- Consumes: the existing finish.css design tokens / CSS custom properties.

- [ ] **Step 1: Style the gender option buttons in `finish.css`**

`qcard__gender-opts` / `qcard__gender-btn` are currently unstyled (they inherit generic `qcard__actions` layout). Add, near the existing `qcard__rule` rule (finish.css ~line 572), a three-up button layout that harmonizes with the existing `fin-btn`/`qcard` aesthetic. Read the surrounding finish.css first for the design tokens (CSS custom properties for color/spacing/radius/border) and reuse them; the following is the intended structure — substitute the file's actual `var(--…)` tokens:

```css
.qcard__gender-opts {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
}

.qcard__gender-btn {
  flex: 1 1 0;
  padding: 0.75rem 0.5rem;
  font: inherit;
  font-variant: small-caps;
  cursor: pointer;
  background: var(--surface, #fff);
  border: 1px solid var(--rule, #d8d2c4);
  border-radius: var(--radius, 8px);
  color: inherit;
  transition: border-color 0.12s ease, background 0.12s ease;
}

.qcard__gender-btn:hover {
  border-color: var(--ink, #1a1a1a);
}

.qcard__gender-btn:active {
  background: var(--surface-2, #f3efe6);
}
```

- [ ] **Step 2: Style the review screen shell**

Create `frontend/src/styles/gender-review.css`:

```css
.gr {
  max-width: 36rem;
  margin: 0 auto;
  padding: 2rem 1.25rem;
}

.gr__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.gr__title {
  font: inherit;
  font-size: 1.25rem;
  margin: 0;
}

.gr__progress {
  opacity: 0.6;
}

.gr__empty,
.gr__summary {
  margin: 1.5rem 0;
  line-height: 1.5;
}

.gr__actions {
  display: flex;
  gap: 0.75rem;
}

.gr__loading {
  padding: 2rem 0;
  opacity: 0.5;
}
```

Then import it at the top of `frontend/src/routes/GenderReview.tsx`:

```tsx
import "../styles/gender-review.css";
```

- [ ] **Step 3: Build + visual check**

Run: `cd frontend && npm run build`
Expected: PASS. Manually confirm the three der/die/das buttons render as a clear three-up choice (in BOTH the in-story cloze and the `/gender` screen) and the review screen reads cleanly (title + progress header, neutral empty state, summary). Harmonize the placeholder `var(--…)` tokens with the actual finish.css custom properties (substitute the real names) so the buttons match the surrounding palette.

- [ ] **Step 4: Commit**

```bash
cd .. && git add frontend/src/styles/finish.css frontend/src/styles/gender-review.css frontend/src/routes/GenderReview.tsx
git commit -m "style(gender): style der/die/das buttons + gender review screen shell"
```

---

## Definition of done (before opening the PR)

- [ ] `cd frontend && npm run typecheck && npm run build && npm run i18n:check` — all green.
- [ ] The in-story gender cloze still looks and grades exactly as before (behavior-preserving extraction).
- [ ] `/gender` works end to end: fetch → cards (with `key`-reset per card) → grade → summary → "Otra ronda" refetch / "Volver al inicio"; empty queue → neutral state.
- [ ] The Home tile navigates to `/gender` with NO live count fetch.
- [ ] No backend change; no new dependency.
- [ ] PR targets `main` from `feat/gender-srs-b2b`; the spec + plan commits + the six task commits are present.

## Self-review notes (spec coverage)

- Extract presentational `GenderPicker` + `genderRuleNote` (onGrade injected) → Task 1. ✓
- StoryFinish thin wrapper (behavior-preserving) → Task 2. ✓
- i18n `genderReview` + Home tile, 6 locales (solace-wren copy) → Task 3. ✓
- Client `genderReview`/`gradeGender` + `GenderReviewItem` → Task 4. ✓
- `GenderReview.tsx` (direct session→summary, neutral empty, per-card `key` reset) + `/gender` route + Home tile (no badge) → Task 5. ✓
- CSS for the unstyled gender buttons + screen shell → Task 6. ✓
- Verification = typecheck/build/i18n:check (no unit runner) → every task gate. ✓
