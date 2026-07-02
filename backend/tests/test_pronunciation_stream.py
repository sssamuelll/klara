from __future__ import annotations

import asyncio
import threading
import time

import pytest

from klara.pronunciation.schemas import PronunciationScores, WordScore

FAKE_STOP_JOIN_TIMEOUT = 2.0  # stands in for the real SDK's *unbounded* stop() block — tests simulating in-flight callbacks slower than this will see stop() return early


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


class FakeStreamingRecognizer:
    """Honors the SDK contract that breaks bridges: callbacks fire serially on
    one internal thread; stop() blocks until the in-flight callback returns
    (via a bounded join — see FAKE_STOP_JOIN_TIMEOUT)."""

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
            self._thread.join(FAKE_STOP_JOIN_TIMEOUT)

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
