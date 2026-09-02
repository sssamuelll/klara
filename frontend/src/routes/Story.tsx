import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Story, StoryWord, WordBreakdown } from "../api/types";
import BreakdownPopover from "../components/BreakdownPopover";
import EstudiarView from "../components/EstudiarView";
import SessTop from "../components/SessTop";
import StoryFinish from "../components/StoryFinish";
import WordPopover from "../components/WordPopover";
import { autoFscaleStep } from "../lib/autoFscale";
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
  const location = useLocation();
  const { t } = useTranslation();
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fontScale] = useFontScale();
  const [active, setActive] = useState<ActivePopover | null>(null);
  const [reviewIds, setReviewIds] = useState<Set<string>>(new Set());
  const [adding, setAdding] = useState<string | null>(null);
  const [finished, setFinished] = useState(false);

  // Entries pass { state: { from: <pathname> } }; exits go back there.
  // Fallback "/" preserves the old behaviour exactly where no state is passed.
  const exitTo = (location.state as { from?: string } | null)?.from ?? "/";
  const salir = useCallback(() => navigate(exitTo), [navigate, exitTo]);

  const sentences = useMemo(() => story?.content.sentences ?? [], [story]);

  // Per-item persistence targets for the shared hook (new per-item firma in
  // PR #3b). In the reading view the queue index IS the story index — every
  // sentence i belongs to this story at index i — so this is exactly the old
  // single global `persistStoryId: story.id` behaviour, just expressed per
  // line. Empty (and thus persisting nothing) until the story loads, matching
  // the old `story?.id ?? null` guard.
  const persistTargets = useMemo(
    () => (story ? sentences.map((_, i) => ({ storyId: story.id, sentenceIndex: i })) : []),
    [story, sentences],
  );

  // Per-sentence pronunciation lifecycle (mic / TTS / scoring / hints /
  // keyboard) lives in the shared hook, extracted from this file so the
  // standalone Practice ("Pronunciar") session can reuse the exact same
  // behaviour. SentenceView stays presentational; navigation + popovers +
  // the finish screen stay here (reading-view-specific).
  const practice = useSentencePractice({
    sentences,
    targetLanguage: story?.target_language ?? "de",
    persistTargets,
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

  // Font scale: user preference × automatic step decided by the sentence's
  // effective length (spec F2 §5.1). Feeds the --fscale custom property.
  const fscale = useMemo(
    () => (current ? fontScale * autoFscaleStep(current.target, fontScale) : fontScale),
    [current, fontScale],
  );

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
      <div className="k-app">
        <SessTop titulo="" right="" onExit={salir} />
        <div className="k-fill" />
        <div className="k-band">
          <p className="k-error" role="alert">{error}</p>
          <div className="k-wrap">
            <button className="k-btn k-btn--ghost k-btn--block" onClick={salir}>{t("common.exit")}</button>
          </div>
        </div>
      </div>
    );
  }

  if (!story) {
    return (
      <div className="k-app">
        <SessTop titulo="" right="" onExit={salir} />
        <div className="k-fill">
          <span className="k-spinner" />
        </div>
      </div>
    );
  }

  // Interim until F2.4: StoryFinish keeps its legacy skin inside a plain
  // kapp/kframe (no Masthead) — .k-app's overflow:hidden would break the
  // quiz scroll.
  if (finished) {
    return (
      <div className="kapp">
        <div className="kframe">
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
            onSummaryShown={() => {
              api.finishStory(story.id).catch(() => {});
            }}
            onNextInModule={
              story.module_id
                ? async () => {
                    try {
                      const next = await api.claimModuleStory(story.module_id!);
                      navigate(`/estudiar/${next.id}`, { state: { from: exitTo } });
                      setFinished(false);
                      practice.reset();
                    } catch {
                      navigate(`/story/new?module=${story.module_id}`);
                    }
                  }
                : undefined
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="k-app">
      {current && (
        <EstudiarView
          storyTitle={story.title}
          onExit={salir}
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
          recording={practice.recording}
          evaluating={practice.evaluating}
          micLevel={practice.micLevel}
          feedback={practice.feedback}
          liveBands={practice.liveBands}
          phoneticHints={practice.phoneticHints}
          diagnosis={practice.diagnosis}
          diagnosing={practice.diagnosing}
          rate={practice.rate}
          pronError={practice.pronError}
          fscale={fscale}
          onPlayPause={practice.handlePlayPause}
          onCycleSpeed={practice.cycleSpeed}
          onRecordStart={practice.startRecording}
          onRecordStop={practice.stopRecording}
          onRetry={practice.onRetry}
          onErrorDismiss={practice.cancelRecording}
          onPrev={goPrev}
          onNext={goNext}
        />
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
    </div>
  );
}
