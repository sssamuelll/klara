/**
 * Lightweight tooltip for non-target words inside a sentence.
 *
 * Sibling to WordPopover, which keeps doing the full job for target_words
 * (with the «+ Repaso» button, example sentence, POS panel, gendered
 * article colour, etc.). For everyday words in the sentence — the ones
 * the user might glance at without wanting to flashcard them — we show
 * the minimum useful: the word itself, an audio button, and a one-line
 * translation. POS shows if available but is muted.
 *
 * Es la misma ficha anclada que WordPopover (`.k-card k-card--flat
 * k-card--anchored`) con menos bandas: la diferencia entre las dos es lo
 * que traen dentro, no la superficie. Conserva el `data-variant` por si
 * alguna vez hace falta distinguirlas desde CSS.
 */

import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { LanguageCode, WordBreakdown } from "../api/types";
import { speak } from "../lib/tts";
import { IcPlay, useAnclaje } from "./WordPopover";

interface Props {
  entry: WordBreakdown;
  anchorRect: DOMRect;
  targetLanguage: LanguageCode;
  onClose: () => void;
}

export default function BreakdownPopover({
  entry,
  anchorRect,
  targetLanguage,
  onClose,
}: Props) {
  const { t } = useTranslation();
  const { ref, abajo, desborda, style } = useAnclaje(anchorRect);

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

  const posKey = entry.pos ? (`wpop.pos.${entry.pos}` as const) : null;
  const posLabel = posKey ? t(posKey, { defaultValue: entry.pos ?? "" }) : null;

  return (
    <div
      ref={ref}
      className="k-card k-card--flat k-card--anchored"
      data-variant="breakdown"
      data-abajo={abajo || undefined}
      data-scroll={desborda || undefined}
      role="dialog"
      style={style}
    >
      <div className="k-card__head">
        <p className="k-card__answer">
          <span className="k-card__word">{entry.word}</span>
        </p>
        <button
          type="button"
          className="k-rbtn k-rbtn--sm"
          aria-label={t("wpop.audio.aria")}
          onClick={(e) => {
            e.stopPropagation();
            speak(entry.word, targetLanguage);
          }}
        >
          <IcPlay />
        </button>
      </div>
      <p className="k-card__tx">{entry.translation}</p>
      {posLabel && (
        <div className="k-card__foot">
          <span className="k-cap">{posLabel}</span>
        </div>
      )}
      <span className="k-card__tail" />
    </div>
  );
}
