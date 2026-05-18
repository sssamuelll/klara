import { useTranslation } from "react-i18next";
import type { StorySentence, StoryWord } from "../api/types";
import { languageLabel } from "../lib/languages";
import RecordingBar from "./RecordingBar";
import PronunciationFeedback, { type PronScores } from "./PronunciationFeedback";

interface Props {
  sentence: StorySentence;
  index: number;
  total: number;
  targetLanguage: string;
  lemmaIndex: Record<string, string>;
  wordsById: Record<string, StoryWord>;
  activeWordKey: string | null;
  onWordTap: (word: StoryWord, key: string, el: HTMLElement) => void;
  playing: boolean;
  recording: boolean;
  onPlay: () => void;
  onPlaySlow: () => void;
  onRecord: () => void;
  scores?: PronScores;
  feedback?: PronScores;
  onRetry: () => void;
  onPrev: () => void;
  onNext: () => void;
  canPrev: boolean;
  canNext: boolean;
}

const PUNCT_RE = /[.,!?;:„""»«()¡¿—–\-]/g;

interface Tok {
  type: "word" | "space" | "punct";
  text: string;
}

function tokenize(de: string): Tok[] {
  const out: Tok[] = [];
  const re = /(\s+)|([.,!?;:„""»«()¡¿—–\-]+)|([^\s.,!?;:„""»«()¡¿—–\-]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(de)) !== null) {
    if (m[1]) out.push({ type: "space", text: m[1] });
    else if (m[2]) out.push({ type: "punct", text: m[2] });
    else if (m[3]) out.push({ type: "word", text: m[3] });
  }
  return out;
}

function matchToken(text: string, lemmaIndex: Record<string, string>): string | null {
  const clean = text.replace(PUNCT_RE, "").toLowerCase();
  if (!clean) return null;
  if (lemmaIndex[clean]) return lemmaIndex[clean];
  for (const lemma of Object.keys(lemmaIndex)) {
    if (clean === lemma) return lemmaIndex[lemma];
  }
  for (const lemma of Object.keys(lemmaIndex)) {
    if (clean.includes(lemma) || lemma.includes(clean)) return lemmaIndex[lemma];
  }
  return null;
}

export default function SentenceStep({
  sentence,
  index,
  total,
  targetLanguage,
  lemmaIndex,
  wordsById,
  activeWordKey,
  onWordTap,
  playing,
  recording,
  onPlay,
  onPlaySlow,
  onRecord,
  scores,
  feedback,
  onRetry,
  onPrev,
  onNext,
  canPrev,
  canNext,
}: Props) {
  const { t } = useTranslation();
  const tokens = tokenize(sentence.target);
  const targetLabel = languageLabel(targetLanguage);

  return (
    <section className="step" data-active="true">
      <div className="step__progress">
        <span className="k-mono step__counter">
          {String(index + 1).padStart(2, "0")}{" "}
          <span className="step__counter-sep">/</span>{" "}
          {String(total).padStart(2, "0")}
        </span>
        <div className="step__track">
          {Array.from({ length: total }).map((_, i) => (
            <span
              key={i}
              className="step__pip"
              data-state={i < index ? "done" : i === index ? "now" : "next"}
            />
          ))}
        </div>
      </div>

      <div className="step__grid">
        <div className="step__content">
          <p className="step__de">
            {tokens.map((tok, i) => {
              if (tok.type !== "word") {
                return (
                  <span key={i} className="step__tok">
                    {tok.text}
                  </span>
                );
              }
              const score = scores?.[i];
              const wordId = matchToken(tok.text, lemmaIndex);
              const key = `${index}-${i}`;
              const isActive = activeWordKey === key;
              const onClick = wordId
                ? (e: React.MouseEvent<HTMLButtonElement>) =>
                    onWordTap(wordsById[wordId], key, e.currentTarget)
                : undefined;
              return (
                <button
                  key={i}
                  type="button"
                  className="step__word"
                  data-active={isActive}
                  data-score={score}
                  data-matched={Boolean(wordId)}
                  onClick={onClick}
                  disabled={!wordId}
                >
                  {tok.text}
                </button>
              );
            })}
          </p>
          <p className="step__es">{sentence.native}</p>
        </div>

        <aside className="step__actions">
          <div className="step__action-row">
            <button
              type="button"
              className="step__action"
              data-on={playing}
              onClick={onPlay}
              aria-label={playing ? t("story.step.listenAria.pause") : t("story.step.listenAria.play")}
            >
              <span className="step__action-icon">
                {playing ? <span className="step__pause" /> : <span className="step__triangle" />}
              </span>
              <span className="step__action-label">
                <span className="step__action-title">
                  {playing ? t("story.step.pausing") : t("story.step.listen")}
                </span>
                <span className="step__action-sub k-mono">{t("story.step.klaraReads")}</span>
              </span>
            </button>

            <button
              type="button"
              className="step__action step__action--slow"
              onClick={onPlaySlow}
              aria-label={t("story.step.listenSlowAria")}
            >
              <span className="step__action-icon">
                <span className="step__triangle" />
              </span>
              <span className="step__action-label">
                <span className="step__action-title">{t("story.step.listenSlow")}</span>
                <span className="step__action-sub k-mono">0.7×</span>
              </span>
            </button>
          </div>

          <button
            type="button"
            className="step__action step__action--mic"
            data-on={recording}
            onClick={onRecord}
            aria-label={recording ? t("story.step.pronounceAria.stop") : t("story.step.pronounceAria.start")}
          >
            <span className="step__action-icon">
              <span className="step__mic" />
            </span>
            <span className="step__action-label">
              <span className="step__action-title">
                {recording ? t("story.step.listening") : t("story.step.pronounce")}
              </span>
              <span className="step__action-sub k-mono">
                {recording ? t("story.step.sayIn", { target: targetLabel }) : t("story.step.yourTurn")}
              </span>
            </span>
          </button>

          {recording && <RecordingBar />}
          {feedback && !recording && (
            <PronunciationFeedback
              scores={feedback}
              onRetry={onRetry}
              onListen={onPlay}
            />
          )}
        </aside>
      </div>

      <nav className="step__nav">
        <button
          type="button"
          className="step__nav-btn step__nav-btn--prev"
          onClick={onPrev}
          disabled={!canPrev}
          aria-label={t("story.step.prevAria")}
        >
          <span className="k-serif step__nav-arrow">←</span>
          <span className="k-mono">{t("story.step.prev")}</span>
        </button>

        <button
          type="button"
          className="step__nav-btn step__nav-btn--next"
          onClick={onNext}
          aria-label={canNext ? t("story.step.nextAria") : t("story.step.finishAria")}
        >
          <span className="k-mono">{canNext ? t("story.step.next") : t("story.step.finish")}</span>
          <span className="k-serif step__nav-arrow">→</span>
        </button>
      </nav>
    </section>
  );
}
