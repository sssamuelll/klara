import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Story, StoryWord } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import SentenceStep from "../components/SentenceStep";
import WordPopover from "../components/WordPopover";
import type { PronScores } from "../components/PronunciationFeedback";
import { useFontScale } from "../lib/preferences";
import { speak, stop, useTTS } from "../lib/tts";

interface ActiveWord {
  word: StoryWord;
  key: string;
  rect: DOMRect;
}

type Direction = "forward" | "backward";

function tokenizeWordIndices(de: string): number[] {
  // Returns indices of word tokens within the same tokenization SentenceStep uses.
  // Not strictly needed — pronunciation simulator uses contiguous indices anyway.
  const out: number[] = [];
  const re = /(\s+)|([.,!?;:„""»«()¡¿—–\-]+)|([^\s.,!?;:„""»«()¡¿—–\-]+)/g;
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(de)) !== null) {
    if (m[3]) out.push(i);
    i++;
  }
  return out;
}

export default function StoryView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fontScale] = useFontScale();
  const [active, setActive] = useState<ActiveWord | null>(null);
  const [reviewIds, setReviewIds] = useState<Set<string>>(new Set());
  const [adding, setAdding] = useState<string | null>(null);

  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState<Direction>("forward");
  const [recordingIndex, setRecordingIndex] = useState<number | null>(null);
  const [scoresBySentence, setScoresBySentence] = useState<Record<number, PronScores>>({});
  const [finished, setFinished] = useState(false);

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
        if (!cancelled) setError(e instanceof Error ? e.message : "Error");
      });
    return () => {
      cancelled = true;
      stop();
    };
  }, [id]);

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
    return sentences.findIndex((s) => s.de === tts.text);
  }, [sentences, tts.text]);
  const klaraSpeaking = tts.playing && playingIndex >= 0;

  // Pronunciation simulation — replace with real MediaRecorder pipeline later.
  useEffect(() => {
    if (recordingIndex === null) return;
    const sentence = sentences[recordingIndex];
    if (!sentence) return;
    const wordIndices = tokenizeWordIndices(sentence.de);
    const idx = recordingIndex;
    const t = window.setTimeout(() => {
      const scores: PronScores = {};
      for (const i of wordIndices) {
        const r = Math.random();
        scores[i] = r < 0.62 ? "good" : r < 0.88 ? "ok" : "bad";
      }
      setScoresBySentence((s) => ({ ...s, [idx]: scores }));
      setRecordingIndex(null);
    }, 2400);
    return () => window.clearTimeout(t);
  }, [recordingIndex, sentences]);

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
    if (!current) return;
    setRecordingIndex(null);
    if (playingIndex === currentIndex && tts.playing) {
      stop();
    } else {
      speak(current.de);
    }
  }, [current, currentIndex, playingIndex, tts.playing]);

  const handleRecord = useCallback(() => {
    stop();
    setRecordingIndex((r) => (r === currentIndex ? null : currentIndex));
    setScoresBySentence((s) => {
      const n = { ...s };
      delete n[currentIndex];
      return n;
    });
  }, [currentIndex]);

  const goNext = useCallback(() => {
    if (currentIndex >= total - 1) {
      stop();
      setFinished(true);
      return;
    }
    setDirection("forward");
    stop();
    setRecordingIndex(null);
    closePopover();
    setCurrentIndex((i) => i + 1);
  }, [currentIndex, total, closePopover]);

  const goPrev = useCallback(() => {
    if (currentIndex <= 0) return;
    setDirection("backward");
    stop();
    setRecordingIndex(null);
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
          ← Volver
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
          ← Volver
        </button>
        <div className="story-loading">
          <span className="k-mono">Klara está escribiendo…</span>
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
          ← Salir
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
            lemmaIndex={lemmaIndex}
            wordsById={wordsById}
            activeWordKey={active?.key ?? null}
            onWordTap={handleWordTap}
            playing={playingIndex === currentIndex && tts.playing}
            recording={recordingIndex === currentIndex}
            onPlay={handlePlay}
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

      {active && (
        <WordPopover
          word={active.word}
          anchorRect={active.rect}
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
  const sentencesPracticed = Object.keys(scoresBySentence).length;
  const allScores = Object.values(scoresBySentence).flatMap((s) => Object.values(s));
  const goodPct = allScores.length
    ? Math.round((allScores.filter((v) => v === "good").length / allScores.length) * 100)
    : null;

  return (
    <main className="k-page story-end">
      <button className="story__back k-mono" onClick={onHome}>
        ← Volver al inicio
      </button>

      <header className="story-end__head">
        <div className="story-end__sig">
          <KlaraMark size={14} />
          <span className="k-mono">Fin de la historia</span>
        </div>
        <h1 className="story-end__title">{story.title}</h1>
        <p className="story-end__dek k-serif">
          Bien.{" "}
          {sentencesPracticed > 0
            ? `Practicaste tu pronunciación en ${sentencesPracticed} ${
                sentencesPracticed > 1 ? "oraciones" : "oración"
              }.`
            : "Klara te leyó la historia."}
        </p>
      </header>

      {goodPct !== null && (
        <section className="story-end__stats">
          <div className="story-end__stat">
            <span className="story-end__stat-num">
              {goodPct}
              <span className="story-end__stat-unit k-mono">%</span>
            </span>
            <span className="k-mono">claras</span>
          </div>
          <div className="story-end__stat-rule" />
          <div className="story-end__stat">
            <span className="story-end__stat-num">
              {sentencesPracticed}
              <span className="story-end__stat-unit k-mono">/{story.content.sentences.length}</span>
            </span>
            <span className="k-mono">oraciones</span>
          </div>
        </section>
      )}

      {story.target_words.length > 0 && (
        <>
          <hr className="k-hairline" />
          <section className="story__new">
            <header className="story__new-head">
              <span className="k-mono">Palabras para repasar</span>
              <span className="k-mono story__new-count">{story.target_words.length}</span>
            </header>
            <ul className="story__new-list">
              {story.target_words.map((w) => {
                const added = reviewIds.has(w.id);
                const article = w.gender ?? null;
                return (
                  <li key={w.id} className="story__new-item">
                    <div className="story__new-word">
                      {article && <span className="story__new-art">{article}</span>}
                      <span className="story__new-lemma">{w.lemma}</span>
                    </div>
                    {w.translation_es && (
                      <span className="story__new-tx">{w.translation_es}</span>
                    )}
                    <button
                      type="button"
                      className="story__new-add"
                      data-added={added}
                      disabled={adding === w.id}
                      onClick={() => onToggleReview(w)}
                    >
                      {added ? "✓ En repaso" : adding === w.id ? "Añadiendo…" : "+ Repaso"}
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
          Otra historia <span className="arrow">→</span>
        </button>
        <button type="button" className="k-btn k-btn--ghost" onClick={onRestart}>
          Releer esta
        </button>
      </footer>
    </main>
  );
}
