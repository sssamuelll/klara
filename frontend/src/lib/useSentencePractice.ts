/**
 * Per-sentence pronunciation orchestration, extracted verbatim from
 * Story.tsx so both the reading view (Story) and the standalone Practice
 * ("Pronunciar") session share one mic → STT → scoring → hints lifecycle.
 *
 * What lives here (and previously lived inline in Story.tsx):
 *   - playback (TTS) play/pause + speed cycling
 *   - mic recording lifecycle (start / stop / cancel) + live analyser
 *   - silence-detector auto-stop wiring
 *   - Azure scoring → per-token bands, with a simulated fallback on 503
 *   - phonetic-hints fetch (best-effort)
 *   - feedback / evaluating state, keyed by sentence index
 *   - keyboard: SPACE play/pause · M hold-to-talk · ←/→ navigate · ESC cancel
 *
 * SentenceView stays presentational and is unchanged: it consumes the flat
 * props this hook exposes (recording, evaluating, feedback, rate, the
 * handlers, etc.). The host component (Story / PracticeSession) owns
 * navigation and decides what to render around the SentenceView.
 *
 * Two integration points are parameterised so the queue source can differ:
 *   - `persistTargets`: a per-item array, indexed identically to `sentences`.
 *     Each entry is `{ storyId, sentenceIndex }` when that line is a real story
 *     sentence (a scored take is POSTed to that story's pronunciation-attempts
 *     endpoint, best-effort), or `null` when it isn't (Practice's `example_target`
 *     fallback items) → that take is not persisted. `sentenceIndex` is the index
 *     INTO the origin story, which in a Practice queue is NOT the item's queue
 *     position — persisting the queue position would corrupt the struggled
 *     grouping the backend reads. In the reading view (Story) the two coincide.
 *     Omit entirely (or pass undefined) to persist nothing at all.
 *   - the caller supplies the sentence list + target language.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { PronunciationScoreResponse, WordScore } from "../api/types";
import {
  bandsByTokenIndex,
  scoreAudio,
  scoreBand,
  startMicRecording,
  worstBadWord,
  type MicRecorder,
  type PronunciationError,
  type ScoreBand,
} from "./pronunciation";
import { startPcmCapture, pcmStreamingSupported } from "./pcmCapture";
import { createAligner } from "./streamAlign";
import { openScoreStream, type ScoreStream } from "./streamClient";
import { startSilenceDetector } from "./silenceDetector";
import { speak, stop, useTTS } from "./tts";

export type PronScores = Record<number, ScoreBand>;

/** Minimal sentence shape the hook needs. `target` is the text scored/spoken. */
export interface PracticeSentence {
  target: string;
}

// Cuando estás aprendiendo, lo que falta es más lento — nunca más rápido.
// El pill cicla entre normal y 0.7× (toggle binario). Mismo contrato que
// tenía Story.tsx antes de la extracción.
const RATES = [0.7, 1] as const;
export type Rate = (typeof RATES)[number];

// Word-token regex shared with SentenceView; used to extract bad-word
// strings for the phonetic-hints request and the simulated fallback.
const WORD_RE = /(\s+)|([.,!?;:„“”»«()¡¿—–\-]+)|([^\s.,!?;:„“”»«()¡¿—–\-]+)/g;

function badWordsFromBands(text: string, bands: PronScores): string[] {
  const out: string[] = [];
  let i = 0;
  let m: RegExpExecArray | null;
  WORD_RE.lastIndex = 0;
  while ((m = WORD_RE.exec(text)) !== null) {
    if (m[3] && bands[i] === "bad") out.push(m[3]);
    i++;
  }
  return out;
}

// Fallback used only if the backend signals it can't score (e.g. 503 because
// no Azure key in dev). Produces simulated bands keyed by FULL token index
// so the UI still feels alive.
function simulatedBands(text: string): PronScores {
  const out: PronScores = {};
  let i = 0;
  let m: RegExpExecArray | null;
  WORD_RE.lastIndex = 0;
  while ((m = WORD_RE.exec(text)) !== null) {
    if (m[3]) {
      const r = Math.random();
      out[i] = r < 0.62 ? "good" : r < 0.88 ? "ok" : "bad";
    }
    i++;
  }
  return out;
}

/**
 * Where a scored take is persisted: the origin story and the index of this
 * line WITHIN that story (`Story.content.sentences[sentenceIndex]`). NOT a
 * queue position — see `persistTargets` below.
 */
export interface PersistTarget {
  storyId: string;
  sentenceIndex: number;
}

export interface UseSentencePracticeArgs {
  /** Sentences in order; `target` is scored + spoken. */
  sentences: PracticeSentence[];
  /** Target language code (e.g. "de"). */
  targetLanguage: string;
  /**
   * Per-item persistence targets, indexed identically to `sentences`. A
   * non-null entry persists that line's scored take (best-effort,
   * fire-and-forget) to its origin story at its ORIGINAL story index; a `null`
   * entry (e.g. a Practice `example_target` fallback) persists nothing for that
   * item. Omit / undefined → persist nothing at all.
   */
  persistTargets?: Array<PersistTarget | null>;
  /**
   * Called when navigation would advance past the last sentence (Story →
   * finish screen, Practice → summary phase). The host owns what happens.
   */
  onFinish: () => void;
  /**
   * Disable the global keyboard listeners (e.g. while a different phase is
   * showing). Defaults to enabled.
   */
  keyboardEnabled?: boolean;
}

export interface UseSentencePractice {
  currentIndex: number;
  total: number;
  rate: Rate;

  // Per-current-sentence derived state (what SentenceView consumes)
  recording: boolean;
  evaluating: boolean;
  feedback: PronScores | undefined;
  /** Live streaming bands for the sentence being recorded (undefined otherwise). */
  liveBands: PronScores | undefined;
  phoneticHints: Record<string, string> | undefined;
  diagnosis?: { word: string; tip: string };
  /** True while the /diagnose request for the current sentence is in-flight. */
  diagnosing: boolean;
  micAnalyser: AnalyserNode | null;
  /** True when the *current* sentence is the one Klara is reading aloud. */
  sentencePlaying: boolean;
  /** TTS progress 0..1 for the current sentence (0 when not playing it). */
  progress: number;
  duration: number;

  pronError: PronunciationError | null;

  // Handlers (wired straight into SentenceView props)
  handlePlayPause: () => void;
  handleListenFromFeedback: () => void;
  cycleSpeed: () => void;
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<void>;
  cancelRecording: () => void;
  onRetry: () => void;
  goNext: () => void;
  goPrev: () => void;

  /** Reset everything to sentence 0, no feedback. For "restart" / "otra ronda". */
  reset: () => void;
  /** Stop any in-flight audio (call on host unmount). */
  stopAudio: () => void;

  // Aggregate, for summary / finish screens.
  scoresBySentence: Record<number, PronScores>;
  /** Índices cuyas bandas son simuladas (503) — excluir del cierre SRS. */
  simulatedIndices: Set<number>;
}

export function useSentencePractice({
  sentences,
  targetLanguage,
  persistTargets,
  onFinish,
  keyboardEnabled = true,
}: UseSentencePracticeArgs): UseSentencePractice {
  const total = sentences.length;

  const [currentIndex, setCurrentIndex] = useState(0);
  const [recordingIndex, setRecordingIndex] = useState<number | null>(null);
  const [evaluatingIndex, setEvaluatingIndex] = useState<number | null>(null);
  const [scoresBySentence, setScoresBySentence] = useState<Record<number, PronScores>>({});
  // Índices (queue position) cuyas bandas son SIMULADAS (Math.random, fallback de
  // 503 de Azure). Se EXCLUYEN del cierre de ciclo SRS — jamás reprograman cartas
  // reales con ruido (spec §6.1).
  const [simulatedIndices, setSimulatedIndices] = useState<Set<number>>(new Set());
  const [phoneticHintsBySentence, setPhoneticHintsBySentence] = useState<
    Record<number, Record<string, string>>
  >({});
  const [diagnosisBySentence, setDiagnosisBySentence] = useState<
    Record<number, { word: string; tip: string }>
  >({});
  const [diagnosingIndex, setDiagnosingIndex] = useState<number | null>(null);
  const [pronError, setPronError] = useState<PronunciationError | null>(null);
  const [rate, setRate] = useState<Rate>(1);
  const [micAnalyser, setMicAnalyser] = useState<AnalyserNode | null>(null);

  // While set, recorder is live; calling stop() returns the captured Blob.
  const recorderRef = useRef<MicRecorder | null>(null);
  const [liveBands, setLiveBands] = useState<PronScores>({});
  const streamRef = useRef<ScoreStream | null>(null);
  const pcmRef = useRef<{ stop(): void } | null>(null);

  const teardownStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
    pcmRef.current?.stop();
    pcmRef.current = null;
  }, []);

  const tts = useTTS();

  const current = sentences[currentIndex];

  // Which sentence (if any) is currently being read aloud by Klara?
  const playingIndex = useMemo(() => {
    if (!tts.text) return -1;
    return sentences.findIndex((s) => s.target === tts.text);
  }, [sentences, tts.text]);

  // Cleanup any in-flight recording when the component unmounts.
  useEffect(() => {
    return () => {
      recorderRef.current?.cancel();
      recorderRef.current = null;
      setMicAnalyser(null);
      teardownStream();
    };
  }, [teardownStream]);

  const handlePlayPause = useCallback(() => {
    if (!current) return;
    if (playingIndex === currentIndex && tts.playing) {
      stop();
    } else {
      speak(current.target, targetLanguage, { rate });
    }
  }, [current, currentIndex, playingIndex, rate, targetLanguage, tts.playing]);

  const handleListenFromFeedback = useCallback(() => {
    if (!current) return;
    speak(current.target, targetLanguage, { rate });
  }, [current, rate, targetLanguage]);

  const cycleSpeed = useCallback(() => {
    setRate((r) => {
      const idx = RATES.indexOf(r);
      return RATES[(idx + 1) % RATES.length];
    });
  }, []);

  const clearFeedback = useCallback(() => {
    setScoresBySentence((s) => {
      if (!(currentIndex in s)) return s;
      const next = { ...s };
      delete next[currentIndex];
      return next;
    });
    setPhoneticHintsBySentence((s) => {
      if (!(currentIndex in s)) return s;
      const next = { ...s };
      delete next[currentIndex];
      return next;
    });
    setDiagnosisBySentence((s) => {
      if (!(currentIndex in s)) return s;
      const next = { ...s };
      delete next[currentIndex];
      return next;
    });
    setSimulatedIndices((s) => {
      if (!s.has(currentIndex)) return s;
      const next = new Set(s);
      next.delete(currentIndex);
      return next;
    });
  }, [currentIndex]);

  const fetchAndStoreHints = useCallback(
    async (idx: number, sentenceText: string, bands: PronScores, language: string) => {
      const badWords = badWordsFromBands(sentenceText, bands);
      if (badWords.length === 0) return;
      try {
        const resp = await api.getPhoneticHints(badWords, language);
        if (Object.keys(resp.hints).length === 0) return;
        setPhoneticHintsBySentence((s) => ({ ...s, [idx]: resp.hints }));
      } catch {
        // best-effort: an empty hints map just means the verdict shows
        // without a phonetic tip.
      }
    },
    [],
  );

  const fetchAndStoreDiagnosis = useCallback(
    async (idx: number, words: WordScore[], language: string) => {
      const worst = worstBadWord(words);
      // Nothing to diagnose — skip entirely, don't enter loading state.
      if (!worst) return;
      setDiagnosingIndex(idx);
      let tip = "";
      try {
        const resp = await api.diagnose(worst.word, worst.phonemes, language);
        tip = resp.tip ?? "";
      } catch {
        // best-effort: no tip, the stress hint stays.
      }
      setDiagnosisBySentence((s) => ({ ...s, [idx]: { word: worst.word, tip } }));
      // Only clear if this sentence is still the one diagnosing (not superseded).
      setDiagnosingIndex((cur) => (cur === idx ? null : cur));
    },
    [],
  );

  const startRecording = useCallback(async () => {
    // Ignore if we're already recording or no sentence yet.
    if (recordingIndex !== null || !current) return;
    stop(); // any Klara playback stops when the mic opens
    clearFeedback();
    setPronError(null);
    try {
      const rec = await startMicRecording();
      recorderRef.current = rec;
      setMicAnalyser(rec.analyser);
      setRecordingIndex(currentIndex);
      setLiveBands({});
      // Live streaming is pure enhancement: any failure below leaves a
      // batch-pure session, silently (spec: batch iff no `final`).
      if (pcmStreamingSupported()) {
        try {
          const aligner = createAligner(current.target);
          const stream = openScoreStream({
            referenceText: current.target,
            language: targetLanguage,
            onWord: (w) => {
              if (streamRef.current !== stream) return; // stale post-EOS drain frame
              const idx = aligner(w.word, w.error_type);
              if (idx === null) return;
              const band = w.error_type === "Omission" ? "bad" : scoreBand(w.accuracy_score);
              setLiveBands((b) => ({ ...b, [idx]: band }));
            },
          });
          streamRef.current = stream;
          const pcm = await startPcmCapture(rec.stream, (chunk) => stream.sendChunk(chunk));
          if (streamRef.current !== stream) {
            pcm?.stop();
            return;
          }
          if (pcm) {
            pcmRef.current = pcm;
          } else {
            stream.close();
            streamRef.current = null;
          }
        } catch (e) {
          console.debug("pron_stream: setup failed, batch-pure", e);
          teardownStream();
        }
      }
    } catch (e) {
      setPronError(e as PronunciationError);
    }
  }, [clearFeedback, current, currentIndex, recordingIndex, targetLanguage, teardownStream]);

  const stopRecording = useCallback(async () => {
    const rec = recorderRef.current;
    if (rec === null || recordingIndex === null) return;
    const idxAtStart = recordingIndex;
    recorderRef.current = null;
    setRecordingIndex(null);
    setMicAnalyser(null);
    setEvaluatingIndex(idxAtStart);
    const stream = streamRef.current;
    streamRef.current = null;
    try {
      const blob = await rec.stop();
      pcmRef.current?.stop();
      pcmRef.current = null;
      if (!blob || blob.size === 0) {
        stream?.close();
        setPronError({ kind: "no_speech" });
        return;
      }
      const sentence = sentences[idxAtStart];
      if (!sentence) {
        stream?.close();
        return;
      }
      let resp: PronunciationScoreResponse | null = null;
      if (stream) {
        stream.sendEos();
        const final = await stream.result; // bounded: 8 s post-eos inside the client
        if (final) {
          resp = {
            recognized_text: final.words
              .filter((w) => w.error_type !== "Omission")
              .map((w) => w.word)
              .join(" "),
            reference_text: sentence.target,
            language: targetLanguage,
            scores: final.scores,
            words: final.words,
          };
        } else {
          console.debug("pron_stream: no final, falling back to batch");
        }
      }
      if (!resp) resp = await scoreAudio(blob, sentence.target, targetLanguage);
      const bands = bandsByTokenIndex(sentence.target, resp.words);
      setScoresBySentence((s) => ({ ...s, [idxAtStart]: bands }));
      setPronError(null);
      // Best-effort: persist the attempt so SRS + souvenir picker can use it
      // across sessions. Failure here doesn't affect the UX. We persist against
      // the line's ORIGIN story at its ORIGINAL story index — NOT idxAtStart
      // (the queue position), which only coincides with the story index in the
      // reading view. A null target (Practice `example_target` fallback, or no
      // targets supplied) persists nothing.
      const target = persistTargets?.[idxAtStart] ?? null;
      if (target) {
        void api
          .recordPronunciationAttempt(target.storyId, {
            sentence_index: target.sentenceIndex,
            reference_text: sentence.target,
            recognized_text: resp.recognized_text,
            // Pure phoneme accuracy, not Azure's compositum — see useMicScorer.
            overall_score: resp.scores.accuracy,
            word_bands: Object.fromEntries(
              Object.entries(bands).map(([k, v]) => [k, v]),
            ),
          })
          .catch(() => undefined);
      }
      // Fire-and-forget: hints arrive after the panel is already on screen.
      void fetchAndStoreHints(idxAtStart, sentence.target, bands, targetLanguage);
      void fetchAndStoreDiagnosis(idxAtStart, resp.words, targetLanguage);
    } catch (e) {
      const perr = e as PronunciationError;
      if (perr.kind === "service_unavailable") {
        const sentence = sentences[idxAtStart];
        if (sentence) {
          setScoresBySentence((s) => ({ ...s, [idxAtStart]: simulatedBands(sentence.target) }));
          setSimulatedIndices((s) => new Set(s).add(idxAtStart));
        }
        setPronError(null);
      } else {
        setPronError(perr);
      }
    } finally {
      setEvaluatingIndex(null);
      setLiveBands({});
    }
  }, [fetchAndStoreDiagnosis, fetchAndStoreHints, persistTargets, recordingIndex, sentences, targetLanguage]);

  const cancelRecording = useCallback(() => {
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setRecordingIndex(null);
    setMicAnalyser(null);
    teardownStream();
    setLiveBands({});
    setPronError(null);
  }, [teardownStream]);

  // Primary stop trigger for the sentence pronunciation flow: 1.5s of
  // silence (after a 800ms grace period) auto-stops the take. Manual
  // stops still work — clicking the mic again, pressing ESC, or
  // releasing M (hold-to-talk) all short-circuit ahead of the detector.
  // stopRecording is idempotent so a race between manual + auto is fine.
  useEffect(() => {
    if (recordingIndex === null || !micAnalyser) return;
    return startSilenceDetector(micAnalyser, () => {
      void stopRecording();
    });
  }, [recordingIndex, micAnalyser, stopRecording]);

  const goNext = useCallback(() => {
    if (currentIndex >= total - 1) {
      stop();
      onFinish();
      return;
    }
    stop();
    cancelRecording();
    setEvaluatingIndex(null);
    setCurrentIndex((i) => i + 1);
  }, [cancelRecording, currentIndex, onFinish, total]);

  const goPrev = useCallback(() => {
    if (currentIndex <= 0) return;
    stop();
    cancelRecording();
    setEvaluatingIndex(null);
    setCurrentIndex((i) => i - 1);
  }, [cancelRecording, currentIndex]);

  const onRetry = useCallback(() => {
    clearFeedback();
    // The retry button doesn't start recording immediately — user holds the
    // mic (or presses M) to re-attempt. This matches the hold-to-talk model.
  }, [clearFeedback]);

  const reset = useCallback(() => {
    stop();
    cancelRecording();
    setEvaluatingIndex(null);
    setCurrentIndex(0);
    setScoresBySentence({});
    setPhoneticHintsBySentence({});
    setDiagnosisBySentence({});
    setDiagnosingIndex(null);
    setSimulatedIndices(new Set());
    setPronError(null);
  }, [cancelRecording]);

  const stopAudio = useCallback(() => {
    stop();
  }, []);

  // Keyboard: SPACE play/pause · M hold-to-talk · ←/→ navigate · ESC cancel
  useEffect(() => {
    if (!keyboardEnabled) return;
    function isTypingTarget(el: EventTarget | null): boolean {
      if (!(el instanceof HTMLElement)) return false;
      return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable;
    }
    function onKey(e: KeyboardEvent) {
      if (isTypingTarget(e.target)) return;
      if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      } else if (e.key === " ") {
        e.preventDefault();
        handlePlayPause();
      } else if (e.key === "m" || e.key === "M") {
        // Hold-to-talk: ignore autorepeat firings of keydown.
        if (e.repeat) return;
        e.preventDefault();
        void startRecording();
      } else if (e.key === "Escape") {
        e.preventDefault();
        if (recordingIndex !== null) cancelRecording();
        else if (currentIndex in scoresBySentence) clearFeedback();
      }
    }
    function onKeyUp(e: KeyboardEvent) {
      if (isTypingTarget(e.target)) return;
      if (e.key === "m" || e.key === "M") {
        e.preventDefault();
        void stopRecording();
      }
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [
    cancelRecording,
    clearFeedback,
    currentIndex,
    goNext,
    goPrev,
    handlePlayPause,
    keyboardEnabled,
    recordingIndex,
    scoresBySentence,
    startRecording,
    stopRecording,
  ]);

  const recording = recordingIndex === currentIndex;
  const evaluating = evaluatingIndex === currentIndex;
  const feedback = scoresBySentence[currentIndex];
  const phoneticHints = phoneticHintsBySentence[currentIndex];
  const diagnosis = diagnosisBySentence[currentIndex];
  const sentencePlaying = playingIndex === currentIndex && tts.playing;

  return {
    currentIndex,
    total,
    rate,
    recording,
    evaluating,
    feedback,
    liveBands: recording ? liveBands : undefined,
    phoneticHints,
    diagnosis,
    diagnosing: diagnosingIndex === currentIndex,
    micAnalyser: recording ? micAnalyser : null,
    sentencePlaying,
    progress: sentencePlaying ? tts.progress : 0,
    duration: tts.duration,
    pronError,
    handlePlayPause,
    handleListenFromFeedback,
    cycleSpeed,
    startRecording,
    stopRecording,
    cancelRecording,
    onRetry,
    goNext,
    goPrev,
    reset,
    stopAudio,
    scoresBySentence,
    simulatedIndices,
  };
}
