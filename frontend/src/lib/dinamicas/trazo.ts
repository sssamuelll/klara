import type { Evidencia, Modo } from "../../api/types";

/**
 * El juicio de un trazo (spec 2026-10-09 §5.5), sin DOM: el componente le pasa
 * los puntos del dedo y el trazo de KanjiVG ya muestreado.
 *
 * Remuestrea los dos a N puntos por largo de arco y mira la distancia media
 * entre pares y la razón de largos. La dirección no sale gratis: en un trazo
 * corto, al revés la media también queda bajo el umbral (≈ largo / 2), así que
 * se mira aparte: pareado al derecho tiene que quedar más cerca que al revés.
 * Antes de medir se descarta el pulso del dedo (`decimar`).
 */
export type Punto = [number, number];

export const N = 24;
// Perillas: se afinan con los `media` y `largo` reales que quedan en el detalle, y con `rechazos`: lo que
// midieron los intentos que no valieron.
// ponytail: con `decimar` (PASO_MIN) un pulso de ≤ 0,5 px casi no rechaza trazos buenos (≤ 0,2 % a 60 y a
// 120 Hz, con lienzo de 272 o de 180 px); con ±1 px y un dedo lento (120 Hz, ≤ 40 u/s) todavía rechaza del 18
// al 95 %, y un dedo apoyado con ruido de 1 px (σ) aún se juzga como trazo (85 de 104). Si `rechazos` lo
// muestra: subir PASO_MIN o medir el largo sobre puntos suavizados.
export const UMBRAL_MEDIA = 12;
export const LARGO_MIN = 0.55;
export const LARGO_MAX = 1.7;
/** Menos que esto es un toque, no un trazo: se ignora. */
export const TOQUE_MIN = 4;
/** Entre dos puntos, menos que esto es el pulso del dedo, no el trazo: no suma largo ni cuenta para el toque. */
export const PASO_MIN = 1;

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

/**
 * Quita los puntos que no se alejan `paso` del último que se queda. Un dedo lento
 * y tembloroso manda cientos de eventos de una fracción de unidad: sumados, el
 * trazo sale 2 o 3 veces más largo de lo que es, y un dedo apoyado en el punto
 * parece un trazo. El primero y el último (donde se levantó el dedo) se quedan.
 */
export function decimar(pts: Punto[], paso = PASO_MIN): Punto[] {
  if (pts.length < 2) return pts;
  const out: Punto[] = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const q = out[out.length - 1];
    if (Math.hypot(pts[i][0] - q[0], pts[i][1] - q[1]) >= paso) out.push(pts[i]);
  }
  const ultimo = pts[pts.length - 1];
  if (out.length === 1) out.push(ultimo);
  else out[out.length - 1] = ultimo;
  return out;
}

const distanciaMedia = (a: Punto[], b: Punto[]) =>
  a.reduce((s, p, i) => s + Math.hypot(p[0] - b[i][0], p[1] - b[i][1]), 0) / N;

export function evaluarTrazo(puntos: Punto[], esperado: Esperado): Juicio {
  const pts = decimar(puntos);
  const r = remuestrear(pts);
  if (!r) return { toque: true, ok: false, media: 0, largo: 0 };
  // Sin trazo de referencia (el muestreo del DOM falló) no hay con qué comparar: no vale, y no revienta.
  if (esperado.pts.length !== N) return { toque: false, ok: false, media: 0, largo: 0 };
  const media = distanciaMedia(r, esperado.pts);
  const alReves = distanciaMedia(r, [...esperado.pts].reverse());
  const razon = largo(pts) / esperado.largo;
  return {
    toque: false,
    ok: media < UMBRAL_MEDIA && media < alReves && razon > LARGO_MIN && razon < LARGO_MAX,
    media,
    largo: razon,
  };
}

/** Lo que midió `evaluarTrazo` de un intento que no valió, con un decimal. */
export interface Intento {
  media: number;
  largo: number;
}

/** Cuántos intentos fallados se guardan por trazo: bastan para afinar los umbrales. */
const INTENTOS_MAX = 5;

export interface DetalleTrazo {
  n: number;
  media: number;
  largo: number;
  fallos: number;
  /** Los últimos intentos que no valieron en este trazo; sin la clave si valió a la primera. */
  rechazos?: Intento[];
}

export interface EstadoTrazo {
  /** El índice del trazo que toca. */
  actual: number;
  /** Fallos en el trazo actual. */
  fallos: number;
  /** Lo medido en los últimos intentos fallados del trazo actual. */
  intentos: Intento[];
  pistas: number;
  /** La pista del trazo actual está a la vista. */
  mostrando: boolean;
  detalle: DetalleTrazo[];
  terminado: boolean;
}

export const inicialTrazo: EstadoTrazo = {
  actual: 0,
  fallos: 0,
  intentos: [],
  pistas: 0,
  mostrando: false,
  detalle: [],
  terminado: false,
};

/** Fallos en un mismo trazo antes de enseñarlo: dos en práctica, uno en prueba. */
export function fallosParaPista(modo: Modo): number {
  return modo === "comprobar" ? 1 : 2;
}

const redondo = (x: number, decimales = 2) => Math.round(x * 10 ** decimales) / 10 ** decimales;

export function alSoltar(e: EstadoTrazo, j: Juicio, modo: Modo, total: number): EstadoTrazo {
  if (e.terminado || j.toque) return e;
  if (j.ok) {
    const actual = e.actual + 1;
    return {
      ...e,
      actual,
      fallos: 0,
      intentos: [],
      mostrando: false,
      terminado: actual >= total,
      detalle: [
        ...e.detalle,
        {
          n: actual,
          media: redondo(j.media),
          largo: redondo(j.largo),
          fallos: e.fallos,
          ...(e.intentos.length > 0 ? { rechazos: e.intentos } : {}),
        },
      ],
    };
  }
  const fallos = e.fallos + 1;
  const pista = !e.mostrando && fallos >= fallosParaPista(modo);
  const intentos = [...e.intentos, { media: redondo(j.media, 1), largo: redondo(j.largo, 1) }].slice(-INTENTOS_MAX);
  return { ...e, fallos, intentos, mostrando: e.mostrando || pista, pistas: e.pistas + (pista ? 1 : 0) };
}

/**
 * Una evidencia por kana: hasta dos pistas sigue siendo acierto (`hard`). Pero la pista llega una sola vez
 * por trazo, así que en un kana de uno o dos trazos `pistas <= 2` se cumpliría siempre y nunca habría
 * `again`: además, tiene que haber algún trazo que se hiciera sin pista.
 */
export function evidenciaTrazo(item: string, e: EstadoTrazo, ms: number, total: number): Evidencia {
  return {
    item,
    faceta: "escribir",
    acierto: e.pistas <= 2 && e.pistas < total,
    pistas: e.pistas,
    ms,
    detalle: { trazos: e.detalle },
  };
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

/** Del inicio de un trazo al centro de su número. */
const NUM_DIST = 7;
/** Lo más cerca que puede quedar un número de la tinta (medido a su eje) o de otro número. */
const NUM_LIBRE = 5.5;
/** Lo más cerca del borde de la caja de 109 que puede quedar el centro de un número. */
const NUM_BORDE = 5;
/** Dónde probar, girando desde «detrás del inicio»: primero atrás, luego a los lados. */
const NUM_GIROS = [0, 50, -50, 100, -100, 150, -150, 180].map((g) => (g * Math.PI) / 180);

function distanciaASegmento(p: Punto, a: Punto, b: Punto): number {
  const l2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 || 1;
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / l2));
  return Math.hypot(p[0] - (a[0] + t * (b[0] - a[0])), p[1] - (a[1] + t * (b[1] - a[1])));
}

/**
 * Dónde va el número de cada trazo al presentar (KanjiVG no lo trae): junto al inicio, detrás del trazo si
 * ahí hay sitio y, si no, hacia un lado; sin tocar la tinta de ningún trazo ni otro número, y dentro de la
 * caja. `null` para un trazo sin muestras.
 */
export function lugaresNumeros(esperados: Esperado[]): (Punto | null)[] {
  const tramos = esperados.flatMap((e) => e.pts.slice(1).map((q, i): [Punto, Punto] => [e.pts[i], q]));
  const puestos: Punto[] = [];
  const dentro = (v: number) => Math.min(109 - NUM_BORDE, Math.max(NUM_BORDE, v));
  return esperados.map((e) => {
    if (e.pts.length < 2) return null;
    const [x0, y0] = e.pts[0];
    const atras = Math.atan2(y0 - e.pts[1][1], x0 - e.pts[1][0]);
    const holgura = (p: Punto) =>
      Math.min(
        ...tramos.map(([a, b]) => distanciaASegmento(p, a, b)),
        ...puestos.map((q) => Math.hypot(p[0] - q[0], p[1] - q[1])),
      );
    let mejor: Punto = [x0, y0];
    let mejorHolgura = -1;
    for (const giro of NUM_GIROS) {
      const p: Punto = [dentro(x0 + Math.cos(atras + giro) * NUM_DIST), dentro(y0 + Math.sin(atras + giro) * NUM_DIST)];
      const h = holgura(p);
      if (h >= NUM_LIBRE) {
        mejor = p;
        break;
      }
      if (h > mejorHolgura) {
        mejor = p;
        mejorHolgura = h;
      }
    }
    puestos.push(mejor);
    return mejor;
  });
}
