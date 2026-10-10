import type { Evidencia, Modo } from "../api/types";
import type { Capacidad } from "../lib/sesion";

/** Un audio que la dinámica quiere hacer sonar (spec 2026-10-09 §3.1). */
export interface AudioRef {
  /** Ruta bajo la API (`/audio/ja/a.mp3`), o null para TTS en vivo. */
  src: string | null;
  /** Lo que se dice: el TTS lo sintetiza y Web Speech lo lee si el archivo falla. */
  texto: string;
  idioma: string;
}

/** Lo que el reproductor le presta a una dinámica: la voz y qué está apagado. */
export interface Capacidades {
  reproducir: (audio: AudioRef, opts?: { lento?: boolean }) => void;
  puede: (c: Capacidad) => boolean;
}

/** Una dinámica no sabe nada de lecciones, de Hoy ni de la API: recibe contenido
 *  y devuelve evidencias. */
export interface PropsDinamica<C> {
  contenido: C;
  modo: Modo;
  capacidades: Capacidades;
  /** Solo en practicar y comprobar, una vez por actividad. Presentar avanza con
   *  el botón del reproductor. */
  onResultado: (evidencias: Evidencia[]) => void;
}
