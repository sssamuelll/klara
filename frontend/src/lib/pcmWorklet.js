/* AudioWorklet module — fetched by URL, runs in the worklet global scope.
 * Self-contained on purpose: classic-fetched worklet code cannot share
 * bundled imports. The float→int16 loop mirrors floatTo16BitPCM in
 * pcmCapture.ts (the tested reference implementation). */
const CHUNK_SAMPLES = 3200; // keep in sync with pcmCapture.ts

class PcmChunker extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buf = new Float32Array(CHUNK_SAMPLES);
    this.filled = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    let off = 0;
    while (off < ch.length) {
      const take = Math.min(CHUNK_SAMPLES - this.filled, ch.length - off);
      this.buf.set(ch.subarray(off, off + take), this.filled);
      this.filled += take;
      off += take;
      if (this.filled === CHUNK_SAMPLES) {
        const ints = new Int16Array(CHUNK_SAMPLES);
        for (let i = 0; i < CHUNK_SAMPLES; i++) {
          const s = Math.max(-1, Math.min(1, this.buf[i]));
          ints[i] = Math.round(s < 0 ? s * 0x8000 : s * 0x7fff);
        }
        this.port.postMessage(ints.buffer, [ints.buffer]);
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-chunker", PcmChunker);
