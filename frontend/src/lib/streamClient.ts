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
      const { type: _type, ...payload } = msg;
      const final = payload as unknown as FinalPayload;
      // An empty final (nothing recognized — VAD auto-stopped on silence) is
      // not authoritative: settle as if no final arrived so the caller falls
      // back to batch (which 422s → no_speech), matching main's behavior.
      settle(final.words?.length ? final : null);
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
