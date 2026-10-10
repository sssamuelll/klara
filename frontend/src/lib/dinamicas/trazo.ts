import type { Evidencia, Modo } from "../../api/types";

/**
 * El juicio de un trazo (spec 2026-10-09 §5.5), sin DOM: el componente le pasa
 * los puntos del dedo y el trazo de KanjiVG ya muestreado.
 *
 * Remuestrea los dos a N puntos por largo de arco y mira la distancia media
 * entre pares y la razón de largos. La dirección sale gratis: un trazo al revés
 * dispara la media.
 */
export type Punto = [number, number];

export const N = 24;
// Perillas: se afinan con los `media` y `largo` reales que quedan en el detalle.
// ponytail: UMBRAL_MEDIA es absoluto, así que en los 9 de 104 trazos de ≤ 29 unidades (う え お な ふ や ら)
// el trazo al revés también vale (media 8,7–11,9); si molesta, `min(UMBRAL_MEDIA, 0.3 * largo)`. Y `largo`
// suma el ruido del dedo: con ≥ 120 puntos y ±1 px, 16 de 104 trazos buenos pasan de LARGO_MAX (con ≤ 60,
// ninguno); si pasa, descartar los puntos a menos de 1 unidad del anterior antes de medir.
export const UMBRAL_MEDIA = 12;
export const LARGO_MIN = 0.55;
export const LARGO_MAX = 1.7;
/** Menos que esto es un toque, no un trazo: se ignora. */
export const TOQUE_MIN = 4;

export interface Esperado {
  pts: Punto[];
  largo: number;
}

export interface Juicio {
  toque: boolean;
  ok: boolean;
  media: number;
  largo: number;
}

export function largo(pts: Punto[]): number {
  let total = 0;
  for (let i = 1; i < pts.length; i++) total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return total;
}

/** Remuestrea por largo de arco a `n` puntos; null si es un toque. */
export function remuestrear(pts: Punto[], n = N): Punto[] | null {
  if (pts.length < 2) return null;
  const acum = [0];
  for (let i = 1; i < pts.length; i++) {
    acum.push(acum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  }
  const total = acum[acum.length - 1];
  if (total < TOQUE_MIN) return null;
  const out: Punto[] = [];
  let j = 0;
  for (let k = 0; k < n; k++) {
    const objetivo = (total * k) / (n - 1);
    while (j < acum.length - 2 && acum[j + 1] < objetivo) j++;
    const tramo = acum[j + 1] - acum[j] || 1;
    const u = Math.min(1, Math.max(0, (objetivo - acum[j]) / tramo));
    out.push([pts[j][0] + (pts[j + 1][0] - pts[j][0]) * u, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * u]);
  }
  return out;
}

export function evaluarTrazo(puntos: Punto[], esperado: Esperado): Juicio {
  const r = remuestrear(puntos);
  if (!r) return { toque: true, ok: false, media: 0, largo: 0 };
  const media = r.reduce((s, p, i) => s + Math.hypot(p[0] - esperado.pts[i][0], p[1] - esperado.pts[i][1]), 0) / N;
  const razon = largo(puntos) / esperado.largo;
  return { toque: false, ok: media < UMBRAL_MEDIA && razon > LARGO_MIN && razon < LARGO_MAX, media, largo: razon };
}

export interface DetalleTrazo {
  n: number;
  media: number;
  largo: number;
  fallos: number;
}

export interface EstadoTrazo {
  /** El índice del trazo que toca. */
  actual: number;
  /** Fallos en el trazo actual. */
  fallos: number;
  pistas: number;
  /** La pista del trazo actual está a la vista. */
  mostrando: boolean;
  detalle: DetalleTrazo[];
  terminado: boolean;
}

export const inicialTrazo: EstadoTrazo = {
  actual: 0,
  fallos: 0,
  pistas: 0,
  mostrando: false,
  detalle: [],
  terminado: false,
};

/** Fallos en un mismo trazo antes de enseñarlo: dos en práctica, uno en prueba. */
export function fallosParaPista(modo: Modo): number {
  return modo === "comprobar" ? 1 : 2;
}

const redondo = (x: number) => Math.round(x * 100) / 100;

export function alSoltar(e: EstadoTrazo, j: Juicio, modo: Modo, total: number): EstadoTrazo {
  if (e.terminado || j.toque) return e;
  if (j.ok) {
    const actual = e.actual + 1;
    return {
      ...e,
      actual,
      fallos: 0,
      mostrando: false,
      terminado: actual >= total,
      detalle: [...e.detalle, { n: actual, media: redondo(j.media), largo: redondo(j.largo), fallos: e.fallos }],
    };
  }
  const fallos = e.fallos + 1;
  const pista = !e.mostrando && fallos >= fallosParaPista(modo);
  return { ...e, fallos, mostrando: e.mostrando || pista, pistas: e.pistas + (pista ? 1 : 0) };
}

/** Una evidencia por kana: hasta dos pistas sigue siendo acierto (`hard`). */
export function evidenciaTrazo(item: string, e: EstadoTrazo, ms: number): Evidencia {
  return { item, faceta: "escribir", acierto: e.pistas <= 2, pistas: e.pistas, ms, detalle: { trazos: e.detalle } };
}

/**
 * La mnemotecnia es español con algún kana dentro («Es さ en el espejo…»). Cada
 * tramo de kana lleva su `lang="ja"` (el lector lo dice con voz japonesa y
 * `.k-note [lang="ja"]` le da su fuente); el resto, no.
 */
export function partirKana(texto: string): { texto: string; ja: boolean }[] {
  // Con grupo de captura, `split` alterna: lo de fuera en pares, el kana en impares.
  return texto
    .split(/([\u3040-\u30ff]+)/)
    .map((t, i) => ({ texto: t, ja: i % 2 === 1 }))
    .filter((p) => p.texto !== "");
}
