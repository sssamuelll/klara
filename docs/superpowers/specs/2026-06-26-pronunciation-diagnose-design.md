# Pronunciation diagnose — explain WHAT the learner did wrong — Design

**Issue #42.** Today's read-along feedback names the word and its stressed syllable (*«Casi. Revisa au-to-BÚS»*) but never the failing **phoneme** nor how to fix it. This adds a corrective tip — *"tu /u/ salió muy abierta: redondea bien los labios"* — for the single worst mispronounced word, in the learner's native language, off phoneme scores **Azure already returns and we currently discard**.

## Problem

`/pronunciation/score` returns per-word **and per-phoneme** accuracy (`WordScore.phonemes`, `azure_client.py:188-191`). The frontend bands words off `accuracy_score` and throws the phoneme strings away. So we pay Azure for the data that says *which sound failed* and never use it. The result is feedback that scores ("you missed it") instead of teaching ("your /u/ was too open — round your lips"). The raw material for the teaching version is already on the wire.

This is purely additive to the existing pronunciation flow. It does not touch scoring correctness, SRS, or the Speak (free-conversation) path.

## Decisions (locked)

- **D1 — New additive endpoint `POST /pronunciation/diagnose`.** `phonetic-hints` is **unchanged** — it keeps giving the `au-to-BÚS` stress hint to **every** bad word. `/diagnose` only adds the corrective tip for the **single worst** bad word. Two independent best-effort calls; `/diagnose` introduces exactly one new, isolated failure mode (the LLM call), already covered by a fallback.
- **D2 — One corrective tip per recording: the worst bad word only.** Issue's vote ("demasiado info abruma"). The other bad words keep only their stress hint. Worst word = lowest word `accuracy_score` among `bad`-band words.
- **D3 — Additive UX.** The worst word shows its existing `au-to-BÚS` (from `phonetic-hints`) **plus** a new corrective line below it. Both signals visible; the stress hint is never replaced or dropped.
- **D4 — Read-along scoring switches to IPA.** `score_pronunciation` gains `phonemeAlphabet: "IPA"` (mirroring `score_unscripted`, `azure_client.py:140-150`). This eliminates the SAPI-vs-IPA dual-alphabet problem at the source: the diagnose prompt only ever sees IPA. **Verified low-risk** — the only server-side consumer of phoneme *strings* is `speak_analysis.py`, which runs on the Speak path (already IPA); the read-along phoneme strings are consumed by nobody (frontend bands off `accuracy_score`). Lets the service reuse `speak_analysis.normalize_phoneme` and align with the German `FOCUS_PHONEME_SETS` vocabulary.
- **D5 — Responsibility split.** The **frontend** picks the worst word (it already holds `resp.words`) and sends that word with its phoneme array. The **backend** reads `native_language` from the authenticated user (never trusts the client for it) and picks the weakest phoneme. The selection rule lives in Python, unit-tested.
- **D6 — Cache + analytics in one table, NOT `pronunciation_attempts.detail`.** `PronunciationAttempt` has **no** `detail` column (only `QuizAttempt` does), and coupling an async diagnose write to the attempt row is fragile (the diagnosis arrives after the attempt is persisted). Instead, a dedicated `pronunciation_diagnoses` table serves both goals: the cache (skip the LLM for a seen `(L1, target, word, phoneme)`) and the analytics log (which phonemes Spanish speakers fail most). Decoupled from the attempt; no migration to `pronunciation_attempts`.
- **D7 — Tip contract.** ≤25 words, in `native_language`, concrete and actionable (mouth anatomy, rhythm, comparison to a native-language sound), never abstract ("try again"). Clone of the `phonetic_hints` LLM discipline: strict JSON, `_extract_json` recovery, best-effort.
- **D8 — Level calibration is OUT.** Tone-by-`user.level` (A0 concrete vs B1 phonetic terms) is a deferred follow-up, not v1 (issue's own note). One register for now.

## Data model

```python
class PronunciationDiagnosis(Base):
    __tablename__ = "pronunciation_diagnoses"
    __table_args__ = (
        UniqueConstraint("native_language", "target_language", "word", "weakest_phoneme",
                         name="uq_pron_diag_key"),
        Index("ix_pron_diag_phoneme", "native_language", "target_language", "weakest_phoneme"),
    )
    id: Mapped[uuid_pk]
    native_language: Mapped[str] = mapped_column(String(8), nullable=False)   # learner L1, e.g. "es"
    target_language: Mapped[str] = mapped_column(String(8), nullable=False)   # e.g. "de"
    word: Mapped[str] = mapped_column(String(120), nullable=False)            # canonical lower-cased lookup key
    weakest_phoneme: Mapped[str] = mapped_column(String(32), nullable=False)  # IPA symbol
    phoneme_score: Mapped[float] = mapped_column(Float, nullable=False)       # 0-100, the score that triggered it
    tip: Mapped[str] = mapped_column(String(400), nullable=False)             # ≤25-word corrective tip in L1
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]
```

- **Cache:** lookup by the unique key. Hit → return the stored `tip`, increment `hit_count`, no LLM. Miss → call the LLM, insert (`hit_count=1`).
- **Analytics:** `SELECT weakest_phoneme, SUM(hit_count) ... WHERE native_language='es' GROUP BY weakest_phoneme ORDER BY 2 DESC` → most-failed phonemes per L1. Blog material; no per-user row, no PII (the diagnosis is language-pair-specific, not user-specific).
- Alembic migration `20260626_0013_pronunciation_diagnoses`. `word` is stored **lower-cased** as the canonical cache key, so the unique constraint dedupes case variants (the UI shows the original spelling from the sentence, not from this row). The tip describes a sound, not a spelling.

## Backend

### Scoring change (D4)
`score_pronunciation` (`azure_client.py:61-100`) moves to the `json_string` config form to add `"phonemeAlphabet": "IPA"`, keeping `referenceText`, `gradingSystem: HundredMark`, `granularity: Phoneme`, `enableMiscue: False`, and the `PhraseListGrammar` bias unchanged. No response-shape change; only the (currently unconsumed) phoneme strings become IPA.

### Schemas (`pronunciation/schemas.py`)
```python
class DiagnoseRequest(BaseModel):
    language: str = Field(..., min_length=2, max_length=8)   # target language (BCP-47 or short)
    word: str = Field(..., min_length=1, max_length=120)
    phonemes: list[PhonemeScore] = Field(..., min_length=1)  # the worst word's phoneme array

class DiagnoseResponse(BaseModel):
    tip: str = ""                 # "" when no tip available (fallback)
    weakest_phoneme: str = ""     # echoed for the UI / debugging; "" on fallback
```

### Service (`services/pronunciation_diagnose.py`)
`generate_diagnosis(llm, db, *, word, phonemes, target_language, native_language) -> DiagnoseResponse`:
1. Pick the weakest phoneme = `min(phonemes, key=accuracy_score)`; short-circuit to empty if `phonemes` is empty.
2. Cache lookup on `(native_language, target_language, lower(word), weakest_phoneme)`. Hit → bump `hit_count`, return cached tip.
3. Miss → LLM call (clone of `generate_phonetic_hints`: system prompt with anatomical examples, `temperature=0`, `response_format=json_object`, `_extract_json`). On malformed/empty → return empty (no row written).
4. On a valid tip → insert the row, return `{tip, weakest_phoneme}`.

System prompt shape: *"You are a pronunciation coach. The learner (native language: {L1_label}) mispronounced the {target_label} word «{word}»; the weakest sound was the IPA phoneme /{phoneme}/. Write ONE corrective tip, ≤25 words, in {L1_label}, concrete (mouth/lips/tongue/air, or a comparison to a {L1_label} sound). No abstractions, no «try again». Return STRICT JSON: {"tip": "..."}"*.

### Router (`routers/pronunciation.py`)
```python
@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(user: CurrentUser, llm: ChatLLM, db: DBSession, payload: DiagnoseRequest):
    try:
        return await generate_diagnosis(
            llm, db, word=payload.word, phonemes=payload.phonemes,
            target_language=payload.language, native_language=user.native_language,
        )
    except Exception:
        return DiagnoseResponse()   # best-effort: empty tip, UI keeps the stress hint
```

## Frontend

- `api/types.ts`: `DiagnoseRequest` / `DiagnoseResponse`.
- `api/client.ts`: `api.diagnose(word, phonemes, language)` — best-effort, mirrors `getPhoneticHints` doc.
- `lib/useSentencePractice.ts`: after scoring, alongside the existing `fetchAndStoreHints` (all bad words), compute the worst bad word from `resp.words` (lowest `accuracy_score` among `bad`-band words) and fire `/diagnose` fire-and-forget with that word's `phonemes`. Store the tip in a new `diagnosisBySentence: Record<number, { word: string; tip: string }>`, cleared on the same sentence-change / reset paths as `phoneticHintsBySentence`. Exposed as flat `diagnosis` for the current sentence.
- `components/SentenceView.tsx`: under the worst word's `au-to-BÚS` stress hint, render the corrective `tip` (plain text) when present; a small skeleton while it loads (~1-2s, instant on cache hit). Presentational — consumes the flat `diagnosis`, no logic.

## i18n

One new key for the loading/skeleton label (e.g. `practice.feedback.diagnosing`) in all 6 locales (`es` source, solace-wren copy, `i18n:check` parity). The **tip body** is LLM content in the learner's `native_language`, not i18n chrome.

## Error handling / degradation

Cascade, all best-effort:
- Cache miss → LLM; LLM fails or returns malformed JSON → no row written, `tip=""`.
- `/diagnose` 5xx / timeout → frontend ignores; the `au-to-BÚS` stress hint stays on screen.
- No bad word in the sentence → frontend never calls `/diagnose` (no LLM cost).

Acceptance-criteria fallback ("fall back to the phonetic hint if /diagnose fails") is satisfied structurally: the stress hint is a separate, untouched call.

## Out of scope / explicitly NOT doing

- Replacing or deprecating `phonetic-hints` (kept as the always-on stress-hint path and the structural fallback).
- Tips for more than the worst word per recording (D2).
- Tone calibration by `user.level` (D8, deferred).
- Per-user analytics / scheduling off failed phonemes (the table is language-pair-keyed; a future weak-phoneme scheduler is the Speak path's job, `speak_finish.py`).
- The Speak (free-conversation) correction flow — unaffected.
- Streaming / real-time scoring (issue #22, separate and spike-gated).

## Testing

- **Backend (pytest):** weakest-phoneme selection (incl. empty `phonemes` → empty response); cache hit (no LLM, `hit_count` bumped) / miss (LLM called, row inserted); case-insensitive word lookup; malformed-LLM → `tip=""` and **no** row; native_language taken from the user, not the payload; prompt includes word + IPA phoneme + L1 label.
- **Scoring:** `score_pronunciation` still returns a valid `ScoreResponse`; phoneme strings are IPA; `speak_analysis` (Speak path) unaffected.
- **Migration:** Alembic roundtrip; add `pronunciation_diagnoses` to the conftest truncate list.
- **Frontend:** worst-word selection from `resp.words`; render with tip / with skeleton / with fallback (no tip) — `typecheck` + `build` + `i18n:check`.
