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
 * loadPracticeQueue(). This component is endpoint-agnostic — it renders whatever
 * PracticeItem[] comes back.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { PronunciationReviewIn, RescheduledCard, StorySentence } from "../api/types";
import GenderReviewSession from "../components/GenderReviewSession";
import KlaraMark from "../components/KlaraMark";
import SentenceView from "../components/SentenceView";
import { useFontScale } from "../lib/preferences";
import { focusBand } from "../lib/pronunciation";
import {
  loadPracticeQueue,
  countByReason,
  type PracticeItem,
  type PracticeQueue,
} from "../lib/practiceQueue";
import { humanizeNextReview } from "../lib/srsTime";
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

function tallySummary(
  items: PracticeItem[],
  sentences: StorySentence[],
  scoresBySentence: Record<number, PronScores>,
): { clear: number; mid: number; revisit: number; answered: number } {
  let clear = 0;
  let mid = 0;
  let revisit = 0;
  let answered = 0;
  for (let i = 0; i < items.length; i++) {
    const scores = scoresBySentence[i];
    if (!scores || Object.keys(scores).length === 0) continue;
    const band = focusBand(sentences[i].target, items[i].focusText, scores);
    if (!band) continue;
    answered++;
    if (band === "good") clear++;
    else if (band === "ok") mid++;
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
    loadPracticeQueue()
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

  const [segment, setSegment] = useState<"pronunciation" | "gender" | null>(null);
  const [phase, setPhase] = useState<Phase>("setup");

  type SendState = "idle" | "sending" | "ok" | "failed";
  const [sendState, setSendState] = useState<SendState>("idle");
  const [rescheduled, setRescheduled] = useState<RescheduledCard[]>([]);
  // Se marca al CONFIRMAR éxito (no al disparar): un fallo deja reintentar en vez
  // de perder la reprogramación en silencio (spec §4.4).
  const sessionSubmittedRef = useRef(false);

  // SentenceView consumes StorySentence; map once.
  const sentences = useMemo(() => items.map(toStorySentence), [items]);

  // Per-item persistence targets, indexed identically to `sentences`. An item
  // backed by a REAL story sentence (struggled, or a review resolved from a
  // story breakdown) persists its scored take against that story's ORIGINAL
  // sentence index; an `example_target` fallback review item carries neither
  // storyId nor sentenceIndex → null → not persisted. The index used is the
  // item's own `sentenceIndex` (the story index), NOT its queue position.
  const persistTargets = useMemo(
    () =>
      items.map((it) =>
        // Backend serializes a fallback item's storyId/sentenceIndex as JSON
        // `null` (not omitted), so the guard must catch null AND undefined.
        // `!= null` narrows both away → storyId: string, sentenceIndex: number.
        it.storyId != null && it.sentenceIndex != null
          ? { storyId: it.storyId, sentenceIndex: it.sentenceIndex }
          : null,
      ),
    [items],
  );

  const practice = useSentencePractice({
    sentences,
    targetLanguage: queue?.targetLanguage ?? "de",
    persistTargets,
    onFinish: () => {
      setPhase("summary");
      window.scrollTo({ top: 0 });
    },
    // Keyboard shortcuts only while the session is on screen.
    keyboardEnabled: phase === "session",
  });

  const item = items[practice.currentIndex];

  const submitSession = useCallback(() => {
    const reviews: PronunciationReviewIn[] = [];
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const scores = practice.scoresBySentence[i];
      // Salta items sin carta, simulados, sin score, o con score vacío ({}) — este
      // último pasaría `!scores` pero no es una respuesta real (alineado con
      // tallySummary, que exige Object.keys(scores).length > 0).
      if (
        !it.cardId ||
        !scores ||
        Object.keys(scores).length === 0 ||
        practice.simulatedIndices.has(i)
      )
        continue;
      reviews.push({
        cardId: it.cardId,
        focusText: it.focusText,
        sentenceTarget: sentences[i].target,
        wordBands: scores,
      });
    }
    if (reviews.length === 0) {
      sessionSubmittedRef.current = true;
      setRescheduled([]);
      setSendState("ok");
      return;
    }
    setSendState("sending");
    api
      .submitPronunciationReviews(reviews)
      .then((res) => {
        sessionSubmittedRef.current = true; // marca al confirmar
        setRescheduled(res.rescheduled);
        setSendState("ok");
      })
      .catch(() => {
        // ref sigue en false → el botón "Reintentar" del bloque `failed` del
        // summary re-invoca este mismo submitSession sin duplicar ni rehacer
        // la sesión (spec §4.4: "ofrecer reintento").
        setSendState("failed");
      });
  }, [items, sentences, practice.scoresBySentence, practice.simulatedIndices]);

  useEffect(() => {
    if (phase === "summary" && !sessionSubmittedRef.current && sendState === "idle") {
      submitSession();
    }
  }, [phase, sendState, submitSession]);

  // ---- SEGMENT: gender (reuses the standalone /gender session) -----------
  if (segment === "gender") {
    return (
      <GenderReviewSession onExit={() => setSegment(null)} exitLabel={t("practice.segment.back")} />
    );
  }

  // ---- SEGMENT CHOOSER ---------------------------------------------------
  if (segment === null) {
    return (
      <main className="k-page kp-setup">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("common.back")}
        </button>
        <header className="kp-setup__head">
          <h1 className="kp-setup__title">{t("practice.segment.title")}</h1>
        </header>
        <section className="kp-segments">
          <button className="kp-segment" onClick={() => setSegment("pronunciation")}>
            <span className="kp-segment__title">{t("practice.segment.pron.title")}</span>
            <span className="kp-segment__dek">{t("practice.segment.pron.dek")}</span>
            <span className="kp-segment__arrow k-serif">→</span>
          </button>
          <button className="kp-segment" onClick={() => setSegment("gender")}>
            <span className="kp-segment__title">{t("practice.segment.gender.title")}</span>
            <span className="kp-segment__dek">{t("practice.segment.gender.dek")}</span>
            <span className="kp-segment__arrow k-serif">→</span>
          </button>
        </section>
      </main>
    );
  }

  // segment === "pronunciation" → the existing pronunciation flow (below, unchanged)

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
              sessionSubmittedRef.current = false;
              setSendState("idle");
              setRescheduled([]);
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
          {/* The signature always renders. Single-story queues get the
              quoted title ("de «X»"); the backend blanks sourceTitle for
              mixed-story queues, so we fall back to an explicit, unquoted
              "from several stories" line instead of dropping it. */}
          <span className="k-mono">
            {queue.sourceTitle
              ? t("practice.setup.from", { title: queue.sourceTitle })
              : t("practice.setup.fromMany")}
          </span>
        </div>
      </main>
    );
  }

  // ---- SUMMARY ------------------------------------------------------------
  if (phase === "summary") {
    const { clear, mid, revisit } = tallySummary(items, sentences, practice.scoresBySentence);
    // Glosa local por palabra-foco (reusa focusTx del item; el contrato del backend
    // NO devuelve traducción — spec §4.3 "contrato mínimo").
    const txByFocus: Record<string, string> = {};
    for (const it of items) txByFocus[it.focusText] = it.focusTx;

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

        {sendState === "ok" && rescheduled.length > 0 && (
          <>
            <hr className="k-hairline" />
            <section className="kp-returns">
              <header className="kp-returns__head">
                <span className="k-mono">{t("practice.summary.returns.title")}</span>
                <span className="k-mono kp-returns__count">{rescheduled.length}</span>
              </header>
              <ul className="kp-returns__list">
                {rescheduled.map((r) => (
                  <li key={`${r.focusText}-${r.nextReviewAt}`} className="kp-returns__item">
                    <span className="kp-returns__word">{r.focusText}</span>
                    <span className="kp-returns__tx">{txByFocus[r.focusText] ?? ""}</span>
                    <span className="kp-returns__next k-mono">
                      {humanizeNextReview(r.nextReviewAt)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}

        {/* En fallo NO fabricamos intervalos (spec §4.4): ocultamos la sección de
            próximos repasos y ofrecemos reintentar el MISMO POST. submitSession
            es idempotente desde aquí porque sessionSubmittedRef sigue en false
            (solo se marca al confirmar éxito), así que reintentar no duplica ni
            rehace la sesión — a diferencia de "Otra ronda". */}
        {sendState === "failed" && (
          <>
            <hr className="k-hairline" />
            <div className="kp-send-fail" role="alert">
              <span className="k-mono">{t("practice.summary.send.failed")}</span>
              <button
                className="k-btn k-btn--ghost"
                onClick={() => submitSession()}
              >
                {t("practice.summary.send.retry")}
              </button>
            </div>
          </>
        )}

        <footer className="kp-sum__cta">
          <button
            className="k-btn"
            onClick={() => {
              sessionSubmittedRef.current = false;
              setSendState("idle");
              setRescheduled([]);
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
          diagnosis={practice.diagnosis}
          diagnosing={practice.diagnosing}
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
