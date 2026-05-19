import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Story, StoryWord } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import SentenceView from "../components/SentenceView";
import WordPopover from "../components/WordPopover";
import { useFontScale } from "../lib/preferences";
import {
  bandsByTokenIndex,
  scoreAudio,
  startMicRecording,
  type MicRecorder,
  type PronunciationError,
  type ScoreBand,
} from "../lib/pronunciation";
import { speak, stop, useTTS } from "../lib/tts";

interface ActiveWord {
  word: StoryWord;
  key: string;
  rect: DOMRect;
}

type PronScores = Record<number, ScoreBand>;

const RATES = [0.7, 1, 1.3] as const;
type Rate = (typeof RATES)[number];

// Word-token regex shared with SentenceView; used here to extract bad-word
// strings for the phonetic-hints request.
const WORD_RE = /(\s+)|([.,!?;:„""»«()¡¿—–\-]+)|([^\s.,!?;:„""»«()¡¿—–\-]+)/g;

function badWordsFromBands(text: string, bands: PronScores): string[] {
  const out: string[] = [];
  let i = 0;
  let m: RegExpExecArray | null;
  WORD_RE.lastIndex = 0;
  while ((m = WORD_RE.exec(text)) !== null) {
    if (m[3] && bands[i] === "bad") out.push(m[3]);
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
  const [recordingIndex, setRecordingIndex] = useState<number | null>(null);
  const [evaluatingIndex, setEvaluatingIndex] = useState<number | null>(null);
  const [scoresBySentence, setScoresBySentence] = useState<Record<number, PronScores>>({});
  const [phoneticHintsBySentence, setPhoneticHintsBySentence] = useState<
    Record<number, Record<string, string>>
  >({});
  const [pronError, setPronError] = useState<PronunciationError | null>(null);
  const [finished, setFinished] = useState(false);
  const [rate, setRate] = useState<Rate>(1);
  const [micAnalyser, setMicAnalyser] = useState<AnalyserNode | null>(null);

  // While set, recorder is live; calling stop() returns the captured Blob.
  const recorderRef = useRef<MicRecorder | null>(null);

  const tts = useTTS();

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setStory(null);
    setError(null);
    setActive(null);
    setReviewIds(new Set());
    setCurrentIndex(0);
    setRecordingIndex(null);
    setScoresBySentence({});
    setPhoneticHintsBySentence({});
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

  // Cleanup any in-flight recording when the story or component unmounts.
  useEffect(() => {
    return () => {
      recorderRef.current?.cancel();
      recorderRef.current = null;
      setMicAnalyser(null);
    };
  }, []);

  // Fallback used only if the backend signals it can't score (e.g. 503 because
  // no Azure key in dev). Produces simulated bands keyed by FULL token index
  // so the UI still feels alive.
  function simulatedBands(text: string): PronScores {
    const out: PronScores = {};
    let i = 0;
    let m: RegExpExecArray | null;
    WORD_RE.lastIndex = 0;
    while ((m = WORD_RE.exec(text)) !== null) {
      if (m[3]) {
        const r = Math.random();
        out[i] = r < 0.62 ? "good" : r < 0.88 ? "ok" : "bad";
      }
      i++;
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
    [],
  );

  const handlePlayPause = useCallback(() => {
    if (!current || !story) return;
    if (playingIndex === currentIndex && tts.playing) {
      stop();
    } else {
      speak(current.target, story.target_language, { rate });
    }
  }, [current, currentIndex, playingIndex, rate, story, tts.playing]);

  const handleListenFromFeedback = useCallback(() => {
    if (!current || !story) return;
    speak(current.target, story.target_language, { rate });
  }, [current, rate, story]);

  const cycleSpeed = useCallback(() => {
    setRate((r) => {
      const idx = RATES.indexOf(r);
      return RATES[(idx + 1) % RATES.length];
    });
  }, []);

  const clearFeedback = useCallback(() => {
    setScoresBySentence((s) => {
      if (!(currentIndex in s)) return s;
      const next = { ...s };
      delete next[currentIndex];
      return next;
    });
    setPhoneticHintsBySentence((s) => {
      if (!(currentIndex in s)) return s;
      const next = { ...s };
      delete next[currentIndex];
      return next;
    });
  }, [currentIndex]);

  const fetchAndStoreHints = useCallback(
    async (idx: number, sentenceText: string, bands: PronScores, language: string) => {
      const badWords = badWordsFromBands(sentenceText, bands);
      if (badWords.length === 0) return;
      try {
        const resp = await api.getPhoneticHints(badWords, language);
        if (Object.keys(resp.hints).length === 0) return;
        setPhoneticHintsBySentence((s) => ({ ...s, [idx]: resp.hints }));
      } catch {
        // best-effort: an empty hints map just means the verdict shows
        // without a phonetic tip.
      }
    },
    [],
  );

  const startRecording = useCallback(async () => {
    // Ignore if we're already recording or no sentence yet.
    if (recordingIndex !== null || !current || !story) return;
    stop(); // any Klara playback stops when the mic opens
    clearFeedback();
    setPronError(null);
    try {
      const rec = await startMicRecording();
      recorderRef.current = rec;
      setMicAnalyser(rec.analyser);
      setRecordingIndex(currentIndex);
    } catch (e) {
      setPronError(e as PronunciationError);
    }
  }, [clearFeedback, current, currentIndex, recordingIndex, story]);

  const stopRecording = useCallback(async () => {
    const rec = recorderRef.current;
    if (rec === null || recordingIndex === null || !story) return;
    const idxAtStart = recordingIndex;
    recorderRef.current = null;
    setRecordingIndex(null);
    setMicAnalyser(null);
    setEvaluatingIndex(idxAtStart);
    try {
      const blob = await rec.stop();
      if (!blob || blob.size === 0) {
        setPronError({ kind: "no_speech" });
        return;
      }
      const sentence = sentences[idxAtStart];
      if (!sentence) return;
      const resp = await scoreAudio(blob, sentence.target, story.target_language);
      const bands = bandsByTokenIndex(sentence.target, resp.words);
      setScoresBySentence((s) => ({ ...s, [idxAtStart]: bands }));
      setPronError(null);
      // Fire-and-forget: hints arrive after the panel is already on screen.
      void fetchAndStoreHints(idxAtStart, sentence.target, bands, story.target_language);
    } catch (e) {
      const perr = e as PronunciationError;
      if (perr.kind === "service_unavailable") {
        const sentence = sentences[idxAtStart];
        if (sentence) {
          setScoresBySentence((s) => ({ ...s, [idxAtStart]: simulatedBands(sentence.target) }));
        }
        setPronError(null);
      } else {
        setPronError(perr);
      }
    } finally {
      setEvaluatingIndex(null);
    }
  }, [fetchAndStoreHints, recordingIndex, sentences, story]);

  const cancelRecording = useCallback(() => {
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setRecordingIndex(null);
    setMicAnalyser(null);
    setPronError(null);
  }, []);

  const goNext = useCallback(() => {
    if (currentIndex >= total - 1) {
      stop();
      setFinished(true);
      return;
    }
    stop();
    cancelRecording();
    setEvaluatingIndex(null);
    closePopover();
    setCurrentIndex((i) => i + 1);
  }, [cancelRecording, closePopover, currentIndex, total]);

  const goPrev = useCallback(() => {
    if (currentIndex <= 0) return;
    stop();
    cancelRecording();
    setEvaluatingIndex(null);
    closePopover();
    setCurrentIndex((i) => i - 1);
  }, [cancelRecording, closePopover, currentIndex]);

  const onRetry = useCallback(() => {
    clearFeedback();
    // The retry button doesn't start recording immediately — user holds the
    // mic (or presses M) to re-attempt. This matches the hold-to-talk model.
  }, [clearFeedback]);

  // Keyboard: SPACE play/pause · M hold-to-talk · ←/→ navigate · ESC cancel
  useEffect(() => {
    if (finished || !story) return;
    function isTypingTarget(el: EventTarget | null): boolean {
      if (!(el instanceof HTMLElement)) return false;
      return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable;
    }
    function onKey(e: KeyboardEvent) {
      if (isTypingTarget(e.target)) return;
      if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        goNext();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPrev();
      } else if (e.key === " ") {
        e.preventDefault();
        handlePlayPause();
      } else if (e.key === "m" || e.key === "M") {
        // Hold-to-talk: ignore autorepeat firings of keydown.
        if (e.repeat) return;
        e.preventDefault();
        void startRecording();
      } else if (e.key === "Escape") {
        e.preventDefault();
        if (recordingIndex !== null) cancelRecording();
        else if (currentIndex in scoresBySentence) clearFeedback();
      }
    }
    function onKeyUp(e: KeyboardEvent) {
      if (isTypingTarget(e.target)) return;
      if (e.key === "m" || e.key === "M") {
        e.preventDefault();
        void stopRecording();
      }
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [
    cancelRecording,
    clearFeedback,
    currentIndex,
    finished,
    goNext,
    goPrev,
    handlePlayPause,
    recordingIndex,
    scoresBySentence,
    startRecording,
    stopRecording,
    story,
  ]);

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
          setScoresBySentence({});
          setPhoneticHintsBySentence({});
          setFinished(false);
        }}
        onNew={() => navigate("/story/new")}
        onHome={() => navigate("/")}
        onToggleReview={toggleReview}
      />
    );
  }

  const recording = recordingIndex === currentIndex;
  const feedback = scoresBySentence[currentIndex];
  const phoneticHints = phoneticHintsBySentence[currentIndex];
  const sentencePlaying = playingIndex === currentIndex && tts.playing;

  return (
    <main
      className="k-page story story--audio"
      style={{ "--font-scale": fontScale } as React.CSSProperties}
    >
      {current && (
        <SentenceView
          storyTitle={story.title}
          storyLevel={story.level}
          onExit={() => navigate("/")}
          sentence={current}
          index={currentIndex}
          total={total}
          targetLanguage={story.target_language}
          lemmaIndex={lemmaIndex}
          wordsById={wordsById}
          activeWordKey={active?.key ?? null}
          onWordTap={handleWordTap}
          playing={sentencePlaying}
          progress={sentencePlaying ? tts.progress : 0}
          duration={tts.duration}
          recording={recording}
          micAnalyser={recording ? micAnalyser : null}
          feedback={feedback}
          phoneticHints={phoneticHints}
          rate={rate}
          onPlayPause={handlePlayPause}
          onCycleSpeed={cycleSpeed}
          onRecordStart={startRecording}
          onRecordStop={stopRecording}
          onRecordCancel={cancelRecording}
          onRetry={onRetry}
          onListenFromFeedback={handleListenFromFeedback}
          onPrev={goPrev}
          onNext={goNext}
          canPrev={currentIndex > 0}
          canNext={currentIndex < total - 1}
        />
      )}

      {evaluatingIndex === currentIndex && (
        <div className="k-mono story__evaluating" role="status" aria-live="polite">
          {t("pron.evaluating")}
        </div>
      )}
      {pronError && (
        <div className="k-error story__pron-error" role="alert">
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
                    {w.translation && <span className="story__new-tx">{w.translation}</span>}
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
