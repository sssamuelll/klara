# Slice 3 PR-C.1 — Gender suffix-rule render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the optional `rule` (suffix-rule note) already returned by `POST /stories/{id}/gender/attempts` as a small pedagogical line in the gender-cloze verdict, in all 6 locales.

**Architecture:** Pure frontend. The backend (`GenderAttemptOut.rule`, shipped in PR-C #74) returns a showable suffix rule only in Case A (agreement) or Case C (`is_exception`), always alongside a verified `correct_gender`. The frontend models the `rule` type, captures it in the gender-cloze result state, selects one of three copy variants (hard / tendency / exception), and renders it as a `qcard__rule` note inside the existing verdict block. The §6-NULL rule (no note when grading failed) falls out for free: the `.catch` path leaves `rule = null`.

**Tech Stack:** React 18 + TypeScript + Vite, react-i18next (6 locales, `es` source of truth). No unit-test runner — verification gates are `npm run typecheck`, `npm run i18n:check`, `npm run build`.

---

## File Structure

- `frontend/src/api/types.ts` — add `GenderRule` interface; add `rule?: GenderRule | null` to `GenderAttemptOut`.
- `frontend/src/components/StoryFinish.tsx` — import `GenderRule`; widen `GenderClozeQuestion` result state to carry `rule`; capture `r.rule` in `.then`; add `genderRuleNote()` helper; render `<p className="qcard__rule">` after the verdict block.
- `frontend/src/locales/{es,en,de,fr,pt,ja}/common.json` — add `story.finish.quiz.genderCloze.rule.{hard,tendency,exception}` (6 files, identical key paths for `i18n:check` parity).
- `frontend/src/styles/finish.css` — add `.qcard__rule` (clone of `.qcard__after`, 15px).

---

## Display contract

The frontend prepends a hyphen to the stored suffix (`-${rule.suffix}` → `-ung`). Variant selection (exhaustive over the showable set the backend emits):

- `rule.is_exception === true` → `exception`  (vars: `suffix`, `ruleGender = rule.rule_gender`, `gender = correctGender`, `lemma`)
- `rule.suffix_class === "hard"` → `hard`  (vars: `suffix`, `gender = rule.rule_gender`)
- otherwise (`tendency`) → `tendency`  (vars: `suffix`, `gender = rule.rule_gender`)

Note shown iff `result.rule != null && result.correctGender != null` — i.e. on both correct and wrong answers, never when grading failed.

---

### Task 1: Model the `rule` type

**Files:**
- Modify: `frontend/src/api/types.ts:235-238`

- [ ] **Step 1: Add the type**

```ts
export interface GenderRule {
  suffix: string;
  suffix_class: "hard" | "tendency";
  rule_gender: "der" | "die" | "das";
  is_exception: boolean;
}

export interface GenderAttemptOut {
  was_correct: boolean;
  correct_gender: string;
  rule?: GenderRule | null;
}
```

- [ ] **Step 2: Typecheck** — `cd frontend && npm run typecheck`. Expected: PASS (additive optional field).

---

### Task 2: Add the 6-locale copy

**Files:**
- Modify: `frontend/src/locales/{es,en,de,fr,pt,ja}/common.json` (the `story.finish.quiz.genderCloze` block, after `failed`)

- [ ] **Step 1:** Add a `rule` object after `"failed"` in each locale's `genderCloze` block (add a comma after `failed`). Strings:

```jsonc
// es
"rule": {
  "hard": "Las palabras en {{suffix}} siempre son {{gender}}.",
  "tendency": "Las palabras en {{suffix}} suelen ser {{gender}}.",
  "exception": "{{suffix}} casi siempre es {{ruleGender}}, pero «{{lemma}}» es {{gender}}."
}
// en
"rule": {
  "hard": "Words ending in {{suffix}} are always {{gender}}.",
  "tendency": "Words ending in {{suffix}} are usually {{gender}}.",
  "exception": "{{suffix}} is almost always {{ruleGender}}, but «{{lemma}}» is {{gender}}."
}
// de
"rule": {
  "hard": "Wörter auf {{suffix}} sind immer {{gender}}.",
  "tendency": "Wörter auf {{suffix}} sind meistens {{gender}}.",
  "exception": "{{suffix}} ist fast immer {{ruleGender}}, aber «{{lemma}}» ist {{gender}}."
}
// fr
"rule": {
  "hard": "Les mots en {{suffix}} sont toujours {{gender}}.",
  "tendency": "Les mots en {{suffix}} sont souvent {{gender}}.",
  "exception": "{{suffix}} est presque toujours {{ruleGender}}, mais «{{lemma}}» est {{gender}}."
}
// pt
"rule": {
  "hard": "As palavras em {{suffix}} são sempre {{gender}}.",
  "tendency": "As palavras em {{suffix}} costumam ser {{gender}}.",
  "exception": "{{suffix}} é quase sempre {{ruleGender}}, mas «{{lemma}}» é {{gender}}."
}
// ja
"rule": {
  "hard": "{{suffix}} で終わる語はすべて {{gender}} です。",
  "tendency": "{{suffix}} で終わる語はたいてい {{gender}} です。",
  "exception": "{{suffix}} はほぼ {{ruleGender}} ですが、「{{lemma}}」は {{gender}} です。"
}
```

- [ ] **Step 2: Parity** — `cd frontend && npm run i18n:check`. Expected: PASS (identical key set in all 6).

---

### Task 3: Render the note

**Files:**
- Modify: `frontend/src/components/StoryFinish.tsx` (import block ~23-35; `GenderClozeQuestion` 896-982)

- [ ] **Step 1: Import the type** — add `GenderRule` to the `import type { ... } from "../api/types"` block (alphabetical, after `GenderClozeQuizItem`).

- [ ] **Step 2: Widen the result state** (lines 905-908):

```tsx
const [result, setResult] = useState<{
  correct: boolean;
  correctGender: string | null;
  rule: GenderRule | null;
} | null>(null);
```

- [ ] **Step 3: Capture `rule`** in `.then`/`.catch` (lines 919 / 925):

```tsx
.then((r) => {
  setResult({ correct: r.was_correct, correctGender: r.correct_gender, rule: r.rule ?? null });
  onAnswered({ correct: r.was_correct, revealed: false });
})
.catch(() => {
  setResult({ correct: false, correctGender: null, rule: null });
  onAnswered({ correct: false, revealed: false });
});
```

- [ ] **Step 4: Add the helper** (top-level, near `GENDER_OPTIONS` line 894):

```tsx
function genderRuleNote(
  rule: GenderRule,
  correctGender: string,
  lemma: string,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
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

- [ ] **Step 5: Render** — inside `<footer className="qcard__foot">`, immediately after the `{result && (<div className="qcard__result">…</div>)}` block:

```tsx
{result?.rule && result.correctGender && (
  <p className="qcard__rule">
    {genderRuleNote(result.rule, result.correctGender, q.lemma, t)}
  </p>
)}
```

- [ ] **Step 6: Typecheck** — `cd frontend && npm run typecheck`. Expected: PASS.

---

### Task 4: Style the note

**Files:**
- Modify: `frontend/src/styles/finish.css` (after `.qcard__after`, ~line 571)

- [ ] **Step 1: Add the rule**

```css
.qcard__rule {
  margin: 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 15px;
  line-height: 1.45;
  color: var(--ink-2);
  max-width: 64ch;
}
```

- [ ] **Step 2: Build** — `cd frontend && npm run build`. Expected: PASS (tsc -b + vite build).

---

### Task 5: Verify + review

- [ ] **Step 1:** `cd frontend && npm run typecheck && npm run i18n:check && npm run build` — all PASS.
- [ ] **Step 2:** Adversarial review — iris-tane (visual hierarchy of the note in the verdict) + spec-compliance against PR-C spec C2/C4/§6 + i18n correctness.
- [ ] **Step 3:** Commit, open PR, merge on green (with explicit user authorization — merge to main = prod deploy).
