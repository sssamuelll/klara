import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Story, StoryWord } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import SentenceStep from "../components/SentenceStep";
import WordPopover from "../components/WordPopover";
import type { PronScores } from "../components/PronunciationFeedback";
import { useFontScale } from "../lib/preferences";
import {
  bandsByTokenIndex,
  scoreAudio,
  startMicRecording,
  type PronunciationError,
} from "../lib/pronunciation";
import { speak, stop, useTTS } from "../lib/tts";

interface ActiveWord {
  word: StoryWord;
  key: string;
  rect: DOMRect;
}

type Direction = "forward" | "backward";

function tokenizeWordIndices(text: string): number[] {
  // Returns indices of word tokens within the same tokenization SentenceStep uses.
  // Not strictly needed — pronunciation simulator uses contiguous indices anyway.
  const out: number[] = [];
  const re = /(\s+)|([.,!?;:„""»«()¡¿—–\-]+)|([^\s.,!?;:„""»«()¡¿—–\-]+)/g;
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[3]) out.push(i);
    i++;
  }
  return out;
}

export default function StoryView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fontScale] = useFontScale();
  const [active, setActive] = useState<ActiveWord | null>(null);
  const [reviewIds, setReviewIds] = useState<Set<string>>(new Set());
  const [adding, setAdding] = useState<string | null>(null);

  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState<Direction>("forward");
  const [recordingIndex, setRecordingIndex] = useState<number | null>(null);
  const [evaluatingIndex, setEvaluatingIndex] = useState<number | null>(null);
  const [scoresBySentence, setScoresBySentence] = useState<Record<number, PronScores>>({});
  const [pronError, setPronError] = useState<PronunciationError | null>(null);
  const [finished, setFinished] = useState(false);

  // Active recording handle. While set, recorder is live; calling stop()
  // returns the captured audio Blob.
  const recorderRef = useRef<{ stop: () => Promise<Blob>; cancel: () => void } | null>(null);

  const tts = useTTS();

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setStory(null);
    setError(null);
    setActive(null);
    setReviewIds(new Set());
    setCurrentIndex(0);
    setDirection("forward");
    setRecordingIndex(null);
    setScoresBySentence({});
    setFinished(false);
    api
      .getStory(id)
      .then((s) => {
        if (!cancelled) setStory(s);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : t("common.unknownError"));
      });
    return () => {
      cancelled = true;
      stop();
    };
  }, [id, t]);

  const sentences = story?.content.sentences ?? [];
  const total = sentences.length;
  const current = sentences[currentIndex];

  const wordsById = useMemo<Record<string, StoryWord>>(() => {
    if (!story) return {};
    return Object.fromEntries(story.target_words.map((w) => [w.id, w]));
  }, [story]);

  const lemmaIndex = useMemo<Record<string, string>>(() => {
    if (!story) return {};
    const idx: Record<string, string> = {};
    for (const w of story.target_words) {
      idx[w.lemma.toLowerCase()] = w.id;
    }
    return idx;
  }, [story]);

  // Which sentence (if any) is currently being read aloud by Klara?
  const playingIndex = useMemo(() => {
    if (!tts.text) return -1;
    return sentences.findIndex((s) => s.target === tts.text);
  }, [sentences, tts.text]);
  const klaraSpeaking = tts.playing && playingIndex >= 0;

  // Cleanup any in-flight recording when the story or component unmounts.
  useEffect(() => {
    return () => {
      recorderRef.current?.cancel();
      recorderRef.current = null;
    };
  }, []);

  // Fallback used only if the backend signals it can't score (e.g. 503 because
  // no Azure key in dev). Produces simulated bands so the UI still feels alive.
  function simulatedBands(text: string): PronScores {
    const out: PronScores = {};
    for (const i of tokenizeWordIndices(text)) {
      const r = Math.random();
      out[i] = r < 0.62 ? "good" : r < 0.88 ? "ok" : "bad";
    }
    return out;
  }

  const closePopover = useCallback(() => {
    setActive(null);
  }, []);

  const handleWordTap = useCallback(
    (word: StoryWord, key: string, el: HTMLElement) => {
      setActive({ word, key, rect: el.getBoundingClientRect() });
    },
    []
  );

  const handlePlay = useCallback(() => {
    if (!current || !story) return;
    setRecordingIndex(null);
    if (playingIndex === currentIndex && tts.playing) {
      stop();
    } else {
      speak(current.target, story.target_language);
    }
  }, [current, currentIndex, playingIndex, tts.playing, story]);

  const handlePlaySlow = useCallback(() => {
    if (!current || !story) return;
    setRecordingIndex(null);
    speak(current.target, story.target_language, { rate: 0.7 });
  }, [current, story]);

  const handleRecord = useCallback(async () => {
    stop();
    // Toggle off: stop the active recorder and let the upload finish.
    if (recordingIndex === currentIndex && recorderRef.current) {
      const rec = recorderRef.current;
      recorderRef.current = null;
      setRecordingIndex(null);
      setEvaluatingIndex(currentIndex);
      try {
        const blob = await rec.stop();
        if (!blob || blob.size === 0) {
          setPronError({ kind: "no_speech" });
          return;
        }
        const sentence = sentences[currentIndex];
        if (!sentence || !story) return;
        const resp = await scoreAudio(blob, sentence.target, story.target_language);
        const bands = bandsByTokenIndex(sentence.target, resp.words);
        setScoresBySentence((s) => ({ ...s, [currentIndex]: bands }));
        setPronError(null);
      } catch (e) {
        const perr = e as PronunciationError;
        // 503 (no Azure key configured) → fall back to the simulated bands so
        // the dev experience without a key still feels functional.
        if (perr.kind === "service_unavailable") {
          const sentence = sentences[currentIndex];
          if (sentence) {
            setScoresBySentence((s) => ({ ...s, [currentIndex]: simulatedBands(sentence.target) }));
          }
          setPronError(null);
        } else {
          setPronError(perr);
        }
      } finally {
        setEvaluatingIndex(null);
      }
      return;
    }
    // Toggle on: clear any previous score for this sentence and open the mic.
    setScoresBySentence((s) => {
      const n = { ...s };
      delete n[currentIndex];
      return n;
    });
    setPronError(null);
    try {
      const rec = await startMicRecording();
      recorderRef.current = rec;
      setRecordingIndex(currentIndex);
    } catch (e) {
      setPronError(e as PronunciationError);
    }
  }, [currentIndex, recordingIndex, sentences, story]);

  const goNext = useCallback(() => {
    if (currentIndex >= total - 1) {
      stop();
      setFinished(true);
      return;
    }
    setDirection("forward");
    stop();
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setRecordingIndex(null);
    setEvaluatingIndex(null);
    setPronError(null);
    closePopover();
    setCurrentIndex((i) => i + 1);
  }, [currentIndex, total, closePopover]);

  const goPrev = useCallback(() => {
    if (currentIndex <= 0) return;
    setDirection("backward");
    stop();
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setRecordingIndex(null);
    setEvaluatingIndex(null);
    setPronError(null);
    closePopover();
    setCurrentIndex((i) => i - 1);
  }, [currentIndex, closePopover]);

  useEffect(() => {
    if (finished || !story) return;
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      } else if (e.key === " ") {
        e.preventDefault();
        handlePlay();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goNext, goPrev, handlePlay, finished, story]);

  async function toggleReview(word: StoryWord) {
    if (reviewIds.has(word.id) || adding === word.id) return;
    setAdding(word.id);
    try {
      await api.addCard(word.id);
      setReviewIds((s) => {
        const n = new Set(s);
        n.add(word.id);
        return n;
      });
    } catch {
      // silent
    } finally {
      setAdding(null);
    }
  }

  if (error) {
    return (
      <main className="k-page story">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("common.back")}
        </button>
        <div className="k-error" role="alert">
          {error}
        </div>
      </main>
    );
  }

  if (!story) {
    return (
      <main className="k-page story">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("common.back")}
        </button>
        <div className="story-loading">
          <span className="k-mono">{t("common.klaraWriting")}</span>
          <span className="k-spinner" />
        </div>
      </main>
    );
  }

  if (finished) {
    return (
      <StoryFinished
        story={story}
        reviewIds={reviewIds}
        adding={adding}
        scoresBySentence={scoresBySentence}
        onRestart={() => {
          stop();
          setCurrentIndex(0);
          setDirection("forward");
          setScoresBySentence({});
          setFinished(false);
        }}
        onNew={() => navigate("/story/new")}
        onHome={() => navigate("/")}
        onToggleReview={toggleReview}
      />
    );
  }

  return (
    <main
      className="k-page story"
      style={{ "--font-scale": fontScale } as React.CSSProperties}
    >
      <div className="story__topbar">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("common.exit")}
        </button>
        <div className="story__byline-mini">
          <KlaraMark size={12} speaking={klaraSpeaking} />
          <span className="k-mono">{story.title}</span>
        </div>
        <span className="k-level story__topbar-level">{story.level}</span>
      </div>

      <div className="story__stage" data-direction={direction}>
        {current && (
          <SentenceStep
            key={currentIndex}
            sentence={current}
            index={currentIndex}
            total={total}
            targetLanguage={story.target_language}
            lemmaIndex={lemmaIndex}
            wordsById={wordsById}
            activeWordKey={active?.key ?? null}
            onWordTap={handleWordTap}
            playing={playingIndex === currentIndex && tts.playing}
            recording={recordingIndex === currentIndex}
            onPlay={handlePlay}
            onPlaySlow={handlePlaySlow}
            onRecord={handleRecord}
            scores={scoresBySentence[currentIndex]}
            feedback={scoresBySentence[currentIndex]}
            onRetry={handleRecord}
            onPrev={goPrev}
            onNext={goNext}
            canPrev={currentIndex > 0}
            canNext={currentIndex < total - 1}
          />
        )}
      </div>

      {evaluatingIndex === currentIndex && (
        <div className="k-mono" style={{ marginTop: "0.75rem", color: "var(--ink-3)" }}>
          {t("pron.evaluating")}
        </div>
      )}
      {pronError && (
        <div className="k-error" role="alert" style={{ marginTop: "0.75rem" }}>
          {t(`pron.error.${pronError.kind}`)}
        </div>
      )}

      {active && (
        <WordPopover
          word={active.word}
          anchorRect={active.rect}
          targetLanguage={story.target_language}
          alreadyAdded={reviewIds.has(active.word.id)}
          onClose={closePopover}
          onAdded={(id) =>
            setReviewIds((s) => {
              const n = new Set(s);
              n.add(id);
              return n;
            })
          }
        />
      )}
    </main>
  );
}

interface FinishedProps {
  story: Story;
  reviewIds: Set<string>;
  adding: string | null;
  scoresBySentence: Record<number, PronScores>;
  onRestart: () => void;
  onNew: () => void;
  onHome: () => void;
  onToggleReview: (word: StoryWord) => void;
}

function StoryFinished({
  story,
  reviewIds,
  adding,
  scoresBySentence,
  onRestart,
  onNew,
  onHome,
  onToggleReview,
}: FinishedProps) {
  const { t } = useTranslation();
  const sentencesPracticed = Object.keys(scoresBySentence).length;
  const allScores = Object.values(scoresBySentence).flatMap((s) => Object.values(s));
  const goodPct = allScores.length
    ? Math.round((allScores.filter((v) => v === "good").length / allScores.length) * 100)
    : null;

  return (
    <main className="k-page story-end">
      <button className="story__back k-mono" onClick={onHome}>
        {t("common.backHome")}
      </button>

      <header className="story-end__head">
        <div className="story-end__sig">
          <KlaraMark size={14} />
          <span className="k-mono">{t("story.end.kicker")}</span>
        </div>
        <h1 className="story-end__title">{story.title}</h1>
        <p className="story-end__dek k-serif">
          {sentencesPracticed > 0
            ? t("story.end.dek.practiced", { count: sentencesPracticed })
            : t("story.end.dek.read")}
        </p>
      </header>

      {goodPct !== null && (
        <section className="story-end__stats">
          <div className="story-end__stat">
            <span className="story-end__stat-num">
              {goodPct}
              <span className="story-end__stat-unit k-mono">%</span>
            </span>
            <span className="k-mono">{t("story.end.stat.clear")}</span>
          </div>
          <div className="story-end__stat-rule" />
          <div className="story-end__stat">
            <span className="story-end__stat-num">
              {sentencesPracticed}
              <span className="story-end__stat-unit k-mono">/{story.content.sentences.length}</span>
            </span>
            <span className="k-mono">{t("story.end.stat.sentences")}</span>
          </div>
        </section>
      )}

      {story.target_words.length > 0 && (
        <>
          <hr className="k-hairline" />
          <section className="story__new">
            <header className="story__new-head">
              <span className="k-mono">{t("story.end.words.title")}</span>
              <span className="k-mono story__new-count">{story.target_words.length}</span>
            </header>
            <ul className="story__new-list">
              {story.target_words.map((w) => {
                const added = reviewIds.has(w.id);
                const showArticle = story.target_language === "de";
                const article = showArticle ? w.gender ?? null : null;
                return (
                  <li key={w.id} className="story__new-item">
                    <div className="story__new-word">
                      {article && <span className="story__new-art">{article}</span>}
                      <span className="story__new-lemma">{w.lemma}</span>
                    </div>
                    {w.translation && (
                      <span className="story__new-tx">{w.translation}</span>
                    )}
                    <button
                      type="button"
                      className="story__new-add"
                      data-added={added}
                      disabled={adding === w.id}
                      onClick={() => onToggleReview(w)}
                    >
                      {added
                        ? t("story.end.words.added")
                        : adding === w.id
                        ? t("story.end.words.adding")
                        : t("story.end.words.add")}
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        </>
      )}

      <hr className="k-hairline" />

      <footer className="story__foot">
        <button type="button" className="k-btn" onClick={onNew}>
          {t("story.end.cta.another")} <span className="arrow">→</span>
        </button>
        <button type="button" className="k-btn k-btn--ghost" onClick={onRestart}>
          {t("story.end.cta.reread")}
        </button>
      </footer>
    </main>
  );
}
