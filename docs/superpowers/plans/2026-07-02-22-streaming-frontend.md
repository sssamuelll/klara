# #22 Live Pronunciation Streaming — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SentenceView paints word bands live while the user speaks, via the merged WS transport (PR #101), falling back silently to the existing batch scoring on any failure.

**Architecture:** Three new lib modules — `streamAlign.ts` (pure aligner), `streamClient.ts` (WS lifecycle; `result: Promise<FinalPayload|null>` is the whole fallback contract), `pcmCapture.ts` + `pcmWorklet.js` (AudioWorklet → 16 kHz Int16 chunks off the same MediaStream) — orchestrated inside the existing `useSentencePractice` hook. `SentenceView` gets one `liveBands` prop reusing the existing underline classes. First frontend test framework: vitest, scoped to the pure modules.

**Tech Stack:** React 18 + TS 5.6 + Vite 5.4; vitest (new dev-dep); Web Audio AudioWorklet; native WebSocket.

**Spec:** `docs/superpowers/specs/2026-07-02-22-streaming-frontend-design.md`

## Global Constraints

- **Fallback rule: batch iff no `final` message was received.** Close codes are hints only; the consumer never inspects them.
- Streaming is silent enhancement: every failure path (`no support / WS refused / 4401 / 4408 / 4500 / mid-drop / no final in 8 s`) ends in the byte-identical batch path; `console.debug` only.
- Live paint may under-paint but **never mispaints a position**; `final` (or batch) repaints everything.
- Post-eos final-wait timeout: **8000 ms**. PCM chunk: **3200 samples (200 ms @ 16 kHz), Int16 mono**. Aligner look-ahead window: **3**.
- Reuse existing exports: `scoreBand` (70/45), `bandsByTokenIndex`, `wordTokensByIndex` from `frontend/src/lib/pronunciation.ts` — do not duplicate tokenization.
- **Do NOT rename the CI job** `frontend / typecheck + build + i18n` — it is a required status-check context in the repo ruleset. Add steps inside it only.
- No new user-facing strings (zero i18n changes). No new runtime dependencies — vitest is a dev-dep.
- Every task: `cd frontend && npm run typecheck` clean before commit; tasks with tests also `npm run test` green.

---

## File Structure

- Create `frontend/src/lib/streamAlign.ts` — pure aligner (Task 1)
- Create `frontend/src/lib/streamAlign.test.ts` (Task 1)
- Create `frontend/src/lib/streamClient.ts` — WS client + URL derivation (Task 2)
- Create `frontend/src/lib/streamClient.test.ts` (Task 2)
- Create `frontend/src/lib/pcmCapture.ts` — capability guard, capture graph, `floatTo16BitPCM` (Task 3)
- Create `frontend/src/lib/pcmCapture.test.ts` (Task 3)
- Create `frontend/src/lib/pcmWorklet.js` — self-contained worklet, plain JS (Task 3)
- Modify `frontend/package.json` (vitest + `test` script, Task 1), `.github/workflows/ci.yml` (test step, Task 1)
- Modify `frontend/src/lib/pronunciation.ts:143-152,248` (expose `stream` on `MicRecorder`, Task 4), `frontend/vite.config.ts:17-20` (`ws: true`, Task 4)
- Modify `frontend/src/lib/useSentencePractice.ts` + `frontend/src/components/SentenceView.tsx` + the two `<SentenceView` hosts (Task 5)

---

## Task 1: vitest infra + streamAlign

**Files:**
- Modify: `frontend/package.json`
- Modify: `.github/workflows/ci.yml:131-138` (inside the `frontend-checks` job — do not rename it)
- Create: `frontend/src/lib/streamAlign.ts`
- Test: `frontend/src/lib/streamAlign.test.ts`

**Interfaces:**
- Consumes: `wordTokensByIndex(text): Record<number,string>` from `./pronunciation`.
- Produces: `createAligner(referenceText: string): (word: string, errorType: string) => number | null` and `normalizeWord(w: string): string`. Task 5 calls the aligner with each live word.

- [ ] **Step 1: Install vitest and add the script**

```bash
cd frontend && npm install -D vitest
```

In `frontend/package.json` scripts, after `"i18n:check"`:

```json
    "test": "vitest run"
```

- [ ] **Step 2: Add the CI step (job name unchanged)**

In `.github/workflows/ci.yml`, inside `frontend-checks`, after the `npm run i18n:check` step and before `npm run build`:

```yaml
      - working-directory: frontend
        run: npm run test
```

- [ ] **Step 3: Write the failing tests**

```ts
// frontend/src/lib/streamAlign.test.ts
import { describe, expect, it } from "vitest";
import { createAligner, normalizeWord } from "./streamAlign";

const REF = "Ich fahre mit dem Autobus.";
// Token indices (spaces/punct counted): Ich=0, fahre=2, mit=4, dem=6, Autobus=8

describe("createAligner", () => {
  it("matches words in order and returns their full token indices", () => {
    const align = createAligner(REF);
    expect(align("Ich", "None")).toBe(0);
    expect(align("fahre", "None")).toBe(2);
    expect(align("mit", "None")).toBe(4);
  });

  it("normalizes case", () => {
    const align = createAligner(REF);
    expect(align("ich", "None")).toBe(0);
  });

  it("ignores insertions without consuming a token", () => {
    const align = createAligner(REF);
    expect(align("Ich", "None")).toBe(0);
    expect(align("ähm", "Insertion")).toBeNull();
    expect(align("fahre", "None")).toBe(2);
  });

  it("look-ahead window (3) skips unspoken tokens and leaves them unpainted", () => {
    const align = createAligner(REF);
    expect(align("Ich", "None")).toBe(0);
    // user skipped "fahre" and "mit"; "dem" is 3rd token ahead → within window
    expect(align("dem", "None")).toBe(6);
    // skipped tokens are consumed: "fahre" can no longer match
    expect(align("fahre", "None")).toBeNull();
    expect(align("Autobus", "None")).toBe(8);
  });

  it("out-of-window word returns null and does not advance", () => {
    const align = createAligner("eins zwei drei vier fünf sechs");
    expect(align("sechs", "None")).toBeNull(); // 6th token, window is 3
    expect(align("eins", "None")).toBe(0); // pointer unmoved
  });

  it("returns null once the reference is exhausted", () => {
    const align = createAligner("Hallo");
    expect(align("Hallo", "None")).toBe(0);
    expect(align("Hallo", "None")).toBeNull();
  });

  it("never returns the same token index twice", () => {
    const align = createAligner("die die die");
    expect(align("die", "None")).toBe(0);
    expect(align("die", "None")).toBe(2);
    expect(align("die", "None")).toBe(4);
    expect(align("die", "None")).toBeNull();
  });
});

describe("normalizeWord", () => {
  it("lowercases and trims", () => {
    expect(normalizeWord(" Autobus ")).toBe("autobus");
  });
});
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd frontend && npm run test`
Expected: FAIL — `Cannot find module './streamAlign'` (or equivalent resolve error). This also proves the vitest runner itself works.

- [ ] **Step 5: Implement streamAlign**

```ts
// frontend/src/lib/streamAlign.ts
/**
 * Aligns live streaming words (append-order, no index — see the backend
 * spec: offsets are temporal and lie) to reference word-token indices.
 *
 * Invariant: may under-paint (return null), never mispaints a position.
 * The authoritative `final` (or batch) repaints everything afterwards.
 */
import { wordTokensByIndex } from "./pronunciation";

const LOOKAHEAD = 3;

export function normalizeWord(w: string): string {
  return w.toLowerCase().trim();
}

export function createAligner(
  referenceText: string,
): (word: string, errorType: string) => number | null {
  const entries = Object.entries(wordTokensByIndex(referenceText))
    .map(([idx, w]) => ({ idx: Number(idx), norm: normalizeWord(w) }))
    .sort((a, b) => a.idx - b.idx);
  let pos = 0; // next unmatched reference token

  return (word, errorType) => {
    if (errorType === "Insertion") return null;
    const norm = normalizeWord(word);
    for (let j = 0; j < LOOKAHEAD && pos + j < entries.length; j++) {
      if (entries[pos + j].norm === norm) {
        const tokenIdx = entries[pos + j].idx;
        pos = pos + j + 1; // skipped tokens stay unpainted; final resolves them
        return tokenIdx;
      }
    }
    return null;
  };
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && npm run test`
Expected: PASS (8 tests). Also run `npm run typecheck` — clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/streamAlign.ts frontend/src/lib/streamAlign.test.ts .github/workflows/ci.yml
git commit -m "feat(pronunciation): #22 FE stream aligner + vitest infra"
```

---

## Task 2: streamClient

**Files:**
- Create: `frontend/src/lib/streamClient.ts`
- Test: `frontend/src/lib/streamClient.test.ts`

**Interfaces:**
- Consumes: `WordScore`, `PronunciationScoreResponse` types from `../api/types`.
- Produces (Task 5 relies on these exact names):
  - `interface LiveWord { word: string; accuracy_score: number; error_type: string }`
  - `interface FinalPayload { words: WordScore[]; scores: PronunciationScoreResponse["scores"] }`
  - `interface ScoreStream { sendChunk(buf: ArrayBuffer): void; sendEos(): void; close(): void; result: Promise<FinalPayload | null> }`
  - `openScoreStream(opts: { referenceText: string; language: string; onWord: (w: LiveWord) => void; makeWs?: (url: string) => WsLike; finalTimeoutMs?: number; url?: string }): ScoreStream`
  - `deriveWsUrl(loc: { protocol: string; host: string }): string`
- Note (spec deviation, sanctioned): the spec mentioned deriving from an absolute `VITE_API_BASE_URL`; in reality `api/client.ts` always uses the relative `/api/v1` and the env var only feeds the Vite proxy target — the browser is always same-origin. `deriveWsUrl` therefore takes only `location`. YAGNI.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/streamClient.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  deriveWsUrl,
  openScoreStream,
  type FinalPayload,
  type WsLike,
} from "./streamClient";

class FakeWs implements WsLike {
  binaryType = "blob";
  readyState = 0; // CONNECTING
  sent: (string | ArrayBuffer)[] = [];
  closed = false;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  send(data: string | ArrayBuffer) {
    this.sent.push(data);
  }
  close() {
    this.closed = true;
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  receive(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
}

const OPTS = { referenceText: "Hallo Welt", language: "de" };

describe("deriveWsUrl", () => {
  it("uses wss on https and ws on http, same origin", () => {
    expect(deriveWsUrl({ protocol: "https:", host: "klara.example" })).toBe(
      "wss://klara.example/api/v1/pronunciation/stream",
    );
    expect(deriveWsUrl({ protocol: "http:", host: "localhost:5273" })).toBe(
      "ws://localhost:5273/api/v1/pronunciation/stream",
    );
  });
});

describe("openScoreStream", () => {
  let ws: FakeWs;
  const make = () => {
    ws = new FakeWs();
    return openScoreStream({
      ...OPTS,
      onWord: (w) => words.push(w.word),
      makeWs: () => ws,
      url: "ws://test/api/v1/pronunciation/stream",
    });
  };
  let words: string[] = [];
  beforeEach(() => {
    words = [];
    vi.useFakeTimers();
  });
  afterEach(() => vi.useRealTimers());

  it("sends the handshake as the first frame on open", () => {
    make();
    ws.open();
    expect(ws.sent[0]).toBe(JSON.stringify({ reference_text: "Hallo Welt", language: "de" }));
  });

  it("drops chunks before open, sends them after", () => {
    const s = make();
    s.sendChunk(new ArrayBuffer(4)); // CONNECTING → dropped
    ws.open();
    s.sendChunk(new ArrayBuffer(4));
    expect(ws.sent.length).toBe(2); // handshake + one chunk
  });

  it("routes word messages to onWord", () => {
    make();
    ws.open();
    ws.receive({ type: "word", word: "Hallo", accuracy_score: 91, error_type: "None" });
    expect(words).toEqual(["Hallo"]);
  });

  it("resolves result with the final payload and closes", async () => {
    const s = make();
    ws.open();
    const final: FinalPayload = {
      words: [
        { word: "Hallo", accuracy_score: 91, error_type: "None", phonemes: [] },
      ],
      scores: { accuracy: 91, fluency: 91, completeness: 100, pronunciation: 91 },
    };
    ws.receive({ type: "final", ...final });
    await expect(s.result).resolves.toEqual(final);
    expect(ws.closed).toBe(true);
  });

  it("resolves null on close without final", async () => {
    const s = make();
    ws.open();
    ws.onclose?.();
    await expect(s.result).resolves.toBeNull();
  });

  it("resolves null when no final arrives within the post-eos timeout", async () => {
    const s = make();
    ws.open();
    s.sendEos();
    expect(ws.sent[1]).toBe(JSON.stringify({ type: "eos" }));
    vi.advanceTimersByTime(8000);
    await expect(s.result).resolves.toBeNull();
  });

  it("final beats the eos timeout when it arrives in time", async () => {
    const s = make();
    ws.open();
    s.sendEos();
    ws.receive({
      type: "final",
      words: [],
      scores: { accuracy: 0, fluency: 0, completeness: 0, pronunciation: 0 },
    });
    vi.advanceTimersByTime(10000);
    const r = await s.result;
    expect(r).not.toBeNull();
  });

  it("sendChunk after close is a no-op", async () => {
    const s = make();
    ws.open();
    s.close();
    const sentBefore = ws.sent.length;
    s.sendChunk(new ArrayBuffer(4));
    expect(ws.sent.length).toBe(sentBefore);
    await expect(s.result).resolves.toBeNull();
  });

  it("ignores malformed JSON without settling", () => {
    const s = make();
    ws.open();
    ws.onmessage?.({ data: "not json{" });
    ws.receive({ type: "word", word: "ok", accuracy_score: 80, error_type: "None" });
    expect(words).toEqual(["ok"]);
    void s;
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test`
Expected: FAIL — cannot resolve `./streamClient`; streamAlign tests still pass.

- [ ] **Step 3: Implement streamClient**

```ts
// frontend/src/lib/streamClient.ts
/**
 * WS client for the #22 live pronunciation stream (backend contract:
 * docs/superpowers/specs/2026-07-01-22-streaming-backpressure-design.md).
 *
 * The whole fallback contract is `result`: it resolves the authoritative
 * FinalPayload, or null (close/error/timeout without final). The caller
 * batches iff null — close codes are never inspected.
 */
import type { PronunciationScoreResponse, WordScore } from "../api/types";

export interface LiveWord {
  word: string;
  accuracy_score: number;
  error_type: string;
}

export interface FinalPayload {
  words: WordScore[];
  scores: PronunciationScoreResponse["scores"];
}

export interface ScoreStream {
  sendChunk(buf: ArrayBuffer): void;
  sendEos(): void;
  close(): void;
  result: Promise<FinalPayload | null>;
}

/** Minimal WebSocket surface, injectable for tests. */
export interface WsLike {
  binaryType: string;
  readyState: number;
  send(data: string | ArrayBuffer): void;
  close(): void;
  onopen: (() => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
}

export const STREAM_PATH = "/api/v1/pronunciation/stream";
const WS_OPEN = 1;
const FINAL_TIMEOUT_MS = 8000;

/** Browser is always same-origin (api/client.ts uses relative /api/v1). */
export function deriveWsUrl(loc: { protocol: string; host: string }): string {
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${loc.host}${STREAM_PATH}`;
}

export function openScoreStream(opts: {
  referenceText: string;
  language: string;
  onWord: (w: LiveWord) => void;
  makeWs?: (url: string) => WsLike;
  finalTimeoutMs?: number;
  url?: string;
}): ScoreStream {
  const timeoutMs = opts.finalTimeoutMs ?? FINAL_TIMEOUT_MS;
  const url = opts.url ?? deriveWsUrl(window.location);
  const makeWs =
    opts.makeWs ?? ((u: string) => new WebSocket(u) as unknown as WsLike);

  let settled = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let resolveResult!: (v: FinalPayload | null) => void;
  const result = new Promise<FinalPayload | null>((res) => {
    resolveResult = res;
  });

  let ws: WsLike;
  try {
    ws = makeWs(url);
  } catch (e) {
    console.debug("pron_stream: ws constructor failed", e);
    resolveResult(null);
    return { sendChunk: () => {}, sendEos: () => {}, close: () => {}, result };
  }

  const settle = (v: FinalPayload | null) => {
    if (settled) return;
    settled = true;
    if (timer) clearTimeout(timer);
    resolveResult(v);
    try {
      ws.close();
    } catch {
      // already closed
    }
  };

  ws.binaryType = "arraybuffer";
  ws.onopen = () => {
    // Handshake MUST be the first frame (backend reads it before the session).
    ws.send(
      JSON.stringify({ reference_text: opts.referenceText, language: opts.language }),
    );
  };
  ws.onmessage = (ev) => {
    if (typeof ev.data !== "string") return;
    let msg: { type?: string } & Record<string, unknown>;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    if (msg.type === "word") {
      opts.onWord(msg as unknown as LiveWord);
    } else if (msg.type === "final") {
      settle(msg as unknown as FinalPayload);
    }
  };
  ws.onclose = () => settle(null);
  ws.onerror = () => settle(null);

  return {
    sendChunk(buf) {
      if (settled || ws.readyState !== WS_OPEN) return; // pre-open/late chunks drop
      try {
        ws.send(buf);
      } catch {
        // socket died between check and send — settle path will fire via onclose
      }
    },
    sendEos() {
      if (settled) return;
      if (ws.readyState === WS_OPEN) {
        try {
          ws.send(JSON.stringify({ type: "eos" }));
        } catch {
          // as above
        }
      }
      timer = setTimeout(() => settle(null), timeoutMs);
    },
    close() {
      settle(null);
    },
    result,
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test`
Expected: PASS (streamAlign 8 + streamClient 10). `npm run typecheck` clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/streamClient.ts frontend/src/lib/streamClient.test.ts
git commit -m "feat(pronunciation): #22 FE stream client (result = final | null)"
```

---

## Task 3: pcmCapture + worklet

**Files:**
- Create: `frontend/src/lib/pcmCapture.ts`
- Create: `frontend/src/lib/pcmWorklet.js` (plain JS on purpose — worklet modules are fetched by URL and must be self-contained; Vite serves/emits it via `new URL(..., import.meta.url)`)
- Test: `frontend/src/lib/pcmCapture.test.ts`

**Interfaces:**
- Produces (Task 5 relies on): `pcmStreamingSupported(): boolean`; `startPcmCapture(stream: MediaStream, onChunk: (chunk: ArrayBuffer) => void): Promise<{ stop(): void } | null>` (null = capability guard failed → batch-pure session); pure `floatTo16BitPCM(input: Float32Array): Int16Array`; consts `PCM_SAMPLE_RATE = 16000`, `CHUNK_SAMPLES = 3200`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/pcmCapture.test.ts
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test`
Expected: FAIL — cannot resolve `./pcmCapture`.

- [ ] **Step 3: Implement pcmCapture**

```ts
// frontend/src/lib/pcmCapture.ts
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
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
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
  try {
    await ctx.audioWorklet.addModule(new URL("./pcmWorklet.js", import.meta.url));
  } catch (e) {
    console.debug("pron_stream: worklet load failed", e);
    void ctx.close();
    return null;
  }
  const source = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, "pcm-chunker");
  node.port.onmessage = (e: MessageEvent) => onChunk(e.data as ArrayBuffer);
  source.connect(node);
  // The worklet outputs silence; connecting to destination keeps the graph
  // pulled so process() actually runs.
  node.connect(ctx.destination);
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
```

- [ ] **Step 4: Write the worklet (plain JS, self-contained)**

```js
// frontend/src/lib/pcmWorklet.js
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
          ints[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        this.port.postMessage(ints.buffer, [ints.buffer]);
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-chunker", PcmChunker);
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm run test`
Expected: PASS (all three test files). `npm run typecheck` clean (the worklet is .js and outside tsc's program; if tsc complains about it, exclude is NOT needed — `include` covers `src` but plain .js is ignored unless `allowJs`; verify typecheck stays clean).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/pcmCapture.ts frontend/src/lib/pcmCapture.test.ts frontend/src/lib/pcmWorklet.js
git commit -m "feat(pronunciation): #22 FE AudioWorklet PCM capture"
```

---

## Task 4: plumbing — MicRecorder.stream + Vite WS proxy

**Files:**
- Modify: `frontend/src/lib/pronunciation.ts:143-152` (interface) and `:248` (resolve)
- Modify: `frontend/vite.config.ts:16-21`

**Interfaces:**
- Produces: `MicRecorder.stream: MediaStream` — Task 5 hands it to `startPcmCapture`.

- [ ] **Step 1: Expose the MediaStream on MicRecorder**

In `frontend/src/lib/pronunciation.ts`, add to the `MicRecorder` interface (after `analyser`):

```ts
  /** The underlying mic stream — the live-streaming PCM capture hangs off it. */
  stream: MediaStream;
```

And at the resolve site (`recorder.onstart = () => resolve({ stop, cancel, analyser });`):

```ts
    recorder.onstart = () => resolve({ stop, cancel, analyser, stream });
```

- [ ] **Step 2: Vite dev proxy forwards WS upgrades**

In `frontend/vite.config.ts`, the `/api` proxy entry becomes:

```ts
      proxy: {
        "/api": {
          target: apiBase,
          changeOrigin: true,
          ws: true,
        },
      },
```

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run typecheck && npm run test`
Expected: both clean/green (no behavior change; the added field is additive).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/pronunciation.ts frontend/vite.config.ts
git commit -m "feat(pronunciation): #22 FE expose mic stream + WS dev proxy"
```

---

## Task 5: integration — useSentencePractice + SentenceView + hosts

**Files:**
- Modify: `frontend/src/lib/useSentencePractice.ts` (imports :36-46; interface :130-172; state ~:200; `startRecording` :308-322; `stopRecording` :324-383; `cancelRecording` :385-391; unmount cleanup :216-222; return :511-539)
- Modify: `frontend/src/components/SentenceView.tsx` (props interface ~:68; `scoreByTokenIdx` memo :260-263)
- Modify: the two `<SentenceView` hosts (find them: `grep -rn "<SentenceView" frontend/src` — Story and the Practice host) to pass the new prop through.

**Interfaces:**
- Consumes: everything produced by Tasks 1-4 (`createAligner`, `openScoreStream`/`ScoreStream`/`FinalPayload`, `startPcmCapture`/`pcmStreamingSupported`, `MicRecorder.stream`), plus existing `scoreBand`.
- Produces: `UseSentencePractice.liveBands: PronScores | undefined` (only defined while the current sentence is recording); `SentenceViewProps.liveBands?: Record<number, ScoreBand>`.

No unit test (React hook + component; vitest covers the logic modules). Verification = typecheck + full vitest + build + the manual smoke checklist at the end of this plan.

- [ ] **Step 1: Hook — imports, refs, state**

In `frontend/src/lib/useSentencePractice.ts`:

Add to the `./pronunciation` import: `scoreBand`. Add new imports after it:

```ts
import { startPcmCapture, pcmStreamingSupported } from "./pcmCapture";
import { createAligner } from "./streamAlign";
import { openScoreStream, type ScoreStream } from "./streamClient";
```

Add to the returned interface (`UseSentencePractice`), after `feedback`:

```ts
  /** Live streaming bands for the sentence being recorded (undefined otherwise). */
  liveBands: PronScores | undefined;
```

Add state + refs next to `recorderRef` (~line 203):

```ts
  const [liveBands, setLiveBands] = useState<PronScores>({});
  const streamRef = useRef<ScoreStream | null>(null);
  const pcmRef = useRef<{ stop(): void } | null>(null);
```

Add a teardown helper right after the refs (used by stop/cancel/unmount):

```ts
  const teardownStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
    pcmRef.current?.stop();
    pcmRef.current = null;
  }, []);
```

- [ ] **Step 2: Hook — startRecording opens the stream (best-effort)**

Replace the body of the `try` in `startRecording` (currently lines 314-318) with:

```ts
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
              const idx = aligner(w.word, w.error_type);
              if (idx === null) return;
              const band = w.error_type === "Omission" ? "bad" : scoreBand(w.accuracy_score);
              setLiveBands((b) => ({ ...b, [idx]: band }));
            },
          });
          streamRef.current = stream;
          const pcm = await startPcmCapture(rec.stream, (chunk) => stream.sendChunk(chunk));
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
```

(`startRecording`'s dependency array gains `targetLanguage` and `teardownStream`.)

- [ ] **Step 3: Hook — stopRecording prefers the final, falls back to batch**

In `stopRecording`, after `setEvaluatingIndex(idxAtStart);` and before `const blob = await rec.stop();`, capture and clear the stream refs:

```ts
    const stream = streamRef.current;
    streamRef.current = null;
```

Immediately after `const blob = await rec.stop();` add:

```ts
      pcmRef.current?.stop();
      pcmRef.current = null;
```

Change the empty-blob early return to also close the stream:

```ts
      if (!blob || blob.size === 0) {
        stream?.close();
        setPronError({ kind: "no_speech" });
        return;
      }
```

Replace `const resp = await scoreAudio(blob, sentence.target, targetLanguage);` with:

```ts
      let resp: PronunciationScoreResponse | null = null;
      if (stream) {
        stream.sendEos();
        const final = await stream.result; // bounded: 8 s post-eos inside the client
        if (final) {
          resp = {
            recognized_text: final.words.map((w) => w.word).join(" "),
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
```

(Add `import type { PronunciationScoreResponse } from "../api/types";` — the file already imports `WordScore` from there; extend that import.)

Everything downstream (`bandsByTokenIndex`, persist, hints, diagnose, the 503-simulated catch) stays byte-identical. At the end of the `finally` block add:

```ts
      setLiveBands({});
```

- [ ] **Step 4: Hook — cancel, unmount, return**

`cancelRecording` gains, before `setPronError(null)`:

```ts
    teardownStream();
    setLiveBands({});
```

The unmount cleanup effect (:216-222) gains `teardownStream();` (add it to the effect body; `teardownStream` to its dep array).

The hook's return gains:

```ts
    liveBands: recording ? liveBands : undefined,
```

- [ ] **Step 5: SentenceView — liveBands prop**

In `frontend/src/components/SentenceView.tsx` props interface (after `feedback?:` ~line 68):

```ts
  /** Live streaming bands while recording — same shape/classes as feedback. */
  liveBands?: Record<number, ScoreBand>;
```

Destructure `liveBands` with the other props, and replace the `scoreByTokenIdx` memo (:260-263) with:

```ts
  const scoreByTokenIdx = useMemo(() => {
    if (showFeedback && feedback) return feedback;
    if (recording && liveBands) return liveBands;
    return null;
  }, [feedback, showFeedback, recording, liveBands]);
```

No other render changes — the existing token underline at `:404` (`scoreByTokenIdx?.[i]`) now paints live too.

- [ ] **Step 6: Hosts — thread the prop**

`grep -rn "<SentenceView" frontend/src` → in each host (Story + Practice), where `feedback={...}` is passed from the hook, add:

```tsx
  liveBands={practice.liveBands}
```

(using whatever local name the host gives the hook result — match the `feedback` wiring next to it.)

- [ ] **Step 7: Verify**

Run: `cd frontend && npm run typecheck && npm run test && npm run build && npm run i18n:check`
Expected: all clean/green (no new strings → i18n unchanged).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/useSentencePractice.ts frontend/src/components/SentenceView.tsx frontend/src
git commit -m "feat(pronunciation): #22 FE live paint via streaming, batch fallback"
```

---

## Manual smoke checklist (out of CI — needs backend + Azure creds)

Covers the worklet, the real WS, and the pending backend live smoke in one pass:

1. `docker compose up` (or backend dev + `npm run dev`), with `AZURE_SPEECH_KEY` set. Open a story sentence, hold M, read it.
2. **Live paint:** words underline green/amber/red progressively while speaking; on release, the feedback panel appears with the complete bands (final repaint) — the "scoring…" spinner should be near-instant.
3. **Latency:** p95 < 500 ms word-spoken → word-painted (#22 criterion; eyeball or performance.now logs).
4. **Fallback:** stop the backend mid-sentence (or set `PRON_STREAM_GLOBAL_CAP=0`) → no visible error; score arrives via batch as today. DevTools console shows only `pron_stream:` debug lines.
5. **No streaming support path:** dev-tools → disable AudioWorklet is impractical; instead temporarily hardcode `pcmStreamingSupported = () => false` and confirm batch-pure behavior is byte-identical to main.
6. Prod deploy: confirm the reverse proxy forwards the WS upgrade for `/api/v1/pronunciation/stream` (backend spec checklist); confirm `dist/assets/pcmWorklet-*.js` is emitted (not inlined as data:).

## Self-review notes (author)

- **Spec coverage:** aligner+window+Insertion (T1), client+URL+8s timeout+fallback-iff-no-final (T2), worklet+16kHz guard+float→int16 (T3), MicRecorder.stream + `ws:true` (T4), hook integration + liveBands prop + hosts + existing downstream untouched (T5), vitest+CI (T1), manual smoke (checklist). Spec deviation sanctioned and documented in T2: `deriveWsUrl` is same-origin-only (client.ts never uses an absolute base in the browser).
- **Type consistency:** `PronScores = Record<number, ScoreBand>` reused for liveBands; `ScoreStream`/`FinalPayload`/`LiveWord` defined in T2 and consumed by name in T5; `MicRecorder.stream` defined in T4, consumed in T5; aligner signature `(word, errorType) => number|null` consistent T1/T5.
- **Verify during impl:** the exact host prop-wiring names (Step 6 greps rather than guessing); tsc's treatment of the plain-JS worklet (T3 Step 5 note); `startRecording` dep array after edits (exhaustive-deps).
