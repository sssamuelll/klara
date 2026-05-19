import { api } from "../api/client";
import type { PronunciationScoreResponse, WordScore } from "../api/types";

export type ScoreBand = "good" | "ok" | "bad";

/**
 * Azure accuracy_score ranges 0-100. The UI buckets it into three bands so
 * the same color-coding the simulator used keeps working unchanged.
 */
export function scoreBand(accuracy: number): ScoreBand {
  if (accuracy >= 80) return "good";
  if (accuracy >= 60) return "ok";
  return "bad";
}

/**
 * Tokenize the reference text the same way SentenceView does. Returns the
 * index of every word token (skipping spaces and punctuation), so the result
 * lines up with what SentenceView renders.
 */
export function wordTokenIndices(text: string): number[] {
  const re = /(\s+)|([.,!?;:„""»«()¡¿—–\-]+)|([^\s.,!?;:„""»«()¡¿—–\-]+)/g;
  const out: number[] = [];
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[3]) out.push(i);
    i++;
  }
  return out;
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
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
  // without touching the MediaRecorder. fftSize 64 gives 32 frequency bins,
  // matching the handoff's 16 visible bars after we pair-average.
  const AudioCtx = (window.AudioContext ||
    (window as unknown as { webkitAudioContext: typeof AudioContext })
      .webkitAudioContext) as typeof AudioContext;
  const audioCtx = new AudioCtx();
  const source = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 64;
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
    recorder.onstart = () => resolve({ stop, cancel, analyser });
    recorder.start();
  });
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
    const msg = e instanceof Error ? e.message : String(e);
    // ApiError stringifies as `${status}: ${detail}` — parse status back out.
    const m = msg.match(/^(\d{3})/);
    const status = m ? parseInt(m[1], 10) : 0;
    let kind: PronunciationErrorKind = "unknown";
    if (status === 422) kind = "no_speech";
    else if (status === 413) kind = "audio_too_large";
    else if (status === 400) kind = "audio_undecodable";
    else if (status === 503) kind = "service_unavailable";
    else if (status === 0) kind = "network";
    const err: PronunciationError = { kind, detail: msg };
    throw err;
  }
}
