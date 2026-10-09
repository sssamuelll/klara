import type { Evidencia, Faceta } from "../../api/types";

/** El contenido que arma el backend para `eleccion` (catalogo/generar.py). */
export interface OpcionEleccion {
  item: string;
  texto: string;
  lang: string | null;
}

export interface ContenidoEleccion {
  item: string;
  faceta: Faceta;
  pregunta: { texto: string | null; lang: string | null; audio: string | null };
  opciones: OpcionEleccion[];
  correcta: string;
}

export type Tono = "good" | "bad";

export function evaluarEleccion(c: ContenidoEleccion, elegida: string, ms: number): Evidencia {
  return { item: c.item, faceta: c.faceta, acierto: elegida === c.correcta, pistas: 0, ms, detalle: { elegida } };
}

/** Ya respondida: la correcta en bien y la elegida, si falló, en mal. */
export function tonoOpcion(c: ContenidoEleccion, opcion: string, elegida: string | null): Tono | undefined {
  if (elegida === null) return undefined;
  if (opcion === c.correcta) return "good";
  return opcion === elegida ? "bad" : undefined;
}

/** El texto de la respuesta correcta: lo que dice Web Speech si el audio falla. */
export function textoCorrecto(c: ContenidoEleccion): string {
  return c.opciones.find((o) => o.item === c.correcta)?.texto ?? "";
}
