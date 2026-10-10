import { describe, expect, it } from "vitest";
import type { Linea } from "../api/types";
import { alDia, buildHoyVM, clavesDelPlan, dekPanel, estadoParada, frase, medianocheLocal, subFila } from "./hoyView";

const BAJADA = "la fila de か: leerla, oírla y escribirla";
const linea = (over: Partial<Linea> = {}): Linea => ({
  idioma: "ja",
  estado: "ahora",
  minutos: 18,
  repasos: 6,
  leccion: { id: "ja/hiragana/ka", titulo: "か き く け こ", bajada: BAJADA },
  hecho: null,
  ...over,
});
/** El mapa terminado y nada que repasar: el servidor la marca `ahora`, con 0 minutos. */
const lineaAlDia = (over: Partial<Linea> = {}): Linea => linea({ leccion: null, repasos: 0, minutos: 0, ...over });

describe("buildHoyVM", () => {
  it("sin datos todavía: nada, y sin el aviso de idiomas", () => {
    const vm = buildHoyVM(null);
    expect(vm.lineas).toEqual([]);
    expect(vm.sinIdiomas).toBe(false);
  });

  it("sin líneas: el aviso de Ajustes", () => {
    expect(buildHoyVM({ lineas: [] }).sinIdiomas).toBe(true);
  });

  it("la línea actual y los minutos de lo que falta", () => {
    const vm = buildHoyVM({
      lineas: [
        linea({ estado: "hecha", minutos: 18, hecho: { repasos: 6, leccion: "か き く け こ" } }),
        linea({ idioma: "de", estado: "ahora", minutos: 17 }),
        linea({ idioma: "en", estado: "pendiente", minutos: 15 }),
      ],
    });
    expect(vm.ahora?.idioma).toBe("de");
    expect(vm.minutos).toBe(32);
    expect([vm.algunaHecha, vm.todoHecho]).toEqual([true, false]);
  });

  it("todo hecho", () => {
    const vm = buildHoyVM({ lineas: [linea({ estado: "hecha", hecho: { repasos: 0, leccion: null } })] });
    expect([vm.todoHecho, vm.minutos, vm.ahora]).toEqual([true, 0, null]);
  });

  it("el orden es el del servidor", () => {
    const vm = buildHoyVM({
      lineas: [linea({ idioma: "en", estado: "hecha" }), linea({ idioma: "ja" }), linea({ idioma: "de", estado: "pendiente" })],
    });
    expect(vm.lineas.map((l) => l.idioma)).toEqual(["en", "ja", "de"]);
  });
});

describe("una línea al día (sin lección y sin repasos)", () => {
  it("alDia: solo cuando no queda ni lección ni repasos", () => {
    expect(alDia(lineaAlDia())).toBe(true);
    expect(alDia(linea({ leccion: null }))).toBe(false); // el mapa terminado, con repasos
    expect(alDia(linea({ repasos: 0 }))).toBe(false); // sin repasos, con la lección
  });

  it("una sola: no hay «estás aquí» y el día está hecho", () => {
    const vm = buildHoyVM({ lineas: [lineaAlDia()] });
    expect([vm.ahora, vm.minutos, vm.algunaHecha, vm.todoHecho, vm.sinIdiomas]).toEqual([null, 0, false, true, false]);
    expect(vm.lineas).toHaveLength(1); // sigue en la lista, como fila
  });

  it("antes de otra con algo que hacer: el «estás aquí» pasa a la siguiente", () => {
    const vm = buildHoyVM({
      lineas: [lineaAlDia({ estado: "ahora" }), linea({ idioma: "de", estado: "pendiente", minutos: 17 })],
    });
    expect(vm.ahora?.idioma).toBe("de");
    expect(vm.minutos).toBe(17);
    expect([vm.algunaHecha, vm.todoHecho]).toEqual([false, false]);
  });

  it("después de otra con algo que hacer: no estorba", () => {
    const vm = buildHoyVM({
      lineas: [linea({ idioma: "de", minutos: 17 }), lineaAlDia({ estado: "pendiente" }), linea({ idioma: "en", estado: "pendiente", minutos: 15 })],
    });
    expect(vm.ahora?.idioma).toBe("de");
    expect(vm.minutos).toBe(32);
  });

  it("todas: nada que hacer hoy", () => {
    const vm = buildHoyVM({ lineas: [lineaAlDia({ estado: "ahora" }), lineaAlDia({ idioma: "de", estado: "pendiente" })] });
    expect([vm.ahora, vm.minutos, vm.algunaHecha, vm.todoHecho]).toEqual([null, 0, false, true]);
  });

  it("una hecha y otra al día: todo hecho", () => {
    const vm = buildHoyVM({
      lineas: [linea({ estado: "hecha", hecho: { repasos: 6, leccion: "か き く け こ" } }), lineaAlDia({ idioma: "de", estado: "ahora" })],
    });
    expect([vm.ahora, vm.minutos, vm.algunaHecha, vm.todoHecho]).toEqual([null, 0, true, true]);
  });

  it("el texto: ni «solo repasos» ni «0 repasos», sino que está al día", () => {
    expect(dekPanel(lineaAlDia())).toEqual({ tipo: "alDia" });
    expect(subFila(lineaAlDia())).toEqual({ tipo: "alDia" });
    expect(subFila(lineaAlDia({ estado: "pendiente" }))).toEqual({ tipo: "alDia" });
  });

  it("hecha y sin nada más: la fila sigue diciendo lo que hiciste", () => {
    const l = lineaAlDia({ estado: "hecha", hecho: { repasos: 6, leccion: "わ を ん" } });
    expect(subFila(l)).toEqual({ tipo: "hecha", repasos: 6, leccion: "わ を ん" });
  });
});

describe("clavesDelPlan", () => {
  const vm = (lineas: Linea[]) => buildHoyVM({ lineas });
  const hecha = linea({ estado: "hecha", hecho: { repasos: 6, leccion: "か き く け こ" } });

  it("con algo por hacer: el plan, o lo que queda si ya hiciste algo", () => {
    expect(clavesDelPlan(vm([linea()]))).toEqual({ rotulo: "hoy.plan", fin: "hoy.fin" });
    expect(clavesDelPlan(vm([hecha, linea({ idioma: "de" })]))).toEqual({ rotulo: "hoy.quedan", fin: "hoy.fin" });
  });

  it("todo hecho porque lo hiciste: «hecho»", () => {
    expect(clavesDelPlan(vm([hecha, lineaAlDia({ idioma: "de" })]))).toEqual({ rotulo: "hoy.planHecho", fin: "hoy.finHecho" });
  });

  it("nada que hacer y nada hecho: al día, no «hecho»", () => {
    expect(clavesDelPlan(vm([lineaAlDia(), lineaAlDia({ idioma: "de", estado: "pendiente" })]))).toEqual({
      rotulo: "hoy.planAlDia",
      fin: "hoy.finAlDia",
    });
  });
});

describe("estadoParada", () => {
  it("el «estás aquí», lo que no pide nada hoy y lo que espera", () => {
    const ahora = linea({ idioma: "de" });
    expect(estadoParada(ahora, ahora)).toBe("now");
    expect(estadoParada(linea({ estado: "hecha" }), ahora)).toBe("done");
    expect(estadoParada(lineaAlDia({ idioma: "en", estado: "pendiente" }), ahora)).toBe("done");
    expect(estadoParada(linea({ idioma: "en", estado: "pendiente" }), ahora)).toBe("pending");
  });

  it("la que el servidor marcó `ahora` pero está al día no es el «estás aquí»", () => {
    const vm = buildHoyVM({ lineas: [lineaAlDia(), linea({ idioma: "de", estado: "pendiente" })] });
    expect(vm.lineas.map((l) => estadoParada(l, vm.ahora))).toEqual(["done", "now"]);
  });

  it("sin «estás aquí», nada es now", () => {
    const l = linea({ estado: "pendiente" });
    expect(estadoParada(l, null)).toBe("pending");
  });
});

describe("dekPanel", () => {
  it("repasos y luego la lección", () => {
    expect(dekPanel(linea())).toEqual({ tipo: "luego", repasos: 6, bajada: BAJADA });
  });

  it("sin repasos, la bajada sola", () => {
    expect(dekPanel(linea({ repasos: 0 }))).toEqual({ tipo: "bajada", bajada: BAJADA });
  });

  it("sin lección, solo repasos", () => {
    expect(dekPanel(linea({ leccion: null }))).toEqual({ tipo: "soloRepasos" });
  });
});

describe("subFila", () => {
  it("hecha: lo que hiciste", () => {
    const l = linea({ estado: "hecha", hecho: { repasos: 6, leccion: "か き く け こ" } });
    expect(subFila(l)).toEqual({ tipo: "hecha", repasos: 6, leccion: "か き く け こ" });
  });

  it("hecha el primer día, sin repasos: solo la lección, sin «0 repasos»", () => {
    const l = linea({ estado: "hecha", hecho: { repasos: 0, leccion: "あ い う え お" } });
    expect(subFila(l)).toEqual({ tipo: "hecha", repasos: null, leccion: "あ い う え お" });
  });

  it("hecha solo de repasos: los repasos", () => {
    const l = linea({ estado: "hecha", hecho: { repasos: 4, leccion: null } });
    expect(subFila(l)).toEqual({ tipo: "hecha", repasos: 4, leccion: null });
  });

  it("pendiente con repasos: los repasos y la bajada", () => {
    expect(subFila(linea({ estado: "pendiente" }))).toEqual({ tipo: "repasos", repasos: 6, detalle: BAJADA });
  });

  it("pendiente sin repasos: la bajada", () => {
    expect(subFila(linea({ estado: "pendiente", repasos: 0 }))).toEqual({ tipo: "bajada", bajada: BAJADA });
  });

  it("sin lección: solo los repasos", () => {
    expect(subFila(linea({ estado: "pendiente", leccion: null }))).toEqual({ tipo: "repasos", repasos: 6, detalle: null });
  });
});

describe("frase y medianocheLocal", () => {
  it("la bajada como frase suelta", () => {
    expect(frase("la fila de か")).toBe("La fila de か.");
  });

  it("la medianoche local del día", () => {
    expect(medianocheLocal(new Date(2026, 9, 9, 15, 30))).toBe(new Date(2026, 9, 9, 0, 0).toISOString());
  });

  it("la medianoche local en los días que cambia la hora (de 23 y de 25 horas)", () => {
    const tz = process.env.TZ;
    try {
      process.env.TZ = "Europe/Berlin";
      // El 29 de marzo de 2026 el reloj salta de las 2 a las 3, y el 25 de octubre retrocede de las 3 a las 2.
      expect(medianocheLocal(new Date("2026-03-29T10:30:00Z"))).toBe("2026-03-28T23:00:00.000Z");
      expect(medianocheLocal(new Date("2026-10-25T10:30:00Z"))).toBe("2026-10-24T22:00:00.000Z");
    } finally {
      if (tz === undefined) delete process.env.TZ;
      else process.env.TZ = tz;
    }
  });
});
