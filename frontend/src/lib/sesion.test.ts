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
});

describe("necesita", () => {
  it("el trazo pide escribir salvo al presentar; oír pide escuchar", () => {
    expect(necesita(act("x", { dinamica: "trazo", faceta: "escribir" }))).toBe("escribir");
    expect(necesita(act("x", { dinamica: "trazo", modo: "presentar", faceta: "escribir" }))).toBeNull();
    expect(necesita(act("x", { faceta: "oir" }))).toBe("escuchar");
    expect(necesita(act("x"))).toBeNull();
    expect(necesita(act("x", { dinamica: "emparejar" }))).toBeNull();
  });
});

describe("etiquetaItem", () => {
  it("se queda con lo que va después del tipo", () => {
    expect(etiquetaItem("ja:kana:か")).toBe("か");
    expect(etiquetaItem("de:sustantivo:Frau")).toBe("Frau");
  });
});
