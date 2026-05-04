import { useState } from "react";
import type { Story, StorySentence } from "../api/types";
import { speakGerman } from "../lib/tts";
import WordPopover from "./WordPopover";
import "./SentenceView.css";

interface Props {
  story: Story;
}

function buildLemmaIndex(story: Story): Record<string, string> {
  const idx: Record<string, string> = {};
  for (const w of story.target_words) {
    idx[w.lemma.toLowerCase()] = w.id;
  }
  return idx;
}

function tokenize(sentence: string): string[] {
  return sentence.split(/(\s+|[.,!?;:„"»«()])/).filter((s) => s.length > 0);
}

function matchToken(token: string, lemmaIndex: Record<string, string>): string | null {
  const clean = token.replace(/[.,!?;:„"»«()]/g, "").toLowerCase();
  if (!clean) return null;
  if (lemmaIndex[clean]) return lemmaIndex[clean];
  for (const lemma of Object.keys(lemmaIndex)) {
    if (clean.includes(lemma) || lemma.includes(clean)) return lemmaIndex[lemma];
  }
  return null;
}

export default function SentenceView({ story }: Props) {
  const [openWordId, setOpenWordId] = useState<string | null>(null);
  const [showTranslations, setShowTranslations] = useState(false);
  const lemmaIndex = buildLemmaIndex(story);
  const wordsById: Record<string, (typeof story.target_words)[number]> = Object.fromEntries(
    story.target_words.map((w) => [w.id, w])
  );
  const openWord = openWordId ? wordsById[openWordId] : null;

  return (
    <div className="sentence-view">
      <div className="sentence-view__toolbar">
        <button
          className="btn btn-ghost"
          onClick={() => setShowTranslations((v) => !v)}
          aria-pressed={showTranslations}
        >
          {showTranslations ? "Ocultar traducciones" : "Ver traducciones"}
        </button>
      </div>

      <div className="sentence-list">
        {story.content.sentences.map((s, i) => (
          <SentenceRow
            key={i}
            sentence={s}
            lemmaIndex={lemmaIndex}
            showTranslation={showTranslations}
            onWordClick={setOpenWordId}
          />
        ))}
      </div>

      {openWord && <WordPopover word={openWord} onClose={() => setOpenWordId(null)} />}
    </div>
  );
}

function SentenceRow({
  sentence,
  lemmaIndex,
  showTranslation,
  onWordClick,
}: {
  sentence: StorySentence;
  lemmaIndex: Record<string, string>;
  showTranslation: boolean;
  onWordClick: (id: string) => void;
}) {
  const tokens = tokenize(sentence.de);

  return (
    <div className="sentence-row">
      <button
        className="sentence-row__speak"
        onClick={() => speakGerman(sentence.de)}
        aria-label="Escuchar frase"
      >
        🔊
      </button>
      <div className="sentence-row__body">
        <p className="sentence-row__de">
          {tokens.map((t, idx) => {
            if (/^\s+$/.test(t)) return <span key={idx}>{t}</span>;
            const wordId = matchToken(t, lemmaIndex);
            if (wordId) {
              return (
                <button
                  key={idx}
                  className="word-token word-token--target"
                  onClick={() => onWordClick(wordId)}
                >
                  {t}
                </button>
              );
            }
            return (
              <span key={idx} className="word-token">
                {t}
              </span>
            );
          })}
        </p>
        {showTranslation && <p className="sentence-row__es">{sentence.es}</p>}
      </div>
    </div>
  );
}
