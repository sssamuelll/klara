/**
 * `emparejar` (spec 2026-10-09 §3.2): el tablero de parejas contra el reloj.
 * Las dos columnas se barajan por separado al montar; la lógica es pura
 * (lib/dinamicas/emparejar.ts).
 */
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  estadoFicha,
  evidenciasTablero,
  inicialTablero,
  seAcaboElTiempo,
  tocar,
  type ContenidoEmparejar,
  type Lado,
} from "../lib/dinamicas/emparejar";
import type { PropsDinamica } from "./tipos";

function barajar<T>(xs: T[]): T[] {
  const out = [...xs];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

export default function Emparejar({ contenido, onResultado }: PropsDinamica<ContenidoEmparejar>) {
  const { t } = useTranslation();
  const [estado, setEstado] = useState(() => {
    const items = contenido.pares.map((p) => p.item);
    return inicialTablero(barajar(items), barajar(items));
  });
  const [quedan, setQuedan] = useState(contenido.segundos);
  // El tablero se puede tocar desde que se monta: de ahí corren el reloj y los `ms`.
  const inicio = useRef(performance.now());
  // Una sola tanda por actividad: cerrar la última pareja y que el reloj llegue a cero pueden coincidir.
  const reportado = useRef(false);
  const pares = useMemo(() => new Map(contenido.pares.map((p) => [p.item, p])), [contenido]);

  // ponytail: cuenta ticks de 1 s y no mira la hora de pared; si el sistema frena o congela los temporizadores
  // (la app en segundo plano) el tablero espera con ellos. Un plazo contra `performance.now()` lo acabaría a su hora.
  useEffect(() => {
    if (estado.terminado) return;
    const id = window.setInterval(() => setQuedan((s) => s - 1), 1000);
    return () => window.clearInterval(id);
  }, [estado.terminado]);

  useEffect(() => {
    if (quedan <= 0) setEstado((e) => seAcaboElTiempo(e));
  }, [quedan]);

  useEffect(() => {
    if (!estado.terminado || reportado.current) return;
    const evidencias = evidenciasTablero(contenido, estado, Math.round(performance.now() - inicio.current));
    // El reproductor ignora `[]` fuera de presentar: sin parejas no hay nada que contar.
    if (evidencias.length === 0) return;
    reportado.current = true;
    onResultado(evidencias);
  }, [estado, contenido, onResultado]);

  const ficha = (lado: Lado, item: string) => {
    const p = pares.get(item);
    if (!p) return null;
    const e = estadoFicha(estado, lado, item);
    return (
      <button
        type="button"
        className="k-tablero__ficha"
        data-estado={e}
        aria-pressed={e === "elegida"}
        disabled={estado.terminado || e === "hecha"}
        onClick={() => setEstado((s) => tocar(s, lado, item))}
      >
        {/* El `lang` va en el texto y no en el botón: la palabra del veredicto no es japonés. */}
        <span lang={lado === "izq" ? contenido.lang_izquierda ?? undefined : undefined}>
          {lado === "izq" ? p.izquierda : p.derecha}
        </span>
        {/* El veredicto no es solo color ni solo sacudida: glifo + palabra para el lector (como `eleccion`). */}
        {(e === "hecha" || e === "mal") && (
          <>
            <span className="k-chip__mark" aria-hidden="true">
              {e === "hecha" ? "✓" : "✗"}
            </span>
            <span className="k-sr"> {t(e === "hecha" ? "dinamica.emparejar.hecha" : "dinamica.emparejar.mal")}</span>
          </>
        )}
      </button>
    );
  };

  const restante = Math.max(quedan, 0);
  return (
    <>
      <div className="k-bar k-bar--fill">
        <div
          className="k-bar__track"
          role="progressbar"
          aria-label={t("dinamica.emparejar.tiempo")}
          aria-valuenow={restante}
          aria-valuemin={0}
          aria-valuemax={contenido.segundos}
        >
          <i className="k-bar__fill" style={{ width: `${(restante / contenido.segundos) * 100}%` }} />
        </div>
      </div>
      <div className="k-tablero">
        {estado.izquierda.map((item, i) => (
          <Fragment key={item}>
            {ficha("izq", item)}
            {ficha("der", estado.derecha[i])}
          </Fragment>
        ))}
      </div>
      <p className="k-cap k-cap--center">
        {t("dinamica.emparejar.cuenta", { n: estado.hechas.length, total: contenido.pares.length })} ·{" "}
        {t("dinamica.emparejar.instruccion")}
      </p>
    </>
  );
}
