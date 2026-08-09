import type { CardOut, ModulePathItem } from "../api/types";

export type PasoId = "leer" | "pronunciar" | "hablar" | "repasar";

export interface PasoVM {
  n: string;
  id: PasoId;
  to: string;
  e: "ahora" | "luego";
}

export interface CourseVM {
  id: "aleman";
  progreso: number;
  vencen: number | null;
  modules: ModulePathItem[] | null;
  pasos: PasoVM[];
}

// ponytail: F1 no tiene máquina de estados de pasos — "ahora" es siempre el
// primero y no existe "hecha"; la máquina real llega con plan_steps en F3.
export function buildCourseVM(args: {
  modules: ModulePathItem[] | null;
  due: CardOut[] | null;
  latestStoryId: string | null;
}): CourseVM {
  const { modules, due, latestStoryId } = args;
  const total = modules?.length ?? 0;
  const done = modules?.filter((m) => m.completed).length ?? 0;
  const leerTo = latestStoryId ? `/story/${latestStoryId}` : "/story/new";
  // ponytail: 02 y 04 apuntan ambos a /review — hoy la cola de Practice mezcla
  // pronunciación y repaso SRS; F2 separa Repaso en su propia pantalla.
  const pasos: PasoVM[] = [
    { n: "01", id: "leer", to: leerTo, e: "ahora" },
    { n: "02", id: "pronunciar", to: "/review", e: "luego" },
    { n: "03", id: "hablar", to: "/chat", e: "luego" },
    { n: "04", id: "repasar", to: "/review", e: "luego" },
  ];
  return {
    id: "aleman",
    progreso: total ? done / total : 0,
    vencen: due ? due.length : null,
    modules,
    pasos,
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
