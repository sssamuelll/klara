# #22 — Live pronunciation streaming: transport & correctness contract

**Date:** 2026-07-01
**Issue:** #22 (live pronunciation streaming with progressive scoring)
**Status:** Design — approved, pending implementation plan
**Scope:** backend streaming transport + client protocol + backpressure/failure policy. NOT the frontend render, reconnect UX, or the full assessment business logic (those are downstream).

## Background

Today Klara scores pronunciation in one shot: the client records a blob, POSTs it to `POST /api/v1/pronunciation/score`, and the backend calls Azure `recognize_once()` inside `run_in_threadpool` (`backend/src/klara/pronunciation/azure_client.py`, `routers/pronunciation.py:59`). There is no WebSocket, no continuous recognition, and no callback-driven code anywhere in the repo.

#22 wants a live experience: words underline and colour progressively while the user speaks. That requires Azure *continuous* recognition (`PushAudioInputStream` + `start_continuous_recognition` + `PronunciationAssessmentConfig`), where Azure fires `recognized` events on SDK-internal threads that must be marshalled onto the single uvicorn event loop and pushed over a per-session WebSocket.

The concurrency spike (`backend/spikes/spike_22_streaming_bridge.py`, merged in PR #100) settled the **bridge primitive**:

- **Bridge A (ship this):** `loop.call_soon_threadsafe(offer, evt)` onto an `asyncio.Queue` — non-blocking on the SDK thread.
- **Bridge B (rejected):** `asyncio.run_coroutine_threadsafe(q.put(evt), loop).result()` from the SDK thread — a real circular-wait deadlock + SDK-thread leak under backpressure, confirmed even with an offloaded `stop`.

The spike left the **backpressure/failure policy** open. This spec closes it, incorporating a roster panel review (Halberg/runtime, Vex Rune/complexity, Voronov/architecture, Null Vale/assumptions, Cassian/ship).

## Locked product decisions

1. **Score truth = droppable live PREVIEW + authoritative COMPLETE final snapshot.** The backend keeps a full ordered accumulator of recognized words and NEVER drops server-side. At `session_stopped` it sends one complete `{words[], scores}` payload the client reconciles. Single Azure stream, no double cost.
2. **Scale = LOW (~1-5 concurrent speakers).** Minimal machinery; a generous session cap (`Semaphore(~8)`) as a safety net, not a pacing system.
3. **Failure model = progressive enhancement.** The client ALWAYS records a local blob (`MediaRecorder`) alongside the PCM stream. ANY streaming failure (WS drop, cap full, Azure `canceled`) routes to the existing batch endpoint `POST /pronunciation/score`. Batch is the floor; streaming is pure enhancement.

## Core principle

The panel's decisive finding: framing the live channel as "bounded by utterance length" is a **category error**. An utterance is a linguistic unit; queue depth is temporal. Nothing resets the queue at an utterance boundary. The real invariant is:

> The live queue stays bounded **iff `ws.send` drains at least as fast as Azure fires.** Utterance length never enters.

Two conditions break any word-count bound, at any scale:

- **A stuck `ws.send`** — a dead-but-open client / TCP zero-window with no send timeout parks the consumer forever (Halberg). This is a per-connection failure, independent of load.
- **A silence-bounded long utterance** — in continuous mode an utterance ends on ~1.5s of silence (`Speech_SegmentationSilenceTimeoutMs`), so a fluent monologue or a paragraph read without pause is ONE arbitrarily long utterance (Null Vale). The unscripted mode (`score_unscripted`, empty `referenceText`) has no word ceiling at all.

Therefore: **bound the live channel by drain health, not word count.** On any drain-health failure, do not coalesce-and-limp — tear the session down and let the already-locked batch floor deliver the complete score.

## Architecture

New authenticated endpoint: `WS /api/v1/pronunciation/stream`.

Per session, five units with clear boundaries:

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| **Session lifecycle** | Create/teardown recognizer, push stream, queue; hold the `Semaphore` slot | Azure SDK, event loop |
| **Bridge + queue** | `recognized` handler (SDK thread) → `call_soon_threadsafe` → bounded `asyncio.Queue` | loop |
| **Accumulator** | Complete ordered list of recognized words; source of truth for the final snapshot | — |
| **Consumer/sender** | Drain queue → `ws.send` with a send timeout | queue, WS |
| **Teardown/failover** | Single exit path: stop recognition (offloaded), close recognizer + push stream, close WS | all of the above |

Session cap: `asyncio.Semaphore(~8)`. At capacity the WS upgrade is rejected with a "capacity" close code; the client goes straight to batch.

## Data flow & WS protocol (happy path)

1. Client opens the WS with params (`reference_text` or unscripted, `language`); starts `AudioWorklet` PCM capture **and** a parallel `MediaRecorder` blob.
2. Client → server: PCM chunks (16 kHz mono, ~200 ms) as binary frames → `push_stream.write`.
3. Server → client (live, best-effort): per `recognized` final →
   `{ "type": "word", "index": <int>, "word": <str>, "accuracy_score": <float>, "error_type": <str>, "offset_ms": <int>, "duration_ms": <int> }`
4. Client signals end-of-speech (control message / input close) → server `push_stream.close()`.
5. Server → client (final, authoritative): on `session_stopped` →
   `{ "type": "final", "words": [ ...complete ordered list... ], "scores": { "accuracy": .., "fluency": .., "completeness": .., "pronunciation": .. } }`
   built from the accumulator.
6. Client paints live by `index`; on `final`, reconciles and repaints the complete set.

## Backpressure & failure policy

- The `asyncio.Queue` has a small `maxsize` — a **guard, not a load-bearing bound**. A single utterance's finals fit trivially; the cap only exists to detect drain failure.
- **Overflow detection point:** the offer function is the target of `call_soon_threadsafe`, so it runs on the loop thread. It attempts `put_nowait`; on `QueueFull` it does NOT raise into the loop callback and does NOT drop — it flags the session for teardown (sets a teardown event the consumer/lifecycle observes). This is the precise "what happens at QueueFull" that a naive never-drop leaves undefined.
- `ws.send` is wrapped in `asyncio.wait_for(..., SEND_TIMEOUT)`.
- **Any of {queue full (flagged as above), `ws.send` timeout, WS send error, Azure `canceled`, max-session-duration exceeded} is a drain-health failure → tear the session down.** No coalescing, no drop counter.
- On teardown the client observes the WS close and falls back to batch: it POSTs the local blob to `/pronunciation/score` for the complete authoritative score.
- Session-cap rejection is the same story with no WS ever established.

**Net correctness guarantee:** exactly one of — the final snapshot (streaming succeeded) OR a batch score (streaming failed). The live channel is decoration; losing it never costs a score.

## Live-paint source (v1) & the index caveat

- **v1 paints from `recognized` FINALS only.** No `recognizing` partials: they fire by the clock (not per word) and re-send a growing list, and in unscripted mode the transcript is revised mid-stream. Excluding them removes a flood the spike never modeled and keeps the coordinate space stable.
- **Index** is derived from `offset_ms` (already present on every event — free). Reliable for read-along (fixed reference grid). For unscripted, the transcript may revise, so live index instability is possible — but the **final snapshot is the reconciliation truth**; the client repaints from it, so any live wobble is cosmetic and self-heals.
- **Deferred (YAGNI):** `recognizing` partials for a snappier live feel, added only if v1 feels laggy. That would introduce coalesce-latest **on partials specifically** (only the newest partial matters) — a scoped, later change, not part of v1.

## Teardown / lifecycle

- Every exit path (normal end, client disconnect, overflow, send timeout, `canceled`, cap, max-duration) routes through a single `finally` / async-context-manager that: stops recognition, closes the recognizer, closes the push stream, releases the `Semaphore` slot, closes the WS. Goal: **zero leaked SDK threads or recognizers** on any path.
- `stop_continuous_recognition()` is **always offloaded** (`run_in_threadpool`), never called on the loop thread. The spike proved on-loop stop + any blocking callback = deadlock; we keep stop off-loop as discipline even though bridge A doesn't block.
- Client disconnect is detected by `ws.send` raising, which triggers teardown.
- A **max-session-duration guard** caps the pathological never-silent utterance → teardown → batch, bounding the accumulator.

## Testing

- **Extend the spike's `FakeContinuousRecognizer`** (it already models the SDK threading contract) into the test suite. Add cases:
  - **stuck `ws.send`** (consumer parks) → assert teardown + batch-fallback signal fires; no silent stall.
  - **long utterance** (finals ≫ queue maxsize) → assert no silent unbounded growth; overflow trips teardown.
  - **Azure `canceled`** → assert teardown + fallback.
  - **client disconnect mid-utterance** → assert clean teardown.
  - Every path asserts: 0 zombie SDK threads, and every failure yields a batch-fallback signal.
- Keep the fake stdlib-only (no live Azure) so it runs in CI.
- One optional **creds-gated smoke test** against real Azure for the end-to-end `p95 < 500 ms/word` criterion — separate, manual, not in CI.

## Out of scope (scope fence)

- Frontend `AudioWorklet` implementation, reconnect UX, progressive CSS rendering — downstream implementation.
- Real Azure end-to-end latency validation (`p95 < 500 ms`) — creds-gated smoke test, tracked separately.
- Multi-worker / horizontal scaling — only needed if concurrency grows past low (out of scope per locked decision #2). At high N the single-loop marshaling + N native SDK threads becomes the bottleneck Halberg flagged; that is an infra frente, not this policy.

## Open items for the implementation plan

- Concrete constants: `SEND_TIMEOUT`, queue `maxsize`, `Semaphore` size, `MAX_SESSION_DURATION`.
- Exact WS control-message shape for end-of-speech and for the "capacity" reject close code.
- Where the streaming session manager lives (new module under `pronunciation/`) and how it reuses `PronunciationAssessmentConfig` construction from `azure_client.py`.
- Client contract doc for the frontend frente (message types above are the source of truth).
