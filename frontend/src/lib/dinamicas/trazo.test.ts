import { describe, expect, it } from "vitest";
import {
  alSoltar,
  decimar,
  evaluarTrazo,
  evidenciaTrazo,
  inicialTrazo,
  largo,
  lugaresNumeros,
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

// Un trazo real: el 1 de ふ (KanjiVG, 28 unidades), muestreado a N puntos como lo hace Trazo.tsx
// con getPointAtLength. Es uno de los 9 de 104 que, al revés, quedaban a menos de 12 de la guía.
const FU1: Esperado = {
  pts: [
    [42.63, 15.62], [43.55, 16.44], [44.5, 17.22], [45.48, 17.95], [46.51, 18.63], [47.57, 19.25],
    [48.67, 19.8], [49.79, 20.29], [50.95, 20.72], [52.12, 21.08], [53.31, 21.38], [54.52, 21.62],
    [55.73, 21.8], [56.95, 22.01], [58.15, 22.26], [59.32, 22.63], [60.32, 23.31], [59.96, 24.37],
    [58.97, 25.09], [57.9, 25.7], [56.8, 26.25], [55.7, 26.79], [54.59, 27.32], [53.49, 27.87],
  ],
  largo: 28.27,
};

// Dos kana reales (KanjiVG, muestreados a N puntos como lo hace Trazo.tsx) donde el número de un trazo no cabía
// a 7 unidades de su inicio: el 4 de ほ nace pegado al borde del 2, y el 1 de の rodea su propio inicio.
const HO: Esperado[] = [
  {
    pts: [
      [24.51, 18.75], [26.09, 22.04], [26.07, 25.7], [25.36, 29.31], [24.67, 32.93], [24.02, 36.56],
      [23.4, 40.19], [22.84, 43.83], [22.33, 47.48], [21.89, 51.14], [21.53, 54.81], [21.25, 58.48],
      [21.08, 62.16], [21.0, 65.84], [21.05, 69.53], [21.23, 73.21], [21.54, 76.88], [22.02, 80.53],
      [22.61, 84.17], [23.36, 87.77], [24.49, 85.52], [25.26, 81.91], [26.28, 78.38], [27.75, 75],
    ],
    largo: 84.75,
  },
  {
    pts: [
      [53.08, 21.13], [54.26, 21.82], [55.53, 22.32], [56.87, 22.6], [58.24, 22.63], [59.6, 22.47],
      [60.95, 22.25], [62.3, 22.03], [63.65, 21.8], [65.0, 21.56], [66.35, 21.32], [67.69, 21.06],
      [69.04, 20.8], [70.38, 20.53], [71.72, 20.25], [73.06, 19.95], [74.39, 19.64], [75.72, 19.31],
      [77.04, 18.96], [78.36, 18.6], [79.69, 18.28], [81.04, 18.02], [82.39, 17.83], [83.76, 17.75],
    ],
    largo: 31.49,
  },
  {
    pts: [
      [53.83, 44.3], [55.22, 45.08], [56.7, 45.65], [58.27, 45.95], [59.86, 45.99], [61.44, 45.8],
      [63.01, 45.56], [64.59, 45.32], [66.16, 45.07], [67.73, 44.82], [69.31, 44.57], [70.88, 44.3],
      [72.45, 44.03], [74.01, 43.75], [75.58, 43.45], [77.14, 43.14], [78.7, 42.8], [80.25, 42.44],
      [81.79, 42.05], [83.33, 41.64], [84.89, 41.3], [86.46, 41.03], [88.04, 40.83], [89.63, 40.75],
    ],
    largo: 36.64,
  },
  {
    pts: [
      [72.51, 23], [74.12, 28.82], [74.38, 34.97], [74.71, 41.12], [75.03, 47.27], [75.35, 53.42],
      [75.65, 59.57], [75.91, 65.72], [76.11, 71.88], [75.55, 77.98], [72.33, 83.15], [67.16, 86.43],
      [61.22, 87.98], [55.08, 88.02], [49.22, 86.27], [46.29, 81.3], [49.89, 76.65], [55.82, 75.15],
      [61.97, 75.18], [68.05, 76.17], [73.87, 78.12], [79.14, 81.3], [84.2, 84.81], [89.13, 88.5],
    ],
    largo: 141.63,
  },
];
const NO: Esperado[] = [
  {
    pts: [
      [53.82, 28.62], [53.94, 38.86], [51.17, 49.01], [47.81, 58.98], [43.79, 68.7], [38.35, 77.68],
      [29.27, 80.47], [22.65, 72.42], [18.38, 62.84], [19.14, 52.47], [24.09, 43.23], [31.34, 35.64],
      [40.06, 29.79], [49.82, 25.91], [60.22, 24.49], [70.57, 26.12], [79.96, 30.78], [87.29, 38.25],
      [91.5, 47.83], [92.21, 58.28], [89.51, 68.4], [83.7, 77.11], [75.36, 83.45], [65.45, 86.88],
    ],
    largo: 242.02,
  },
];

/** Un dedo sobre el trazo: `n` eventos repartidos por su largo, con pulso de ±`amp` unidades
 *  (1 px son 0,4 u en un lienzo de 272 px). El pulso es siempre el mismo. */
const pulso = (semilla = 1) => {
  let s = semilla;
  return () => ((s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296) * 2 - 1;
};
const dedo = (e: Esperado, n: number, amp = 0, semilla = 1): Punto[] => {
  const r = pulso(semilla);
  return remuestrear(e.pts, n)!.map(([x, y]): Punto => [x + r() * amp, y + r() * amp]);
};

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
  const con = (pistas: number) => ({ ...inicialTrazo, pistas, terminado: true });

  it("hasta dos pistas sigue siendo acierto; tres ya no", () => {
    expect(evidenciaTrazo("ja:kana:あ", con(2), 9000, 3)).toMatchObject({
      item: "ja:kana:あ",
      faceta: "escribir",
      acierto: true,
      pistas: 2,
      ms: 9000,
    });
    expect(evidenciaTrazo("ja:kana:あ", con(3), 9000, 3).acierto).toBe(false);
  });

  it("con tantas pistas como trazos tiene el kana, ya no es acierto (la pista llega una vez por trazo)", () => {
    // し tiene un trazo: con 1 pista no puede ser «difícil», es «otra vez».
    expect(evidenciaTrazo("ja:kana:し", con(0), 1000, 1).acierto).toBe(true);
    expect(evidenciaTrazo("ja:kana:し", con(1), 1000, 1).acierto).toBe(false);
    // un kana de dos trazos: una pista vale; las dos, no.
    expect(evidenciaTrazo("ja:kana:い", con(1), 1000, 2).acierto).toBe(true);
    expect(evidenciaTrazo("ja:kana:い", con(2), 1000, 2).acierto).toBe(false);
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

describe("la dirección", () => {
  const CORTO: Esperado = { pts: linea(20, 50, 42, 50), largo: 22 };

  it("un trazo corto sale igual de cerca al revés (media ≈ largo / 2), pero el derecho gana", () => {
    expect(evaluarTrazo(linea(20, 50, 42, 50, 30), CORTO).ok).toBe(true);
    const alReves = evaluarTrazo(linea(42, 50, 20, 50, 30), CORTO);
    expect(alReves.media).toBeLessThan(12);
    expect(alReves.ok).toBe(false);
  });

  it("el ふ real vale hacia delante y no al revés", () => {
    expect(evaluarTrazo(dedo(FU1, 30), FU1).ok).toBe(true);
    expect(evaluarTrazo(dedo(FU1, 30).reverse(), FU1).ok).toBe(false);
  });

  it("un derecho que se desvía sigue ganando al revés", () => {
    const desviado = dedo(FU1, 30).map(([x, y]): Punto => [x + 4, y + 4]);
    expect(evaluarTrazo(desviado, FU1).ok).toBe(true);
  });
});

describe("el pulso del dedo", () => {
  it("un trazo bueno, lento y tembloroso (150 eventos, ±1 px) vale", () => {
    const j = evaluarTrazo(dedo(FU1, 150, 0.4), FU1);
    expect(j.ok).toBe(true);
    expect(j.largo).toBeLessThan(1.3);
  });

  it("un dedo apoyado en el punto, tembloroso, es un toque y no un trazo fallado", () => {
    const [x0, y0] = FU1.pts[0];
    const r = pulso();
    const quieto = Array.from({ length: 30 }, (): Punto => [x0 + r() * 0.4, y0 + r() * 0.4]);
    expect(largo(quieto)).toBeGreaterThan(TOQUE_MIN); // sumado, el temblor parece un trazo
    expect(evaluarTrazo(quieto, FU1).toque).toBe(true);
  });

  it("el temblor no tapa un trazo que de verdad no vale", () => {
    expect(evaluarTrazo(dedo(FU1, 150, 0.4).reverse(), FU1).ok).toBe(false);
    expect(evaluarTrazo(dedo(FU1, 150, 0.4).slice(0, 50), FU1).ok).toBe(false);
  });

  it("un zigzag grande sigue siendo largo: el temblor se descarta, el zigzag no", () => {
    const zigzag: Punto[] = Array.from({ length: 40 }, (_, i) => [20 + (70 * i) / 39, i % 2 ? 58 : 42]);
    expect(evaluarTrazo(zigzag, ESPERADO).largo).toBeGreaterThan(2);
  });
});

describe("el dedo lento del lienzo chico (1 px = 0,6 u a 180 px)", () => {
  it("un trazo bueno muy lento (240 eventos) con ±1 u de pulso vale", () => {
    expect(evaluarTrazo(dedo(FU1, 240, 1), FU1).ok).toBe(true);
    expect(evaluarTrazo(dedo(FU1, 240, 1).reverse(), FU1).ok).toBe(false);
  });

  it("un dedo apoyado medio segundo (60 eventos) con ±1 u es un toque", () => {
    const [x0, y0] = FU1.pts[0];
    const r = pulso();
    expect(evaluarTrazo(Array.from({ length: 60 }, (): Punto => [x0 + r(), y0 + r()]), FU1).toque).toBe(true);
  });
});

describe("decimar", () => {
  it("descarta lo que no se aleja 1 unidad del último que se queda, y guarda el primero y el último", () => {
    const pts: Punto[] = [[0, 0], [0.3, 0], [0.6, 0.1], [1.2, 0], [1.4, 0.2], [3, 0], [3.2, 0.1]];
    expect(decimar(pts, 1)).toEqual([[0, 0], [1.2, 0], [3.2, 0.1]]);
  });

  it("un dedo quieto se queda en dos puntos casi iguales", () => {
    expect(decimar([[5, 5], [5.1, 5], [5, 5.2], [5.2, 5.1]])).toEqual([[5, 5], [5.2, 5.1]]);
  });

  it("menos de dos puntos, tal cual", () => {
    expect(decimar([])).toEqual([]);
    expect(decimar([[1, 1]])).toEqual([[1, 1]]);
  });
});

describe("sin trazo de referencia", () => {
  it("no hay juicio que dar, pero tampoco un error: el trazo no vale", () => {
    expect(evaluarTrazo(linea(20, 50, 90, 50, 40), { pts: [], largo: 1 })).toEqual({ toque: false, ok: false, media: 0, largo: 0 });
    expect(evaluarTrazo([[50, 50]], { pts: [], largo: 1 }).toque).toBe(true);
  });
});

describe("los intentos que no valieron", () => {
  const falla = (media: number, largo: number): Juicio => ({ toque: false, ok: false, media, largo });

  it("quedan en el detalle del trazo cuando vale: los últimos 5, con un decimal", () => {
    let e = inicialTrazo;
    for (let i = 0; i < 7; i++) e = alSoltar(e, falla(20.04 + i, 0.5 + i / 100), "practicar", 3);
    e = alSoltar(e, bien, "practicar", 3);
    expect(e.detalle[0].fallos).toBe(7);
    expect(e.detalle[0].rechazos).toEqual([
      { media: 22, largo: 0.5 },
      { media: 23, largo: 0.5 },
      { media: 24, largo: 0.5 },
      { media: 25, largo: 0.6 },
      { media: 26, largo: 0.6 },
    ]);
  });

  it("cada trazo lleva los suyos, y el que vale a la primera no lleva la clave", () => {
    let e = alSoltar(inicialTrazo, bien, "practicar", 3);
    e = alSoltar(e, falla(31.26, 1.04), "practicar", 3);
    e = alSoltar(e, bien, "practicar", 3);
    e = alSoltar(e, bien, "practicar", 3);
    expect(e.detalle[0]).not.toHaveProperty("rechazos");
    expect(e.detalle[1].rechazos).toEqual([{ media: 31.3, largo: 1 }]);
    expect(e.detalle[2]).not.toHaveProperty("rechazos");
    expect(e.intentos).toEqual([]);
  });

  it("un toque no es un intento", () => {
    expect(alSoltar(inicialTrazo, toque, "practicar", 3).intentos).toEqual([]);
  });
});

describe("lugaresNumeros", () => {
  const dist = (a: Punto, b: Punto) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const distSeg = (p: Punto, a: Punto, b: Punto) => {
    const l2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 || 1;
    const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / l2));
    return dist(p, [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
  };
  const libre = (p: Punto, es: Esperado[]) =>
    Math.min(...es.flatMap((e) => e.pts.slice(1).map((q, i) => distSeg(p, e.pts[i], q))));
  const trazo = (x0: number, y0: number, x1: number, y1: number): Esperado => ({
    pts: linea(x0, y0, x1, y1),
    largo: Math.hypot(x1 - x0, y1 - y0),
  });

  it("el número va detrás del inicio del trazo, si ahí hay sitio", () => {
    const [p] = lugaresNumeros([trazo(40, 50, 90, 50)]);
    expect(p![0]).toBeLessThan(40);
    expect(Math.abs(p![1] - 50)).toBeLessThan(1);
  });

  it("cabe en la caja y queda lejos de la tinta, también si el trazo empieza en el borde", () => {
    const es = [trazo(50, 8, 50, 70), trazo(20, 30, 90, 30), trazo(8, 90, 100, 90)];
    for (const p of lugaresNumeros(es)) {
      expect(p![0]).toBeGreaterThanOrEqual(5);
      expect(p![0]).toBeLessThanOrEqual(104);
      expect(p![1]).toBeGreaterThanOrEqual(5);
      expect(p![1]).toBeLessThanOrEqual(104);
    }
    const [arriba] = lugaresNumeros(es);
    expect(libre(arriba!, [es[1]])).toBeGreaterThan(3);
  });

  it("dos trazos que empiezan juntos no se pisan los números", () => {
    const es = [trazo(50, 50, 90, 50), trazo(50, 56, 90, 56)];
    const [a, b] = lugaresNumeros(es);
    expect(dist(a!, b!)).toBeGreaterThanOrEqual(5);
  });

  it("con trazos reales, el número que no cabe a 7 u se va a 10, encima de su inicio, y no toca la tinta", () => {
    for (const es of [HO, NO]) {
      const lugares = lugaresNumeros(es);
      lugares.forEach((p, i) => {
        // la tinta es de 5,6 u y el dígito, de 5,6: a 5,5 del eje de cualquier trazo ya no se tocan
        expect(libre(p!, es), `número ${i + 1}`).toBeGreaterThanOrEqual(5.5);
        // y cada número está más cerca de su inicio que del de cualquier otro trazo
        es.forEach((otro, j) => {
          if (j !== i) expect(dist(p!, es[i].pts[0])).toBeLessThanOrEqual(dist(p!, otro.pts[0]));
        });
      });
    }
    const cuatro = lugaresNumeros(HO)[3]!;
    expect(dist(cuatro, HO[3].pts[0])).toBeCloseTo(10);
    expect(cuatro[1]).toBeLessThan(HO[3].pts[0][1]);
    const uno = lugaresNumeros(NO)[0]!;
    expect(dist(uno, NO[0].pts[0])).toBeCloseTo(10);
    expect(uno[1]).toBeLessThan(NO[0].pts[0][1]);
  });

  it("los que sí caben se quedan a 7 u: la segunda vuelta es solo para los que no", () => {
    const lugares = lugaresNumeros(HO);
    for (const i of [0, 1, 2]) expect(dist(lugares[i]!, HO[i].pts[0])).toBeCloseTo(7);
  });

  it("un trazo sin puntos no tiene número, y no estorba", () => {
    expect(lugaresNumeros([{ pts: [], largo: 1 }, trazo(40, 50, 90, 50)])[0]).toBeNull();
    expect(lugaresNumeros([{ pts: [], largo: 1 }, trazo(40, 50, 90, 50)])[1]).not.toBeNull();
  });
});
