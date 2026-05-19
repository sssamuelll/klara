/**
 * Waveform analysis for Klara's TTS audio.
 *
 * Fetches the audio for a given (text, lang) pair, decodes it via
 * OfflineAudioContext, and downsamples to 64 RMS buckets — those are what
 * the SentenceView's k-wave bars render. The audio bytes come from the same
 * /api/v1/tts endpoint the <audio> element plays from, so the browser HTTP
 * cache (Cache-Control: public, max-age=immutable on the response) dedupes
 * the two fetches into one network round-trip.
 *
 * Results are cached in memory for the lifetime of the SPA — the same
 * sentence read twice doesn't re-fetch + re-decode.
 */

const BARS = 64;
const cache = new Map<string, Promise<number[]>>();

function urlFor(text: string, lang?: string): string {
  const base = `/api/v1/tts?text=${encodeURIComponent(text)}`;
  return lang ? `${base}&lang=${encodeURIComponent(lang)}` : base;
}

function cacheKey(text: string, lang?: string): string {
  return `${lang ?? ""}:${text}`;
}

/**
 * Returns 64 normalized amplitudes (0–1) for the audio of `text` in `lang`.
 * Throws on network / decode failure — callers should treat that as "no
 * waveform available" and fall back to a flat / placeholder render.
 */
export function getWaveform(text: string, lang?: string): Promise<number[]> {
  const key = cacheKey(text, lang);
  const existing = cache.get(key);
  if (existing) return existing;

  const promise = (async () => {
    const resp = await fetch(urlFor(text, lang));
    if (!resp.ok) throw new Error(`tts fetch failed: ${resp.status}`);
    const buf = await resp.arrayBuffer();

    // Safari still ships webkitAudioContext as the only constructor.
    const Ctx = (window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext) as typeof AudioContext;
    if (!Ctx) throw new Error("AudioContext not supported");

    // Use OfflineAudioContext when available (cheaper, doesn't allocate hardware
    // output). Some browsers want the constructor invoked with explicit args.
    const tmp = new Ctx();
    let audioBuffer: AudioBuffer;
    try {
      audioBuffer = await tmp.decodeAudioData(buf.slice(0));
    } finally {
      void tmp.close?.();
    }

    return bucketize(audioBuffer, BARS);
  })().catch((err) => {
    // Drop failed entries so a retry has a chance — empty waveform isn't
    // worth caching forever.
    cache.delete(key);
    throw err;
  });

  cache.set(key, promise);
  return promise;
}

/**
 * Downsample the first channel of `audio` into `n` RMS buckets, normalized
 * so the peak bar is 1.0. RMS (vs. peak) is more perceptually accurate for
 * "how full is this slice of audio" — peak picks up clicks, RMS reflects
 * sustained loudness.
 */
function bucketize(audio: AudioBuffer, n: number): number[] {
  const data = audio.getChannelData(0);
  const bucketSize = Math.max(1, Math.floor(data.length / n));
  const rms: number[] = new Array(n).fill(0);
  for (let i = 0; i < n; i++) {
    const start = i * bucketSize;
    const end = Math.min(data.length, start + bucketSize);
    let sumSq = 0;
    for (let j = start; j < end; j++) {
      const s = data[j];
      sumSq += s * s;
    }
    rms[i] = Math.sqrt(sumSq / Math.max(1, end - start));
  }
  let max = 0;
  for (const v of rms) if (v > max) max = v;
  if (max === 0) return rms;
  // Floor at 0.12 so even silent bars still register visually (matches the
  // handoff's deterministic placeholder which kept a 0.12 floor).
  return rms.map((v) => Math.max(0.12, v / max));
}
