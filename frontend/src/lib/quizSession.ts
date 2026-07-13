import type { QuizItem } from "../api/types";

/**
 * Pure state machine for the Finish quiz with an adaptive retry round
 * (consenso 2026-07-13): after the main pass, failed items are re-asked
 * once (max MAX_RETRIES), then the session ends. The component drives this
 * via useReducer and owns all side effects (attempt POSTs, timing, TTS) —
 * same pattern as recallSession.ts.
 */
export type QuizPhase = "main" | "retry" | "done";

export interface QuizAnswer {
  index: number; // index into items (stable across passes)
  qType: QuizItem["type"];
  correct: boolean;
  revealed: boolean;
  phase: QuizPhase;
}

export interface QuizPassResult {
  index: number;
  qType: QuizItem["type"];
  correct: boolean;
  revealed: boolean;
}

export interface QuizSessionState {
  items: QuizItem[];
  order: number[]; // indices into items for the CURRENT pass
  pos: number; // position within order
  phase: QuizPhase;
  answers: QuizAnswer[];
}

// ponytail: one retry round, capped — a second round is a punishment loop,
// and the quiz is 4-5 items anyway.
export const MAX_RETRIES = 4;

export function initQuizSession(items: QuizItem[]): QuizSessionState {
  return { items, order: items.map((_, i) => i), pos: 0, phase: "main", answers: [] };
}

export function currentItem(
  s: QuizSessionState,
): { item: QuizItem; index: number } | null {
  if (s.phase === "done") return null;
  const index = s.order[s.pos];
  return index === undefined ? null : { item: s.items[index], index };
}

export type QuizSessionAction =
  | { type: "answer"; correct: boolean; revealed: boolean }
  | { type: "next" };

export function quizSessionReducer(
  s: QuizSessionState,
  a: QuizSessionAction,
): QuizSessionState {
  switch (a.type) {
    case "answer": {
      const cur = currentItem(s);
      if (cur === null) return s;
      // One answer per item per pass (children fire onAnswered exactly once,
      // but a stray double-fire must not corrupt the score).
      if (s.answers.some((x) => x.index === cur.index && x.phase === s.phase)) return s;
      return {
        ...s,
        answers: [
          ...s.answers,
          {
            index: cur.index,
            qType: cur.item.type,
            correct: a.correct,
            revealed: a.revealed,
            phase: s.phase,
          },
        ],
      };
    }
    case "next": {
      if (s.phase === "done") return s;
      const nextPos = s.pos + 1;
      if (nextPos < s.order.length) return { ...s, pos: nextPos };
      if (s.phase === "main") {
        const failed = s.answers
          .filter((x) => x.phase === "main" && !x.correct)
          .map((x) => x.index)
          .slice(0, MAX_RETRIES);
        if (failed.length > 0) return { ...s, order: failed, pos: 0, phase: "retry" };
      }
      return { ...s, phase: "done" };
    }
    default:
      return s;
  }
}

/** Results in the shape Summary consumes — main pass ONLY, so the retry
 * round never inflates the score. */
export function mainResults(s: QuizSessionState): QuizPassResult[] {
  return s.answers
    .filter((x) => x.phase === "main")
    .map(({ index, qType, correct, revealed }) => ({ index, qType, correct, revealed }));
}
