import type { ActividadOut, Evidencia, Faceta } from "../api/types";

/**
 * El reproductor de lecciones como máquina de estados pura (spec 2026-10-09
 * §5.4). La ruta (routes/Sesion.tsx) pone los efectos: pedir la sesión, abrir y
 * cerrar la corrida, mandar las evidencias y el avance automático. Aquí solo
 * hay transiciones, para poder probarlas sin DOM.
 */
export type Capacidad = "escuchar" | "hablar" | "escribir";
export type Fase = "cargando" | "fallo" | "vacia" | "actividad" | "resultado" | "fin";
export type Marca = "bien" | "pista" | "mal";

export interface EstadoSesion {
  fase: Fase;
  cola: ActividadOut[];
  idx: number;
  apagadas: Capacidad[];
  saltadas: string[];
  /** Ids originales que ya volvieron una vez: no vuelven dos. */
  reintentadas: string[];
  todoBien: boolean;
  /** Lo que pasó en las pruebas, por ítem y faceta; se queda con lo peor. */
  resumen: Record<string, Partial<Record<Faceta, Marca>>>;
  enviosFallidos: number;
}

export type AccionSesion =
  | { tipo: "cargando" }
  | { tipo: "cargada"; actividades: ActividadOut[] }
  | { tipo: "fallo" }
  | { tipo: "resultado"; evidencias: Evidencia[] }
  | { tipo: "seguir" }
  | { tipo: "apagar"; capacidad: Capacidad }
  | { tipo: "envioFallido" };

/** Si acertó todo, el reproductor sigue solo después de esto. */
export const AUTO_AVANCE_MS = 700;
/** Una actividad de práctica fallada vuelve una vez, después de estas otras. */
export const REINTENTO_TRAS = 3;

export const inicialSesion: EstadoSesion = {
  fase: "cargando",
  cola: [],
  idx: 0,
  apagadas: [],
  saltadas: [],
  reintentadas: [],
  todoBien: false,
  resumen: {},
  enviosFallidos: 0,
};

/** La capacidad sin la que una actividad no se puede hacer. */
export function necesita(a: ActividadOut): Capacidad | null {
  switch (a.dinamica) {
    case "trazo":
      return a.modo === "presentar" ? null : "escribir";
    case "eleccion":
      return a.faceta === "oir" ? "escuchar" : null;
    case "par-minimo":
      return "escuchar";
    case "sombra":
      return "hablar";
    default:
      return null;
  }
}

const GRAVEDAD: Record<Marca, number> = { bien: 0, pista: 1, mal: 2 };

function marcaDe(e: Evidencia): Marca {
  if (!e.acierto) return "mal";
  return e.pistas > 0 ? "pista" : "bien";
}

/**
 * Avanza a `desde` y salta lo que pide una capacidad apagada. Limpia `todoBien`,
 * que era de la actividad que se deja.
 */
function avanzar(e: EstadoSesion, desde: number): EstadoSesion {
  let i = desde;
  const saltadas = [...e.saltadas];
  while (i < e.cola.length) {
    const c = necesita(e.cola[i]);
    if (c === null || !e.apagadas.includes(c)) break;
    saltadas.push(e.cola[i].id);
    i++;
  }
  return { ...e, idx: i, saltadas, todoBien: false, fase: i >= e.cola.length ? "fin" : "actividad" };
}

export function sesionReducer(e: EstadoSesion, a: AccionSesion): EstadoSesion {
  switch (a.tipo) {
    case "cargando":
      return inicialSesion;
    case "cargada":
      return a.actividades.length === 0
        ? { ...inicialSesion, fase: "vacia" }
        : avanzar({ ...inicialSesion, cola: a.actividades }, 0);
    case "fallo":
      return { ...e, fase: "fallo" };
    case "resultado": {
      if (e.fase !== "actividad") return e;
      const act = e.cola[e.idx];
      // `[]` es el «listo, sigue» de presentar (spec §3.1); en práctica o prueba no cuenta.
      if (a.evidencias.length === 0) return act.modo === "presentar" ? avanzar(e, e.idx + 1) : e;
      const original = act.id.replace(/~r$/, "");
      let { cola, reintentadas, resumen } = e;
      if (act.modo === "practicar" && a.evidencias.some((ev) => !ev.acierto) && !reintentadas.includes(original)) {
        const en = Math.min(e.idx + 1 + REINTENTO_TRAS, cola.length);
        cola = [...cola.slice(0, en), { ...act, id: `${original}~r` }, ...cola.slice(en)];
        reintentadas = [...reintentadas, original];
      }
      if (act.modo === "comprobar") {
        resumen = { ...resumen };
        for (const ev of a.evidencias) {
          const previa = resumen[ev.item]?.[ev.faceta];
          const nueva = marcaDe(ev);
          const queda = previa !== undefined && GRAVEDAD[previa] > GRAVEDAD[nueva] ? previa : nueva;
          resumen[ev.item] = { ...resumen[ev.item], [ev.faceta]: queda };
        }
      }
      return {
        ...e,
        cola,
        reintentadas,
        resumen,
        todoBien: a.evidencias.every((ev) => ev.acierto && ev.pistas === 0),
        fase: "resultado",
      };
    }
    case "seguir":
      return e.fase === "resultado" ? avanzar(e, e.idx + 1) : e;
    case "apagar": {
      if (e.apagadas.includes(a.capacidad)) return e;
      const s = { ...e, apagadas: [...e.apagadas, a.capacidad] };
      return s.fase === "actividad" ? avanzar(s, s.idx) : s;
    }
    case "envioFallido":
      return { ...e, enviosFallidos: e.enviosFallidos + 1 };
  }
}

/** Los ítems con alguna faceta fallada en la prueba. */
export function porReforzar(e: EstadoSesion): string[] {
  return Object.entries(e.resumen)
    .filter(([, facetas]) => Object.values(facetas).includes("mal"))
    .map(([item]) => item);
}

/** `ja:kana:か` → `か`; `de:sustantivo:Frau` → `Frau`. */
export function etiquetaItem(item: string): string {
  return item.split(":").slice(2).join(":");
}
