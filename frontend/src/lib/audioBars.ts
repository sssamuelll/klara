/**
 * Drive a row of bar elements from an AnalyserNode's frequency data.
 *
 * Used by the recording pills in SentenceView, Cloze, Shadow, and MC
 * cards. All four had the same RAF loop inlined; sharing it here keeps
 * the bucketing math correct when the analyser's fftSize changes.
 *
 * `bars.length` is whatever the caller renders (currently always 16).
 * Bins-per-bar adapts so the visualization stays correct regardless of
 * the analyser's bin count.
 */

export function startAudioBars(
  analyser: AnalyserNode,
  bars: HTMLElement[],
): () => void {
  if (bars.length === 0) return () => undefined;
  const buf = new Uint8Array(analyser.frequencyBinCount);
  const binsPerBar = Math.max(1, Math.floor(analyser.frequencyBinCount / bars.length));
  let raf = 0;
  const tick = () => {
    analyser.getByteFrequencyData(buf);
    for (let i = 0; i < bars.length; i++) {
      let sum = 0;
      for (let j = 0; j < binsPerBar; j++) {
        sum += buf[i * binsPerBar + j] ?? 0;
      }
      // Floor at 0.05 so silence still shows a flat line instead of bars
      // collapsing to zero.
      const v = Math.max(0.05, sum / binsPerBar / 255);
      const el = bars[i];
      if (el) el.style.height = `${(v * 100).toFixed(0)}%`;
    }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}
