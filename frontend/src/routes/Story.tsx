import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Story, StoryWord, WordBreakdown } from "../api/types";
import BreakdownPopover from "../components/BreakdownPopover";
import SentenceView from "../components/SentenceView";
import StoryFinish from "../components/StoryFinish";
import WordPopover from "../components/WordPopover";
import { useFontScale } from "../lib/preferences";
import { useSentencePractice } from "../lib/useSentencePractice";

// Tap state for the in-sentence popovers. Two flavours:
//   target    → full WordPopover with example + Repaso button + POS panel.
//   breakdown → BreakdownPopover with just translation + audio.
type ActivePopover =
  | { kind: "target"; word: StoryWord; key: string; rect: DOMRect }
  | { kind: "breakdown"; entry: WordBreakdown; key: string; rect: DOMRect };

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
  const [finished, setFinished] = useState(false);

  const sentences = useMemo(() => story?.content.sentences ?? [], [story]);

  // Per-sentence pronunciation lifecycle (mic / TTS / scoring / hints /
  // keyboard) lives in the shared hook, extracted from this file so the
  // standalone Practice ("Pronunciar") session can reuse the exact same
  // behaviour. SentenceView stays presentational; navigation + popovers +
  // the finish screen stay here (reading-view-specific).
  const practice = useSentencePractice({
    sentences,
    targetLanguage: story?.target_language ?? "de",
    persistStoryId: story?.id ?? null,
    onFinish: () => setFinished(true),
    keyboardEnabled: Boolean(story) && !finished,
  });

  const closePopover = useCallback(() => {
    setActive(null);
  }, []);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setStory(null);
    setError(null);
    setActive(null);
    setReviewIds(new Set());
    setFinished(false);
    practice.reset();
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
      practice.stopAudio();
    };
    // practice.reset / stopAudio are stable callbacks; depending on `id`/`t`
    // matches the original effect (which re-ran only when story id changed).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, t]);

  const total = sentences.length;
  const current = sentences[practice.currentIndex];

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

  // Wrap navigation so popovers close on every sentence change, matching the
  // original goNext/goPrev which called closePopover().
  const goNext = useCallback(() => {
    closePopover();
    practice.goNext();
  }, [closePopover, practice]);

  const goPrev = useCallback(() => {
    closePopover();
    practice.goPrev();
  }, [closePopover, practice]);

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
        scoresBySentence={practice.scoresBySentence}
        onRestart={() => {
          practice.reset();
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
      className="k-page story story--audio"
      style={{ "--font-scale": fontScale } as React.CSSProperties}
    >
      {current && (
        <SentenceView
          storyTitle={story.title}
          storyLevel={story.level}
          onExit={() => navigate("/")}
          sentence={current}
          index={practice.currentIndex}
          total={total}
          targetLanguage={story.target_language}
          lemmaIndex={lemmaIndex}
          wordsById={wordsById}
          activeWordKey={active?.key ?? null}
          onWordTap={handleWordTap}
          onBreakdownTap={handleBreakdownTap}
          playing={practice.sentencePlaying}
          progress={practice.progress}
          duration={practice.duration}
          recording={practice.recording}
          micAnalyser={practice.micAnalyser}
          evaluating={practice.evaluating}
          feedback={practice.feedback}
          phoneticHints={practice.phoneticHints}
          rate={practice.rate}
          onPlayPause={practice.handlePlayPause}
          onCycleSpeed={practice.cycleSpeed}
          onRecordStart={practice.startRecording}
          onRecordStop={practice.stopRecording}
          onRetry={practice.onRetry}
          onListenFromFeedback={practice.handleListenFromFeedback}
          onPrev={goPrev}
          onNext={goNext}
          canPrev={practice.currentIndex > 0}
          canNext={practice.currentIndex < total - 1}
        />
      )}

      {practice.pronError && (
        <div className="k-error story__pron-error" role="alert">
          {t(`pron.error.${practice.pronError.kind}`)}
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
