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
