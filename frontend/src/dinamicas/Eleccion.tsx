/**
 * `eleccion` (spec 2026-10-09 §3.2): ves un kana y eliges su sonido, u oyes un
 * sonido y eliges el kana. La pregunta va en `.k-glifo` o detrás de un
 * `.k-rbtn`; las opciones son chips que, ya respondidos, se tiñen.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  evaluarEleccion,
  textoCorrecto,
  tonoOpcion,
  type ContenidoEleccion,
} from "../lib/dinamicas/eleccion";
import type { PropsDinamica } from "./tipos";

function IcOir() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4Z" />
      <path d="M15.5 9.5a3.5 3.5 0 0 1 0 5" />
      <path d="M18 7a7 7 0 0 1 0 10" />
    </svg>
  );
}

export default function Eleccion({ contenido, capacidades, onResultado }: PropsDinamica<ContenidoEleccion>) {
  const { t } = useTranslation();
  const [elegida, setElegida] = useState<string | null>(null);
  const inicio = useRef(performance.now());
  const respondida = useRef(false);
  const { pregunta } = contenido;

  const oir = useCallback(() => {
    if (!pregunta.audio || !capacidades.puede("escuchar")) return;
    capacidades.reproducir({ src: pregunta.audio, texto: textoCorrecto(contenido), idioma: pregunta.lang ?? "ja" });
  }, [capacidades, contenido, pregunta]);

  // La pregunta de oír suena sola al aparecer, una vez.
  useEffect(() => {
    oir();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const elegir = useCallback(
    (item: string) => {
      // Una vez por actividad. El ref y no `elegida`: dos toques seguidos llegan
      // antes de que React repinte, y el estado todavía diría «sin responder».
      if (respondida.current) return;
      respondida.current = true;
      setElegida(item);
      onResultado([evaluarEleccion(contenido, item, Math.round(performance.now() - inicio.current))]);
    },
    [contenido, onResultado],
  );

  // En escritorio, 1–4 eligen.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Ctrl/Alt/Cmd + número es del navegador (cambiar de pestaña), y una tecla
      // sostenida desde la pregunta anterior no puede contestar la que viene.
      if (e.ctrlKey || e.altKey || e.metaKey || e.repeat) return;
      const n = Number(e.key);
      if (Number.isInteger(n) && n >= 1 && n <= contenido.opciones.length) elegir(contenido.opciones[n - 1].item);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [contenido, elegir]);

  return (
    <>
      {pregunta.texto !== null ? (
        <p className="k-glifo" lang={pregunta.lang ?? undefined}>
          {pregunta.texto}
        </p>
      ) : (
        <button
          type="button"
          className="k-rbtn k-rbtn--lg k-rbtn--ink"
          onClick={oir}
          disabled={!capacidades.puede("escuchar")}
          aria-label={t("dinamica.oirOtraVez")}
        >
          <IcOir />
        </button>
      )}
      <p className="k-cap k-cap--center">
        {pregunta.texto !== null ? t("dinamica.eleccion.comoSuena") : t("dinamica.eleccion.cualOyes")}
      </p>
      <div className="k-wrap k-wrap--centro">
        {contenido.opciones.map((o) => {
          const tono = tonoOpcion(contenido, o.item, elegida);
          return (
            <button
              key={o.item}
              type="button"
              className={o.lang === "ja" ? "k-chip k-chip--glifo" : "k-chip"}
              data-tone={tono}
              // «Esta» es la buena: tinta sólida (como la opción buena del quiz). El tono
              // solo no basta: punto de color + glifo + palabra, nunca solo color.
              data-selected={tono === "good" ? "true" : undefined}
              disabled={elegida !== null && tono === undefined}
              onClick={() => elegir(o.item)}
            >
              {tono && <span className="k-chip__dot" aria-hidden="true" />}
              <span lang={o.lang ?? undefined}>{o.texto}</span>
              {tono && (
                <>
                  <span className="k-chip__mark" aria-hidden="true">
                    {tono === "good" ? "✓" : "✗"}
                  </span>
                  <span className="k-sr">
                    {" "}
                    {t(tono === "good" ? "dinamica.eleccion.correcta" : "dinamica.eleccion.tuRespuesta")}
                  </span>
                </>
              )}
            </button>
          );
        })}
      </div>
    </>
  );
}
