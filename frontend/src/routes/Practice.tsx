/**
 * Practice — "Pronunciar". Klara's spaced-pronunciation set: sentences the
 * learner already read, pulled back because a word stuck (struggled) or it's
 * due by SRS (review). No streaks, no guilt, no game-score. The mic is the
 * protagonist.
 *
 * This REPLACES the old /review stub — Practice IS the review.
 *
 * Three phases: setup → session → summary.
 *   - setup / summary: ported from the design handoff (kp-* markup), strings
 *     extracted to i18n (es is the source).
 *   - session: reuses the reading view's <SentenceView> driven by the shared
 *     useSentencePractice hook, so mic / TTS / scoring / hints / keyboard
 *     behave identically to Story.
 *
 * Queue source: GET /api/v1/practice/queue, fetched once on mount via
 * buildMockQueue(). This component is endpoint-agnostic — it renders whatever
 * PracticeItem[] comes back.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { StorySentence } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import SentenceView from "../components/SentenceView";
import { useFontScale } from "../lib/preferences";
import {
  buildMockQueue,
  countByReason,
  type PracticeItem,
  type PracticeQueue,
} from "../lib/practiceQueue";
import { useSentencePractice, type PronScores } from "../lib/useSentencePractice";

type Phase = "setup" | "session" | "summary";

// Adapt a PracticeItem's origin sentence to the StorySentence shape
// SentenceView consumes. Practice items carry no per-word breakdown, so taps
// fall through to non-clickable like older stories without breakdowns.
function toStorySentence(item: PracticeItem): StorySentence {
  return {
    target: item.sentence.target,
    native: item.sentence.native,
    new_words: [],
    breakdown: null,
  };
}

// Summary tally: per item, fraction of "good" bands → clear / mid / revisit.
// Mirrors the handoff's bucketing (≥0.8 clear, ≥0.5 mid, else revisit).
function tallySummary(
  total: number,
  scoresBySentence: Record<number, PronScores>,
): { clear: number; mid: number; revisit: number; answered: number } {
  let clear = 0;
  let mid = 0;
  let revisit = 0;
  let answered = 0;
  for (let i = 0; i < total; i++) {
    const scores = scoresBySentence[i];
    if (!scores) continue;
    const vals = Object.values(scores);
    if (vals.length === 0) continue;
    answered++;
    const good = vals.filter((s) => s === "good").length;
    const frac = good / vals.length;
    if (frac >= 0.8) clear++;
    else if (frac >= 0.5) mid++;
    else revisit++;
  }
  return { clear, mid, revisit, answered };
}

export default function Practice() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [fontScale] = useFontScale();

  // Queue is fetched once on mount; stable for the lifetime of the screen.
  const [queue, setQueue] = useState<PracticeQueue | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  useEffect(() => {
    let alive = true;
    buildMockQueue()
      .then((q) => {
        if (alive) setQueue(q);
      })
      .catch(() => {
        if (alive) setLoadFailed(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  const items = queue?.items ?? [];
  const total = items.length;
  const struggledN = useMemo(() => countByReason(items, "struggled"), [items]);
  const reviewN = total - struggledN;

  const [phase, setPhase] = useState<Phase>("setup");

  // SentenceView consumes StorySentence; map once.
  const sentences = useMemo(() => items.map(toStorySentence), [items]);

  const practice = useSentencePractice({
    sentences,
    targetLanguage: queue?.targetLanguage ?? "de",
    persistStoryId: null, // mock queue → nothing persisted (no real story id)
    onFinish: () => {
      setPhase("summary");
      window.scrollTo({ top: 0 });
    },
    // Keyboard shortcuts only while the session is on screen.
    keyboardEnabled: phase === "session",
  });

  const item = items[practice.currentIndex];

  // ---- LOADING / ERROR / EMPTY -------------------------------------------
  if (phase === "setup" && (queue === null || loadFailed || total === 0)) {
    const message = loadFailed
      ? t("practice.loading.error")
      : queue === null
        ? t("practice.loading.wait")
        : t("practice.loading.empty");
    return (
      <main className="k-page kp-setup">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("common.back")}
        </button>
        <div className="kp-sign">
          <KlaraMark size={13} />
          <span className="k-mono">{message}</span>
        </div>
      </main>
    );
  }

  // Past this point the queue is loaded and non-empty (guarded above). The
  // explicit null check narrows the type for the render branches below.
  if (queue === null) return null;

  // ---- SETUP --------------------------------------------------------------
  if (phase === "setup") {
    return (
      <main className="k-page kp-setup">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("common.back")}
        </button>
        <header className="kp-setup__head">
          <span className="k-mono">{t("practice.setup.kicker")}</span>
          <h1 className="kp-setup__title">{t("practice.setup.title", { count: total })}</h1>
          <p className="kp-setup__dek">{t("practice.setup.dek")}</p>
        </header>

        <hr className="k-hairline" />

        <section className="kp-sources">
          <div className="kp-source">
            <span className="kp-source__n">{struggledN}</span>
            <span
              className="kp-source__t"
              dangerouslySetInnerHTML={{ __html: t("practice.setup.struggled") }}
            />
          </div>
          <div className="kp-source">
            <span className="kp-source__n">{reviewN}</span>
            <span
              className="kp-source__t"
              dangerouslySetInnerHTML={{ __html: t("practice.setup.review") }}
            />
          </div>
        </section>

        <section className="kp-chips">
          <span className="k-mono kp-chips__cap">{t("practice.setup.startBy")}</span>
          <div className="kp-chips__row">
            <span className="kp-chip" data-selected="true">
              {t("practice.setup.chip.all", { count: total })}
            </span>
            <span className="kp-chip">
              {t("practice.setup.chip.hard", { count: struggledN })}
            </span>
            <span className="kp-chip">
              {t("practice.setup.chip.review", { count: reviewN })}
            </span>
          </div>
        </section>

        <footer className="kp-setup__cta">
          <button
            className="k-btn"
            onClick={() => {
              practice.reset();
              setPhase("session");
            }}
          >
            {t("practice.setup.start")} <span className="arrow">→</span>
          </button>
          <button className="k-btn k-btn--ghost" onClick={() => navigate("/")}>
            {t("practice.setup.later")}
          </button>
        </footer>

        <div className="kp-sign">
          <KlaraMark size={13} />
          <span className="k-mono">{t("practice.setup.from", { title: queue.sourceTitle })}</span>
        </div>
      </main>
    );
  }

  // ---- SUMMARY ------------------------------------------------------------
  if (phase === "summary") {
    const { clear, mid, revisit } = tallySummary(total, practice.scoresBySentence);
    const returns = items.filter((i) => i.reason === "struggled").slice(0, 3);

    return (
      <main className="k-page kp-summary">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("common.backHome")}
        </button>
        <header className="kp-sum__head">
          <div className="kp-sum__sig">
            <span className="kp-sum__k">K</span>
            <span className="k-mono">{t("practice.summary.kicker")}</span>
          </div>
          <h1 className="kp-sum__title">{t("practice.summary.title", { count: total })}</h1>
          <p className="kp-sum__dek">{t("practice.summary.dek")}</p>
        </header>

        <section className="kp-sum__stats">
          <div className="kp-stat">
            <span className="kp-stat__n">{clear}</span>
            <span className="k-mono">{t("practice.summary.stat.clear")}</span>
          </div>
          <span className="kp-stat__rule" />
          <div className="kp-stat">
            <span className="kp-stat__n">{mid}</span>
            <span className="k-mono">{t("practice.summary.stat.ok")}</span>
          </div>
          <span className="kp-stat__rule" />
          <div className="kp-stat">
            <span className="kp-stat__n">{revisit}</span>
            <span className="k-mono">{t("practice.summary.stat.bad")}</span>
          </div>
        </section>

        <hr className="k-hairline" />

        <section className="kp-returns">
          <header className="kp-returns__head">
            <span className="k-mono">{t("practice.summary.returns.title")}</span>
            <span className="k-mono kp-returns__count">{returns.length}</span>
          </header>
          <ul className="kp-returns__list">
            {returns.map((r, i) => (
              <li key={r.focusText} className="kp-returns__item">
                <span className="kp-returns__word">{r.focusText}</span>
                <span className="kp-returns__tx">{r.focusTx}</span>
                <span className="kp-returns__next k-mono">
                  {i === 0
                    ? t("practice.summary.returns.tomorrow")
                    : i === 1
                      ? t("practice.summary.returns.inTwoDays")
                      : t("practice.summary.returns.thisWeek")}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <footer className="kp-sum__cta">
          <button
            className="k-btn"
            onClick={() => {
              practice.reset();
              setPhase("setup");
            }}
          >
            {t("practice.summary.again")} <span className="arrow">→</span>
          </button>
          <button className="k-btn k-btn--ghost" onClick={() => navigate("/")}>
            {t("practice.summary.home")}
          </button>
        </footer>
      </main>
    );
  }

  // ---- SESSION ------------------------------------------------------------
  return (
    <main
      className="k-page story story--audio kp-page"
      style={{ "--font-scale": fontScale } as React.CSSProperties}
    >
      {item && (
        <SentenceView
          storyTitle={t("practice.session.chapterTitle")}
          storyLevel={item.source}
          onExit={() => setPhase("setup")}
          sentence={sentences[practice.currentIndex]}
          index={practice.currentIndex}
          total={total}
          targetLanguage={queue.targetLanguage}
          lemmaIndex={{}}
          wordsById={{}}
          activeWordKey={null}
          onWordTap={() => undefined}
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
          onPrev={practice.goPrev}
          onNext={practice.goNext}
          canPrev={practice.currentIndex > 0}
          canNext={practice.currentIndex < total - 1}
        />
      )}

      {practice.pronError && (
        <div className="k-error story__pron-error" role="alert">
          {t(`pron.error.${practice.pronError.kind}`)}
        </div>
      )}
    </main>
  );
}
