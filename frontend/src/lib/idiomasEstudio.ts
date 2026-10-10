import type { MapaResumen } from "../api/types";

/** Lo que Ajustes sabe de los mapas: `null` mientras llegan y `"fallo"` si no llegaron. */
export type MapasCargados = MapaResumen[] | "fallo" | null;

/** Marca o desmarca un idioma de estudio (spec 2026-10-09 §5.6). Siempre queda al
 *  menos uno, y la lista sale en el orden de los mapas. */
export function alternarIdioma(actual: string[], idioma: string, orden: string[]): string[] {
  if (actual.includes(idioma)) return actual.length > 1 ? actual.filter((i) => i !== idioma) : actual;
  return orden.filter((i) => i === idioma || actual.includes(i));
}

/** Lo que va en `study_languages` al guardar, o `undefined` para no mandarlo. Solo si el aprendiz la
 *  cambió: la copia del formulario sale de `user`, así que mandarla siempre pisaría lo del servidor con
 *  una lista vieja y fijaría como elegida la que solo salía de `target_language`. Y solo con los mapas a
 *  la vista: sin ellos (cargando, caídos o ninguno) no hay selector, y la lista no se arma a ciegas. */
export function estudioParaGuardar(guardado: string[], estudio: string[], mapas: MapasCargados): string[] | undefined {
  if (!Array.isArray(mapas) || mapas.length === 0) return undefined;
  return estudio.join() === guardado.join() ? undefined : estudio;
}
