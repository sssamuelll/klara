import type { CardOut, ModulePathItem } from "../api/types";

export interface CourseVM {
  id: "aleman";
  progreso: number;
  vencen: number | null;
  modules: ModulePathItem[] | null;
}

export function buildCourseVM(args: {
  modules: ModulePathItem[] | null;
  due: CardOut[] | null;
}): CourseVM {
  const { modules, due } = args;
  const total = modules?.length ?? 0;
  const done = modules?.filter((m) => m.completed).length ?? 0;
  return {
    id: "aleman",
    progreso: total ? done / total : 0,
    vencen: due ? due.length : null,
    modules,
  };
}

export type RowEstado = "dominado" | "encurso" | "proximo" | "futuro";

export function moduleRowEstado(
  m: Pick<ModulePathItem, "completed" | "is_current" | "unlocked">
): RowEstado {
  if (m.completed) return "dominado";
  if (m.is_current) return "encurso";
  if (m.unlocked) return "proximo";
  return "futuro";
}
