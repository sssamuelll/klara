"""Spike for #22 — Azure continuous-recognition -> asyncio bridge under concurrency.

Question (frozen #22 / Halcyon brief): when live pronunciation streaming runs N
concurrent WebSocket sessions on Klara's *single* uvicorn event loop, does the
sync-callback -> asyncio bridge survive, or does it deadlock / drop events / leak
threads?

Context from the repo: Klara today only ever calls Azure via a blocking
recognize_once() inside run_in_threadpool (one thread per request, no callbacks).
#22 introduces the *continuous* pattern: PushAudioInputStream +
start_continuous_recognition(), where Azure fires `recognized` events on its own
internal thread and each event must be marshalled onto the event loop to be sent
over the WebSocket. That marshalling is the bridge, and it is net-new code with no
prior art in the repo (no asyncio.Queue / call_soon_threadsafe / run_coroutine_threadsafe
anywhere today).

No Azure creds, no network. FakeContinuousRecognizer reproduces the two parts of the
SDK threading contract that actually break bridges:

  1. `recognized` handlers run serially on ONE internal thread (not the loop).
  2. stop_continuous_recognition() BLOCKS until the in-flight handler returns
     (real SDK: unbounded block; here: a timeout we report as "would deadlock").

Two candidate bridges, identical except for the marshalling call, are run under the
same load and compared:

  Bridge A (non-blocking): loop.call_soon_threadsafe(offer, evt)  -> bounded Queue,
                           drop-oldest on overflow (explicit backpressure).
  Bridge B (blocking):     asyncio.run_coroutine_threadsafe(q.put(evt), loop).result()
                           -> the SDK thread blocks on the loop.

WHAT THIS SPIKE PROVES: which marshalling *primitive* to ship (A, not B). B's
SDK-thread-blocking .result() is a genuine circular-wait deadlock + thread leak
under backpressure; A's non-blocking call_soon_threadsafe is not.

WHAT IT DOES *NOT* DISCHARGE (still keeps #22 frozen — audited by marcus-halberg):
  - drop-oldest is a *liveness* trick, not correctness: it silently loses `recognized`
    events, i.e. per-word scores. For a scoring feature that's a product defect, not
    graceful degradation. The right backpressure policy for #22 is an open DESIGN
    question (never-drop + monitor? gap-marker to the client? cap sessions?).
  - the bounded Queue bounds the queue, NOT the loop's ready-deque: call_soon_threadsafe
    onto a *CPU-blocked* loop still grows loop._ready unbounded. Not tested here.
  - no `canceled` event (Azure's error/teardown path), no ws.send() backpressure, no
    client-disconnect/teardown races, no N>>20, no real Azure round-trip latency.
  - the p95 below is *bridge-hop overhead only* (~1-2ms). It is NOT end-to-end latency
    and must NOT be cited against #22's "p95 < 500ms/word" (that budget is dominated
    by Azure cloud recognition, untested here).

Run:  python spike_22_streaming_bridge.py    (exits non-zero if any check fails)

ponytail: this is a throwaway de-risking spike, not shipped code. It proves WHICH
bridge pattern to ship, then it can be deleted (or kept under backend/spikes/ as the
#22 "spike validated" artifact).
"""

from __future__ import annotations

import asyncio
import statistics
import threading
import time
from dataclasses import dataclass, field

# --- knobs -----------------------------------------------------------------
SDK_THREAD_NAME = "sdk-callback"
QUEUE_MAXSIZE = 8            # bounded per-session queue == the backpressure boundary
STOP_JOIN_TIMEOUT = 1.0     # stands in for the SDK's *unbounded* stop() block
WORDS = [f"wort{i}" for i in range(12)]

# healthy scenario: consumer keeps up, correct (offloaded) stop
HEALTHY_SESSIONS = 20
HEALTHY_CADENCE = 0.03

# stall scenario: consumer parked, natural on-loop stop() -> exposes B
STALL_SESSIONS = 5
STALL_CADENCE = 0.02
STALL_FEED_TIME = 0.6       # > CADENCE*(QUEUE_MAXSIZE+1): queue fills before stop
CONSUMER_START_DELAY = 5.0  # consumer stays parked through the whole stop attempt


# --- fake SDK (faithful to the dangerous parts of the contract) ------------
@dataclass
class RecognizedEvent:
    word: str
    accuracy_score: float
    error_type: str
    offset_ms: int
    duration_ms: int
    fired_at: float = 0.0   # perf_counter at the moment the SDK thread fired it


class EventSignal:
    """Mimics speechsdk.EventSignal: connect(handler); SDK fires it on its thread."""

    def __init__(self) -> None:
        self._handlers: list = []

    def connect(self, handler) -> None:
        self._handlers.append(handler)

    def _fire(self, evt) -> None:
        for h in self._handlers:
            h(evt)


class FakeContinuousRecognizer:
    """ponytail: a fake, but faithful to the two SDK behaviours that wedge bridges —
    callbacks on a private *serial* thread, and a *blocking* stop(). Not a full SDK."""

    def __init__(self, words: list[str], cadence: float) -> None:
        self.recognized = EventSignal()
        self.session_stopped = EventSignal()
        self._words = words
        self._cadence = cadence
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start_continuous_recognition(self) -> None:
        self._thread = threading.Thread(target=self._run, name=SDK_THREAD_NAME, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        for i, w in enumerate(self._words):
            if self._stop.is_set():
                break
            time.sleep(self._cadence)
            evt = RecognizedEvent(
                word=w, accuracy_score=90.0, error_type="None",
                offset_ms=i * 300, duration_ms=280, fired_at=time.perf_counter(),
            )
            self.recognized._fire(evt)      # <-- the bridge runs HERE, on this thread
        self.session_stopped._fire(None)

    def stop_continuous_recognition(self) -> None:
        self._stop.set()
        assert self._thread is not None
        self._thread.join(STOP_JOIN_TIMEOUT)
        if self._thread.is_alive():
            # Real SDK would block here forever waiting for the wedged callback.
            raise TimeoutError("stop_continuous_recognition() wedged: in-flight callback never returned")


# --- per-session bookkeeping ----------------------------------------------
@dataclass
class SessionStats:
    latencies: list[float] = field(default_factory=list)
    delivered: int = 0
    dropped: int = 0
    wedged: bool = False


def _offer_drop_oldest(q: asyncio.Queue, evt: RecognizedEvent, stats: SessionStats) -> None:
    """Runs on the loop thread (via call_soon_threadsafe), so put_nowait is safe."""
    try:
        q.put_nowait(evt)
    except asyncio.QueueFull:
        try:
            q.get_nowait()
            stats.dropped += 1
        except asyncio.QueueEmpty:
            pass
        q.put_nowait(evt)


def make_bridge(variant: str, loop, q: asyncio.Queue, stopped: asyncio.Event, stats: SessionStats):
    if variant == "A":                                  # non-blocking marshal
        def on_recognized(evt: RecognizedEvent) -> None:
            loop.call_soon_threadsafe(_offer_drop_oldest, q, evt, stats)

        def on_stopped(_evt) -> None:
            loop.call_soon_threadsafe(stopped.set)

    elif variant == "B":                                # blocking marshal (the trap)
        def on_recognized(evt: RecognizedEvent) -> None:
            try:
                asyncio.run_coroutine_threadsafe(q.put(evt), loop).result()
            except Exception:
                pass  # only reached at loop-close teardown; the wedge is the *block* above
        def on_stopped(_evt) -> None:
            async def _set() -> None:
                stopped.set()
            try:
                asyncio.run_coroutine_threadsafe(_set(), loop).result()
            except Exception:
                pass
    else:
        raise ValueError(variant)

    return on_recognized, on_stopped


async def _consume(q: asyncio.Queue, stopped: asyncio.Event, stats: SessionStats,
                   start_delay: float = 0.0) -> None:
    if start_delay:
        await asyncio.sleep(start_delay)
    while not (stopped.is_set() and q.empty()):
        try:
            evt = await asyncio.wait_for(q.get(), timeout=0.2)
        except asyncio.TimeoutError:
            continue
        stats.latencies.append(time.perf_counter() - evt.fired_at)
        stats.delivered += 1


async def run_session(variant: str, cadence: float, scenario: str) -> SessionStats:
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    stopped = asyncio.Event()
    stats = SessionStats()
    rec = FakeContinuousRecognizer(WORDS, cadence)
    on_rec, on_stop = make_bridge(variant, loop, q, stopped, stats)
    rec.recognized.connect(on_rec)
    rec.session_stopped.connect(on_stop)

    if scenario == "healthy":
        consumer = asyncio.create_task(_consume(q, stopped, stats))
        rec.start_continuous_recognition()
        await stopped.wait()
        await loop.run_in_executor(None, rec.stop_continuous_recognition)   # offloaded == correct
        await consumer
    else:  # "stall": consumer parked + natural on-loop stop() (the easy mistake)
        consumer = asyncio.create_task(_consume(q, stopped, stats, CONSUMER_START_DELAY))
        rec.start_continuous_recognition()
        await asyncio.sleep(STALL_FEED_TIME)        # queue fills; bridge B wedges here
        try:
            rec.stop_continuous_recognition()        # <-- called ON the loop thread
        except TimeoutError:
            stats.wedged = True
        stopped.set()
        consumer.cancel()
    return stats


async def run_fleet(variant: str, cadence: float, scenario: str, n: int) -> list[SessionStats]:
    return await asyncio.gather(*(run_session(variant, cadence, scenario) for _ in range(n)))


# --- reporting -------------------------------------------------------------
def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    return sorted(xs)[min(len(xs) - 1, int(p / 100 * len(xs)))]


def summarize(tag: str, fleet: list[SessionStats]) -> dict:
    lat = [x * 1000 for s in fleet for x in s.latencies]  # ms
    row = {
        "tag": tag,
        "sessions": len(fleet),
        "delivered": sum(s.delivered for s in fleet),
        "expected": len(fleet) * len(WORDS),
        "dropped": sum(s.dropped for s in fleet),
        "wedged": sum(1 for s in fleet if s.wedged),
        "p50": _pct(lat, 50),
        "p95": _pct(lat, 95),
        "p99": _pct(lat, 99),
    }
    print(
        f"  {tag:<26} sessions={row['sessions']:<3} "
        f"delivered={row['delivered']}/{row['expected']:<5} "
        f"dropped={row['dropped']:<4} wedged={row['wedged']:<3} "
        f"lat_p50={row['p50']:.2f}ms p95={row['p95']:.2f}ms p99={row['p99']:.2f}ms"
    )
    return row


def zombie_sdk_threads() -> int:
    return sum(1 for t in threading.enumerate() if t.name == SDK_THREAD_NAME and t.is_alive())


async def main() -> int:
    print("SPIKE #22 -- continuous-recognition -> asyncio bridge, single event loop\n")

    print("HEALTHY load (consumer keeps up, offloaded stop):")
    h_a = summarize("A call_soon_threadsafe", await run_fleet("A", HEALTHY_CADENCE, "healthy", HEALTHY_SESSIONS))
    h_b = summarize("B run_coroutine.result()", await run_fleet("B", HEALTHY_CADENCE, "healthy", HEALTHY_SESSIONS))

    print("\nSTALL / backpressure (consumer parked, natural on-loop stop):")
    s_a = summarize("A call_soon_threadsafe", await run_fleet("A", STALL_CADENCE, "stall", STALL_SESSIONS))
    leak_a = zombie_sdk_threads()
    s_b = summarize("B run_coroutine.result()", await run_fleet("B", STALL_CADENCE, "stall", STALL_SESSIONS))
    leak_b = zombie_sdk_threads() - leak_a
    print(f"\n  zombie SDK threads left alive:  A={leak_a}   B={leak_b}")

    # --- self-check: the harness must actually distinguish the two bridges ---
    checks = [
        ("healthy/A delivers every event", h_a["delivered"] == h_a["expected"]),
        ("healthy/A marshal p95 < 50ms on one loop", 0 < h_a["p95"] < 50),
        ("stall/A stays live, no wedge", s_a["wedged"] == 0),
        ("stall/A leaks no SDK threads", leak_a == 0),
        # NB: dropping is A trading correctness for liveness. drops>0 confirms A degrades
        # by shedding (not deadlocking) -- it is NOT a sign A is production-safe. The
        # drop-oldest POLICY is a scoring-correctness defect #22 must still resolve.
        ("stall/A degrades by DROPPING words, not wedging (policy defect, see docstring)", s_a["dropped"] > 0),
        ("stall/B DEADLOCKS under backpressure", s_b["wedged"] > 0),
        ("stall/B leaks zombie SDK threads", leak_b > 0),
    ]
    print("\nchecks:")
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed

    verdict = (
        "PRIMITIVE settled: ship bridge A (non-blocking call_soon_threadsafe onto a bounded "
        "asyncio.Queue). AVOID bridge B (run_coroutine_threadsafe(...).result() from the SDK "
        "thread): real deadlock + thread leak under backpressure.\n"
        "         FEATURE NOT discharged: backpressure policy (drop vs never-drop), CPU-blocked-loop "
        "growth, canceled/disconnect teardown, N>>20, and real Azure latency are all UNTESTED. "
        "Keep #22 frozen on those; this spike only closes 'which bridge primitive'."
    )
    print("\nVERDICT:", verdict if ok else "INCONCLUSIVE -- a self-check failed, do not trust the numbers.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
