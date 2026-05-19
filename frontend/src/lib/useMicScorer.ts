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

const AUTO_STOP_MS = 5000;

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
  const phaseRef = useRef<MicScorerPhase>("idle");
  phaseRef.current = phase;

  const clearAutoStop = useCallback(() => {
    if (autoStopRef.current !== null) {
      clearTimeout(autoStopRef.current);
      autoStopRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    clearAutoStop();
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setAnalyser(null);
    setPhase("idle");
  }, [clearAutoStop]);

  const stop = useCallback(async () => {
    if (phaseRef.current !== "recording" || recorderRef.current === null) return;
    clearAutoStop();
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
        overallScore: resp.scores.pronunciation,
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
  }, [clearAutoStop, language, referenceText]);

  const start = useCallback(async () => {
    if (phaseRef.current === "recording" || phaseRef.current === "scoring") return;
    setError(null);
    setResult(null);
    try {
      const rec = await startMicRecording();
      recorderRef.current = rec;
      setAnalyser(rec.analyser);
      setPhase("recording");
      autoStopRef.current = window.setTimeout(() => {
        void stop();
      }, AUTO_STOP_MS);
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
      clearAutoStop();
      recorderRef.current?.cancel();
      recorderRef.current = null;
    };
  }, [clearAutoStop]);

  return { phase, analyser, result, error, start, stop, cancel, reset };
}
