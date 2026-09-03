import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { LanguageCode, StoryWord } from "../api/types";
import { api } from "../api/client";
import { speak } from "../lib/tts";

interface Props {
  word: StoryWord;
  anchorRect: DOMRect;
  targetLanguage: LanguageCode;
  alreadyAdded?: boolean;
  onClose: () => void;
  onAdded?: (wordId: string) => void;
}

/**
 * Sitúa el globo sobre la palabra sin dejar que se salga de la pantalla.
 *
 * `.k-card--anchored` mide 320px fijos y se centra sobre el ancla con
 * `translateX(-50%)`, así que una palabra a menos de 160px de un canto dejaba
 * medio globo fuera del cascarón —que es `overflow: hidden`, o sea recortado y
 * sin scroll—. Se midieron hasta 68px perdidos por la izquierda.
 *
 * La caja se acota a la pantalla y la COLA se desplaza lo mismo en sentido
 * contrario, así que sigue apuntando a la palabra: lo que se mueve es el globo,
 * no lo que señala. `--k-tail-x` lo lee `.k-card--anchored .k-card__tail`.
 */
const ANCHO = 320;
const MARGEN = 8;
const HUECO = 12;
/** Suelo del tope de alto: por debajo de esto el globo deja de ser legible. */
const TOPE_MIN = 160;

export function useAnclaje(rect: DOMRect) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [abajo, setAbajo] = useState(false);
  const [desborda, setDesborda] = useState(false);

  // El sitio que hay a cada lado de la palabra, descontando el hueco de la cola
  // y el margen contra el canto de la pantalla.
  const alto = document.documentElement.clientHeight;
  const sitioArriba = rect.top - HUECO - MARGEN;
  const sitioAbajo = alto - rect.bottom - HUECO - MARGEN;

  // Si encima no cabe, el globo baja; si no cabe en ninguno de los dos lados
  // —un compuesto alemán de tres renglones pasa de 550px—, se va al lado con
  // más sitio y ahí lo remata el `max-height`, que le da scroll propio. El alto
  // solo se sabe una vez montado, y `useLayoutEffect` corre antes de pintar:
  // no hay salto visible.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const necesita = el.scrollHeight;
    const va = necesita > sitioArriba && sitioAbajo > sitioArriba;
    setAbajo(va);
    // El tope y el scroll SOLO cuando de verdad desbordan: `overflow-y: auto`
    // recorta la cola, que vive fuera de la caja. En el caso normal el globo no
    // tiene ni tope ni scroll y la cola se ve.
    setDesborda(necesita > Math.max(TOPE_MIN, va ? sitioAbajo : sitioArriba));
  }, [rect, sitioArriba, sitioAbajo]);

  const centro = rect.left + rect.width / 2 + window.scrollX;
  const disponible = document.documentElement.clientWidth;
  // El mismo `min()` que el `max-width` de `.k-card--anchored`: en un teléfono
  // de 320px el globo de 320 no cabe con márgenes, así que encoge — y el
  // cálculo tiene que encoger con él o la cuenta se descuadra.
  const ancho = Math.min(ANCHO, disponible - 2 * MARGEN);
  const min = ancho / 2 + MARGEN;
  const max = Math.max(min, disponible - ancho / 2 - MARGEN);
  const left = Math.min(Math.max(centro, min), max);

  return {
    ref,
    abajo,
    desborda,
    style: {
      top: abajo
        ? rect.bottom + window.scrollY + HUECO
        : rect.top + window.scrollY - HUECO,
      left,
      maxHeight: desborda
        ? Math.max(TOPE_MIN, abajo ? sitioAbajo : sitioArriba)
        : undefined,
      transform: abajo ? "translate(-50%, 0)" : "translate(-50%, -100%)",
      "--k-tail-x": `${(centro - left).toFixed(1)}px`,
    } as React.CSSProperties,
  };
}

/** Icono de trazo 1.5 del átomo 2; el tamaño lo pone `.k-rbtn svg`. */
export function IcPlay() {
  return (
    <svg
      data-icon="play"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M8 5.4 19 12 8 18.6Z" />
    </svg>
  );
}

export default function WordPopover({
  word,
  anchorRect,
  targetLanguage,
  alreadyAdded,
  onClose,
  onAdded,
}: Props) {
  const { t } = useTranslation();
  const { ref, abajo, desborda, style } = useAnclaje(anchorRect);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(!!alreadyAdded);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [onClose]);

  async function handleAdd() {
    if (added || adding) return;
    setAdding(true);
    try {
      await api.addCard(word.id);
      setAdded(true);
      onAdded?.(word.id);
    } catch {
      // swallow — UI already shows non-added state; optional toast later
    } finally {
      setAdding(false);
    }
  }

  const showArticle = targetLanguage === "de";
  // El género lo tiñe `.k-card__article[data-gender]` con --art-der/die/das;
  // el mapa de tres oklch literales que vivía aquí muere con él.
  const article = showArticle && word.gender ? word.gender : null;
  const posKey = `wpop.pos.${word.pos}` as const;
  const posLabel = t(posKey, { defaultValue: word.pos });

  return (
    <div
      ref={ref}
      className="k-card k-card--flat k-card--anchored"
      data-abajo={abajo || undefined}
      data-scroll={desborda || undefined}
      role="dialog"
      style={style}
    >
      <div className="k-card__head">
        <p className="k-card__answer">
          {article && (
            <span className="k-card__article" data-gender={article}>
              {article}
            </span>
          )}
          <span className="k-card__word">{word.lemma}</span>
        </p>
        <button
          type="button"
          className="k-rbtn k-rbtn--sm"
          aria-label={t("wpop.audio.aria")}
          onClick={(e) => {
            e.stopPropagation();
            speak(word.lemma, targetLanguage);
          }}
        >
          <IcPlay />
        </button>
      </div>

      {word.translation && <p className="k-card__tx">{word.translation}</p>}

      {word.example_target && (
        <>
          <hr className="k-card__rule" />
          <p className="k-card__eg">{word.example_target}</p>
        </>
      )}

      {word.frequency_rank != null && (
        <p className="k-cap">{t("wpop.freq", { rank: word.frequency_rank })}</p>
      )}

      <div className="k-card__foot">
        <button
          type="button"
          className="k-btn k-btn--text"
          data-added={added}
          disabled={adding}
          onClick={handleAdd}
        >
          {added ? t("wpop.add.added") : adding ? t("wpop.add.adding") : t("wpop.add.add")}
        </button>
        {posLabel && <span className="k-cap">{posLabel}</span>}
      </div>
      <span className="k-card__tail" />
    </div>
  );
}
