import { describe, expect, it } from "vitest";
import type { CardOut } from "../api/types";
import { initialRecallState, recallReducer, restedCount } from "./recallSession";

const card = (id: string): CardOut => ({
  id, vocab_item_id: `v-${id}`, lemma: "Wort", pos: "noun", translation: "palabra",
  example_target: "Ein Wort.", gender: "das", state: "new", interval_days: 0,
  next_review_at: null, repetitions: 0, ease: 2.5,
});

describe("recallReducer", () => {
  it("loaded with cards → prompt at index 0", () => {
    const s = recallReducer(initialRecallState, { type: "loaded", cards: [card("a"), card("b")] });
    expect(s.phase).toBe("prompt");
    expect(s.idx).toBe(0);
    expect(s.cards).toHaveLength(2);
  });

  it("loaded with no cards → empty", () => {
    expect(recallReducer(initialRecallState, { type: "loaded", cards: [] }).phase).toBe("empty");
  });

  it("failed → failed phase", () => {
    expect(recallReducer(initialRecallState, { type: "failed" }).phase).toBe("failed");
  });

  it("flip only advances prompt → revealed; it is a no-op from any other phase", () => {
    const prompt = recallReducer(initialRecallState, { type: "loaded", cards: [card("a")] });
    expect(recallReducer(prompt, { type: "flip" }).phase).toBe("revealed");
    const revealed = recallReducer(prompt, { type: "flip" });
    expect(recallReducer(revealed, { type: "flip" })).toBe(revealed); // no-op returns same ref
  });

  it("rate is a no-op unless revealed", () => {
    const prompt = recallReducer(initialRecallState, { type: "loaded", cards: [card("a")] });
    expect(recallReducer(prompt, { type: "rate", rating: "good" })).toBe(prompt);
  });

  it("rate advances to the next card (back to prompt) and counts 'again'", () => {
    let s = recallReducer(initialRecallState, { type: "loaded", cards: [card("a"), card("b")] });
    s = recallReducer(s, { type: "flip" });
    s = recallReducer(s, { type: "rate", rating: "again" });
    expect(s.phase).toBe("prompt");
    expect(s.idx).toBe(1);
    expect(s.againCount).toBe(1);
  });

  it("rating the last card → done; restedCount = total - again", () => {
    let s = recallReducer(initialRecallState, { type: "loaded", cards: [card("a"), card("b")] });
    s = recallReducer(recallReducer(s, { type: "flip" }), { type: "rate", rating: "good" }); // card a: good
    s = recallReducer(recallReducer(s, { type: "flip" }), { type: "rate", rating: "again" }); // card b: again (last)
    expect(s.phase).toBe("done");
    expect(s.againCount).toBe(1);
    expect(restedCount(s)).toBe(1); // 2 total - 1 again
  });

  it("rateFailed increments failedCount", () => {
    let s = recallReducer(initialRecallState, { type: "loaded", cards: [card("a")] });
    s = recallReducer(s, { type: "rateFailed" });
    expect(s.failedCount).toBe(1);
    s = recallReducer(s, { type: "rateFailed" });
    expect(s.failedCount).toBe(2);
  });

  it("loaded resets failedCount to 0", () => {
    let s = recallReducer(initialRecallState, { type: "loaded", cards: [card("a")] });
    s = recallReducer(s, { type: "rateFailed" });
    expect(s.failedCount).toBe(1);
    s = recallReducer(s, { type: "loaded", cards: [card("b")] });
    expect(s.failedCount).toBe(0);
  });
});
