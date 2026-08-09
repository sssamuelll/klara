import { describe, expect, it } from "vitest";
import { buildCourseVM, moduleRowEstado } from "./courseView";
import type { ModulePathItem } from "../api/types";

const mod = (over: Partial<ModulePathItem>): ModulePathItem =>
  ({
    id: "m1", sequence_order: 1, title: "x", cefr_level: "A1",
    can_dos: [], grammatical_focus: [],
    encountered: 0, mastered: 0, total: 10,
    gender_encountered: 0, gender_mastered: 0, gender_total: 0,
    stories_finished: 0, stories_to_complete: 5,
    completed: false, is_current: false, unlocked: false, library_available: 0,
    ...over,
  }) as ModulePathItem;

describe("buildCourseVM", () => {
  it("deriva progreso de módulos completados", () => {
    const vm = buildCourseVM({
      modules: [mod({ completed: true }), mod({ id: "m2", is_current: true }), mod({ id: "m3" })],
      due: [], latestStoryId: null,
    });
    expect(vm.progreso).toBeCloseTo(1 / 3);
    expect(vm.modules?.length).toBe(3);
  });

  it("sin datos: progreso 0, vencen null, pasos completos igual", () => {
    const vm = buildCourseVM({ modules: null, due: null, latestStoryId: null });
    expect(vm.progreso).toBe(0);
    expect(vm.vencen).toBeNull();
    expect(vm.modules).toBeNull();
    expect(vm.pasos).toHaveLength(4);
    expect(vm.pasos[0]).toMatchObject({ id: "leer", to: "/story/new", e: "ahora" });
  });

  it("con historia: leer apunta a la historia y es el paso 'ahora'", () => {
    const vm = buildCourseVM({ modules: [], due: [], latestStoryId: "abc" });
    expect(vm.pasos.map((p) => [p.id, p.to])).toEqual([
      ["leer", "/story/abc"],
      ["pronunciar", "/review"],
      ["hablar", "/chat"],
      ["repasar", "/review"],
    ]);
    expect(vm.pasos.filter((p) => p.e === "ahora")).toHaveLength(1);
  });
});

describe("moduleRowEstado", () => {
  it("mapea estados", () => {
    expect(moduleRowEstado({ completed: true, is_current: false, unlocked: true })).toBe("dominado");
    expect(moduleRowEstado({ completed: false, is_current: true, unlocked: true })).toBe("encurso");
    expect(moduleRowEstado({ completed: false, is_current: false, unlocked: true })).toBe("proximo");
    expect(moduleRowEstado({ completed: false, is_current: false, unlocked: false })).toBe("futuro");
  });
});
