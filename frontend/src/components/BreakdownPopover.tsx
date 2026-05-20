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
 * Shares wpop__* CSS classes with WordPopover so positioning + chrome
 * stay consistent. Adds a `data-variant="breakdown"` hook on the root
 * if specific overrides are ever needed.
 */

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { LanguageCode, WordBreakdown } from "../api/types";
import { speak } from "../lib/tts";

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
  const ref = useRef<HTMLDivElement | null>(null);

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

  const top = anchorRect.top + window.scrollY - 12;
  const left = anchorRect.left + anchorRect.width / 2 + window.scrollX;
  const posKey = entry.pos ? (`wpop.pos.${entry.pos}` as const) : null;
  const posLabel = posKey ? t(posKey, { defaultValue: entry.pos ?? "" }) : null;

  return (
    <div
      ref={ref}
      className="wpop"
      data-variant="breakdown"
      role="dialog"
      style={{ top, left, transform: "translate(-50%, -100%)" }}
    >
      <div className="wpop__head">
        <span className="wpop__lemma">{entry.word}</span>
        <button
          type="button"
          className="wpop__audio"
          aria-label={t("wpop.audio.aria")}
          onClick={(e) => {
            e.stopPropagation();
            speak(entry.word, targetLanguage);
          }}
        >
          <span className="wpop__audio-icon" />
        </button>
      </div>
      <div className="wpop__translation">{entry.translation}</div>
      {posLabel && (
        <div className="wpop__foot">
          <span className="k-mono wpop__pos">{posLabel}</span>
        </div>
      )}
      <span className="wpop__tail" />
    </div>
  );
}
