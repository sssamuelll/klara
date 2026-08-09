import { describe, expect, it } from "vitest";
import { autoFscaleStep } from "./autoFscale";

const chars = (n: number) => "a".repeat(n);

describe("autoFscaleStep", () => {
  it("mantiene escala 1 en oraciones cortas", () => {
    expect(autoFscaleStep(chars(170), 1)).toBe(1);
  });

  it("baja a 0.92 por encima de 170 chars efectivos", () => {
    expect(autoFscaleStep(chars(171), 1)).toBe(0.92);
    expect(autoFscaleStep(chars(220), 1)).toBe(0.92);
  });

  it("piso 0.85 por encima de 220 — el clamp CSS es el último recurso", () => {
    expect(autoFscaleStep(chars(221), 1)).toBe(0.85);
    expect(autoFscaleStep(chars(400), 1)).toBe(0.85);
  });

  it("pondera por la escala de fuente del usuario", () => {
    expect(autoFscaleStep(chars(150), 1.3)).toBe(0.92); // 195 efectivos
    expect(autoFscaleStep(chars(200), 0.85)).toBe(1); // 170 efectivos
  });
});
