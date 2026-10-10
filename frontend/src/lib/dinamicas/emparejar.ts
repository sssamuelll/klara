import type { Evidencia, Faceta } from "../../api/types";

/**
 * El tablero de parejas (spec 2026-10-09 §3.2): dos columnas barajadas, contra
 * el reloj. Cada pareja deja una evidencia, y solo en práctica.
 */
export interface Par {
  item: string;
  izquierda: string;
  derecha: string;
}

export interface ContenidoEmparejar {
  pares: Par[];
  segundos: number;
  lang_izquierda: string | null;
  faceta: Faceta;
}

export type Lado = "izq" | "der";
export type EstadoFicha = "elegida" | "hecha" | "mal";

export interface EstadoTablero {
  /** Ítems en el orden de cada columna. */
  izquierda: string[];
  derecha: string[];
  elegida: { lado: Lado; item: string } | null;
  hechas: string[];
  /** Ítems con algún intento fallido: su pareja ya no cuenta como acierto. */
  falladas: string[];
  /** La última ficha que falló, para sacudirla. */
  ultimoMal: { lado: Lado; item: string } | null;
  terminado: boolean;
}

export function inicialTablero(izquierda: string[], derecha: string[]): EstadoTablero {
  return { izquierda, derecha, elegida: null, hechas: [], falladas: [], ultimoMal: null, terminado: false };
}

/** La primera ficha queda elegida; la segunda, del otro lado, cierra la pareja o falla. */
export function tocar(e: EstadoTablero, lado: Lado, item: string): EstadoTablero {
  if (e.terminado || e.hechas.includes(item)) return e;
  if (e.elegida === null || e.elegida.lado === lado) {
    return { ...e, elegida: { lado, item }, ultimoMal: null };
  }
  if (e.elegida.item === item) {
    const hechas = [...e.hechas, item];
    return { ...e, elegida: null, ultimoMal: null, hechas, terminado: hechas.length === e.izquierda.length };
  }
  const falladas = [...new Set([...e.falladas, e.elegida.item, item])];
  return { ...e, elegida: null, falladas, ultimoMal: { lado, item } };
}

/** Termina el tablero: ni la elegida ni la última fallada se quedan marcadas en uno que ya acabó. */
export function seAcaboElTiempo(e: EstadoTablero): EstadoTablero {
  return e.terminado ? e : { ...e, elegida: null, ultimoMal: null, terminado: true };
}

export function estadoFicha(e: EstadoTablero, lado: Lado, item: string): EstadoFicha | undefined {
  if (e.hechas.includes(item)) return "hecha";
  if (e.elegida?.lado === lado && e.elegida.item === item) return "elegida";
  if (e.ultimoMal?.lado === lado && e.ultimoMal.item === item) return "mal";
  return undefined;
}

/** Una por pareja: acierto si la cerró sin ningún intento fallido con sus fichas. */
export function evidenciasTablero(c: ContenidoEmparejar, e: EstadoTablero, ms: number): Evidencia[] {
  return c.pares.map((p) => ({
    item: p.item,
    faceta: c.faceta,
    acierto: e.hechas.includes(p.item) && !e.falladas.includes(p.item),
    pistas: 0,
    ms,
  }));
}
