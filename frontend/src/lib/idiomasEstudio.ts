/** Marca o desmarca un idioma de estudio (spec 2026-10-09 §5.6). Siempre queda al
 *  menos uno, y la lista sale en el orden de los mapas. */
export function alternarIdioma(actual: string[], idioma: string, orden: string[]): string[] {
  if (actual.includes(idioma)) return actual.length > 1 ? actual.filter((i) => i !== idioma) : actual;
  return orden.filter((i) => i === idioma || actual.includes(i));
}
