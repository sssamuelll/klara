import { describe, expect, it } from "vitest";
import { CHUNK_SAMPLES, floatTo16BitPCM, PCM_SAMPLE_RATE } from "./pcmCapture";

describe("floatTo16BitPCM", () => {
  it("converts full-scale values", () => {
    const out = floatTo16BitPCM(new Float32Array([0, 0.5, -0.5, 1, -1]));
    expect(out[0]).toBe(0);
    expect(out[1]).toBe(Math.round(0.5 * 0x7fff));
    expect(out[2]).toBe(Math.round(-0.5 * 0x8000));
    expect(out[3]).toBe(0x7fff);
    expect(out[4]).toBe(-0x8000);
  });

  it("clips values beyond ±1", () => {
    const out = floatTo16BitPCM(new Float32Array([1.5, -1.5]));
    expect(out[0]).toBe(0x7fff);
    expect(out[1]).toBe(-0x8000);
  });

  it("preserves length", () => {
    expect(floatTo16BitPCM(new Float32Array(320)).length).toBe(320);
  });
});

describe("chunk constants", () => {
  it("3200 samples = 200ms at 16kHz", () => {
    expect(CHUNK_SAMPLES / PCM_SAMPLE_RATE).toBeCloseTo(0.2);
  });
});
