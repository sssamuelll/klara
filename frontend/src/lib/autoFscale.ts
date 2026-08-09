/**
 * Escalón automático de la oración del teleprompter (spec F2 §5.1):
 * 1 → 0.92 → 0.85, piso 0.85. La longitud efectiva pondera la escala de
 * fuente elegida por el usuario; el line-clamp:7 del CSS queda como último
 * recurso para outliers del LLM. Umbrales calibrados a ~25-30 chars/línea
 * en 430px (validados contra contenido real en el PR).
 */
export function autoFscaleStep(target: string, userScale: number): 1 | 0.92 | 0.85 {
  const efectiva = target.length * userScale;
  if (efectiva <= 170) return 1;
  if (efectiva <= 220) return 0.92;
  return 0.85;
}
