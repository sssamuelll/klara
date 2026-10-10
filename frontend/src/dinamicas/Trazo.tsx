/**
 * `trazo` (spec 2026-10-09 §5.5): escribir un kana con el dedo, en la caja de
 * 109 de KanjiVG. Cada trazo se juzga al soltar (lib/dinamicas/trazo.ts) y, si
 * vale, se reemplaza por el limpio. Pointer Events: el mismo código sirve para
 * dedo, lápiz y mouse; `.k-trazo` lleva `touch-action: none`.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";
import {
  alSoltar,
  evaluarTrazo,
  evidenciaTrazo,
  inicialTrazo,
  lugaresNumeros,
  N,
  partirKana,
  pasar,
  puedePasar,
  type Esperado,
  type Punto,
} from "../lib/dinamicas/trazo";
import type { PropsDinamica } from "./tipos";

/** El contenido que arma el backend para `trazo` (catalogo/generar.py). */
export interface ContenidoTrazo {
  item: string;
  kana: string;
  romaji: string;
  audio: string;
  trazos: string[];
  mnemotecnia: string;
}

function muestrear(el: SVGPathElement): Esperado {
  const total = el.getTotalLength();
  const pts: Punto[] = Array.from({ length: N }, (_, i) => {
    const p = el.getPointAtLength((total * i) / (N - 1));
    return [p.x, p.y];
  });
  return { pts, largo: total };
}

const camino = (pts: Punto[]) => "M" + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");

export default function Trazo({ contenido, modo, capacidades, onResultado }: PropsDinamica<ContenidoTrazo>) {
  const { t } = useTranslation();
  const refs = useRef<(SVGPathElement | null)[]>([]);
  // El trazo en curso vive en refs: un toque rápido (bajar y soltar sin render en
  // medio) no puede dejar el lienzo creyendo que el dedo sigue apoyado.
  // `dedo` es el puntero dueño del trazo: un segundo dedo o una palma que lleguen
  // con el primero apoyado no lo mezclan ni lo reinician.
  const dedo = useRef<number | null>(null);
  const puntos = useRef<Punto[]>([]);
  // Desde que se puede trazar (ver el efecto de abajo), no desde el montaje.
  const inicio = useRef(0);
  const reportado = useRef(false);
  const [esperados, setEsperados] = useState<Esperado[] | null>(null);
  const [estado, setEstado] = useState(inicialTrazo);
  const [mano, setMano] = useState<Punto[] | null>(null);
  const [mal, setMal] = useState(false);
  const [vuelta, setVuelta] = useState(0);
  const total = contenido.trazos.length;
  // Dónde va el número de cada trazo al presentar.
  const lugares = useMemo(() => (esperados ? lugaresNumeros(esperados) : null), [esperados]);

  // Los trazos de referencia se muestrean del propio SVG: getTotalLength necesita el DOM.
  useEffect(() => {
    setEsperados(refs.current.slice(0, total).map((el) => (el ? muestrear(el) : { pts: [], largo: 1 })));
    inicio.current ||= performance.now();
  }, [contenido, total]);

  const oir = useCallback(() => {
    if (!capacidades.puede("escuchar")) return;
    capacidades.reproducir({ src: contenido.audio, texto: contenido.kana, idioma: "ja" });
  }, [capacidades, contenido]);

  // Al presentar y en la prueba suena al aparecer; en la práctica manda el dibujo.
  useEffect(() => {
    if (modo !== "practicar") oir();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (modo === "presentar" || !estado.terminado || reportado.current) return;
    reportado.current = true;
    onResultado([evidenciaTrazo(contenido.item, estado, Math.round(performance.now() - inicio.current), total)]);
  }, [estado, modo, contenido.item, total, onResultado]);

  // De píxeles de pantalla a la caja de 109: el SVG escala, y la matriz también.
  const punto = (e: PointerEvent<SVGSVGElement>): Punto => {
    const caja = e.currentTarget;
    const p = caja.createSVGPoint();
    p.x = e.clientX;
    p.y = e.clientY;
    const q = p.matrixTransform(caja.getScreenCTM()!.inverse());
    return [q.x, q.y];
  };

  const dibujando = modo !== "presentar" && !estado.terminado && esperados !== null;

  const bajar = (e: PointerEvent<SVGSVGElement>) => {
    // Solo el botón principal, y solo si no hay ya un trazo en curso.
    if (!dibujando || dedo.current !== null || e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    dedo.current = e.pointerId;
    puntos.current = [punto(e)];
    setMal(false);
    setMano(puntos.current);
  };

  const mover = (e: PointerEvent<SVGSVGElement>) => {
    if (e.pointerId !== dedo.current) return;
    puntos.current = [...puntos.current, punto(e)];
    setMano(puntos.current);
  };

  const soltar = (e: PointerEvent<SVGSVGElement>) => {
    if (e.pointerId !== dedo.current) return;
    dedo.current = null;
    if (!esperados) return;
    const juicio = evaluarTrazo(puntos.current, esperados[estado.actual]);
    setEstado((s) => alSoltar(s, juicio, modo, total));
    if (juicio.toque || juicio.ok) setMano(null);
    else setMal(true);
  };

  // El sistema se quedó con el dedo (un gesto suyo, una llamada): lo trazado no es
  // un intento, así que no se juzga ni cuenta como fallo.
  const cancelar = (e: PointerEvent<SVGSVGElement>) => {
    if (e.pointerId !== dedo.current) return;
    dedo.current = null;
    puntos.current = [];
    setMano(null);
  };

  const n = estado.actual + 1;
  let nota: string;
  if (estado.terminado) nota = t("dinamica.trazo.listo");
  else if (mal && estado.mostrando) nota = t("dinamica.trazo.asiVa", { n });
  else if (mal) nota = t("dinamica.trazo.eseNo");
  // «Trazo 1 de 3» es rótulo, sin punto: lo une a la frase el separador de la app, como la cuenta del tablero.
  else if (modo === "practicar" && estado.actual === 0) nota = `${t("dinamica.trazo.trazoN", { n, total })} · ${t("dinamica.trazo.empieza")}`;
  else nota = t("dinamica.trazo.trazoN", { n, total });

  const inicioTrazo = esperados?.[estado.actual]?.pts[0];
  const sinVoz = !capacidades.puede("escuchar");
  const salida = modo !== "presentar" && puedePasar(estado, modo);

  return (
    <>
      {modo === "comprobar" && (
        <>
          <p className="k-cap k-cap--center">{t("dinamica.trazo.escribe")}</p>
          <p className="k-trazo__son">{contenido.romaji}</p>
        </>
      )}
      <div className="k-trazo" data-modo={modo}>
        <svg
          viewBox="0 0 109 109"
          role="img"
          // En la prueba el kana es la respuesta: el lector oye qué es el lienzo, no qué hay que escribir.
          aria-label={modo === "comprobar" ? t("dinamica.trazo.lienzo") : contenido.kana}
          lang={modo === "comprobar" ? undefined : "ja"}
          onPointerDown={bajar}
          onPointerMove={mover}
          onPointerUp={soltar}
          onPointerCancel={cancelar}
          onLostPointerCapture={cancelar}
        >
          <g className="k-trazo__guia" aria-hidden="true">
            <line x1="54.5" y1="4" x2="54.5" y2="105" />
            <line x1="4" y1="54.5" x2="105" y2="54.5" />
          </g>
          {/* La referencia siempre está en el DOM (para muestrearla); en práctica es la plantilla gris. */}
          <g className="k-trazo__ref" aria-hidden="true">
            {contenido.trazos.map((p, i) => (
              <path
                key={i}
                d={p}
                ref={(el) => {
                  refs.current[i] = el;
                }}
              />
            ))}
          </g>
          {modo === "presentar" ? (
            <g key={vuelta} className="k-trazo__orden">
              {contenido.trazos.map((p, i) => (
                <path key={i} d={p} pathLength={1} style={{ "--i": i } as CSSProperties} />
              ))}
              {lugares?.map(
                (l, i) =>
                  l && (
                    <text key={`n${i}`} className="k-trazo__num" x={l[0]} y={l[1]} dy=".35em" textAnchor="middle" style={{ "--i": i } as CSSProperties}>
                      {i + 1}
                    </text>
                  ),
              )}
            </g>
          ) : (
            <>
              {/* Dejado con «Pasar a la siguiente», el kana entero es la corrección que anuncia el reproductor. */}
              <g className="k-trazo__tinta">
                {contenido.trazos.slice(0, estado.pasado ? total : estado.actual).map((p, i) => (
                  <path key={i} d={p} />
                ))}
              </g>
              {estado.mostrando && !estado.terminado && (
                <path
                  key={`pista-${estado.actual}`}
                  className="k-trazo__pista"
                  d={contenido.trazos[estado.actual]}
                  pathLength={1}
                />
              )}
              {mano && <path className="k-trazo__mano" data-mal={mal || undefined} d={camino(mano)} />}
              {modo === "practicar" && inicioTrazo && !estado.terminado && (
                <>
                  <circle className="k-trazo__aro" cx={inicioTrazo[0]} cy={inicioTrazo[1]} r={3} />
                  <circle className="k-trazo__inicio" cx={inicioTrazo[0]} cy={inicioTrazo[1]} r={2.4} />
                </>
              )}
            </>
          )}
        </svg>
      </div>
      {modo === "presentar" ? (
        <>
          <p className="k-trazo__son">{contenido.romaji}</p>
          <p className="k-note">
            {partirKana(contenido.mnemotecnia).map((p, i) =>
              p.ja ? (
                <span key={i} lang="ja">
                  {p.texto}
                </span>
              ) : (
                p.texto
              ),
            )}
          </p>
          <div className="k-wrap k-wrap--centro">
            <button type="button" className="k-btn k-btn--ghost" onClick={oir} disabled={sinVoz}>
              {t("dinamica.oirOtraVez")}
            </button>
            <button type="button" className="k-btn k-btn--text" onClick={() => setVuelta((v) => v + 1)}>
              {t("dinamica.trazo.verElOrden")}
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="k-note" aria-live="polite">{nota}</p>
          {/* Siempre está, y reserva su alto (átomo 21): en la práctica va vacía hasta que hay salida, y que
              aparezca no mueve el lienzo entre un intento y el siguiente. */}
          <div className="k-wrap k-wrap--centro">
            {modo === "comprobar" && (
              <button type="button" className="k-btn k-btn--text" onClick={oir} disabled={sinVoz}>
                {t("dinamica.oirOtraVez")}
              </button>
            )}
            {/* Ni con la pista sale este trazo: el kana se deja (una evidencia sin acierto) y se sigue. */}
            {salida && (
              <button type="button" className="k-btn k-btn--text" onClick={() => setEstado((s) => pasar(s, modo))}>
                {t("dinamica.trazo.pasar")}
              </button>
            )}
          </div>
        </>
      )}
    </>
  );
}
