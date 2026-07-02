/**
 * AudioWorklet PCM capture for the live pronunciation stream. Hangs off the
 * SAME MediaStream that startMicRecording owns (one mic permission, one
 * getUserMedia). Produces 16 kHz mono Int16 chunks of 200 ms.
 *
 * Every failure returns null → the session silently stays batch-pure.
 */

export const PCM_SAMPLE_RATE = 16000;
export const CHUNK_SAMPLES = 3200; // 200 ms @ 16 kHz

/** Reference implementation; the worklet mirrors this loop (it cannot import). */
export function floatTo16BitPCM(input: Float32Array): Int16Array {
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = Math.round(s < 0 ? s * 0x8000 : s * 0x7fff);
  }
  return out;
}

export function pcmStreamingSupported(): boolean {
  return (
    typeof AudioWorkletNode !== "undefined" && typeof WebSocket !== "undefined"
  );
}

export async function startPcmCapture(
  stream: MediaStream,
  onChunk: (chunk: ArrayBuffer) => void,
): Promise<{ stop(): void } | null> {
  if (!pcmStreamingSupported()) return null;
  let ctx: AudioContext;
  try {
    ctx = new AudioContext({ sampleRate: PCM_SAMPLE_RATE });
  } catch (e) {
    console.debug("pron_stream: 16kHz AudioContext unavailable", e);
    return null;
  }
  // Some platforms ignore the requested rate and force the hardware rate.
  if (ctx.sampleRate !== PCM_SAMPLE_RATE) {
    console.debug("pron_stream: context rate", ctx.sampleRate, "!= 16000");
    void ctx.close();
    return null;
  }
  // Some engines (Safari) hand back a suspended context in async
  // continuations of the user gesture — the worklet never processes, so
  // resume it here, or bail cleanly (zero chunks, batch-pure).
  if (ctx.state !== "running") {
    try {
      await ctx.resume();
    } catch {
      // fall through to the state check
    }
  }
  if (ctx.state !== "running") {
    console.debug("pron_stream: AudioContext not running", ctx.state);
    void ctx.close();
    return null;
  }
  try {
    await ctx.audioWorklet.addModule(new URL("./pcmWorklet.js", import.meta.url));
  } catch (e) {
    console.debug("pron_stream: worklet load failed", e);
    void ctx.close();
    return null;
  }
  let source: MediaStreamAudioSourceNode;
  let node: AudioWorkletNode;
  try {
    source = ctx.createMediaStreamSource(stream);
    node = new AudioWorkletNode(ctx, "pcm-chunker");
    node.port.onmessage = (e: MessageEvent) => onChunk(e.data as ArrayBuffer);
    source.connect(node);
    // The worklet outputs silence; connecting to destination keeps the graph
    // pulled so process() actually runs.
    node.connect(ctx.destination);
  } catch (e) {
    console.debug("pron_stream: audio graph construction failed", e);
    void ctx.close();
    return null;
  }
  return {
    stop() {
      try {
        source.disconnect();
        node.disconnect();
      } catch {
        // already torn down
      }
      node.port.onmessage = null;
      void ctx.close();
    },
  };
}
