import { api, ApiError } from "../api/client";
import type { PronunciationScoreResponse, WordScore } from "../api/types";

export type ScoreBand = "good" | "ok" | "bad";

/**
 * Azure accuracy_score ranges 0-100. The UI buckets it into three bands.
 *
 * Thresholds were 80/60 originally — calibrated as if for native speakers.
 * Users reported (issue #40) that the 80/60 cut was firing false `bad`
 * tags on words that sounded fine, undermining trust in the feedback.
 * Comparable learner apps (Speakly, Babbel) use ~70/45 instead. Moved
 * here too. If a real native says a word at accuracy 75, that's still
 * "good" — anyone above 70 is plenty intelligible at A0-B1 levels.
 */
export function scoreBand(accuracy: number): ScoreBand {
  if (accuracy >= 70) return "good";
  if (accuracy >= 45) return "ok";
  return "bad";
}

// Clase de puntuación canónica del repo. DEBE coincidir byte a byte con
// backend services/tokens.py `_PUNCT`, o los índices de word_bands se desalinean
// entre cliente y servidor. Codepoints: . , ! ? ; : „(U+201E) "(U+201C) "(U+201D)
// »(U+00BB) «(U+00AB) ( ) ¡(U+00A1) ¿(U+00BF) —(U+2014) –(U+2013) -.
const WORD_PUNCT = ".,!?;:„“”»«()¡¿—–\\-";
const WORD_RE_SRC = `(\\s+)|([${WORD_PUNCT}]+)|([^\\s${WORD_PUNCT}]+)`;

/**
 * Tokenize the reference text the same way SentenceView does. Returns the
 * index of every word token (skipping spaces and punctuation), so the result
 * lines up with what SentenceView renders.
 */
export function wordTokenIndices(text: string): number[] {
  const re = new RegExp(WORD_RE_SRC, "g");
  const out: number[] = [];
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[3]) out.push(i);
    i++;
  }
  return out;
}

/** {índice_global_de_token: palabra} — espeja backend word_tokens_by_index. */
export function wordTokensByIndex(text: string): Record<number, string> {
  const re = new RegExp(WORD_RE_SRC, "g");
  const out: Record<number, string> = {};
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[3]) out[i] = m[3];
    i++;
  }
  return out;
}

const BAND_RANK: Record<ScoreBand, number> = { bad: 0, ok: 1, good: 2 };

/** La peor banda presente, o null. Espeja backend worst_band. */
export function worstBand(bands: Record<number, ScoreBand>): ScoreBand | null {
  const vals = Object.values(bands);
  if (vals.length === 0) return null;
  return vals.reduce((w, b) => (BAND_RANK[b] < BAND_RANK[w] ? b : w));
}

/** Banda de la palabra-foco con fallback a la peor banda de la frase (spec D3). */
export function focusBand(
  text: string,
  focusText: string,
  bands: Record<number, ScoreBand>,
): ScoreBand | null {
  const target = focusText.toLowerCase();
  const tokens = wordTokensByIndex(text);
  for (const [idx, word] of Object.entries(tokens)) {
    if (word.toLowerCase() === target) {
      const b = bands[Number(idx)];
      if (b) return b;
      break;
    }
  }
  return worstBand(bands);
}

/** The lowest-scoring word that bands as "bad" and has at least one phoneme,
 *  or null if none qualifies. Words with no phonemes are skipped so we never
 *  POST phonemes:[] → 422 to the diagnose endpoint. */
export function worstBadWord(words: WordScore[]): WordScore | null {
  let worst: WordScore | null = null;
  for (const w of words) {
    if (scoreBand(w.accuracy_score) !== "bad") continue;
    if (w.phonemes.length === 0) continue;
    if (worst === null || w.accuracy_score < worst.accuracy_score) worst = w;
  }
  return worst;
}

/**
 * Map an Azure response back to one band per reference-text word token.
 *
 * Azure returns one entry per *recognized* word — insertions add entries
 * not in the reference, omissions remove entries that were expected.
 * We filter out insertions, then pair the remaining N entries with the
 * N reference word tokens; if Azure returned fewer, the trailing tokens
 * stay unmapped (rendered as no-score).
 */
export function bandsByTokenIndex(
  text: string,
  words: WordScore[],
): Record<number, ScoreBand> {
  const tokenIdxs = wordTokenIndices(text);
  const expected = words.filter((w) => w.error_type !== "Insertion");
  const out: Record<number, ScoreBand> = {};
  const n = Math.min(tokenIdxs.length, expected.length);
  for (let i = 0; i < n; i++) {
    const w = expected[i];
    if (w.error_type === "Omission") {
      out[tokenIdxs[i]] = "bad";
    } else {
      out[tokenIdxs[i]] = scoreBand(w.accuracy_score);
    }
  }
  return out;
}

export type PronunciationErrorKind =
  | "mic_denied"
  | "mic_unavailable"
  | "no_speech"
  | "audio_too_large"
  | "audio_undecodable"
  | "service_unavailable"
  | "scoring_failed"
  | "network"
  | "unknown";

export interface PronunciationError {
  kind: PronunciationErrorKind;
  detail?: string;
}

export interface MicRecorder {
  stop: () => Promise<Blob>;
  cancel: () => void;
  /**
   * AnalyserNode wired to the mic stream. Read frequency / time-domain data
   * each frame to visualize the live waveform. Disconnects automatically
   * when stop() or cancel() fires.
   */
  analyser: AnalyserNode;
  /** The underlying mic stream — the live-streaming PCM capture hangs off it. */
  stream: MediaStream;
}

/**
 * Single-shot: opens the mic, returns a stop() function. Caller stops the
 * recording when the user clicks again (or after a timeout), receives the
 * Blob, and uploads it. Also exposes an AnalyserNode so the UI can render
 * a live waveform driven by the actual voice signal.
 */
export async function startMicRecording(): Promise<MicRecorder> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
    const err: PronunciationError = { kind: "mic_unavailable" };
    throw err;
  }
  let stream: MediaStream;
  try {
    // Ask the browser for mono @ 16kHz to match what Azure ultimately
    // consumes after ffmpeg transcodes. Browsers may decline (some default
    // to 48kHz stereo) but requesting it saves a downsample step when they
    // do honour it, and channelCount=1 is widely respected. Keep NS / EC /
    // AGC at browser defaults — most users aren't recording in studios.
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, sampleRate: 16000 },
    });
  } catch (e) {
    const err: PronunciationError = {
      kind: "mic_denied",
      detail: e instanceof Error ? e.message : String(e),
    };
    throw err;
  }
  // Pick a mime type the browser actually supports; Azure-side ffmpeg
  // handles all of these. Webm/opus is the default on modern browsers.
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  const mimeType =
    candidates.find((m) => (window as any).MediaRecorder?.isTypeSupported?.(m)) ??
    "audio/webm";

  // AnalyserNode lives on its own AudioContext so we can tear it down
  // without touching the MediaRecorder.
  //
  // fftSize was 64 (1.5ms of audio per read @ 44.1kHz) — fine for the visual
  // bars but useless for RMS-based silence detection because each read sees
  // a microscopic slice and RMS oscillates wildly. Bumped to 1024 (~23ms
  // per read) so the same AnalyserNode powers both:
  //   - 16 visible bars (binsPerBar = frequencyBinCount/16 = 32)
  //   - getByteTimeDomainData → stable RMS for silence detection
  const AudioCtx = (window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext })
      .webkitAudioContext) as typeof AudioContext;
  const audioCtx = new AudioCtx();
  const source = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 1024;
  analyser.smoothingTimeConstant = 0.6;
  source.connect(analyser);

  const chunks: Blob[] = [];
  const recorder = new MediaRecorder(stream, { mimeType });
  recorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) chunks.push(e.data);
  };

  return new Promise((resolve) => {
    const cleanup = () => {
      try {
        source.disconnect();
      } catch {
        // already disconnected
      }
      void audioCtx.close?.();
      for (const t of stream.getTracks()) t.stop();
    };
    const stop = (): Promise<Blob> =>
      new Promise<Blob>((res) => {
        recorder.onstop = () => {
          cleanup();
          res(new Blob(chunks, { type: mimeType }));
        };
        if (recorder.state !== "inactive") recorder.stop();
        else {
          cleanup();
          res(new Blob(chunks, { type: mimeType }));
        }
      });
    const cancel = () => {
      try {
        if (recorder.state !== "inactive") recorder.stop();
      } finally {
        cleanup();
      }
    };
    recorder.onstart = () => resolve({ stop, cancel, analyser, stream });
    recorder.start();
  });
}

/**
 * Translate a thrown score-request error into a PronunciationError the UI
 * can render with a translation key. Classifies on ApiError.status — NOT on
 * the message text, which carries the backend's localized `detail` and used
 * to defeat the old regex parse (every detail-bearing error, including the
 * backend's own 502, showed up as "you appear to be offline").
 *
 * 502/504 get their own kind instead of "service_unavailable" because that
 * kind triggers the simulated-score fallback in useSentencePractice — a real
 * upstream failure must surface as an error, not as fake scores.
 */
export function classifyScoreError(e: unknown): PronunciationError {
  if (e instanceof ApiError) {
    const detail = e.message;
    switch (e.status) {
      case 422:
        return { kind: "no_speech", detail };
      case 413:
        return { kind: "audio_too_large", detail };
      case 400:
        return { kind: "audio_undecodable", detail };
      case 503:
        return { kind: "service_unavailable", detail };
      case 502:
      case 504:
        return { kind: "scoring_failed", detail };
      default:
        return { kind: "unknown", detail };
    }
  }
  // fetch() rejects with a TypeError when the request never left or never
  // completed — the only case where "you appear to be offline" is honest.
  if (e instanceof TypeError) {
    return { kind: "network", detail: e.message };
  }
  return { kind: "unknown", detail: e instanceof Error ? e.message : String(e) };
}

/**
 * POST audio + reference to the backend and translate the HTTP error into
 * a PronunciationError the UI can render with a translation key.
 */
export async function scoreAudio(
  audio: Blob,
  referenceText: string,
  language: string,
): Promise<PronunciationScoreResponse> {
  try {
    return await api.scorePronunciation(audio, referenceText, language);
  } catch (e) {
    throw classifyScoreError(e);
  }
}
