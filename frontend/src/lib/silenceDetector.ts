/**
 * Mic analysis on the time-domain signal: silence detection (VAD) plus the
 * live capture-quality level used by the recording pills.
 *
 * Both read the same RMS off the same AnalyserNode on the same animation
 * frame. They are one loop on purpose — a second RAF over the same buffer
 * would compute a number we already have.
 *
 * Why time-domain (not frequency): RMS over the raw samples gives a
 * stable amplitude readout. Frequency bins for the visualizer are too
 * noisy at instantaneous reads to compare against a threshold.
 *
 * Why no Silero/WebRTC VAD: ML-based VADs are more accurate but ship a
 * 2 MB+ model that runs in WASM. RMS is precise enough when the room
 * is quiet, which is the assumed use case for a learning app. Future
 * upgrade path is in issue #23 (option 2 → option 3).
 *
 * Why float samples (not getByteTimeDomainData): 8-bit time-domain data
 * quantizes at 1/128, whose own noise floor sits near -42 dBFS RMS. That
 * is inside the band the level meter has to judge — the backend gate
 * rejects below -45 dBFS — so a byte read cannot tell "too quiet" from
 * "quantization". At the VAD threshold (0.015 ≈ -36 dBFS) the two agree
 * to within 1.5%, so switching costs the silence detector nothing.
 *
 * Behaviour:
 *   - Polls the analyser on every animation frame.
 *   - Computes RMS and peak over the latest `fftSize` time-domain samples.
 *   - Tracks how long the RMS has been below `silenceThreshold` continuously.
 *   - Fires `onSilence` once that duration crosses `silenceDurationMs`,
 *     but only after `minRecordingMs` has elapsed since start
 *     (gives the user time to draw a breath without being cut off).
 *   - Fires `onLevel` on every *change* of the capture-quality verdict.
 *
 * Cleanup is idempotent and safe to call after the detector fired.
 */

/**
 * Capture-quality verdict for the live meter (issue #120, point 1).
 *
 *   silent — room tone only; the user has not spoken yet. Nothing to advise.
 *   quiet  — voice present but softer than the backend gate accepts.
 *   ok     — usable level.
 *   loud   — clipping; the signal is being destroyed before it leaves the mic.
 */
export type MicLevel = "silent" | "quiet" | "ok" | "loud";

export interface LevelClassifierOptions {
  /**
   * Frames below this read as room tone and do not move the verdict.
   * Default -50 dBFS.
   */
  floorDbfs?: number;
  /**
   * Speech held below this reads as too soft. Default -34 dBFS, which
   * leaves ~11 dB of headroom over the backend gate's -45 dBFS so the
   * user is warned before a take is rejected, not after.
   *
   * ponytail: fixed dBFS thresholds. A phone at the lips and a laptop at
   * arm's length differ by 20 dB or more, so this cannot be right for
   * both — per-device calibration is issue #120 point 4, which needs the
   * `audio_quality_measurements` corpus that started filling on
   * 2026-08-07. Until then these are options, not constants.
   */
  quietDbfs?: number;
  /** |sample| at or above this counts the frame as clipped. Default 0.98. */
  clipPeak?: number;
  /** Peak-hold fall time constant, ms. Default 800. */
  holdMs?: number;
  /** How long one clipped frame pins the verdict to "loud". Default 1200. */
  clipHoldMs?: number;
}

export interface LevelClassifier {
  /** Feed one frame; returns the current verdict. `dtMs` since last frame. */
  push: (rms: number, peak: number, dtMs: number) => MicLevel;
}

const dbfsToLinear = (db: number): number => Math.pow(10, db / 20);

/**
 * Translation key for the recording-pill label at a given verdict.
 *
 * "silent" keeps the plain "listening" copy on purpose: before the user
 * has made a sound there is nothing to correct, and an unprompted "speak
 * up" would be advice about a take that hasn't started.
 *
 * Lives here rather than in each pill so the four recording surfaces
 * cannot drift apart on what a verdict means.
 */
export function micLevelKey(level: MicLevel): string {
  return level === "silent"
    ? "story.sentence.listening"
    : `story.sentence.micLevel.${level}`;
}

/**
 * Turn a stream of per-frame (rms, peak) readings into a stable verdict.
 *
 * Pure and frame-rate independent so it can be tested without an
 * AnalyserNode or a real clock.
 *
 * Two behaviours earn their lines:
 *
 * 1. Peak-hold with exponential decay, not the instantaneous RMS. Speech
 *    is not a steady tone — judging each frame on its own would strobe
 *    the label between "quiet" and "ok" inside a single word.
 *
 * 2. Frames below the floor hold the previous verdict instead of decaying
 *    toward it. Without that, every pause between words drains the hold
 *    past `quiet` and tells someone who was merely breathing to speak up.
 */
export function createLevelClassifier(
  opts: LevelClassifierOptions = {},
): LevelClassifier {
  const floor = dbfsToLinear(opts.floorDbfs ?? -50);
  const quiet = dbfsToLinear(opts.quietDbfs ?? -34);
  const clipPeak = opts.clipPeak ?? 0.98;
  const holdMs = opts.holdMs ?? 800;
  const clipHoldMs = opts.clipHoldMs ?? 1200;

  let held = 0;
  let sinceClipMs = Number.POSITIVE_INFINITY;
  let level: MicLevel = "silent";

  return {
    push(rms, peak, dtMs) {
      sinceClipMs += dtMs;
      if (peak >= clipPeak) sinceClipMs = 0;
      // Clipping outranks level: a clipped take is unusable however loud
      // its RMS reads, and "back off" is the only useful advice.
      if (sinceClipMs <= clipHoldMs) {
        level = "loud";
        return level;
      }
      if (rms < floor) return level;
      held = Math.max(rms, held * Math.exp(-dtMs / holdMs));
      level = held < quiet ? "quiet" : "ok";
      return level;
    },
  };
}

export interface SilenceDetectorOptions {
  /**
   * RMS amplitude below which we consider it "silence" (0 → 1 scale).
   * Default 0.015 — comfortably above typical room hum, well below voice.
   */
  silenceThreshold?: number;
  /**
   * Sustained silence duration before triggering, in ms.
   * Default 1500 — enough to wait through natural pauses between words
   * but short enough that the user doesn't feel like the app is hung.
   */
  silenceDurationMs?: number;
  /**
   * Don't fire silence-stop in the first N ms after start. Defaults to
   * 800ms so the user has time to start talking after pressing mic.
   */
  minRecordingMs?: number;
  /**
   * Called whenever the capture-quality verdict changes (never per frame).
   * Omit it and no classifier is built.
   */
  onLevel?: (level: MicLevel) => void;
  /** Thresholds for `onLevel`. Ignored when `onLevel` is absent. */
  levelOptions?: LevelClassifierOptions;
}

export function startSilenceDetector(
  analyser: AnalyserNode,
  onSilence: () => void,
  opts: SilenceDetectorOptions = {},
): () => void {
  const silenceThreshold = opts.silenceThreshold ?? 0.015;
  const silenceDurationMs = opts.silenceDurationMs ?? 1500;
  const minRecordingMs = opts.minRecordingMs ?? 800;

  const onLevel = opts.onLevel;
  const classifier = onLevel ? createLevelClassifier(opts.levelOptions) : null;

  const buf = new Float32Array(analyser.fftSize);
  const startedAt = performance.now();
  let silenceStartedAt: number | null = null;
  let lastFrameAt = startedAt;
  let lastLevel: MicLevel = "silent";
  let raf = 0;
  let fired = false;

  const tick = () => {
    analyser.getFloatTimeDomainData(buf);
    let sumSq = 0;
    let peak = 0;
    for (let i = 0; i < buf.length; i++) {
      const s = buf[i];
      sumSq += s * s;
      const mag = Math.abs(s);
      if (mag > peak) peak = mag;
    }
    const rms = Math.sqrt(sumSq / buf.length);

    const now = performance.now();
    const elapsed = now - startedAt;

    if (classifier && onLevel) {
      const level = classifier.push(rms, peak, now - lastFrameAt);
      // Only on change: React state setters hang off this, and 60 of them
      // a second would re-render every recording pill for no new information.
      if (level !== lastLevel) {
        lastLevel = level;
        onLevel(level);
      }
    }
    lastFrameAt = now;

    if (rms < silenceThreshold) {
      if (silenceStartedAt === null) silenceStartedAt = now;
      const silenceDur = now - silenceStartedAt;
      if (silenceDur >= silenceDurationMs && elapsed >= minRecordingMs) {
        fired = true;
        // Synchronous: cancel our own RAF before handing off.
        cancelAnimationFrame(raf);
        onSilence();
        return;
      }
    } else {
      silenceStartedAt = null;
    }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);

  return () => {
    if (fired) return;
    cancelAnimationFrame(raf);
  };
}
