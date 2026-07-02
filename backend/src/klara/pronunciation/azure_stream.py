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
