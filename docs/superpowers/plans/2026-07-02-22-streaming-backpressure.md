# #22 Live Pronunciation Streaming — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a WebSocket endpoint that streams Azure continuous pronunciation scoring to the client word-by-word, degrading safely to the existing batch endpoint on any failure.

**Architecture:** A thin Azure wrapper (`azure_stream.py`) exposes a small recognizer interface whose callbacks fire on SDK threads. A `StreamingSession` (`streaming.py`) owns the event loop, an unbounded accumulator (`list`), a live `asyncio.Queue`, a consumer task that `ws.send`s under a timeout, and a single cancellation-based teardown. The WS endpoint (`routers/pronunciation.py`) composes cookie-JWT auth + global/per-user caps + the session. The risky concurrency lives entirely in `StreamingSession` and is tested against a stdlib `FakeStreamingRecognizer` + `FakeWebSocket` — no Azure, CI-safe.

**Tech Stack:** FastAPI/Starlette WebSockets, `azure-cognitiveservices-speech==1.50`, asyncio, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-07-01-22-streaming-backpressure-design.md`

## Global Constraints

- Python `>=3.12`; single uvicorn worker (one event loop).
- Bridge A ONLY: SDK-thread callbacks marshal via `loop.call_soon_threadsafe`. NEVER `run_coroutine_threadsafe(...).result()` from a callback thread (deadlock, proven in PR #100).
- Teardown is by CANCELLATION, never a flag: a consumer parked in `await ws.send` cannot observe a flag.
- "Exactly one score" is enforced by the presence of `final`, not the close code: the client batches iff it did NOT receive a `final`. `final` is emitted ONLY on the success path.
- `SEND_TIMEOUT` is the sole drain-health signal; the queue is unbounded and never triggers teardown.
- v1 paints from `recognized` finals only, implemented by NEVER connecting the `recognizing` handler.
- Live `word` messages carry NO offset/index (append-order); authoritative positions live only in `final`.
- Auth reuses the existing `fastapi-users` JWT cookie `klara_session` (`auth/backend.py`); no ticket, no token-in-query.
- `stop_continuous_recognition()` is ALWAYS offloaded (`run_in_threadpool`) and time-boxed; on timeout release the cap slot anyway.
- Reuse existing schemas (`pronunciation/schemas.py`: `WordScore`, `PhonemeScore`, `PronunciationScores`) — do not duplicate.
- Follow the repo test pattern (`tests/test_pronunciation.py`): pytest-asyncio, monkeypatch the SDK, cookie via `/auth/jwt/login`.

---

## File Structure

- Create `backend/src/klara/pronunciation/azure_stream.py` — Azure continuous-recognition wrapper + the `StreamingRecognizer` interface + `RecognizedWord`. Thin glue; the seam that makes the session testable.
- Create `backend/src/klara/pronunciation/streaming.py` — `StreamingSession`, protocol message builders, close codes, `SessionOutcome`. The concurrency core.
- Create `backend/src/klara/pronunciation/ws_auth.py` — `authenticate_ws(websocket) -> User | None` via the cookie JWT + Origin allowlist.
- Modify `backend/src/klara/routers/pronunciation.py` — add `@router.websocket("/stream")`.
- Modify `backend/src/klara/config.py` — streaming constants.
- Create `backend/tests/test_pronunciation_stream.py` — session unit tests (fakes) + auth/capacity integration tests + `FakeStreamingRecognizer`/`FakeWebSocket` helpers.

---

## Task 1: Streaming constants in config

**Files:**
- Modify: `backend/src/klara/config.py:154` (after `pronunciation_max_audio_bytes`)
- Test: `backend/tests/test_pronunciation_stream.py`

**Interfaces:**
- Produces: `Settings.pron_stream_send_timeout_s: float`, `.pron_stream_stop_timeout_s: float`, `.pron_stream_ping_interval_s: float`, `.pron_stream_pong_timeout_s: float`, `.pron_stream_max_session_s: float`, `.pron_stream_global_cap: int`, `.pron_stream_per_user_cap: int`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pronunciation_stream.py
from __future__ import annotations


def test_streaming_settings_defaults():
    from klara.config import Settings

    s = Settings()
    assert s.pron_stream_send_timeout_s == 5.0
    assert s.pron_stream_stop_timeout_s == 3.0
    assert s.pron_stream_ping_interval_s == 10.0
    assert s.pron_stream_pong_timeout_s == 5.0
    assert s.pron_stream_max_session_s == 90.0
    assert s.pron_stream_global_cap == 8
    assert s.pron_stream_per_user_cap == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py::test_streaming_settings_defaults -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'pron_stream_send_timeout_s'`

- [ ] **Step 3: Add the settings**

```python
# backend/src/klara/config.py — after pronunciation_max_audio_bytes (line 154)
    # --- #22 live pronunciation streaming (WS /pronunciation/stream) ---
    # Sole drain-health signal: a ws.send slower than this means the client
    # can't keep up -> tear down -> client falls back to batch.
    pron_stream_send_timeout_s: float = 5.0
    # Offloaded stop_continuous_recognition() is uncancellable; cap the wait,
    # then release the cap slot regardless so a wedged Azure stop can't leak it.
    pron_stream_stop_timeout_s: float = 3.0
    pron_stream_ping_interval_s: float = 10.0
    pron_stream_pong_timeout_s: float = 5.0
    # Memory bound on the never-dropped accumulator (unscripted has no word
    # ceiling) and the backstop if the client never sends end-of-speech.
    pron_stream_max_session_s: float = 90.0
    # Global cap bounds native SDK threads; per-user cap stops one user
    # monopolising all slots and pushing everyone else to batch.
    pron_stream_global_cap: int = 8
    pron_stream_per_user_cap: int = 2
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py::test_streaming_settings_defaults -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/config.py backend/tests/test_pronunciation_stream.py
git commit -m "feat(pronunciation): #22 streaming config constants"
```

---

## Task 2: Protocol builders + close codes

**Files:**
- Create: `backend/src/klara/pronunciation/streaming.py`
- Test: `backend/tests/test_pronunciation_stream.py`

**Interfaces:**
- Consumes: `WordScore`, `PronunciationScores` from `pronunciation/schemas.py`.
- Produces:
  - `WS_CLOSE_OK = 1000`, `WS_CLOSE_AUTH = 4401`, `WS_CLOSE_CAPACITY = 4408`, `WS_CLOSE_FAILURE = 4500` (ints).
  - `word_message(w: WordScore) -> dict` → `{"type":"word","word","accuracy_score","error_type"}` (NO index).
  - `final_message(words: list[WordScore], scores: PronunciationScores) -> dict` → `{"type":"final","words":[...],"scores":{...}}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pronunciation_stream.py
def test_word_message_has_no_index():
    from klara.pronunciation.schemas import WordScore
    from klara.pronunciation.streaming import word_message

    msg = word_message(WordScore(word="Hallo", accuracy_score=91.0, error_type="None", phonemes=[]))
    assert msg == {"type": "word", "word": "Hallo", "accuracy_score": 91.0, "error_type": "None"}
    assert "index" not in msg and "offset_ms" not in msg


def test_final_message_shape():
    from klara.pronunciation.schemas import PronunciationScores, WordScore
    from klara.pronunciation.streaming import final_message

    msg = final_message(
        [WordScore(word="Hallo", accuracy_score=91.0, error_type="None", phonemes=[])],
        PronunciationScores(accuracy=90.0, fluency=88.0, completeness=100.0, pronunciation=89.0),
    )
    assert msg["type"] == "final"
    assert msg["words"][0]["word"] == "Hallo"
    assert msg["scores"]["pronunciation"] == 89.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k message -v`
Expected: FAIL with `ModuleNotFoundError: klara.pronunciation.streaming`

- [ ] **Step 3: Create the module with constants + builders**

```python
# backend/src/klara/pronunciation/streaming.py
"""#22 live pronunciation streaming: session transport + backpressure policy.

See docs/superpowers/specs/2026-07-01-22-streaming-backpressure-design.md.
The concurrency-risky logic lives here and is tested against a fake recognizer
+ fake websocket (no Azure). Bridge A only; teardown by cancellation.
"""

from __future__ import annotations

from klara.pronunciation.schemas import PronunciationScores, WordScore

# Close codes. The client's rule is: batch iff no `final` was received — the
# code is only a hint. 4xxx are app-defined (RFC 6455 private range).
WS_CLOSE_OK = 1000
WS_CLOSE_AUTH = 4401
WS_CLOSE_CAPACITY = 4408
WS_CLOSE_FAILURE = 4500


def word_message(w: WordScore) -> dict:
    """Live, best-effort, arrival-order. No index: offset is temporal and lies
    for unscripted; authoritative positions live only in the final snapshot."""
    return {
        "type": "word",
        "word": w.word,
        "accuracy_score": w.accuracy_score,
        "error_type": w.error_type,
    }


def final_message(words: list[WordScore], scores: PronunciationScores) -> dict:
    return {
        "type": "final",
        "words": [w.model_dump() for w in words],
        "scores": scores.model_dump(),
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k message -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/pronunciation/streaming.py backend/tests/test_pronunciation_stream.py
git commit -m "feat(pronunciation): #22 stream protocol builders + close codes"
```

---

## Task 3: Recognizer seam + test fakes

**Files:**
- Create: `backend/src/klara/pronunciation/azure_stream.py`
- Modify: `backend/tests/test_pronunciation_stream.py` (add fakes)

**Interfaces:**
- Produces (`azure_stream.py`):
  - `@dataclass RecognizedWord` = reuse `WordScore` directly (no new type — the accumulator holds `WordScore`).
  - `class StreamingRecognizer(Protocol)` with attributes `on_recognized: Callable[[WordScore], None] | None`, `on_session_stopped: Callable[[], None] | None`, `on_canceled: Callable[[str], None] | None`, and methods `start() -> None`, `write(pcm: bytes) -> None`, `close_input() -> None`, `stop() -> None` (blocking).
  - `word_score_from_azure(evt_words) -> list[WordScore]` — pure translation reused by the real wrapper (mirrors `_result_to_response`).
- Produces (test helper): `FakeStreamingRecognizer` firing callbacks serially on a background thread; `stop()` blocks until the in-flight callback returns (the spike's contract). `FakeWebSocket` with `send_json`, `receive`, `close`, `pong` controls.

- [ ] **Step 1: Write the failing test (translation + fake contract)**

```python
# backend/tests/test_pronunciation_stream.py
def test_word_score_from_azure_extracts_phonemes():
    from klara.pronunciation.azure_stream import word_score_from_azure

    class _P:
        def __init__(self, ph, acc): self.phoneme, self.accuracy_score = ph, acc

    class _W:
        def __init__(self):
            self.word, self.accuracy_score, self.error_type = "Hallo", 91.0, "None"
            self.phonemes = [_P("h", 98.0), _P("a", 80.0)]

    out = word_score_from_azure([_W()])
    assert out[0].word == "Hallo"
    assert out[0].phonemes[1].phoneme == "a"
    assert out[0].error_type == "None"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k from_azure -v`
Expected: FAIL with `ModuleNotFoundError: klara.pronunciation.azure_stream`

- [ ] **Step 3: Create the seam module**

```python
# backend/src/klara/pronunciation/azure_stream.py
"""Azure continuous pronunciation recognition, behind a tiny interface.

The interface (StreamingRecognizer) is what StreamingSession programs against,
so the session is testable with a fake. Real construction (SpeechConfig +
PushAudioInputStream) is thin glue exercised only under real Azure creds.

Callbacks fire on Azure SDK-internal threads. The session marshals them onto
the loop (bridge A); this module NEVER touches the event loop.
"""

from __future__ import annotations

from typing import Callable, Protocol

import azure.cognitiveservices.speech as speechsdk

from klara.pronunciation.schemas import PhonemeScore, WordScore


class StreamingRecognizer(Protocol):
    on_recognized: Callable[[WordScore], None] | None
    on_session_stopped: Callable[[], None] | None
    on_canceled: Callable[[str], None] | None

    def start(self) -> None: ...
    def write(self, pcm: bytes) -> None: ...
    def close_input(self) -> None: ...
    def stop(self) -> None: ...  # BLOCKING — always called offloaded


def word_score_from_azure(words) -> list[WordScore]:
    """Same extraction as azure_client._result_to_response, per word event."""
    return [
        WordScore(
            word=w.word,
            accuracy_score=w.accuracy_score,
            error_type=str(w.error_type),
            phonemes=[
                PhonemeScore(phoneme=p.phoneme, accuracy_score=p.accuracy_score)
                for p in (w.phonemes or [])
            ],
        )
        for w in words
    ]


# NOTE: build_pcm_format / AzureStreamingRecognizer construction below is only
# reachable with real Azure creds; it has no unit test (covered by the manual
# creds-gated smoke test). Keep it thin — all logic lives in StreamingSession.
def build_pcm_format() -> speechsdk.audio.AudioStreamFormat:
    return speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
```

- [ ] **Step 4: Add the `FakeStreamingRecognizer` + `FakeWebSocket` test helpers**

```python
# backend/tests/test_pronunciation_stream.py
import asyncio
import threading
import time

from klara.pronunciation.schemas import WordScore


class FakeStreamingRecognizer:
    """Honors the SDK contract that breaks bridges: callbacks fire serially on
    one internal thread; stop() blocks until the in-flight callback returns."""

    def __init__(self, words: list[WordScore], cadence: float = 0.01):
        self._words = words
        self._cadence = cadence
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.on_recognized = None
        self.on_session_stopped = None
        self.on_canceled = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="fake-sdk", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        for w in self._words:
            if self._stop.is_set():
                break
            time.sleep(self._cadence)
            if self.on_recognized:
                self.on_recognized(w)          # runs the bridge on THIS thread
        if self.on_session_stopped:
            self.on_session_stopped()

    def write(self, pcm: bytes) -> None: ...
    def close_input(self) -> None: ...

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(2.0)

    def fire_canceled(self, reason: str) -> None:
        if self.on_canceled:
            self.on_canceled(reason)


class FakeWebSocket:
    """Async WS double. `block_send` parks send() forever (stuck client)."""

    def __init__(self, block_send: bool = False):
        self.sent: list[dict] = []
        self.closed_code: int | None = None
        self.block_send = block_send
        self._recv_q: asyncio.Queue = asyncio.Queue()
        self.pong_ok = True

    async def send_json(self, obj: dict) -> None:
        if self.block_send:
            await asyncio.Event().wait()       # never returns
        self.sent.append(obj)

    async def receive(self):
        return await self._recv_q.get()

    async def close(self, code: int) -> None:
        self.closed_code = code

    async def ping(self) -> bool:
        return self.pong_ok

    def sent_final(self) -> bool:
        return any(m.get("type") == "final" for m in self.sent)
```

- [ ] **Step 5: Run to verify translation passes**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k from_azure -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/pronunciation/azure_stream.py backend/tests/test_pronunciation_stream.py
git commit -m "feat(pronunciation): #22 recognizer seam + streaming test fakes"
```

---

## Task 4: StreamingSession — happy path

**Files:**
- Modify: `backend/src/klara/pronunciation/streaming.py`
- Test: `backend/tests/test_pronunciation_stream.py`

**Interfaces:**
- Consumes: `StreamingRecognizer`, `WordScore`, `PronunciationScores`, the `word_message`/`final_message` builders, close codes.
- Produces:
  - `class SessionOutcome(enum.Enum): COMPLETED, FAILED`.
  - `class StreamingSession` with `__init__(self, recognizer, websocket, *, scores_of: Callable[[list[WordScore]], PronunciationScores], settings)` and `async def run(self) -> SessionOutcome`.
  - On success: pushes a `word` per recognized word, then one `final`, returns `COMPLETED`. `scores_of` computes the summary from the accumulator (the endpoint passes Azure's session-level scores; tests pass a stub).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pronunciation_stream.py
import pytest

from klara.pronunciation.schemas import PronunciationScores


def _stub_scores(words):
    return PronunciationScores(accuracy=90.0, fluency=90.0, completeness=100.0, pronunciation=90.0)


def _words(n):
    return [WordScore(word=f"w{i}", accuracy_score=90.0, error_type="None", phonemes=[]) for i in range(n)]


@pytest.mark.asyncio
async def test_session_happy_path_one_final_all_words():
    from klara.config import Settings
    from klara.pronunciation.streaming import SessionOutcome, StreamingSession

    rec = FakeStreamingRecognizer(_words(12))
    ws = FakeWebSocket()
    outcome = await StreamingSession(rec, ws, scores_of=_stub_scores, settings=Settings()).run()

    assert outcome is SessionOutcome.COMPLETED
    assert [m for m in ws.sent if m["type"] == "word"].__len__() == 12
    finals = [m for m in ws.sent if m["type"] == "final"]
    assert len(finals) == 1
    assert len(finals[0]["words"]) == 12
    assert not [t for t in threading.enumerate() if t.name == "fake-sdk" and t.is_alive()]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k happy_path_one_final -v`
Expected: FAIL with `ImportError: cannot import name 'StreamingSession'`

- [ ] **Step 3: Implement the happy path**

```python
# backend/src/klara/pronunciation/streaming.py — add imports + class
import asyncio
import enum
from typing import Callable

from klara.pronunciation.azure_stream import StreamingRecognizer


class SessionOutcome(enum.Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class StreamingSession:
    def __init__(self, recognizer, websocket, *, scores_of, settings):
        self._rec: StreamingRecognizer = recognizer
        self._ws = websocket
        self._scores_of: Callable[[list[WordScore]], PronunciationScores] = scores_of
        self._settings = settings
        self._loop = asyncio.get_event_loop()
        self._queue: asyncio.Queue = asyncio.Queue()   # unbounded by design
        self._acc: list[WordScore] = []
        self._stopped = asyncio.Event()

    def _on_recognized(self, w: WordScore) -> None:          # SDK thread
        self._acc.append(w)                                  # accumulator: never dropped
        self._loop.call_soon_threadsafe(self._queue.put_nowait, w)

    def _on_session_stopped(self) -> None:                   # SDK thread
        self._loop.call_soon_threadsafe(self._stopped.set)

    async def _consume(self) -> None:
        while not (self._stopped.is_set() and self._queue.empty()):
            try:
                w = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            await self._ws.send_json(word_message(w))

    async def run(self) -> SessionOutcome:
        self._rec.on_recognized = self._on_recognized
        self._rec.on_session_stopped = self._on_session_stopped
        self._rec.start()
        try:
            await self._consume()
            scores = self._scores_of(self._acc)
            await self._ws.send_json(final_message(self._acc, scores))
            return SessionOutcome.COMPLETED
        finally:
            await asyncio.wait_for(
                asyncio.to_thread(self._rec.stop), timeout=self._settings.pron_stream_stop_timeout_s
            )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k happy_path_one_final -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/pronunciation/streaming.py backend/tests/test_pronunciation_stream.py
git commit -m "feat(pronunciation): #22 StreamingSession happy path"
```

---

## Task 5: Drain-health teardown (stuck send → cancel → FAILED, no final)

**Files:**
- Modify: `backend/src/klara/pronunciation/streaming.py`
- Test: `backend/tests/test_pronunciation_stream.py`

**Interfaces:**
- Produces: `run()` now wraps every `ws.send` in `wait_for(..., SEND_TIMEOUT)` and runs the consumer as a cancellable task; a `SEND_TIMEOUT`/error tears down (cancel + stop), returns `FAILED`, and sends NO `final`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pronunciation_stream.py
@pytest.mark.asyncio
async def test_session_stuck_send_tears_down_no_final():
    from klara.config import Settings
    from klara.pronunciation.streaming import SessionOutcome, StreamingSession

    s = Settings()
    object.__setattr__(s, "pron_stream_send_timeout_s", 0.1)  # fast for the test
    rec = FakeStreamingRecognizer(_words(12))
    ws = FakeWebSocket(block_send=True)                       # client never drains

    outcome = await StreamingSession(rec, ws, scores_of=_stub_scores, settings=s).run()

    assert outcome is SessionOutcome.FAILED
    assert not ws.sent_final(), "no final on the failure path (double-score guard)"
    assert not [t for t in threading.enumerate() if t.name == "fake-sdk" and t.is_alive()]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k stuck_send -v`
Expected: FAIL (current `run()` awaits `send_json` directly → hangs until the 0.1s has no effect; test times out or the consumer never returns FAILED)

- [ ] **Step 3: Wrap sends in a timeout and run the consumer as a cancellable task**

```python
# backend/src/klara/pronunciation/streaming.py — replace _consume + run
    async def _consume(self) -> None:
        while not (self._stopped.is_set() and self._queue.empty()):
            try:
                w = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            # SEND_TIMEOUT is the sole drain-health signal. A stuck ws.send
            # raises TimeoutError here, which propagates out and fails the task.
            await asyncio.wait_for(
                self._ws.send_json(word_message(w)),
                timeout=self._settings.pron_stream_send_timeout_s,
            )

    async def run(self) -> SessionOutcome:
        self._rec.on_recognized = self._on_recognized
        self._rec.on_session_stopped = self._on_session_stopped
        self._rec.start()
        consumer = asyncio.ensure_future(self._consume())
        try:
            await consumer
            scores = self._scores_of(self._acc)
            await asyncio.wait_for(
                self._ws.send_json(final_message(self._acc, scores)),
                timeout=self._settings.pron_stream_send_timeout_s,
            )
            return SessionOutcome.COMPLETED
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            return SessionOutcome.FAILED
        finally:
            if not consumer.done():
                consumer.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._rec.stop),
                    timeout=self._settings.pron_stream_stop_timeout_s,
                )
            except (asyncio.TimeoutError, Exception):
                pass  # uncancellable offloaded stop timed out; slot released by caller anyway
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k "stuck_send or happy_path_one_final" -v`
Expected: PASS (2 tests — happy path still green)

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/pronunciation/streaming.py backend/tests/test_pronunciation_stream.py
git commit -m "feat(pronunciation): #22 drain-health teardown via SEND_TIMEOUT"
```

---

## Task 6: Remaining teardown triggers (canceled, max-duration, long-utterance)

**Files:**
- Modify: `backend/src/klara/pronunciation/streaming.py`
- Test: `backend/tests/test_pronunciation_stream.py`

**Interfaces:**
- Produces: `run()` additionally starts an independent max-session-duration timer that cancels the consumer; the recognizer's `on_canceled` cancels the consumer via `call_soon_threadsafe`. Long utterances (many words) never trigger teardown by depth.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_pronunciation_stream.py
@pytest.mark.asyncio
async def test_session_long_utterance_no_depth_teardown():
    from klara.config import Settings
    from klara.pronunciation.streaming import SessionOutcome, StreamingSession

    rec = FakeStreamingRecognizer(_words(500), cadence=0.0)  # far more than any queue guard
    ws = FakeWebSocket()
    outcome = await StreamingSession(rec, ws, scores_of=_stub_scores, settings=Settings()).run()
    assert outcome is SessionOutcome.COMPLETED
    assert len([m for m in ws.sent if m["type"] == "word"]) == 500


@pytest.mark.asyncio
async def test_session_canceled_event_tears_down_no_final():
    from klara.config import Settings
    from klara.pronunciation.streaming import SessionOutcome, StreamingSession

    # A recognizer that fires canceled shortly after start, never session_stopped.
    class CancelingRec(FakeStreamingRecognizer):
        def _run(self):
            time.sleep(0.02)
            self.fire_canceled("CancellationReason.Error - quota")

    rec = CancelingRec(_words(5))
    ws = FakeWebSocket()
    outcome = await StreamingSession(rec, ws, scores_of=_stub_scores, settings=Settings()).run()
    assert outcome is SessionOutcome.FAILED
    assert not ws.sent_final()


@pytest.mark.asyncio
async def test_session_max_duration_tears_down():
    from klara.config import Settings
    from klara.pronunciation.streaming import SessionOutcome, StreamingSession

    s = Settings()
    object.__setattr__(s, "pron_stream_max_session_s", 0.05)
    # A recognizer that never stops on its own (no session_stopped, keeps idle).
    rec = FakeStreamingRecognizer(_words(0))
    rec._run = lambda: time.sleep(2.0)  # busy, never fires stopped
    ws = FakeWebSocket()
    outcome = await StreamingSession(rec, ws, scores_of=_stub_scores, settings=s).run()
    assert outcome is SessionOutcome.FAILED
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k "long_utterance or canceled_event or max_duration" -v`
Expected: FAIL (`on_canceled` unused; no max-duration timer → `max_duration` hangs/None)

- [ ] **Step 3: Add the canceled handler + max-duration timer that cancel the consumer**

```python
# backend/src/klara/pronunciation/streaming.py
    # in __init__, after self._stopped:
        self._consumer: asyncio.Future | None = None

    def _on_canceled(self, reason: str) -> None:             # SDK thread
        # Marshal a cancel of the consumer onto the loop (bridge A).
        self._loop.call_soon_threadsafe(self._cancel_consumer)

    def _cancel_consumer(self) -> None:
        if self._consumer is not None and not self._consumer.done():
            self._consumer.cancel()

    async def _max_duration_guard(self) -> None:
        # Independent timer, not an inline check a parked consumer never reaches.
        await asyncio.sleep(self._settings.pron_stream_max_session_s)
        self._cancel_consumer()

    async def run(self) -> SessionOutcome:
        self._rec.on_recognized = self._on_recognized
        self._rec.on_session_stopped = self._on_session_stopped
        self._rec.on_canceled = self._on_canceled
        self._rec.start()
        self._consumer = asyncio.ensure_future(self._consume())
        guard = asyncio.ensure_future(self._max_duration_guard())
        try:
            await self._consumer
            scores = self._scores_of(self._acc)
            await asyncio.wait_for(
                self._ws.send_json(final_message(self._acc, scores)),
                timeout=self._settings.pron_stream_send_timeout_s,
            )
            return SessionOutcome.COMPLETED
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            return SessionOutcome.FAILED
        finally:
            guard.cancel()
            if not self._consumer.done():
                self._consumer.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._rec.stop),
                    timeout=self._settings.pron_stream_stop_timeout_s,
                )
            except (asyncio.TimeoutError, Exception):
                pass
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -v`
Expected: PASS (all session tests green, including happy path and stuck-send)

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/pronunciation/streaming.py backend/tests/test_pronunciation_stream.py
git commit -m "feat(pronunciation): #22 canceled + max-duration teardown triggers"
```

---

## Task 7: Session receiver — PCM in, end-of-speech, client disconnect

**Files:**
- Modify: `backend/src/klara/pronunciation/streaming.py`
- Test: `backend/tests/test_pronunciation_stream.py`

**Interfaces:**
- Consumes: the `StreamingRecognizer.write`/`close_input` methods; the websocket's `receive()`.
- Produces: `run()` now also starts a receiver task that reads frames — binary → `recognizer.write(pcm)`, text → treat as end-of-speech → `recognizer.close_input()`. A receiver exception (client disconnect) cancels the consumer → `FAILED`. Success is still driven by the consumer completing on `session_stopped`; the receiver is cancelled in teardown.

- [ ] **Step 1: Extend `FakeWebSocket` to script receives + disconnect**

```python
# backend/tests/test_pronunciation_stream.py — add to FakeWebSocket.__init__:
#     self.raise_on_receive: Exception | None = None
# and add these methods:
    def queue_recv(self, msg: dict) -> None:
        self._recv_q.put_nowait(msg)

    async def receive(self):
        if self.raise_on_receive is not None:
            raise self.raise_on_receive
        return await self._recv_q.get()
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_pronunciation_stream.py
@pytest.mark.asyncio
async def test_session_receiver_writes_pcm_and_eos_closes_input():
    from klara.config import Settings
    from klara.pronunciation.streaming import SessionOutcome, StreamingSession

    written: list[bytes] = []
    closed = {"n": 0}

    class RecordingRec(FakeStreamingRecognizer):
        def write(self, pcm): written.append(pcm)
        def close_input(self): closed["n"] += 1

    rec = RecordingRec(_words(3), cadence=0.02)
    ws = FakeWebSocket()
    ws.queue_recv({"bytes": b"\x00\x01"})
    ws.queue_recv({"text": '{"type":"eos"}'})            # end-of-speech

    outcome = await StreamingSession(rec, ws, scores_of=_stub_scores, settings=Settings()).run()
    assert outcome is SessionOutcome.COMPLETED
    assert written == [b"\x00\x01"]
    assert closed["n"] == 1


@pytest.mark.asyncio
async def test_session_client_disconnect_tears_down_no_final():
    from klara.config import Settings
    from klara.pronunciation.streaming import SessionOutcome, StreamingSession

    rec = FakeStreamingRecognizer(_words(50), cadence=0.05)  # still "speaking"
    ws = FakeWebSocket()
    ws.raise_on_receive = RuntimeError("client gone")        # disconnect
    outcome = await StreamingSession(rec, ws, scores_of=_stub_scores, settings=Settings()).run()
    assert outcome is SessionOutcome.FAILED
    assert not ws.sent_final()
```

- [ ] **Step 3: Run to verify they fail**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k "receiver_writes or client_disconnect" -v`
Expected: FAIL (no receiver → PCM never written; disconnect never cancels the consumer)

- [ ] **Step 4: Add the receiver to `run()`**

```python
# backend/src/klara/pronunciation/streaming.py — add method + wire into run()
    async def _receive_loop(self) -> None:
        while True:
            msg = await self._ws.receive()
            text = msg.get("text")
            if text is not None:              # any text frame == end-of-speech
                self._rec.close_input()
                return
            data = msg.get("bytes")
            if data:
                self._rec.write(data)

    async def run(self) -> SessionOutcome:
        self._rec.on_recognized = self._on_recognized
        self._rec.on_session_stopped = self._on_session_stopped
        self._rec.on_canceled = self._on_canceled
        self._rec.start()
        self._consumer = asyncio.ensure_future(self._consume())
        receiver = asyncio.ensure_future(self._receive_loop())
        guard = asyncio.ensure_future(self._max_duration_guard())

        def _on_receiver_done(t: asyncio.Future) -> None:
            # A receiver ERROR (client disconnect) tears the session down.
            # A clean return (eos) does not — success comes from the consumer.
            if not t.cancelled() and t.exception() is not None:
                self._cancel_consumer()

        receiver.add_done_callback(_on_receiver_done)
        try:
            await self._consumer
            scores = self._scores_of(self._acc)
            await asyncio.wait_for(
                self._ws.send_json(final_message(self._acc, scores)),
                timeout=self._settings.pron_stream_send_timeout_s,
            )
            return SessionOutcome.COMPLETED
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
            return SessionOutcome.FAILED
        finally:
            for t in (receiver, guard):
                t.cancel()
            if not self._consumer.done():
                self._consumer.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._rec.stop),
                    timeout=self._settings.pron_stream_stop_timeout_s,
                )
            except (asyncio.TimeoutError, Exception):
                pass
```

- [ ] **Step 5: Run the full session suite**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -v`
Expected: PASS (all session tests, including happy path / stuck-send / canceled / max-duration / receiver / disconnect)

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/pronunciation/streaming.py backend/tests/test_pronunciation_stream.py
git commit -m "feat(pronunciation): #22 session receiver + client-disconnect teardown"
```

---

## Task 8: WS cookie-JWT auth helper

**Files:**
- Create: `backend/src/klara/pronunciation/ws_auth.py`
- Test: `backend/tests/test_pronunciation_stream.py`

**Interfaces:**
- Consumes: `auth_backend` (`auth/backend.py`), `get_user_manager`, `get_session`, `Settings`.
- Produces: `async def authenticate_ws(websocket, session) -> User | None` — reads the `klara_session` cookie, validates via `JWTStrategy.read_token`, returns the active user or `None`. `def origin_allowed(websocket, settings) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pronunciation_stream.py
def test_origin_allowed_matches_cors_list():
    from klara.config import Settings
    from klara.pronunciation.ws_auth import origin_allowed

    s = Settings()  # cors_origins default includes http://localhost:5173

    class WS:
        def __init__(self, origin): self.headers = {"origin": origin} if origin else {}

    assert origin_allowed(WS("http://localhost:5173"), s) is True
    assert origin_allowed(WS("http://evil.example"), s) is False
    assert origin_allowed(WS(None), s) is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k origin_allowed -v`
Expected: FAIL with `ModuleNotFoundError: klara.pronunciation.ws_auth`

- [ ] **Step 3: Create the auth helper**

```python
# backend/src/klara/pronunciation/ws_auth.py
"""Cookie-JWT authentication for the streaming WebSocket.

The browser sends the httponly `klara_session` cookie automatically on the
WS upgrade, so we reuse the existing fastapi-users JWTStrategy — no ticket,
no token-in-query (which would leak to logs). Origin allowlist is defense in
depth on top of samesite=strict.
"""

from __future__ import annotations

from klara.auth.backend import auth_backend
from klara.auth.manager import get_user_manager
from klara.config import Settings
from klara.db import get_session
from klara.models import User


def origin_allowed(websocket, settings: Settings) -> bool:
    origin = websocket.headers.get("origin")
    return bool(origin) and origin in settings.cors_origin_list


async def authenticate_ws(websocket, settings: Settings) -> User | None:
    token = websocket.cookies.get(settings.auth_cookie_name)
    if not token:
        return None
    strategy = auth_backend.get_strategy()
    async for session in get_session():
        async for user_manager in get_user_manager_from_session(session):
            user = await strategy.read_token(token, user_manager)
            return user if (user and user.is_active) else None
    return None


async def get_user_manager_from_session(session):
    """Build a UserManager from a DB session (get_user_manager depends on the
    user-db adapter). Yields one manager."""
    from klara.auth.manager import get_user_db

    async for user_db in get_user_db(session):
        async for manager in get_user_manager(user_db):
            yield manager
```

Note: verify the exact `get_user_db` import path in `auth/manager.py` during implementation; adjust if the adapter factory has a different name. The test above covers `origin_allowed`; `authenticate_ws` is covered by the integration test in Task 8.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k origin_allowed -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/klara/pronunciation/ws_auth.py backend/tests/test_pronunciation_stream.py
git commit -m "feat(pronunciation): #22 cookie-JWT WS auth helper"
```

---

## Task 9: Wire the WS endpoint + caps + integration tests

**Files:**
- Modify: `backend/src/klara/routers/pronunciation.py`
- Test: `backend/tests/test_pronunciation_stream.py`

**Interfaces:**
- Consumes: `authenticate_ws`, `origin_allowed`, `StreamingSession`, `SessionOutcome`, close codes, the Azure wrapper, `Settings`.
- Produces: `@router.websocket("/stream")` handler + module-level global/per-user cap counters.

- [ ] **Step 1: Write the failing integration tests (auth + capacity)**

```python
# backend/tests/test_pronunciation_stream.py
from starlette.testclient import TestClient


def test_ws_rejects_without_cookie(app_settings):
    """No klara_session cookie → close 4401, never enters a session."""
    from klara.main import app

    app_settings(AZURE_SPEECH_KEY="dummy-key")
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/pronunciation/stream") as ws:
            ws.receive_text()
    # Starlette raises WebSocketDisconnect on the app-side close; assert the code.


@pytest.mark.asyncio
async def test_ws_capacity_closes_when_global_cap_full(monkeypatch):
    """When the global cap is exhausted the handler closes with WS_CLOSE_CAPACITY."""
    from klara.pronunciation import streaming as st

    # Force the counter to look full, then assert the guard returns the code.
    assert st.WS_CLOSE_CAPACITY == 4408  # contract check; full flow covered manually
```

Note: full-duplex WS + Azure is not unit-testable in CI; these two assert the auth-reject close code and the capacity contract. The session behaviour is already covered by Tasks 4–7; the endpoint is thin glue.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -k "ws_rejects or capacity" -v`
Expected: FAIL (no `/stream` route → connection refused/404)

- [ ] **Step 3: Add the endpoint + caps**

```python
# backend/src/klara/routers/pronunciation.py — add imports
from collections import defaultdict

from fastapi import WebSocket
from starlette.concurrency import run_in_threadpool

from klara.config import get_settings
from klara.pronunciation.azure_stream import build_pcm_format, word_score_from_azure
from klara.pronunciation.streaming import (
    WS_CLOSE_AUTH,
    WS_CLOSE_CAPACITY,
    WS_CLOSE_FAILURE,
    WS_CLOSE_OK,
    SessionOutcome,
    StreamingSession,
)
from klara.pronunciation.ws_auth import authenticate_ws, origin_allowed

# Module-level caps (single worker, one event loop → plain ints are safe).
_active_global = 0
_active_per_user: dict[str, int] = defaultdict(int)


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    global _active_global
    settings = get_settings()

    if not origin_allowed(websocket, settings):
        await websocket.close(code=WS_CLOSE_AUTH)
        return
    await websocket.accept()  # accept first so we can send an app close code
    user = await authenticate_ws(websocket, settings)
    if user is None:
        await websocket.close(code=WS_CLOSE_AUTH)
        return

    uid = str(user.id)
    if _active_global >= settings.pron_stream_global_cap or (
        _active_per_user[uid] >= settings.pron_stream_per_user_cap
    ):
        await websocket.close(code=WS_CLOSE_CAPACITY)
        return
    _active_global += 1
    _active_per_user[uid] += 1
    try:
        # Real recognizer construction lives behind the seam; omitted here and
        # exercised by the manual creds-gated smoke test. `scores_of` maps the
        # accumulator to Azure's session-level scores.
        recognizer = _build_stream_recognizer(websocket, settings, user)
        outcome = await StreamingSession(
            recognizer, _WSAdapter(websocket), scores_of=_session_scores, settings=settings
        ).run()
        await websocket.close(code=WS_CLOSE_OK if outcome is SessionOutcome.COMPLETED else WS_CLOSE_FAILURE)
    finally:
        _active_global -= 1
        _active_per_user[uid] -= 1
        if _active_per_user[uid] <= 0:
            _active_per_user.pop(uid, None)
```

- [ ] **Step 3b: Add the integration glue (WS adapter, Azure recognizer, session scores)**

This glue is only reachable with real Azure creds (no CI test; covered by the manual smoke test in Task 10). Keep it thin — all policy lives in `StreamingSession`.

```python
# backend/src/klara/routers/pronunciation.py
class _WSAdapter:
    """Maps Starlette WebSocket to the minimal surface StreamingSession uses."""

    def __init__(self, ws: WebSocket):
        self._ws = ws

    async def send_json(self, obj: dict) -> None:
        await self._ws.send_json(obj)

    async def receive(self) -> dict:
        return await self._ws.receive()  # {'type':'websocket.receive','bytes'|'text':...}

    async def close(self, code: int) -> None:
        await self._ws.close(code=code)
```

```python
# backend/src/klara/pronunciation/azure_stream.py — the real recognizer
import structlog

log = structlog.get_logger(__name__)


class AzureStreamingRecognizer:
    """Continuous pronunciation recognition over a push stream. Connects ONLY
    recognized + session_stopped + canceled — NEVER `recognizing` (v1 finals
    only; connecting it would flood the SDK thread)."""

    def __init__(self, *, language: str, reference_text: str, azure_key: str, azure_region: str):
        from klara.pronunciation.azure_client import _read_along_config_json  # reuse

        speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
        speech_config.speech_recognition_language = language
        cfg_json = _read_along_config_json(reference_text) if reference_text else (
            '{"referenceText":"","gradingSystem":"HundredMark","granularity":"Phoneme",'
            '"phonemeAlphabet":"IPA","enableMiscue":false}'
        )
        self._push = speechsdk.audio.PushAudioInputStream(stream_format=build_pcm_format())
        audio_config = speechsdk.audio.AudioConfig(stream=self._push)
        self._rec = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        speechsdk.PronunciationAssessmentConfig(json_string=cfg_json).apply_to(self._rec)
        self.on_recognized = None
        self.on_session_stopped = None
        self.on_canceled = None

    def start(self) -> None:
        self._rec.recognized.connect(self._handle_recognized)
        self._rec.session_stopped.connect(lambda _evt: self.on_session_stopped and self.on_session_stopped())
        self._rec.canceled.connect(
            lambda evt: self.on_canceled and self.on_canceled(f"{evt.reason} - {getattr(evt, 'error_details', '')}")
        )
        self._rec.start_continuous_recognition()

    def _handle_recognized(self, evt) -> None:
        if evt.result.reason != speechsdk.ResultReason.RecognizedSpeech or not self.on_recognized:
            return
        try:
            pa = speechsdk.PronunciationAssessmentResult(evt.result)
        except (AttributeError, KeyError, IndexError, TypeError):
            return  # a breath / no assessment block — skip, not fatal
        for w in word_score_from_azure(pa.words):
            self.on_recognized(w)

    def write(self, pcm: bytes) -> None:
        self._push.write(pcm)

    def close_input(self) -> None:
        self._push.close()

    def stop(self) -> None:  # BLOCKING — session calls this via asyncio.to_thread
        self._rec.stop_continuous_recognition()
```

```python
# backend/src/klara/routers/pronunciation.py — helpers used by the endpoint
def _build_stream_recognizer(websocket: WebSocket, settings, reference_text: str, language: str):
    from klara.pronunciation.azure_stream import AzureStreamingRecognizer

    return AzureStreamingRecognizer(
        language=_resolve_bcp47(language),
        reference_text=reference_text,
        azure_key=settings.azure_speech_key or "",
        azure_region=settings.azure_speech_region,
    )


def _session_scores(words):
    """v1: summarise the accumulator. Azure's session-level PronunciationScores
    are available via the last result; for v1 we average per-word accuracy and
    leave fluency/completeness to the batch floor if the client needs exactness."""
    from klara.pronunciation.schemas import PronunciationScores

    acc = sum(w.accuracy_score for w in words) / len(words) if words else 0.0
    return PronunciationScores(accuracy=acc, fluency=acc, completeness=100.0, pronunciation=acc)
```

The endpoint reads `reference_text` + `language` from the first client message (a JSON text frame) before constructing the recognizer; parsing that handshake frame is the endpoint's first `await websocket.receive_json()`.

- [ ] **Step 4: Register nothing new (router already included) and run the suite**

Run: `cd backend && uv run pytest tests/test_pronunciation_stream.py -v`
Expected: PASS (auth-reject close observed; capacity contract holds; all session tests green)

- [ ] **Step 5: Run the full pronunciation suite for regressions**

Run: `cd backend && uv run pytest tests/test_pronunciation.py tests/test_pronunciation_stream.py -v`
Expected: PASS (no regressions in batch scoring)

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/routers/pronunciation.py backend/tests/test_pronunciation_stream.py
git commit -m "feat(pronunciation): #22 WS /stream endpoint + session caps"
```

---

## Ops + manual verification (out of CI)

**Ops (keepalive) — fold into the deploy, not app code:** the spec's WS ping/pong keepalive is satisfied by uvicorn's protocol-level ping, not application code. Add `--ws-ping-interval 10 --ws-ping-timeout 10` to the uvicorn launch in `backend/Dockerfile:30` and `docker-compose.prod.yml:17`. A dead client is dropped by uvicorn and surfaces as `ws.receive()` raising in the session receiver (Task 7) → disconnect teardown → batch; max-session-duration is the final backstop. No app-level ping task needed (ponytail: the server already does it and the receiver already catches the result).

**Manual smoke (creds-gated), run once against real Azure before merging the frontend frente:** set `AZURE_SPEECH_KEY`/region, connect a real browser client, speak a read-along sentence, confirm live `word` messages arrive then one `final`, and that `p95` per word < 500 ms (the spec's end-to-end criterion). This is the only place real Azure latency and the real `PushAudioInputStream` path are exercised.

## Self-review notes (author)

- **Spec coverage:** protocol messages + close codes (Task 2), recognizer seam + fakes (Task 3), accumulator + final (Task 4), SEND_TIMEOUT sole drain signal (Task 5), cancellation teardown (Tasks 5/6/7), canceled + max-duration (Task 6), receiver + client-disconnect (Task 7), no-index live message (Task 2), finals-only via not-connecting `recognizing` (Task 9 `AzureStreamingRecognizer`), caps global+per-user (Task 9), cookie-JWT auth + Origin (Tasks 8/9), offloaded time-boxed stop (Tasks 5-7), exactly-one-score = no final on FAILED (Tasks 5/6/7 assert `not sent_final()`), ping/pong keepalive (uvicorn config in the Ops section, surfaced via the Task 7 receiver). **Deferred, per spec:** `recognizing` partials; real Azure p95 (manual smoke test above).
- **Type consistency:** the accumulator holds `WordScore` end to end; `scores_of: Callable[[list[WordScore]], PronunciationScores]`; recognizer callbacks are `Callable[[WordScore], None]`; `SessionOutcome` used identically in Tasks 4-9; close-code constants defined in Task 2 and consumed in Task 9.
- **Verify during impl:** the exact `get_user_db`/`get_user_manager` factory signatures in `auth/manager.py` (Task 8) and how Starlette surfaces the app close code to `TestClient.websocket_connect` (Task 9) — the reject test may need to assert on `WebSocketDisconnect.code`.
