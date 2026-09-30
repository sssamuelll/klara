import type { TodayOut, TodayStep } from "../api/types";
import { apiBase } from "./apiBase";

/** Las cuatro paradas del recorrido, en el orden fijo del spec §1.2. */
export type ParadaId = "leer" | "pronunciar" | "hablar" | "repasar";
export type ParadaEstado = "now" | "done" | "pending";

const ORDEN: ParadaId[] = ["leer", "pronunciar", "hablar", "repasar"];
const DEL_API: Record<ParadaId, TodayStep> = {
  leer: "read",
  pronunciar: "pronounce",
  hablar: "speak",
  repasar: "review",
};
/** Los minutos de `curso.paso.*.meta`. */
export const MINUTOS: Record<ParadaId, number> = { leer: 3, pronunciar: 4, hablar: 3, repasar: 5 };
const DESTINO: Record<Exclude<ParadaId, "leer">, string> = {
  pronunciar: "/pronunciar",
  hablar: "/chat",
  repasar: "/repaso",
};

export type Accion = { tipo: "ir"; to: string } | { tipo: "reclamar"; moduleId: string };

export interface Parada {
  id: ParadaId;
  estado: ParadaEstado;
  /** Leer: el título de la historia del día, cuando ya se sabe. */
  historia: string | null;
  /** Repasar: las fichas que vencen. Se ve aunque la parada esté hecha. */
  vencen: number | null;
  accion: Accion;
}

export type Panel =
  | {
      tipo: "leer";
      estado: "continue" | "new" | "request";
      titulo: string | null;
      subtitulo: string | null;
      arte: string | null;
      accion: Accion;
    }
  | { tipo: "pronunciar"; frase: { target: string; native: string } | null; accion: Accion }
  | { tipo: "hablar"; accion: Accion }
  | { tipo: "repasar"; vencen: number; accion: Accion };

export interface HoyVM {
  paradas: Parada[];
  panel: Panel | null;
  /** La suma de los minutos de las paradas que faltan. */
  minutos: number;
  todoHecho: boolean;
}

function accionLeer(story: TodayOut["story"] | null): Accion {
  if (story && (story.state === "done" || story.state === "continue") && story.id) {
    return { tipo: "ir", to: `/estudiar/${story.id}` };
  }
  if (story?.state === "new" && story.module_id) return { tipo: "reclamar", moduleId: story.module_id };
  return { tipo: "ir", to: "/story/new" };
}

function accionDe(id: ParadaId, today: TodayOut | null): Accion {
  return id === "leer" ? accionLeer(today?.story ?? null) : { tipo: "ir", to: DESTINO[id] };
}

/** La ruta de la API es relativa a su base, que en la app nativa es absoluta. */
export function arteSrc(path: string | null): string | null {
  return path ? `${apiBase()}${path}` : null;
}

/** El instante de tu medianoche local: desde cuándo cuenta «hoy». */
export function medianocheLocal(ahora: Date = new Date()): string {
  const d = new Date(ahora);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

function panelDe(today: TodayOut): Panel | null {
  switch (today.now) {
    case "read":
      return {
        tipo: "leer",
        // "done" no puede ser la parada actual: si Leer está hecha, `now` es otra.
        estado: today.story.state === "done" ? "continue" : today.story.state,
        titulo: today.story.title,
        subtitulo: today.story.subtitle,
        arte: arteSrc(today.story.illustration_path),
        accion: accionDe("leer", today),
      };
    case "pronounce":
      return { tipo: "pronunciar", frase: today.sentence, accion: accionDe("pronunciar", today) };
    case "speak":
      return { tipo: "hablar", accion: accionDe("hablar", today) };
    case "review":
      return { tipo: "repasar", vencen: today.due, accion: accionDe("repasar", today) };
    default:
      return null;
  }
}

export function buildHoyVM(today: TodayOut | null): HoyVM {
  const paradas: Parada[] = ORDEN.map((id) => {
    const paso = DEL_API[id];
    const estado: ParadaEstado = today?.now === paso ? "now" : today?.steps[paso] ? "done" : "pending";
    return {
      id,
      estado,
      historia: id === "leer" ? (today?.story.title ?? null) : null,
      vencen: id === "repasar" && today ? today.due : null,
      accion: accionDe(id, today),
    };
  });
  return {
    paradas,
    panel: today ? panelDe(today) : null,
    minutos: paradas.filter((p) => p.estado !== "done").reduce((n, p) => n + MINUTOS[p.id], 0),
    todoHecho: today !== null && today.now === null,
  };
}
