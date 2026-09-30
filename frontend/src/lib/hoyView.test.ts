import { describe, expect, it } from "vitest";
import type { TodayOut } from "../api/types";
import { apiBase } from "./apiBase";
import { buildHoyVM, medianocheLocal } from "./hoyView";

const SIN_HISTORIA: TodayOut["story"] = {
  state: "request", id: null, library_entry_id: null, module_id: null,
  title: null, subtitle: null, illustration_path: null,
};

const hoy = (over: Partial<TodayOut> = {}): TodayOut => ({
  now: "read",
  steps: { read: false, pronounce: false, speak: false, review: false },
  story: SIN_HISTORIA,
  sentence: null,
  due: 12,
  module: null,
  ...over,
});

describe("buildHoyVM", () => {
  it("sin datos: cuatro paradas pendientes, sin panel, 15 minutos", () => {
    const vm = buildHoyVM(null);
    expect(vm.paradas.map((p) => p.estado)).toEqual(["pending", "pending", "pending", "pending"]);
    expect(vm.panel).toBeNull();
    expect(vm.minutos).toBe(15);
    expect(vm.paradas[0].accion).toEqual({ tipo: "ir", to: "/story/new" });
  });

  it("historia nueva de la biblioteca: el panel la reclama y trae su ilustración", () => {
    const vm = buildHoyVM(hoy({
      story: {
        state: "new", id: null, library_entry_id: "e1", module_id: "m1",
        title: "Die Bäckerei am Samstag", subtitle: "Una panadería.", illustration_path: "/illustrations/abc",
      },
    }));
    expect(vm.paradas[0].estado).toBe("now");
    expect(vm.panel).toEqual({
      tipo: "leer", estado: "new", titulo: "Die Bäckerei am Samstag", subtitulo: "Una panadería.",
      arte: `${apiBase()}/illustrations/abc`, accion: { tipo: "reclamar", moduleId: "m1" },
    });
  });

  it("una historia pedida fuera de un módulo se abre, nunca se reclama, y sin arte queda tipográfica", () => {
    const vm = buildHoyVM(hoy({
      story: { ...SIN_HISTORIA, state: "continue", id: "s1", title: "Mein Hund" },
    }));
    expect(vm.panel).toMatchObject({ tipo: "leer", arte: null, accion: { tipo: "ir", to: "/estudiar/s1" } });
  });

  it("sin historia ni biblioteca, a /story/new", () => {
    expect(buildHoyVM(hoy()).panel).toMatchObject({
      tipo: "leer", estado: "request", accion: { tipo: "ir", to: "/story/new" },
    });
  });

  it("Leer hecha: la fila muestra la historia y el panel pasa a Pronunciar con su frase", () => {
    const vm = buildHoyVM(hoy({
      now: "pronounce",
      steps: { read: true, pronounce: false, speak: false, review: false },
      story: { ...SIN_HISTORIA, state: "done", id: "s1", module_id: "m1", title: "Die Bäckerei am Samstag" },
      sentence: { target: "Der Bäcker öffnet um acht.", native: "El panadero abre a las ocho." },
    }));
    expect(vm.paradas[0]).toMatchObject({
      estado: "done", historia: "Die Bäckerei am Samstag", accion: { tipo: "ir", to: "/estudiar/s1" },
    });
    expect(vm.panel).toEqual({
      tipo: "pronunciar",
      frase: { target: "Der Bäcker öffnet um acht.", native: "El panadero abre a las ocho." },
      accion: { tipo: "ir", to: "/pronunciar" },
    });
    expect(vm.minutos).toBe(12);
  });

  it("Repasar hecha con fichas vencidas: HECHO, y el número sigue a la vista", () => {
    const vm = buildHoyVM(hoy({ steps: { read: false, pronounce: false, speak: false, review: true }, due: 12 }));
    expect(vm.paradas[3]).toMatchObject({ id: "repasar", estado: "done", vencen: 12 });
  });

  it("todo hecho: sin panel y cero minutos", () => {
    const vm = buildHoyVM(hoy({ now: null, steps: { read: true, pronounce: true, speak: true, review: true }, due: 0 }));
    expect(vm.panel).toBeNull();
    expect(vm.todoHecho).toBe(true);
    expect(vm.minutos).toBe(0);
  });
});

describe("medianocheLocal", () => {
  it("devuelve el instante de la medianoche local del día dado", () => {
    const m = new Date(medianocheLocal(new Date(2026, 8, 30, 17, 40)));
    expect([m.getFullYear(), m.getMonth(), m.getDate(), m.getHours(), m.getMinutes()]).toEqual([2026, 8, 30, 0, 0]);
  });
});
