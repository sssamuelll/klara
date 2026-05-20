"""Thin wrapper over Azure AI Speech Pronunciation Assessment.

Synchronous SDK call — the FastAPI route runs it in a threadpool via
`run_in_threadpool` so it doesn't block the event loop.
"""

from __future__ import annotations

import re
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk

from klara.pronunciation.schemas import (
    PhonemeScore,
    PronunciationScores,
    ScoreResponse,
    WordScore,
)


class AzureSpeechError(RuntimeError):
    """Azure returned a non-success result.

    `recoverable=True` for "no speech detected" — the UI should ask the
    user to repeat. `recoverable=False` for genuine failures (auth, quota,
    region mismatch) that won't fix themselves on retry.
    """

    def __init__(self, message: str, *, recoverable: bool = False) -> None:
        super().__init__(message)
        self.recoverable = recoverable


# Outer punctuation Azure tokenises into phantom "words" (or that biases the
# PhraseListGrammar with garbage). We keep inner apostrophes/hyphens because
# they live inside real words (`l'eau`, `c'est`, `pão-de-mel`).
_OUTER_PUNCT_CHARS = "«»“”‘’„‚¡¿().,;:!?—–-"
_OUTER_PUNCT_RE = re.compile(f"[{re.escape(_OUTER_PUNCT_CHARS)}]+")


def _sanitize_reference(text: str) -> str:
    """Strip surrounding punctuation + collapse whitespace.

    Azure ignores most punctuation but mixed-quote characters and em dashes
    have caused alignment artefacts in the wild — better to feed it the bare
    phrase. Returned text still contains the original letters (incl. accents).
    """
    cleaned = _OUTER_PUNCT_RE.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def score_pronunciation(
    wav_path: Path,
    reference_text: str,
    language: str,
    *,
    azure_key: str,
    azure_region: str,
) -> ScoreResponse:
    speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
    speech_config.speech_recognition_language = language

    audio_config = speechsdk.audio.AudioConfig(filename=str(wav_path))

    sanitized_reference = _sanitize_reference(reference_text)

    # enable_miscue=False: in read-along mode the learner is always reading the
    # reference, so insertion/omission detection mostly mis-flags accent
    # variations as miscues and tanks the score. Without miscue, Azure still
    # returns phoneme-level accuracy — that's what the UI bands off of.
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=sanitized_reference,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=False,
    )

    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    pronunciation_config.apply_to(recognizer)

    # Bias the recogniser toward the words we expect — for non-native
    # speakers, mis-recognised words cascade into bad phoneme alignment and
    # systematically low accuracy. PhraseListGrammar tells the ASR "if you're
    # not sure, prefer these words".
    phrase_list = speechsdk.PhraseListGrammar.from_recognizer(recognizer)
    for word in sanitized_reference.split():
        if word:
            phrase_list.addPhrase(word)

    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.NoMatch:
        raise AzureSpeechError("No speech detected in the audio.", recoverable=True)
    if result.reason == speechsdk.ResultReason.Canceled:
        details = speechsdk.CancellationDetails(result)
        raise AzureSpeechError(
            f"Azure cancelled the request: {details.reason} - {details.error_details}"
        )
    if result.reason != speechsdk.ResultReason.RecognizedSpeech:
        raise AzureSpeechError(f"Unexpected result: {result.reason}")

    pa = speechsdk.PronunciationAssessmentResult(result)

    words = [
        WordScore(
            word=w.word,
            accuracy_score=w.accuracy_score,
            error_type=str(w.error_type),
            phonemes=[
                PhonemeScore(phoneme=p.phoneme, accuracy_score=p.accuracy_score)
                for p in (w.phonemes or [])
            ],
        )
        for w in pa.words
    ]

    return ScoreResponse(
        recognized_text=result.text,
        reference_text=reference_text,
        language=language,
        scores=PronunciationScores(
            accuracy=pa.accuracy_score,
            fluency=pa.fluency_score,
            completeness=pa.completeness_score,
            pronunciation=pa.pronunciation_score,
        ),
        words=words,
    )
