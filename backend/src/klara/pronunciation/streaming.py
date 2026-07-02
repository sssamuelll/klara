"""#22 live pronunciation streaming: session transport + backpressure policy.

See docs/superpowers/specs/2026-07-01-22-streaming-backpressure-design.md.
The concurrency-risky logic lives here and is tested against a fake recognizer
+ fake websocket (no Azure). Bridge A only; teardown by cancellation.
"""

from __future__ import annotations

import asyncio
import enum
from collections.abc import Callable

from klara.pronunciation.azure_stream import StreamingRecognizer
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


class SessionOutcome(enum.Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class StreamingSession:
    """Owns one recognizer + one websocket for the life of a pronunciation
    stream. Bridge A only: SDK-thread callbacks marshal onto the loop via
    call_soon_threadsafe — never run_coroutine_threadsafe(...).result(),
    which would deadlock the SDK thread against the consumer it feeds."""

    def __init__(
        self,
        recognizer: StreamingRecognizer,
        websocket,
        *,
        scores_of: Callable[[list[WordScore]], PronunciationScores],
        settings,
    ):
        self._rec = recognizer
        self._ws = websocket
        self._scores_of = scores_of
        self._settings = settings
        self._loop = asyncio.get_running_loop()
        self._queue: asyncio.Queue = asyncio.Queue()  # unbounded by design
        self._acc: list[WordScore] = []
        self._stopped = asyncio.Event()

    def _on_recognized(self, w: WordScore) -> None:  # SDK thread
        self._acc.append(w)  # accumulator: never dropped
        self._loop.call_soon_threadsafe(self._queue.put_nowait, w)

    def _on_session_stopped(self) -> None:  # SDK thread
        self._loop.call_soon_threadsafe(self._stopped.set)

    async def _consume(self) -> None:
        while not (self._stopped.is_set() and self._queue.empty()):
            try:
                w = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except TimeoutError:
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
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._rec.stop),
                    timeout=self._settings.pron_stream_stop_timeout_s,
                )
            except (TimeoutError, Exception):
                # An uncancellable wedged stop must not clobber the session
                # outcome; the caller releases the cap slot regardless (spec).
                pass
