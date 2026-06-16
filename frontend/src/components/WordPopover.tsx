import { useEffect, useRef, useState } from "react";
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

const ARTICLE_COLOR: Record<string, string> = {
  der: "oklch(0.55 0.13 245)",
  die: "oklch(0.55 0.15 15)",
  das: "oklch(0.55 0.13 145)",
};

export default function WordPopover({
  word,
  anchorRect,
  targetLanguage,
  alreadyAdded,
  onClose,
  onAdded,
}: Props) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement | null>(null);
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
  const article =
    showArticle && word.gender && ARTICLE_COLOR[word.gender] ? word.gender : null;
  const articleColor = article ? ARTICLE_COLOR[article] : "var(--ink-3)";
  const top = anchorRect.top + window.scrollY - 12;
  const left = anchorRect.left + anchorRect.width / 2 + window.scrollX;
  const posKey = `wpop.pos.${word.pos}` as const;
  const posLabel = t(posKey, { defaultValue: word.pos });

  return (
    <div
      ref={ref}
      className="wpop"
      role="dialog"
      style={{ top, left, transform: "translate(-50%, -100%)" }}
    >
      <div className="wpop__head">
        {article && (
          <span className="wpop__article" style={{ color: articleColor }}>
            {article}
          </span>
        )}
        <span className="wpop__lemma">{word.lemma}</span>
        <button
          className="wpop__audio"
          aria-label={t("wpop.audio.aria")}
          onClick={(e) => {
            e.stopPropagation();
            speak(word.lemma, targetLanguage);
          }}
        >
          <span className="wpop__audio-icon" />
        </button>
      </div>

      {word.translation && (
        <div className="wpop__translation">{word.translation}</div>
      )}

      {word.example_target && (
        <div className="wpop__example">
          <span className="wpop__example-de">{word.example_target}</span>
        </div>
      )}

      {word.frequency_rank != null && (
        <div className="wpop__freq k-mono">
          {t("wpop.freq", { rank: word.frequency_rank })}
        </div>
      )}

      <div className="wpop__foot">
        <button
          className="wpop__add"
          data-added={added}
          disabled={adding}
          onClick={handleAdd}
        >
          {added ? t("wpop.add.added") : adding ? t("wpop.add.adding") : t("wpop.add.add")}
        </button>
        {posLabel && <span className="k-mono wpop__pos">{posLabel}</span>}
      </div>
      <span className="wpop__tail" />
    </div>
  );
}
