import type { ComponentType } from "react";
import Eleccion from "./Eleccion";
import Emparejar from "./Emparejar";
import Trazo from "./Trazo";
import type { PropsDinamica } from "./tipos";

/** Nombre de la dinámica (el mismo del backend) → componente. Cada dinámica trae
 *  su propio tipo de contenido; el reproductor las trata igual. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const DINAMICAS: Record<string, ComponentType<PropsDinamica<any>>> = {
  eleccion: Eleccion,
  trazo: Trazo,
  emparejar: Emparejar,
};
