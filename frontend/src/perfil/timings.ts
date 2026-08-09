/* Medición del costo real de responder cada pregunta.
 *
 * Es lo único irreparable del Perfil de Aprendizaje: un `elapsed_ms` mal
 * medido hoy no se arregla después, y la poda por valor informativo (#138 v2a)
 * se entrena justamente con esto. Por eso vive aparte y con test propio.
 *
 * Reglas (spec F1.5): arranca al renderizar la pregunta; descuenta el tiempo
 * con la pestaña oculta —el que se va a hacer café no convierte una pregunta
 * barata en carísima—; volver atrás acumula, porque lo que se quiere medir es
 * el costo total; y por encima del tope es ruido, no señal.
 */

import { OB_TOPE_MS } from "./catalog";

export interface Reloj {
  /** La pestaña se ocultó: deja de contar. */
  pausar(): void;
  /** La pestaña volvió: sigue contando. */
  reanudar(): void;
  /** Cierra y devuelve los ms visibles, ya topeados. */
  cerrar(): number;
}

/** `ahora` se inyecta para poder probar sin esperar tiempo real. */
export function iniciarReloj(ahora: () => number = () => performance.now()): Reloj {
  const t0 = ahora();
  let oculto = 0;
  let desde: number | null = null;

  return {
    pausar() {
      if (desde === null) desde = ahora();
    },
    reanudar() {
      if (desde !== null) {
        oculto += ahora() - desde;
        desde = null;
      }
    },
    cerrar() {
      const pendiente = desde !== null ? ahora() - desde : 0;
      const visible = ahora() - t0 - oculto - pendiente;
      return Math.min(OB_TOPE_MS, Math.max(0, Math.round(visible)));
    },
  };
}

/** Suma al acumulado de esa pregunta (volver atrás no pisa, acumula). */
export function acumular(
  timings: Record<string, number>,
  id: string,
  ms: number
): Record<string, number> {
  return { ...timings, [id]: Math.min(OB_TOPE_MS, (timings[id] ?? 0) + ms) };
}
