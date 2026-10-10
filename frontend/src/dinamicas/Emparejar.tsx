/**
 * `emparejar` (spec 2026-10-09 §3.2): el tablero de parejas contra el reloj.
 * Las dos columnas se barajan por separado al montar; la lógica es pura
 * (lib/dinamicas/emparejar.ts).
 */
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import {
  estadoFicha,
  evidenciasTablero,
  inicialTablero,
  paresFallados,
  seAcaboElTiempo,
  sinTiempo,
  tocar,
  ultimoFallo,
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
        data-state={e}
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
  const lang = contenido.lang_izquierda ?? undefined;
  // Al acabar con algún fallo la cuenta cede su sitio a la corrección: las parejas que no acertaron, con su respuesta.
  const corregir = estado.terminado ? paresFallados(contenido, estado) : [];
  // Mientras se juega: «2 de 5 · Toca una ficha y su pareja.», y tras un fallo, el fallo en lugar de la instrucción.
  const fallo = ultimoFallo(estado);
  const izq = fallo && pares.get(fallo.izq)?.izquierda;
  const der = fallo && pares.get(fallo.der)?.derecha;
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
      {/* Una sola región viva, que no se desmonta, para lo que cambia: la cuenta, el último fallo y la corrección.
          El párrafo cambia de átomo (cinta al jugar, nota al corregir) pero es el mismo nodo, y el `<span>` vivo
          también. La instrucción, que no cambia, va fuera: dentro se repetía con cada toque. Todo va en un solo
          `<span>`: la cinta es flex, y dos hijos serían dos columnas que parten cada una por su lado. */}
      <div className="k-tablero__estado">
        <p className={corregir.length > 0 ? "k-note" : "k-cap k-cap--center"} data-state={corregir.length > 0 ? "fix" : undefined}>
          <span>
            <span role="status">
              {corregir.length > 0 ? (
                <>
                  {sinTiempo(estado) && <>{t("dinamica.emparejar.sinTiempo")} </>}
                  <span className="k-note__right">
                    {corregir.map((p, i) => (
                      <Fragment key={p.item}>
                        {i > 0 && (
                          <>
                            <span aria-hidden="true"> · </span>
                            <span className="k-sr">, </span>
                          </>
                        )}
                        <span className="k-tablero__par">
                          <span lang={lang}>{p.izquierda}</span> {p.derecha}
                        </span>
                      </Fragment>
                    ))}
                  </span>
                </>
              ) : (
                <>
                  {t("dinamica.emparejar.cuenta", { n: estado.hechas.length, total: contenido.pares.length })}
                  {izq && der && (
                    <>
                      {" · "}
                      <Trans i18nKey="dinamica.emparejar.noEs" values={{ izq, der }} components={{ 1: <span lang={lang} /> }} />
                    </>
                  )}
                </>
              )}
            </span>
            {corregir.length === 0 && !(izq && der) && <> · {t("dinamica.emparejar.instruccion")}</>}
          </span>
        </p>
      </div>
    </>
  );
}
