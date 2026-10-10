import { describe, expect, it } from "vitest";
import {
  alSoltar,
  evaluarTrazo,
  evidenciaTrazo,
  inicialTrazo,
  largo,
  N,
  partirKana,
  remuestrear,
  TOQUE_MIN,
  type Esperado,
  type Juicio,
  type Punto,
} from "./trazo";

const linea = (x0: number, y0: number, x1: number, y1: number, n = N): Punto[] =>
  Array.from({ length: n }, (_, i) => [x0 + ((x1 - x0) * i) / (n - 1), y0 + ((y1 - y0) * i) / (n - 1)]);
const ESPERADO: Esperado = { pts: linea(20, 50, 90, 50), largo: 70 };
const bien: Juicio = { toque: false, ok: true, media: 2, largo: 1 };
const mal: Juicio = { toque: false, ok: false, media: 30, largo: 1 };
const toque: Juicio = { toque: true, ok: false, media: 0, largo: 0 };

describe("remuestrear", () => {
  it("un punto solo o un toque corto no es un trazo", () => {
    expect(remuestrear([[10, 10]])).toBeNull();
    expect(remuestrear([[10, 10], [10 + TOQUE_MIN / 2, 10]])).toBeNull();
  });

  it("devuelve N puntos y conserva los extremos", () => {
    const r = remuestrear(linea(0, 0, 100, 0, 7))!;
    expect(r).toHaveLength(N);
    expect(r[0]).toEqual([0, 0]);
    expect(r[N - 1][0]).toBeCloseTo(100);
  });

  it("reparte por largo de arco, no por cantidad de puntos", () => {
    // Muchos puntos al principio y uno solo al final: el punto del medio cae igual a la mitad.
    const pts: Punto[] = [...linea(0, 0, 10, 0, 50), [100, 0]];
    expect(remuestrear(pts, 3)![1][0]).toBeCloseTo(50);
  });
});

describe("evaluarTrazo", () => {
  it("vale el trazo bueno, aunque tiemble un poco", () => {
    const j = evaluarTrazo(linea(21, 52, 89, 51, 40), ESPERADO);
    expect(j.ok).toBe(true);
    expect(j.media).toBeLessThan(3);
  });

  it("no vale el mismo trazo al revés", () => {
    const j = evaluarTrazo(linea(90, 50, 20, 50, 40), ESPERADO);
    expect(j.ok).toBe(false);
    expect(j.media).toBeGreaterThan(30);
  });

  it("no vale otro trazo", () => {
    expect(evaluarTrazo(linea(55, 15, 55, 85, 40), ESPERADO).ok).toBe(false);
  });

  it("no vale uno demasiado corto", () => {
    expect(evaluarTrazo(linea(20, 50, 45, 50, 20), ESPERADO).ok).toBe(false);
  });

  it("un zigzag encima de la guía queda cerca, pero es demasiado largo", () => {
    const zigzag: Punto[] = Array.from({ length: 40 }, (_, i) => [20 + (70 * i) / 39, i % 2 ? 58 : 42]);
    const j = evaluarTrazo(zigzag, ESPERADO);
    expect(j.media).toBeLessThan(12);
    expect(j.ok).toBe(false);
  });

  it("un toque no se juzga", () => {
    expect(evaluarTrazo([[50, 50]], ESPERADO).toque).toBe(true);
  });
});

describe("alSoltar", () => {
  it("un trazo bueno avanza y queda en el detalle", () => {
    const e = alSoltar(inicialTrazo, bien, "practicar", 3);
    expect([e.actual, e.fallos, e.terminado]).toEqual([1, 0, false]);
    expect(e.detalle).toEqual([{ n: 1, media: 2, largo: 1, fallos: 0 }]);
  });

  it("un toque no cuenta", () => {
    expect(alSoltar(inicialTrazo, toque, "practicar", 3)).toBe(inicialTrazo);
  });

  it("en práctica la pista llega al segundo fallo, una sola vez", () => {
    let e = alSoltar(inicialTrazo, mal, "practicar", 3);
    expect([e.fallos, e.pistas, e.mostrando]).toEqual([1, 0, false]);
    e = alSoltar(e, mal, "practicar", 3);
    expect([e.fallos, e.pistas, e.mostrando]).toEqual([2, 1, true]);
    e = alSoltar(e, mal, "practicar", 3);
    expect(e.pistas).toBe(1);
    e = alSoltar(e, bien, "practicar", 3);
    expect([e.actual, e.mostrando, e.detalle[0].fallos]).toEqual([1, false, 3]);
  });

  it("en prueba la pista llega al primer fallo", () => {
    const e = alSoltar(inicialTrazo, mal, "comprobar", 3);
    expect([e.pistas, e.mostrando]).toEqual([1, true]);
  });

  it("termina con el último trazo y ya no cambia", () => {
    let e = inicialTrazo;
    for (let i = 0; i < 3; i++) e = alSoltar(e, bien, "comprobar", 3);
    expect(e.terminado).toBe(true);
    expect(alSoltar(e, mal, "comprobar", 3)).toBe(e);
  });
});

describe("evidenciaTrazo", () => {
  it("hasta dos pistas sigue siendo acierto; tres ya no", () => {
    const con = (pistas: number) => ({ ...inicialTrazo, pistas, terminado: true });
    expect(evidenciaTrazo("ja:kana:あ", con(2), 9000)).toMatchObject({
      item: "ja:kana:あ",
      faceta: "escribir",
      acierto: true,
      pistas: 2,
      ms: 9000,
    });
    expect(evidenciaTrazo("ja:kana:あ", con(3), 9000).acierto).toBe(false);
  });
});

describe("largo", () => {
  it("suma los segmentos", () => {
    expect(largo(linea(0, 0, 30, 40, 2))).toBe(50);
  });
});

describe("partirKana", () => {
  it("separa el kana del español que lo rodea, para marcarlo con su lang", () => {
    expect(partirKana("Es さ en el espejo, pero suena «chi».")).toEqual([
      { texto: "Es ", ja: false },
      { texto: "さ", ja: true },
      { texto: " en el espejo, pero suena «chi».", ja: false },
    ]);
  });

  it("sin kana es un solo tramo, y no deja tramos vacíos en los bordes", () => {
    expect(partirKana("Dos palitos: «i».")).toEqual([{ texto: "Dos palitos: «i».", ja: false }]);
    expect(partirKana("は y ほ")).toEqual([
      { texto: "は", ja: true },
      { texto: " y ", ja: false },
      { texto: "ほ", ja: true },
    ]);
    expect(partirKana("")).toEqual([]);
  });
});
