"""Azure continuous pronunciation recognition, behind a tiny interface.

The interface (StreamingRecognizer) is what StreamingSession programs against,
so the session is testable with a fake. Real construction (SpeechConfig +
PushAudioInputStream) is thin glue exercised only under real Azure creds.

Callbacks fire on Azure SDK-internal threads. The session marshals them onto
the loop (bridge A); this module NEVER touches the event loop.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

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
    return speechsdk.audio.AudioStreamFormat(
        samples_per_second=16000, bits_per_sample=16, channels=1
    )


class AzureStreamingRecognizer:
    """Continuous pronunciation recognition over a push stream.

    Connects ONLY recognized + session_stopped + canceled — NEVER `recognizing`
    (v1 finals only; connecting it would flood the SDK thread).
    """

    def __init__(self, *, language: str, reference_text: str, azure_key: str, azure_region: str):
        from klara.pronunciation.azure_client import _read_along_config_json  # reuse

        speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
        speech_config.speech_recognition_language = language
        cfg_json = (
            _read_along_config_json(reference_text)
            if reference_text
            else (
                '{"referenceText":"","gradingSystem":"HundredMark","granularity":"Phoneme",'
                '"phonemeAlphabet":"IPA","enableMiscue":false}'
            )
        )
        self._push = speechsdk.audio.PushAudioInputStream(stream_format=build_pcm_format())
        audio_config = speechsdk.audio.AudioConfig(stream=self._push)
        self._rec = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config
        )
        speechsdk.PronunciationAssessmentConfig(json_string=cfg_json).apply_to(self._rec)
        self.on_recognized: Callable[[WordScore], None] | None = None
        self.on_session_stopped: Callable[[], None] | None = None
        self.on_canceled: Callable[[str], None] | None = None

    def start(self) -> None:
        self._rec.recognized.connect(self._handle_recognized)
        self._rec.session_stopped.connect(
            lambda _evt: self.on_session_stopped and self.on_session_stopped()
        )
        self._rec.canceled.connect(
            lambda evt: (
                self.on_canceled
                and self.on_canceled(f"{evt.reason} - {getattr(evt, 'error_details', '')}")
            )
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
