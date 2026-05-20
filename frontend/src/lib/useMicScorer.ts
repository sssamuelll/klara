/**
 * Single-shot mic recording + Azure pronunciation scoring.
 *
 * Used by the Finish quiz cards (Cloze, Shadow) so each card doesn't need
 * to re-implement the recorder lifecycle. The Sentence view uses the lower-
 * level startMicRecording directly because its UX is richer (hold-to-talk
 * with M key, ESC cancel, evaluating state shared with the parent).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { PronunciationScoreResponse, WordScore } from "../api/types";
import {
  bandsByTokenIndex,
  scoreAudio,
  startMicRecording,
  type MicRecorder,
  type PronunciationError,
  type ScoreBand,
} from "./pronunciation";
import { startSilenceDetector } from "./silenceDetector";

export type MicScorerPhase = "idle" | "recording" | "scoring" | "scored" | "error";

export interface MicScorerResult {
  overallScore: number;
  recognizedText: string;
  words: WordScore[];
  bands: Record<number, ScoreBand>;
  raw: PronunciationScoreResponse;
}

export interface UseMicScorer {
  phase: MicScorerPhase;
  analyser: AnalyserNode | null;
  result: MicScorerResult | null;
  error: PronunciationError | null;
  /** Start recording. No-op if already recording or scoring. */
  start: () => Promise<void>;
  /** Stop recording and trigger Azure scoring. */
  stop: () => Promise<void>;
  /** Cancel without scoring. */
  cancel: () => void;
  /** Reset to idle (clears result + error). For "try again" affordances. */
  reset: () => void;
}

// Safety net only — the silence detector usually stops well before this.
// Set high enough that even slow speakers reciting a full sentence finish
// inside it, but bounded so the recorder doesn't leak when something
// upstream of the detector misbehaves.
const HARD_TIMEOUT_MS = 20_000;

export function useMicScorer(
  referenceText: string,
  language: string,
): UseMicScorer {
  const [phase, setPhase] = useState<MicScorerPhase>("idle");
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const [result, setResult] = useState<MicScorerResult | null>(null);
  const [error, setError] = useState<PronunciationError | null>(null);
  const recorderRef = useRef<MicRecorder | null>(null);
  const autoStopRef = useRef<number | null>(null);
  const silenceCleanupRef = useRef<(() => void) | null>(null);
  const phaseRef = useRef<MicScorerPhase>("idle");
  phaseRef.current = phase;

  const clearTimers = useCallback(() => {
    if (autoStopRef.current !== null) {
      clearTimeout(autoStopRef.current);
      autoStopRef.current = null;
    }
    if (silenceCleanupRef.current !== null) {
      silenceCleanupRef.current();
      silenceCleanupRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    clearTimers();
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setAnalyser(null);
    setPhase("idle");
  }, [clearTimers]);

  const stop = useCallback(async () => {
    if (phaseRef.current !== "recording" || recorderRef.current === null) return;
    clearTimers();
    const rec = recorderRef.current;
    recorderRef.current = null;
    setAnalyser(null);
    setPhase("scoring");
    try {
      const blob = await rec.stop();
      if (!blob || blob.size === 0) {
        setError({ kind: "no_speech" });
        setPhase("error");
        return;
      }
      const resp = await scoreAudio(blob, referenceText, language);
      setResult({
        // Use pure phoneme accuracy, not Azure's `pronunciation` compositum
        // (which blends accuracy + fluency + completeness). Compositum was
        // penalising slow learners who paused between words — the user said
        // the right phonemes but the score said otherwise. Issue #40.
        overallScore: resp.scores.accuracy,
        recognizedText: resp.recognized_text,
        words: resp.words,
        bands: bandsByTokenIndex(referenceText, resp.words),
        raw: resp,
      });
      setError(null);
      setPhase("scored");
    } catch (e) {
      setError(e as PronunciationError);
      setPhase("error");
    }
  }, [clearTimers, language, referenceText]);

  const start = useCallback(async () => {
    if (phaseRef.current === "recording" || phaseRef.current === "scoring") return;
    setError(null);
    setResult(null);
    try {
      const rec = await startMicRecording();
      recorderRef.current = rec;
      setAnalyser(rec.analyser);
      setPhase("recording");
      // Primary stop trigger: 1.5s of silence after the user has had at
      // least 800ms to start speaking. Wrapped as a ref so cancel() /
      // stop() can tear it down without depending on this closure.
      silenceCleanupRef.current = startSilenceDetector(rec.analyser, () => {
        silenceCleanupRef.current = null;
        void stop();
      });
      // Safety net in case the detector misbehaves on a flaky mic.
      autoStopRef.current = window.setTimeout(() => {
        void stop();
      }, HARD_TIMEOUT_MS);
    } catch (e) {
      setError(e as PronunciationError);
      setPhase("error");
    }
  }, [stop]);

  const reset = useCallback(() => {
    cancel();
    setResult(null);
    setError(null);
    setPhase("idle");
  }, [cancel]);

  useEffect(() => {
    return () => {
      clearTimers();
      recorderRef.current?.cancel();
      recorderRef.current = null;
    };
  }, [clearTimers]);

  return { phase, analyser, result, error, start, stop, cancel, reset };
}
