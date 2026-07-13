import { describe, expect, it } from "vitest";
import type { QuizItem } from "../api/types";
import {
  currentItem,
  initQuizSession,
  mainResults,
  MAX_RETRIES,
  quizSessionReducer,
  type QuizSessionState,
} from "./quizSession";

const mc = (n: number): QuizItem => ({
  type: "mc",
  cap: `q${n}`,
  prompt: "p",
  options: ["a", "b"],
  correct: 0,
});

const items = [mc(0), mc(1), mc(2), mc(3)];

function play(s: QuizSessionState, correct: boolean): QuizSessionState {
  const answered = quizSessionReducer(s, { type: "answer", correct, revealed: false });
  return quizSessionReducer(answered, { type: "next" });
}

describe("quizSession", () => {
  it("all correct → done sin retry", () => {
    let s = initQuizSession(items);
    for (let i = 0; i < 4; i++) s = play(s, true);
    expect(s.phase).toBe("done");
    expect(mainResults(s)).toHaveLength(4);
  });

  it("fallos → retry round con SOLO los fallados, en orden", () => {
    let s = initQuizSession(items);
    s = play(s, true);   // 0 ok
    s = play(s, false);  // 1 fail
    s = play(s, true);   // 2 ok
    s = play(s, false);  // 3 fail
    expect(s.phase).toBe("retry");
    expect(s.order).toEqual([1, 3]);
    expect(currentItem(s)).toEqual({ item: items[1], index: 1 });
  });

  it("retry answers llevan phase retry; fallar en retry NO abre segunda ronda", () => {
    let s = initQuizSession(items);
    s = play(s, false);
    s = play(s, true);
    s = play(s, true);
    s = play(s, true);
    expect(s.phase).toBe("retry");
    s = play(s, false); // vuelve a fallar el ítem 0
    expect(s.phase).toBe("done");
    expect(s.answers.filter((a) => a.phase === "retry")).toHaveLength(1);
    // el score del pase principal no se contamina
    expect(mainResults(s)).toHaveLength(4);
    expect(mainResults(s).filter((r) => r.correct)).toHaveLength(3);
  });

  it("retry queue capada a MAX_RETRIES", () => {
    const six = [mc(0), mc(1), mc(2), mc(3), mc(4), mc(5)];
    let s = initQuizSession(six);
    for (let i = 0; i < 6; i++) s = play(s, false);
    expect(s.phase).toBe("retry");
    expect(s.order).toHaveLength(MAX_RETRIES);
  });

  it("doble answer en la misma posición se ignora", () => {
    let s = initQuizSession(items);
    s = quizSessionReducer(s, { type: "answer", correct: true, revealed: false });
    s = quizSessionReducer(s, { type: "answer", correct: false, revealed: false });
    expect(s.answers).toHaveLength(1);
    expect(s.answers[0].correct).toBe(true);
  });

  it("quiz vacío → done inmediato al next", () => {
    let s = initQuizSession([]);
    expect(currentItem(s)).toBeNull();
    s = quizSessionReducer(s, { type: "next" });
    expect(s.phase).toBe("done");
  });
});
