import { describe, expect, it } from "vitest";
import { dockStatus } from "./estadoDock";

const base = {
  playing: false,
  recording: false,
  evaluating: false,
  micLevel: "silent" as const,
  rate: 1,
};

describe("dockStatus", () => {
  it("es null en reposo", () => {
    expect(dockStatus(base)).toBeNull();
  });

  it("grabando gana a todo y lleva el nivel del mic", () => {
    expect(
      dockStatus({ ...base, recording: true, playing: true, evaluating: true, micLevel: "quiet" }),
    ).toEqual({ kind: "escuchando", nivel: "quiet" });
  });

  it("evaluando gana a leyendo", () => {
    expect(dockStatus({ ...base, evaluating: true, playing: true })).toEqual({ kind: "evaluando" });
  });

  it("leyendo reporta el flag despacio desde rate", () => {
    expect(dockStatus({ ...base, playing: true })).toEqual({ kind: "leyendo", despacio: false });
    expect(dockStatus({ ...base, playing: true, rate: 0.7 })).toEqual({
      kind: "leyendo",
      despacio: true,
    });
  });
});
