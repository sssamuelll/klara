import type { MicLevel } from "./silenceDetector";

export type DockStatus =
  | { kind: "escuchando"; nivel: MicLevel }
  | { kind: "evaluando" }
  | { kind: "leyendo"; despacio: boolean }
  | null;

/** Estado de la línea `estadoK` del dock de Estudiar. Precedencia: grabar > evaluar > leer. */
export function dockStatus(o: {
  playing: boolean;
  recording: boolean;
  evaluating: boolean;
  micLevel: MicLevel;
  rate: number;
}): DockStatus {
  if (o.recording) return { kind: "escuchando", nivel: o.micLevel };
  if (o.evaluating) return { kind: "evaluando" };
  if (o.playing) return { kind: "leyendo", despacio: o.rate < 1 };
  return null;
}
