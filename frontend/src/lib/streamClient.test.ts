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
      words: [{ word: "Hallo", accuracy_score: 91, error_type: "None", phonemes: [] }],
      scores: { accuracy: 91, fluency: 91, completeness: 100, pronunciation: 91 },
    });
    vi.advanceTimersByTime(10000);
    const r = await s.result;
    expect(r).not.toBeNull();
  });

  it("empty final (no words) resolves null", async () => {
    const s = make();
    ws.open();
    ws.receive({
      type: "final",
      words: [],
      scores: { accuracy: 0, fluency: 0, completeness: 0, pronunciation: 0 },
    });
    await expect(s.result).resolves.toBeNull();
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
