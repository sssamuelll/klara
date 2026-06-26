"""Thin wrapper over Azure AI Speech Pronunciation Assessment.

Synchronous SDK calls — the FastAPI routes run them in a threadpool via
`run_in_threadpool` so they don't block the event loop.

Two modes:
- `score_pronunciation` — read-along: scores against a known reference text,
  with PhraseListGrammar biasing the recognizer toward the expected words.
- `score_unscripted` — free conversation (Speak): no reference, no phrase
  bias, IPA phoneme alphabet, and Azure's end-of-utterance segmentation
  stretched to match the frontend VAD so multi-clause answers survive.
"""

from __future__ import annotations

import json
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


def _read_along_config_json(reference_text: str) -> str:
    """Read-along assessment config as a json_string so phonemeAlphabet can be
    set to IPA (the SDK constructor has no kwarg for it). IPA keeps the
    read-along phonemes consistent with score_unscripted and lets the
    diagnose prompt reason over real symbols. enable_miscue stays False: in
    read-along the learner is reading the reference, so miscue detection mostly
    mis-flags accent variation and tanks the score."""
    return json.dumps(
        {
            "referenceText": _sanitize_reference(reference_text),
            "gradingSystem": "HundredMark",
            "granularity": "Phoneme",
            "phonemeAlphabet": "IPA",
            "enableMiscue": False,
        }
    )


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

    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        json_string=_read_along_config_json(reference_text)
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
    return _result_to_response(result, reference_text=reference_text, language=language)


#: Azure's default end-of-utterance segmentation fires after a few hundred ms
#: of silence — fine for read-along sentences, fatal for conversation: an A0
#: learner pauses between clauses, recognize_once stops at the first pause,
#: and the rest of the answer is silently discarded. The frontend VAD closes
#: the mic after 1.5s of silence (silenceDetector.ts), so Azure's idea of
#: "the turn is over" must be at least as patient.
_SEGMENTATION_SILENCE_MS = "1500"


def score_unscripted(
    wav_path: Path,
    language: str,
    *,
    azure_key: str,
    azure_region: str,
) -> tuple[ScoreResponse, float | None]:
    """Assess free-form speech: recognize + score without a reference text.

    Returns (response, recognition_confidence). Confidence is NBest[0] from
    the raw result JSON (0-1), or None if Azure didn't include it — callers
    use it to avoid showing corrections built on a fabricated transcript.
    """
    speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
    speech_config.speech_recognition_language = language
    speech_config.set_property(
        speechsdk.PropertyId.Speech_SegmentationSilenceTimeoutMs, _SEGMENTATION_SILENCE_MS
    )
    # The raw JSON carries NBest confidence; request the detailed shape.
    speech_config.output_format = speechsdk.OutputFormat.Detailed

    audio_config = speechsdk.audio.AudioConfig(filename=str(wav_path))

    # json_string form: phonemeAlphabet has no kwarg in the SDK constructor.
    # IPA so the focus-phoneme matching ("ü" = /y/ + /ʏ/) sees real symbols,
    # not Azure's default SAPI names. No reference, no miscue, no PhraseList —
    # we don't know what the user will say, and biasing toward anything would
    # fabricate recognitions.
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        json_string=json.dumps(
            {
                "referenceText": "",
                "gradingSystem": "HundredMark",
                "granularity": "Phoneme",
                "phonemeAlphabet": "IPA",
                "enableMiscue": False,
            }
        )
    )

    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    pronunciation_config.apply_to(recognizer)

    result = recognizer.recognize_once()
    response = _result_to_response(result, reference_text="", language=language)
    return response, _recognition_confidence(result)


def _result_to_response(
    result: speechsdk.SpeechRecognitionResult,
    *,
    reference_text: str,
    language: str,
) -> ScoreResponse:
    if result.reason == speechsdk.ResultReason.NoMatch:
        raise AzureSpeechError("No speech detected in the audio.", recoverable=True)
    if result.reason == speechsdk.ResultReason.Canceled:
        details = speechsdk.CancellationDetails(result)
        raise AzureSpeechError(
            f"Azure cancelled the request: {details.reason} - {details.error_details}"
        )
    if result.reason != speechsdk.ResultReason.RecognizedSpeech:
        raise AzureSpeechError(f"Unexpected result: {result.reason}")

    # The SDK's PronunciationAssessmentResult sets its attributes ONLY when
    # the result JSON contains a PronunciationAssessment/Words block — no
    # class-level defaults. A RecognizedSpeech result with empty text (a
    # breath) can omit them, turning attribute reads into AttributeError /
    # KeyError deep in the SDK. That's a no-speech turn, not a server error.
    try:
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
        scores = PronunciationScores(
            accuracy=pa.accuracy_score,
            fluency=pa.fluency_score,
            completeness=pa.completeness_score,
            pronunciation=pa.pronunciation_score,
        )
    except (AttributeError, KeyError, IndexError, TypeError) as e:
        raise AzureSpeechError(
            f"Recognition carried no assessment data: {e!r}", recoverable=True
        ) from e

    return ScoreResponse(
        recognized_text=result.text,
        reference_text=reference_text,
        language=language,
        scores=scores,
        words=words,
    )


def _recognition_confidence(result: speechsdk.SpeechRecognitionResult) -> float | None:
    """Best-effort NBest[0].Confidence from the raw result JSON."""
    try:
        raw = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
        if not raw:
            return None
        nbest = json.loads(raw).get("NBest") or []
        confidence = nbest[0].get("Confidence") if nbest else None
        return float(confidence) if confidence is not None else None
    except Exception:
        return None
