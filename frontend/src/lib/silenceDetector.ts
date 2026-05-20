/**
 * Voice Activity Detection via RMS threshold on the time-domain signal.
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
 * Behaviour:
 *   - Polls the analyser on every animation frame.
 *   - Computes RMS over the latest `fftSize` time-domain samples.
 *   - Tracks how long the RMS has been below `silenceThreshold` continuously.
 *   - Fires `onSilence` once that duration crosses `silenceDurationMs`,
 *     but only after `minRecordingMs` has elapsed since start
 *     (gives the user time to draw a breath without being cut off).
 *
 * Cleanup is idempotent and safe to call after the detector fired.
 */

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
}

export function startSilenceDetector(
  analyser: AnalyserNode,
  onSilence: () => void,
  opts: SilenceDetectorOptions = {},
): () => void {
  const silenceThreshold = opts.silenceThreshold ?? 0.015;
  const silenceDurationMs = opts.silenceDurationMs ?? 1500;
  const minRecordingMs = opts.minRecordingMs ?? 800;

  const buf = new Uint8Array(analyser.fftSize);
  const startedAt = performance.now();
  let silenceStartedAt: number | null = null;
  let raf = 0;
  let fired = false;

  const tick = () => {
    analyser.getByteTimeDomainData(buf);
    // Time-domain samples are unsigned bytes centered at 128. Convert to
    // signed -1..1 and compute RMS.
    let sumSq = 0;
    for (let i = 0; i < buf.length; i++) {
      const s = (buf[i] - 128) / 128;
      sumSq += s * s;
    }
    const rms = Math.sqrt(sumSq / buf.length);

    const now = performance.now();
    const elapsed = now - startedAt;

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
