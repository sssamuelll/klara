import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Story, StoryWord, WordBreakdown } from "../api/types";
import BreakdownPopover from "../components/BreakdownPopover";
import SentenceView from "../components/SentenceView";
import StoryFinish from "../components/StoryFinish";
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
import { startSilenceDetector } from "../lib/silenceDetector";
import { speak, stop, useTTS } from "../lib/tts";

// Tap state for the in-sentence popovers. Two flavours:
//   target    → full WordPopover with example + Repaso button + POS panel.
//   breakdown → BreakdownPopover with just translation + audio.
type ActivePopover =
  | { kind: "target"; word: StoryWord; key: string; rect: DOMRect }
  | { kind: "breakdown"; entry: WordBreakdown; key: string; rect: DOMRect };

type PronScores = Record<number, ScoreBand>;

// Cuando estás aprendiendo, lo que falta es más lento — nunca más rápido.
// El pill cicla entre normal y 0.7× (toggle binario). El 1.3× anterior se
// removió porque pedagógicamente no aplicaba al caso de uso.
const RATES = [0.7, 1] as const;
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
  const [active, setActive] = useState<ActivePopover | null>(null);
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
      setActive({ kind: "target", word, key, rect: el.getBoundingClientRect() });
    },
    [],
  );

  const handleBreakdownTap = useCallback(
    (entry: WordBreakdown, key: string, el: HTMLElement) => {
      setActive({ kind: "breakdown", entry, key, rect: el.getBoundingClientRect() });
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
      // Best-effort: persist the attempt so SRS + souvenir picker can use it
      // across sessions. Failure here doesn't affect the UX.
      void api
        .recordPronunciationAttempt(story.id, {
          sentence_index: idxAtStart,
          reference_text: sentence.target,
          recognized_text: resp.recognized_text,
          overall_score: resp.scores.pronunciation,
          word_bands: Object.fromEntries(
            Object.entries(bands).map(([k, v]) => [k, v]),
          ),
        })
        .catch(() => undefined);
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

  // Primary stop trigger for the sentence pronunciation flow: 1.5s of
  // silence (after a 800ms grace period) auto-stops the take. Manual
  // stops still work — clicking the mic again, pressing ESC, or
  // releasing M (hold-to-talk) all short-circuit ahead of the detector.
  // stopRecording is idempotent so a race between manual + auto is fine.
  useEffect(() => {
    if (recordingIndex === null || !micAnalyser) return;
    return startSilenceDetector(micAnalyser, () => {
      void stopRecording();
    });
  }, [recordingIndex, micAnalyser, stopRecording]);

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
      <StoryFinish
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
  const evaluating = evaluatingIndex === currentIndex;
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
          onBreakdownTap={handleBreakdownTap}
          playing={sentencePlaying}
          progress={sentencePlaying ? tts.progress : 0}
          duration={tts.duration}
          recording={recording}
          micAnalyser={recording ? micAnalyser : null}
          evaluating={evaluating}
          feedback={feedback}
          phoneticHints={phoneticHints}
          rate={rate}
          onPlayPause={handlePlayPause}
          onCycleSpeed={cycleSpeed}
          onRecordStart={startRecording}
          onRecordStop={stopRecording}
          onRetry={onRetry}
          onListenFromFeedback={handleListenFromFeedback}
          onPrev={goPrev}
          onNext={goNext}
          canPrev={currentIndex > 0}
          canNext={currentIndex < total - 1}
        />
      )}

      {pronError && (
        <div className="k-error story__pron-error" role="alert">
          {t(`pron.error.${pronError.kind}`)}
        </div>
      )}

      {active?.kind === "target" && (
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
      {active?.kind === "breakdown" && (
        <BreakdownPopover
          entry={active.entry}
          anchorRect={active.rect}
          targetLanguage={story.target_language}
          onClose={closePopover}
        />
      )}
    </main>
  );
}

