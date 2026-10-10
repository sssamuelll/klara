import type { Linea, TodayOut } from "../api/types";

/** Lo que pinta Hoy (spec 2026-10-09 §5.1): una línea por idioma de estudio. */
export interface HoyVM {
  lineas: Linea[];
  ahora: Linea | null;
  /** Los minutos de lo que falta. */
  minutos: number;
  algunaHecha: boolean;
  todoHecho: boolean;
  /** Ya respondió el servidor y no hay ningún idioma con mapa: aviso de Ajustes. */
  sinIdiomas: boolean;
}

/**
 * Una línea al día: el mapa terminado y ningún repaso por hacer. No hay sesión que abrir (saldría
 * vacía), así que es una fila sin botón. El servidor igual la marca `ahora`, con 0 minutos.
 */
export function alDia(l: Linea): boolean {
  return l.leccion === null && l.repasos === 0;
}

export function buildHoyVM(today: TodayOut | null): HoyVM {
  const lineas = today?.lineas ?? [];
  // Lo que falta es lo que no está hecho y tiene algo que hacer, en el orden del servidor: la primera
  // es el «estás aquí». Una al día ni cuenta ni lo ocupa; pasa a la siguiente que sí tenga qué hacer.
  const faltan = lineas.filter((l) => l.estado !== "hecha" && !alDia(l));
  return {
    lineas,
    ahora: faltan[0] ?? null,
    minutos: faltan.reduce((s, l) => s + l.minutos, 0),
    algunaHecha: lineas.some((l) => l.estado === "hecha"),
    todoHecho: lineas.length > 0 && faltan.length === 0,
    sinIdiomas: today !== null && lineas.length === 0,
  };
}

/** El estado de la parada en el recorrido: el «estás aquí», lo que no pide nada hoy (hecho o al día) y lo que espera. */
export function estadoParada(l: Linea, ahora: Linea | null): "now" | "done" | "pending" {
  if (ahora !== null && l.idioma === ahora.idioma) return "now";
  return l.estado === "hecha" || alDia(l) ? "done" : "pending";
}

/** Lo que dicen el panel y las filas, sin i18n: Hoy.tsx lo traduce. */
export type TextoLinea =
  | { tipo: "alDia" }
  | { tipo: "soloRepasos" }
  | { tipo: "bajada"; bajada: string }
  | { tipo: "luego"; repasos: number; bajada: string }
  | { tipo: "repasos"; repasos: number; detalle: string | null };

export function dekPanel(l: Linea): TextoLinea {
  if (alDia(l)) return { tipo: "alDia" };
  if (!l.leccion) return { tipo: "soloRepasos" };
  if (l.repasos === 0) return { tipo: "bajada", bajada: l.leccion.bajada };
  return { tipo: "luego", repasos: l.repasos, bajada: l.leccion.bajada };
}

export function subFila(l: Linea): TextoLinea {
  if (l.estado === "hecha" && l.hecho) return { tipo: "repasos", repasos: l.hecho.repasos, detalle: l.hecho.leccion };
  if (alDia(l)) return { tipo: "alDia" };
  if (!l.leccion) return { tipo: "repasos", repasos: l.repasos, detalle: null };
  if (l.repasos === 0) return { tipo: "bajada", bajada: l.leccion.bajada };
  return { tipo: "repasos", repasos: l.repasos, detalle: l.leccion.bajada };
}

/** La bajada como frase suelta: mayúscula al principio y punto al final. */
export function frase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1) + ".";
}

/** La medianoche local del dispositivo, en ISO: el `since` de GET /today. */
export function medianocheLocal(ahora: Date = new Date()): string {
  const d = new Date(ahora);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}
