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
