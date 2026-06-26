# Final Fix Report — Pronunciation Diagnose (#42)

Two findings from the final review of the `feat/pronunciation-diagnose` branch, both in the frontend integration seam.

---

## Finding 1 (MERGE-BLOCKER): skeleton never resolves on empty-tip path

### Root cause
`fetchAndStoreDiagnosis` had two early-exit paths (empty `resp.tip` and the `catch {}`) that returned without writing any entry to `diagnosisBySentence`. `SentenceView` inferred loading from `!diagnosis`, so once the request completed with an empty tip or an error, `diagnosisBySentence[idx]` stayed `undefined` and the skeleton persisted forever.

### Files changed

**`frontend/src/lib/pronunciation.ts`**
- `worstBadWord`: added `w.phonemes.length === 0` guard so words with no phonemes are skipped. This prevents posting `phonemes:[]` to `/diagnose`, which returns a 422 and was itself a trigger for the stuck-skeleton scenario.

**`frontend/src/lib/useSentencePractice.ts`**
- Added state `const [diagnosingIndex, setDiagnosingIndex] = useState<number | null>(null);`
- Rewrote `fetchAndStoreDiagnosis`: (a) returns early (no loading) when `worstBadWord` is null, (b) sets `diagnosingIndex` before the await, (c) ALWAYS writes a terminal entry `{ word: worst.word, tip }` with `tip = resp.tip ?? ""` on success and `tip = ""` on catch, (d) clears `diagnosingIndex` with a functional updater that guards against superseded sentences.
- Added `setDiagnosingIndex(null)` to the `reset` path.
- Added `diagnosing: diagnosingIndex === currentIndex` to the returned object.
- Added `diagnosing: boolean;` to the `UseSentencePractice` interface.

**`frontend/src/components/SentenceView.tsx`**
- Added `diagnosing: boolean;` to the `Props` interface.
- Destructured `diagnosing` from props (next to `diagnosis`).
- Deleted the local `diagnosing` memo that inferred loading from `!diagnosis` — it can never recover from the terminal-entry-missing case.
- Skeleton now renders when the `diagnosing` prop is `true` AND `!badWordTip.tip` (already inside the `badWordTip &&` block, so `badWordTip` existence is implicit). Corrective tip still gated on `badWordTip.tip` being non-empty.

**`frontend/src/routes/Story.tsx`** and **`frontend/src/routes/Practice.tsx`**
- Added `diagnosing={practice.diagnosing}` to `<SentenceView>` right next to `diagnosis={practice.diagnosis}`.

---

## Finding 2 (harden): case-sensitive stress-hint lookup drops worst-word hint

### Root cause
`badWordTip` in `SentenceView` used `phoneticHints?.[focus]` with exact-key lookup. `focus` comes from `diagnosis.word` (Azure's `WordScore.word`), while `phoneticHints` is keyed by sentence-token spellings. A casing divergence (e.g. Azure returns `"Autobus"`, token is `"autobus"`) silently drops the `au-to-BÚS` stress hint, violating the invariant that the hint always stays.

### File changed

**`frontend/src/components/SentenceView.tsx`**
- In the `badWordTip` memo: replaced `phoneticHints?.[focus] ?? null` with a two-step lookup — exact key first, then a case-insensitive scan over `Object.entries(phoneticHints)` matching on `k.toLowerCase() === focus.toLowerCase()`. Returns `null` only if neither matches.

---

## Verification

```
npm run typecheck   → exit 0 (tsc --noEmit, no errors)
npm run i18n:check  → All 6 locales aligned (401 keys each, no change)
npm run build       → ✓ built in 1.07s (118 modules, no warnings)
```
