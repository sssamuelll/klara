# #22 — Live pronunciation streaming: transport & correctness contract

**Date:** 2026-07-01
**Issue:** #22 (live pronunciation streaming with progressive scoring)
**Status:** Design — approved + hardened by roster spec review, pending implementation plan
**Scope:** backend streaming transport + client protocol + backpressure/failure policy. NOT the frontend render, reconnect UX, or the full assessment business logic (those are downstream).

## Background

Today Klara scores pronunciation in one shot: the client records a blob, POSTs it to `POST /api/v1/pronunciation/score`, and the backend calls Azure `recognize_once()` inside `run_in_threadpool` (`backend/src/klara/pronunciation/azure_client.py`, `routers/pronunciation.py:59`). There is no WebSocket, no continuous recognition, and no callback-driven code anywhere in the repo.

`#22` wants a live experience: words underline and colour progressively while the user speaks. That requires Azure *continuous* recognition (`PushAudioInputStream` + `start_continuous_recognition` + `PronunciationAssessmentConfig`), where Azure fires `recognized` events on SDK-internal threads that must be marshalled onto the single uvicorn event loop and pushed over a per-session WebSocket.

The concurrency spike (`backend/spikes/spike_22_streaming_bridge.py`, merged in PR #100) settled the **bridge primitive**:

- **Bridge A (ship this):** `loop.call_soon_threadsafe(offer, evt)` onto an `asyncio.Queue` — non-blocking on the SDK thread.
- **Bridge B (rejected):** `asyncio.run_coroutine_threadsafe(q.put(evt), loop).result()` from the SDK thread — a real circular-wait deadlock + SDK-thread leak under backpressure.

This spec closes the backpressure/failure policy. It was reframed by one roster panel (push policy) and then hardened by a second roster spec review (Serrano/Halberg/Null Vale/Vex/Voronov); the changes from that review are folded in below and flagged inline.

## Locked product decisions

1. **Score truth = droppable live PREVIEW + authoritative COMPLETE final snapshot.** The backend keeps a full ordered accumulator of recognized words and NEVER drops server-side. At `session_stopped` it sends one complete `{words[], scores}` payload the client reconciles. Single Azure stream, no double cost.
2. **Scale = LOW (~1-5 concurrent speakers).** Minimal machinery; a generous global cap plus a small per-user cap as a safety net, not a pacing system.
3. **Failure model = progressive enhancement.** The client ALWAYS records a local blob (`MediaRecorder`, webm/opus) alongside the PCM stream. ANY streaming failure routes to the existing batch endpoint `POST /pronunciation/score`, which already transcodes webm/opus → WAV (`pronunciation/audio.py`). Batch is the floor; streaming is pure enhancement.

## Core principle

The panel's decisive finding: framing the live channel as "bounded by utterance length" is a **category error**. An utterance is a linguistic unit; queue depth is temporal. The real invariant is a *rate*:

> The live channel is healthy **iff `ws.send` drains at least as fast as Azure fires.** Utterance length and queue depth never enter.

So the ONLY drain-health signal is **send latency** (a stuck `ws.send`), not queue occupancy. Two conditions would break any word-count/depth bound, at any scale — a stuck `ws.send` (dead-but-open client, TCP zero-window) and a silence-bounded long utterance (unscripted mode has no word ceiling). Both are handled by measuring drain health directly and, on failure, tearing the session down to the batch floor.

## Architecture

New authenticated endpoint: `WS /api/v1/pronunciation/stream`.

Per session the moving parts are: **one session object** (an async context manager) whose `finally` is the single teardown path, holding **a `list`** (the accumulator), **an `asyncio.Queue`** (the live channel), and **one consumer task**. The table below is *responsibilities, not classes* — do not build five collaborators for what is one context manager + a list + a queue + a task.

| Responsibility | What it is | Notes |
|---|---|---|
| Session lifecycle | the async context manager + its `finally` | acquires/releases both cap slots; owns teardown |
| Bridge → queue | `recognized` handler → `call_soon_threadsafe` → `Queue` | handler runs on the SDK thread; enqueue is non-blocking |
| Accumulator | a `list` appended in the handler | complete, ordered, never dropped; source of truth for `final` |
| Consumer | one task: `get` from queue → `ws.send` under timeout | the only task that touches the socket for sending |
| Teardown | the `finally` | cancels the consumer, stops recognition, closes recognizer/pushstream, releases slots |

Session caps: a **global `asyncio.Semaphore(~8)`** (bounds native SDK threads) AND a **per-user cap (1–2 concurrent streams)** so one user cannot monopolise all slots and push everyone else to batch. At either cap, the client goes to batch (see close codes).

## Security & auth

Auth is **cookie-based**, reusing the existing `fastapi-users` `CookieTransport` + JWT (`auth/backend.py`, cookie `klara_session`, `httponly`, `samesite=strict`). The browser sends this cookie automatically on the WS upgrade — no ticket, no token-in-query (which would leak to logs).

- The WS handler reads `websocket.cookies["klara_session"]`, validates it with the same `JWTStrategy`, resolves the active user, and **rejects on invalid/expired** (accept-then-close with `4401`).
- Defense-in-depth: an **`Origin` allowlist check** on the upgrade (`samesite=strict` already blocks cross-site cookie send; the Origin check is belt-and-suspenders).

## WS protocol

**Client → server**
- Binary frames: PCM chunks (16 kHz mono, ~200 ms) → `push_stream.write`.
- Text control: `{"type":"eos"}` — end of speech → server `push_stream.close()`. If it never arrives, the max-session-duration timer is the backstop (below).

**Server → client**
- Live (best-effort, in arrival order — NO index): `{"type":"word","word":<str>,"accuracy_score":<float>,"error_type":<str>}`. The client paints in arrival order; for read-along it aligns to reference tokens by order + `error_type` (omission/insertion). Positional/offset data is intentionally NOT on the live message — it is a temporal value masquerading as a stable position and is a lie for unscripted (speaker skips/repeats/inserts). The authoritative positions live only in `final`.
- Final (authoritative): `{"type":"final","words":[...complete ordered list...],"scores":{...}}` built from the accumulator. This is the reconciliation truth; the client repaints from it.

**Close codes & the "exactly one score" contract**
- `1000` normal — sent AFTER `final`. Success.
- `4401` auth failed.
- `4408` capacity (global or per-user cap) — accept-then-close (an app close code cannot be set on a rejected upgrade).
- `4500` streaming failure (drain-health teardown, Azure `canceled`, max-duration).

The invariant is enforced at the wire by the **presence of `final`, not the close code**: the client falls back to batch **iff it did NOT receive a `final` message.** (Close code is a hint; a raced close never causes a double score.) `final` is emitted ONLY on the success path — never from the `session_stopped` that fires during teardown's offloaded `stop()`.

## Backpressure & failure policy

- **`SEND_TIMEOUT` is the single drain-health signal.** Each send is `await asyncio.wait_for(ws.send(msg), SEND_TIMEOUT)`. Its expiry (a stuck/slow socket) is the one thing that means "drain unhealthy."
- **The queue is NOT a teardown trigger.** It is effectively unbounded; its depth is bounded in practice by `SEND_TIMEOUT` (a stalled send trips teardown within `SEND_TIMEOUT`, during which the SDK adds at most a few finals) and absolutely by the max-session-duration timer. A `maxsize`-as-trigger was removed: it re-introduced the category error (depth ≠ rate) and would false-positive on a healthy-but-bursty producer (Azure delivering several finals at once).
- **Teardown is by CANCELLATION, not a flag.** A consumer parked in `await ws.send` cannot observe a flag (`Event.set()` does not preempt an in-flight await). So every failure trigger CANCELS the consumer task, which unwinds the await immediately and enters the single teardown path. Triggers: `SEND_TIMEOUT` expiry (raises out of the send), WS send error, Azure `canceled` (handler schedules cancellation via `call_soon_threadsafe`), max-session-duration timer, WS ping timeout.
- On teardown the client observes the close (no `final`) → batch fallback with the local blob. Session-cap rejection is the same story with no live channel ever established.

**Net correctness guarantee:** exactly one of — the `final` snapshot (streaming succeeded) OR a batch score (no `final` received). The live channel is decoration; losing it never costs a score.

## Live-paint source (v1)

- **v1 paints from `recognized` FINALS only, implemented by NEVER CONNECTING the `recognizing` handler.** Not subscribe-and-skip: filtering partials inside a connected handler would drop the clock-driven partial flood back onto the SDK thread as a `call_soon_threadsafe` storm (the untested CPU-blocked-loop `_ready` growth). The handler simply does not exist.
- **Deferred (YAGNI):** `recognizing` partials for a snappier feel, added only if v1 feels laggy. That would introduce coalesce-latest **on partials specifically** (only the newest partial matters) — a scoped, later change.

## Teardown / lifecycle

- Every exit path (normal end, client disconnect, `SEND_TIMEOUT`, WS error, `canceled`, cap, ping timeout, max-duration) routes through the session's single `finally`, which: **cancels the consumer task**, stops recognition, closes the recognizer, closes the push stream, releases both cap slots, closes the WS. Goal: **zero leaked SDK threads or recognizers, and no leaked cap slots.**
- `stop_continuous_recognition()` is **always offloaded AND time-boxed**: `await asyncio.wait_for(run_in_threadpool(rec.stop_continuous_recognition), STOP_TIMEOUT)`. It is never called on the loop thread (the spike proved on-loop stop + any blocking = deadlock). `run_in_threadpool` is not cancellable, so on `STOP_TIMEOUT` we log, **release the cap slot anyway, and proceed** — a wedged Azure network stop must not leak the slot forever. Tradeoff: the lingering threadpool thread may briefly exceed the intended native-thread count; acceptable at low scale and bounded by Azure's own teardown. `# ponytail: slot released before the uncancellable stop joins; per-user cap makes the transient over-count harmless.`
- Client disconnect is detected by `ws.send` raising and by the ping/pong below.
- **WS ping/pong keepalive (v1):** the server pings on an interval; a missed pong within `PONG_TIMEOUT` → cancel → teardown → batch. This catches an idle half-open client that `SEND_TIMEOUT` cannot (no active sends when the user has stopped speaking).
- **Max-session-duration timer** is an INDEPENDENT timer task (not an inline check a parked consumer never reaches). It is the accumulator's memory bound (unscripted has no word ceiling), NOT a drain-health signal; on fire it cancels the consumer → teardown → batch.

## Testing

- **Extend the spike's `FakeContinuousRecognizer`** (it already models the SDK threading contract) into the test suite. Add cases:
  - **stuck `ws.send`** (consumer parks) → assert `SEND_TIMEOUT` cancels the consumer and teardown + batch-fallback signal fire; no silent stall.
  - **long utterance** (finals ≫ any prior maxsize) → assert no teardown from depth alone; only `SEND_TIMEOUT`/max-duration end it.
  - **Azure `canceled`** → assert `call_soon_threadsafe` cancellation → clean teardown, no `final`.
  - **client disconnect mid-utterance** and **missed pong** → assert clean teardown.
  - **normal completion** → assert exactly one `final`, `1000` close, and NO batch-fallback signal (the double-score guard).
  - Every path asserts: 0 zombie SDK threads, 0 leaked cap slots.
- Keep the fake stdlib-only (no live Azure) so it runs in CI.
- One optional **creds-gated smoke test** against real Azure for the end-to-end `p95 < 500 ms/word` criterion — separate, manual, not in CI.

## Out of scope (scope fence)

- Frontend `AudioWorklet` implementation, reconnect UX, progressive CSS rendering — downstream implementation.
- Real Azure end-to-end latency validation (`p95 < 500 ms`) — creds-gated smoke test, tracked separately.
- Multi-worker / horizontal scaling — only if concurrency grows past low (out of scope per decision #2). At high N the single-loop marshaling + N native SDK threads becomes the bottleneck; that is an infra frente, not this policy.

## Open items for the implementation plan

- Concrete constants: `SEND_TIMEOUT`, `STOP_TIMEOUT`, `PONG_TIMEOUT`, ping interval, global `Semaphore` size, per-user cap, `MAX_SESSION_DURATION`.
- The session manager module under `pronunciation/` and how it reuses `PronunciationAssessmentConfig` construction from `azure_client.py` (read-along vs unscripted).
- The exact JWT cookie validation call for WS (reuse `JWTStrategy`) and the `Origin` allowlist source.
- Client contract doc for the frontend frente (the message types + close codes above are the source of truth).
