import type { CardOut, ReviewRating } from "../api/types";

/**
 * Pure state machine for a recall-review session. The component (RecallReviewSession)
 * drives this via useReducer and owns all side effects (fetching due cards, POSTing
 * the review with its elapsed time, TTS). Keeping the transitions here makes the
 * session's behaviour unit-testable without a DOM renderer.
 */
export type RecallPhase = "loading" | "failed" | "empty" | "prompt" | "revealed" | "done";

export interface RecallState {
  cards: CardOut[];
  idx: number;
  phase: RecallPhase;
  againCount: number;
}

export type RecallAction =
  | { type: "loaded"; cards: CardOut[] }
  | { type: "failed" }
  | { type: "flip" }
  | { type: "rate"; rating: ReviewRating };

export const initialRecallState: RecallState = {
  cards: [],
  idx: 0,
  phase: "loading",
  againCount: 0,
};

export function recallReducer(state: RecallState, action: RecallAction): RecallState {
  switch (action.type) {
    case "loaded":
      return {
        cards: action.cards,
        idx: 0,
        phase: action.cards.length === 0 ? "empty" : "prompt",
        againCount: 0,
      };
    case "failed":
      return { ...state, phase: "failed" };
    case "flip":
      return state.phase === "prompt" ? { ...state, phase: "revealed" } : state;
    case "rate": {
      if (state.phase !== "revealed") return state;
      const againCount = state.againCount + (action.rating === "again" ? 1 : 0);
      const nextIdx = state.idx + 1;
      return nextIdx < state.cards.length
        ? { ...state, idx: nextIdx, phase: "prompt", againCount }
        : { ...state, phase: "done", againCount };
    }
    default:
      return state;
  }
}

/** Cards that were NOT rated "again" this session — the "descansan" count. */
export function restedCount(state: RecallState): number {
  return state.cards.length - state.againCount;
}
