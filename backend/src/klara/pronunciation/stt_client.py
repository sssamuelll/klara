"""Plain speech-to-text via Azure SDK. Reuses the same SpeechRecognizer
without applying a PronunciationAssessmentConfig — the recogniser still
returns `result.text`, which is all we need for MC voice-pick.

Separate file from `azure_client.py` because the consumer (quiz MC) cares
about a transcript, not pronunciation accuracy. Mixing them in one
function with conditional logic was tempting but the call sites have
nothing in common beyond the SDK setup.
"""

from __future__ import annotations

from pathlib import Path

import azure.cognitiveservices.speech as speechsdk

from klara.pronunciation.azure_client import AzureSpeechError


def transcribe(
    wav_path: Path,
    language: str,
    *,
    azure_key: str,
    azure_region: str,
) -> str:
    """Return the recognised text, or raise AzureSpeechError on failure."""
    speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
    speech_config.speech_recognition_language = language
    audio_config = speechsdk.audio.AudioConfig(filename=str(wav_path))
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

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
    return result.text or ""
