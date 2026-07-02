# #22 — Live pronunciation streaming: frontend client (read-along v1)

**Date:** 2026-07-02
**Issue:** #22 (live pronunciation streaming with progressive scoring)
**Status:** Design — approved, pending implementation plan
**Backend contract:** `docs/superpowers/specs/2026-07-01-22-streaming-backpressure-design.md` (merged in PR #101, `8e4b691`). This spec is the client side of that contract.

## Locked decisions (from the brainstorm)

1. **Scope v1 = read-along / SentenceView only.** Speak and quiz cards (`useMicScorer`) stay on batch, untouched. Read-along is where the live paint pays: `reference_text` gives a stable grid and the band render (`bandsByTokenIndex`, cutoffs 70/45) already exists.
2. **No reconnect in v1.** A dropped WS mid-sentence means that sentence finishes via batch (complete score, slightly later); the next recording attempt opens a fresh WS. Mid-sentence reconnection cannot recover the Azure session anyway; the batch floor makes backoff machinery redundant.
3. **Full colour live.** Each incoming word paints immediately with its band (green/amber/red). The authoritative `final` repaints the complete set. This is the feature #22 asked for; the mid-sentence red is accepted.
4. **vitest, scoped to the new streaming modules.** First test framework in the frontend; covers the pure logic only (aligner, client contract, PCM packing). Worklet + real WS are covered by the manual smoke.

## Principle

Streaming is **pure enhancement**. Every failure — unsupported browser, WS refused, auth/capacity/failure closes, mid-stream drop, no `final` — collapses silently to the existing batch path. The user never sees a streaming error; the score never depends on streaming working. Kill switch is server-side (`PRON_STREAM_GLOBAL_CAP=0` → all connects close `4408` → everyone batches); no frontend flag.

**Client fallback rule (the whole contract in one line): batch iff no `final` message was received.** Close codes are hints only.

## Architecture

Three new library modules plus one integration point. No new hook; `useSentencePractice` stays the single state machine.

| Unit | File | Responsibility | Depends on |
|---|---|---|---|
| PCM capture | `frontend/src/lib/pcmCapture.ts` + `pcmWorklet.ts` | Same-`MediaStream` AudioWorklet → 16 kHz mono Int16 chunks (~200 ms) | Web Audio; the `MediaStream` owned by `startMicRecording` |
| Stream client | `frontend/src/lib/streamClient.ts` | WS lifecycle, handshake, message parsing, the `result` promise | WebSocket; backend protocol |
| Aligner | `frontend/src/lib/streamAlign.ts` | Pure: append-order live words → reference token indices | shared tokenization regex from `pronunciation.ts` |
| Integration | `frontend/src/lib/useSentencePractice.ts` (+ a small prop in `SentenceView.tsx`) | Orchestrates capture+client+aligner; feeds `final` into the existing post-scoring path | all of the above |

## PCM capture (`pcmCapture.ts` / `pcmWorklet.ts`)

- `startMicRecording` remains the mic owner: one `getUserMedia`, one permission prompt, MediaRecorder blob unchanged. It exposes its `MediaStream` (small additive change to its returned interface).
- `startPcmCapture(stream, onChunk)`: creates `AudioContext({ sampleRate: 16000 })` (native resampling), loads the worklet module via the Vite pattern `new URL('./pcmWorklet.ts', import.meta.url)`, connects `MediaStreamSource → AudioWorkletNode`. The worklet accumulates 3200 samples (200 ms @ 16 kHz), converts Float32 → Int16 mono, and `postMessage`s the buffer (transferable). Returns `{ stop() }` which disconnects and closes the context.
- **Capability guard (checked before opening anything):** `typeof AudioWorkletNode !== 'undefined'` AND `'WebSocket' in window` AND, after constructing the context, `ctx.sampleRate === 16000` (some platforms force the hardware rate — if so, close it and fall back). Guard fails → the session is batch-pure, identical to today.
- Float32→Int16 conversion lives in a pure exported helper (`floatTo16BitPCM`) so it is unit-testable outside the worklet.

## Stream client (`streamClient.ts`)

```ts
openScoreStream({ referenceText, language, onWord }): {
  sendChunk(buf: ArrayBuffer): void
  sendEos(): void
  close(): void
  result: Promise<FinalPayload | null>
}
```

- **URL derivation:** if `API_BASE` is relative (it is today), `(location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host + '/api/v1/pronunciation/stream'`; if `VITE_API_BASE_URL` is an absolute URL, derive host/protocol from it. One helper, both cases.
- On open: send the handshake text frame `{"reference_text", "language"}`, then binary PCM frames. `binaryType = 'arraybuffer'`.
- Incoming `{"type":"word", word, accuracy_score, error_type}` → `onWord`. Incoming `{"type":"final", words[], scores{}}` → resolves `result` with it.
- **`result` resolves `null`** on: close (any code) without `final`, WS `error`, or a **post-eos timeout (~8 s)** with no `final`. After resolution the socket is closed if still open. The consumer never inspects close codes.
- `sendChunk` buffers chunks sent before open and flushes them after the handshake frame; after close it remains a no-op (drop, don't throw) — the capture pipeline may race the close.

## Aligner (`streamAlign.ts`)

`createAligner(referenceText): (word: LiveWord) => number | null`

- Tokenizes the reference with the same `WORD_PUNCT` regex used by `wordTokenIndices`/`bandsByTokenIndex` (import the shared regex — do not duplicate it).
- Keeps an advancing pointer over the reference word-tokens. For each live word: normalize (lowercase, strip outer punctuation); `error_type === "Insertion"` → return `null` (ignore); try to match the pointer token, then a short look-ahead window (3 tokens) — a look-ahead match advances the pointer past the skipped tokens (they stay unpainted; `final` resolves them); no match → return `null`.
- **Invariant: the live paint may under-paint, but never mispaints a position.** `final` is the truth and repaints everything.

## Integration (`useSentencePractice`)

- `startRecording` (unchanged behavior first): mic + MediaRecorder + VAD exactly as today. Then, if the capability guard passes, *try* to open the stream and start PCM capture; any failure at this stage is caught and the session silently proceeds batch-pure.
- New state: `liveBands: Record<number, ScoreBand>` for the sentence currently recording (plus which sentence it belongs to). Incoming word → `aligner(word)` → if index, `liveBands[index] = scoreBand(accuracy_score)`.
- VAD fires (existing 1.5 s) → existing `stop()` produces the blob → `sendEos()` → `await result` (bounded by the client's 8 s post-eos timeout):
  - **`final`** → map to the `PronunciationScoreResponse` shape (`recognized_text` = joined final words; `reference_text`, `language` from the session) → feed the **existing** post-scoring path unchanged: `bandsByTokenIndex`, feedback panel, phonetic hints, diagnose, `recordPronunciationAttempt`. Downstream is blind to the origin.
  - **`null`** → `scoreAudio(blob)` — today's batch path, byte for byte.
- `liveBands` clears when the result (either origin) lands. Cancel (ESC) closes the stream and discards, as today.
- `SentenceView` gets a `liveBands` prop and applies the existing band classes to tokens while its sentence is recording. No new visual vocabulary, no new copy (zero i18n).

## Error matrix (single failure path)

| Failure | What happens |
|---|---|
| Mic denied | Existing path, unchanged (streaming never opens without a stream) |
| No AudioWorklet / WS / 16 kHz context | Guard fails → batch-pure session, silent |
| WS refused / `4401` / `4408` / `4500` | `result` → `null` → batch, silent (`console.debug` with the close code for diagnosis) |
| WS drops mid-sentence | Live paint freezes where it was; `result` → `null` → batch replaces it |
| `eos` sent, no `final` in 8 s | Same: `null` → batch |
| `final` arrives | Success path; close `1000` follows; no batch call |

One failure path = one path to test.

## Dev/build infra

- `vite.config.ts`: add `ws: true` to the existing `/api` proxy (dev WS passthrough).
- Prod: same-origin `/api/v1` via the outer reverse proxy — WS upgrade forwarding for `/api/v1/pronunciation/stream` is part of the pending live smoke checklist (backend spec).

## Testing

- **vitest** (dev-dependency, node environment, no browser): `npm run test` + appended to the frontend CI job (`typecheck + build + i18n + vitest run`).
- `streamAlign.test.ts` — exact match advances pointer; look-ahead window match skips correctly; `Insertion` ignored; out-of-window word → null; punctuation/case normalization; never returns an already-consumed index.
- `streamClient.test.ts` — against a minimal fake WebSocket (constructor-injectable or module-mocked): handshake sent first; `word` events reach `onWord`; `final` resolves `result`; close-without-final resolves `null`; post-eos timeout resolves `null`; `sendChunk` after close is a no-op.
- `pcm.test.ts` — `floatTo16BitPCM`: clipping at ±1, values, length; chunking arithmetic (3200 samples per 200 ms frame).
- Worklet + real WS + real Azure: covered by the manual creds-gated smoke (same checklist as the backend spec; still pending post-merge).

## Out of scope

- Speak and quiz surfaces (batch stays).
- Mid-sentence reconnect; `recognizing` partials (deferred with the backend).
- Any visual redesign beyond applying existing band classes during recording.
- i18n changes (no new user-facing strings).
