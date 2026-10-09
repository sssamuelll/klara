import { describe, expect, it } from "vitest";
import type { ActividadOut, Evidencia } from "../api/types";
import {
  etiquetaItem,
  inicialSesion,
  necesita,
  porReforzar,
  sesionReducer,
  type AccionSesion,
  type EstadoSesion,
} from "./sesion";

const act = (id: string, over: Partial<ActividadOut> = {}): ActividadOut => ({
  id,
  dinamica: "eleccion",
  modo: "practicar",
  items: ["ja:kana:あ"],
  faceta: "reconocer",
  repaso: false,
  contenido: {},
  ...over,
});
const ev = (over: Partial<Evidencia> = {}): Evidencia => ({
  item: "ja:kana:あ",
  faceta: "reconocer",
  acierto: true,
  pistas: 0,
  ms: 900,
  ...over,
});
const correr = (acciones: AccionSesion[], e: EstadoSesion = inicialSesion) =>
  acciones.reduce(sesionReducer, e);
const cargar = (actividades: ActividadOut[]): AccionSesion => ({ tipo: "cargada", actividades });
const responde = (over: Partial<Evidencia> = {}): AccionSesion => ({ tipo: "resultado", evidencias: [ev(over)] });
/** Congela hacia abajo: en un módulo ESM (estricto), mutar algo congelado lanza. */
function congelar<T>(x: T): T {
  if (typeof x === "object" && x !== null && !Object.isFrozen(x)) {
    Object.freeze(x);
    Object.values(x).forEach(congelar);
  }
  return x;
}

describe("sesionReducer", () => {
  it("sin actividades queda vacía", () => {
    expect(correr([cargar([])]).fase).toBe("vacia");
  });

  it("presentar avanza sin pasar por resultado", () => {
    const e = correr([
      cargar([act("a0", { dinamica: "trazo", modo: "presentar", faceta: "escribir" }), act("a1")]),
      { tipo: "resultado", evidencias: [] },
    ]);
    expect([e.fase, e.idx]).toEqual(["actividad", 1]);
  });

  it("si acierta, queda en resultado con todoBien y luego sigue", () => {
    let e = correr([cargar([act("a0"), act("a1")]), responde()]);
    expect([e.fase, e.todoBien]).toEqual(["resultado", true]);
    e = sesionReducer(e, { tipo: "seguir" });
    expect([e.fase, e.idx]).toEqual(["actividad", 1]);
  });

  it("un acierto con pista no es todoBien", () => {
    expect(correr([cargar([act("a0")]), responde({ pistas: 1 })]).todoBien).toBe(false);
  });

  it("un segundo resultado en la misma actividad se ignora", () => {
    const una = correr([cargar([act("a0"), act("a1")]), responde({ acierto: false })]);
    expect(sesionReducer(una, responde())).toBe(una);
  });

  it("lo fallado en práctica vuelve una vez, tres actividades después", () => {
    const cola = ["a0", "a1", "a2", "a3", "a4", "a5"].map((id) => act(id));
    let e = correr([cargar(cola), responde({ acierto: false })]);
    expect(e.cola.map((a) => a.id)).toEqual(["a0", "a1", "a2", "a3", "a0~r", "a4", "a5"]);
    const sigueBien: AccionSesion[] = [responde(), { tipo: "seguir" }];
    e = correr([{ tipo: "seguir" }, ...sigueBien, ...sigueBien, ...sigueBien], e);
    expect(e.cola[e.idx].id).toBe("a0~r");
    e = sesionReducer(e, responde({ acierto: false }));
    expect(e.cola.filter((a) => a.id.startsWith("a0")).length).toBe(2);
  });

  it("cerca del final, el reintento va al final", () => {
    const e = correr([cargar([act("a0"), act("a1")]), responde({ acierto: false })]);
    expect(e.cola.map((a) => a.id)).toEqual(["a0", "a1", "a0~r"]);
  });

  it("en prueba no se repite y entra al resumen", () => {
    const e = correr([cargar([act("a0", { modo: "comprobar" }), act("a1")]), responde({ acierto: false })]);
    expect(e.cola).toHaveLength(2);
    expect(e.resumen).toEqual({ "ja:kana:あ": { reconocer: "mal" } });
  });

  it("el resumen se queda con lo peor de cada faceta", () => {
    const prueba = (id: string) => act(id, { modo: "comprobar" });
    const e = correr([
      cargar([prueba("a0"), prueba("a1"), prueba("a2")]),
      responde({ acierto: false }),
      { tipo: "seguir" },
      responde(),
      { tipo: "seguir" },
      responde({ pistas: 1, faceta: "oir" }),
    ]);
    expect(e.resumen).toEqual({ "ja:kana:あ": { reconocer: "mal", oir: "pista" } });
    expect(porReforzar(e)).toEqual(["ja:kana:あ"]);
  });

  it("la práctica no entra al resumen", () => {
    expect(correr([cargar([act("a0")]), responde()]).resumen).toEqual({});
  });

  it("apagar escribir salta los trazos, también el de ahora", () => {
    const trazo = (id: string) => act(id, { dinamica: "trazo", faceta: "escribir" });
    const e = correr([cargar([trazo("a0"), trazo("a1"), act("a2")]), { tipo: "apagar", capacidad: "escribir" }]);
    expect([e.fase, e.idx]).toEqual(["actividad", 2]);
    expect(e.saltadas).toEqual(["a0", "a1"]);
  });

  it("si se salta todo, termina", () => {
    const oir = (id: string) => act(id, { faceta: "oir" });
    const e = correr([cargar([oir("a0"), oir("a1")]), { tipo: "apagar", capacidad: "escuchar" }]);
    expect(e.fase).toBe("fin");
  });

  it("termina después de la última", () => {
    const e = correr([cargar([act("a0")]), responde(), { tipo: "seguir" }]);
    expect(e.fase).toBe("fin");
  });

  it("cuenta los envíos fallidos sin cambiar de fase", () => {
    const e = correr([cargar([act("a0")]), { tipo: "envioFallido" }, { tipo: "envioFallido" }]);
    expect([e.fase, e.enviosFallidos]).toEqual(["actividad", 2]);
  });

  it("cargando vuelve a empezar", () => {
    const e = correr([cargar([act("a0")]), responde({ acierto: false }), { tipo: "cargando" }]);
    expect(e).toEqual(inicialSesion);
  });

  it("un fallo no es todoBien: la corrección espera al aprendiz", () => {
    const e = correr([cargar([act("a0"), act("a1")]), responde({ acierto: false })]);
    expect([e.fase, e.todoBien]).toEqual(["resultado", false]);
  });

  it("con varias evidencias, un solo fallo basta para reintentar y no ser todoBien", () => {
    const dos = (segunda: Partial<Evidencia>): AccionSesion => ({
      tipo: "resultado",
      evidencias: [ev(), ev({ item: "ja:kana:い", ...segunda })],
    });
    const mal = correr([cargar([act("a0"), act("a1")]), dos({ acierto: false })]);
    expect([mal.todoBien, mal.cola.map((a) => a.id)]).toEqual([false, ["a0", "a1", "a0~r"]]);
    const bien = correr([cargar([act("a0"), act("a1")]), dos({})]);
    expect([bien.todoBien, bien.cola.length]).toEqual([true, 2]);
  });

  it("seguir fuera de resultado y apagar dos veces lo mismo no hacen nada", () => {
    const e = correr([cargar([act("a0")])]);
    expect(sesionReducer(e, { tipo: "seguir" })).toBe(e);
    const sinVoz = sesionReducer(e, { tipo: "apagar", capacidad: "hablar" });
    expect(sesionReducer(sinVoz, { tipo: "apagar", capacidad: "hablar" })).toBe(sinVoz);
  });

  it("apagar en resultado no salta la actividad de ahora; salta la que sigue", () => {
    const trazo = (id: string) => act(id, { dinamica: "trazo", faceta: "escribir" });
    let e = correr([cargar([act("a0"), trazo("a1"), act("a2")]), responde({ acierto: false })]);
    e = sesionReducer(e, { tipo: "apagar", capacidad: "escribir" });
    expect([e.fase, e.idx, e.saltadas]).toEqual(["resultado", 0, []]);
    e = sesionReducer(e, { tipo: "seguir" });
    expect([e.cola[e.idx].id, e.saltadas]).toEqual(["a2", ["a1"]]);
  });

  it("apagar con el reintento ya en cola lo salta como saltado, no como fallado", () => {
    const trazo = (id: string) => act(id, { dinamica: "trazo", faceta: "escribir" });
    const cola = [trazo("a0"), act("a1"), act("a2"), act("a3"), act("a4")];
    let e = correr([cargar(cola), responde({ acierto: false })]);
    expect(e.cola.map((a) => a.id)).toEqual(["a0", "a1", "a2", "a3", "a0~r", "a4"]);
    e = correr([{ tipo: "seguir" }, { tipo: "apagar", capacidad: "escribir" }], e);
    for (let i = 0; i < 3; i++) e = correr([responde(), { tipo: "seguir" }], e);
    expect([e.cola[e.idx].id, e.saltadas, e.resumen]).toEqual(["a4", ["a0~r"], {}]);
  });

  it("fallo marca la fase y deja la cola", () => {
    const e = correr([cargar([act("a0")]), { tipo: "fallo" }]);
    expect([e.fase, e.cola.length]).toEqual(["fallo", 1]);
  });

  it("acertar con pistas no es por reforzar", () => {
    const e = correr([cargar([act("a0", { modo: "comprobar" })]), responde({ pistas: 2 })]);
    expect(e.resumen).toEqual({ "ja:kana:あ": { reconocer: "pista" } });
    expect(porReforzar(e)).toEqual([]);
  });

  it("[] solo vale al presentar: en práctica o prueba no avanza", () => {
    // Dos [] seguidos se comían la práctica que sigue al presentar (idx 0→2, sin evidencia ni saltada).
    for (const modo of ["practicar", "comprobar"] as const) {
      const e = correr([cargar([act("a0", { modo }), act("a1")])]);
      expect(sesionReducer(e, { tipo: "resultado", evidencias: [] }), modo).toBe(e);
    }
  });

  it("seguir limpia todoBien: la actividad nueva no hereda el acierto de la anterior", () => {
    let e = correr([cargar([act("a0"), act("a1")]), responde()]);
    expect(e.todoBien).toBe(true);
    e = sesionReducer(e, { tipo: "seguir" });
    expect([e.fase, e.todoBien]).toEqual(["actividad", false]);
  });

  it("no muta el estado ni las cargas: una sesión entera con todo congelado", () => {
    congelar(inicialSesion); // lo comparten `cargando` y `cargada`: si algo lo empuja, revienta
    const trazo = (id: string) => act(id, { dinamica: "trazo", faceta: "escribir" });
    const acciones: AccionSesion[] = [
      cargar([
        act("a0", { dinamica: "trazo", modo: "presentar", faceta: "escribir" }),
        trazo("a1"),
        act("a2"),
        act("a3", { modo: "comprobar" }),
        act("a4", { modo: "comprobar", faceta: "oir" }),
        act("a5"),
        act("a6", { modo: "comprobar" }),
      ]),
      { tipo: "resultado", evidencias: [] }, // a0 se presenta
      { tipo: "envioFallido" },
      responde({ acierto: false }), // a1 falla y vuelve como a1~r
      { tipo: "apagar", capacidad: "escribir" }, // con la corrección en pantalla
      { tipo: "seguir" }, // a2
      responde(),
      { tipo: "seguir" }, // a3, de prueba
      { tipo: "resultado", evidencias: [ev({ acierto: false }), ev({ faceta: "oir", pistas: 1 })] },
      { tipo: "seguir" }, // a4, que pide escuchar
      { tipo: "apagar", capacidad: "escuchar" }, // salta a4 y a1~r (pide escribir)
      responde(), // a5
      responde({ acierto: false }), // segundo resultado de a5: se ignora
      { tipo: "seguir" }, // a6, de prueba: vuelve a tocar el resumen del mismo ítem
      responde({ faceta: "oir" }),
      { tipo: "seguir" },
    ];
    let e: EstadoSesion = inicialSesion;
    for (const a of acciones) e = congelar(sesionReducer(e, congelar(a)));
    // El recorrido hizo lo que se creía; si no, congelar no probaría nada.
    expect(e.fase).toBe("fin");
    expect(e.cola.map((a) => a.id)).toEqual(["a0", "a1", "a2", "a3", "a4", "a1~r", "a5", "a6"]);
    expect(e.saltadas).toEqual(["a4", "a1~r"]);
    expect(e.resumen).toEqual({ "ja:kana:あ": { reconocer: "mal", oir: "pista" } });
    expect(e.enviosFallidos).toBe(1);
    expect(sesionReducer(e, { tipo: "fallo" }).fase).toBe("fallo");
    expect(sesionReducer(e, { tipo: "cargando" })).toEqual(inicialSesion);
  });

  it("si falla todo, termina y cada original vuelve una sola vez", () => {
    for (const n of [1, 2, 5, 8]) {
      let e = correr([cargar(Array.from({ length: n }, (_, i) => act(`a${i}`)))]);
      let pasos = 0;
      // Falla hasta los reintentos. El tope evita colgarse si la cola creciera sin fin.
      while (e.fase !== "fin" && pasos < 8 * n) {
        e = sesionReducer(e, e.fase === "actividad" ? responde({ acierto: false }) : { tipo: "seguir" });
        pasos++;
      }
      expect(e.fase, `n=${n}`).toBe("fin");
      expect(e.cola, `n=${n}`).toHaveLength(2 * n);
      expect(pasos, `n=${n}`).toBe(4 * n); // un resultado y un seguir por cada actividad de la cola
    }
  });
});

describe("necesita", () => {
  it("el trazo pide escribir salvo al presentar; oír pide escuchar", () => {
    expect(necesita(act("x", { dinamica: "trazo", faceta: "escribir" }))).toBe("escribir");
    expect(necesita(act("x", { dinamica: "trazo", modo: "presentar", faceta: "escribir" }))).toBeNull();
    expect(necesita(act("x", { faceta: "oir" }))).toBe("escuchar");
    expect(necesita(act("x"))).toBeNull();
    expect(necesita(act("x", { dinamica: "emparejar" }))).toBeNull();
  });

  it("par-minimo pide escuchar y sombra pide hablar", () => {
    expect(necesita(act("x", { dinamica: "par-minimo", faceta: "oir" }))).toBe("escuchar");
    expect(necesita(act("x", { dinamica: "sombra", faceta: "pronunciar" }))).toBe("hablar");
  });
});

describe("etiquetaItem", () => {
  it("se queda con lo que va después del tipo", () => {
    expect(etiquetaItem("ja:kana:か")).toBe("か");
    expect(etiquetaItem("de:sustantivo:Frau")).toBe("Frau");
  });
});
