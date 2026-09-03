/**
 * Pronunciar — la práctica de pronunciación, vocabulario k-*.
 *
 * Superficie de sesión propia, como `/estudiar/:id` y `/repaso`: cuelga
 * fuera de LegacyShell y pinta su propio `.k-app`. Antes era el segmento
 * «pronunciación» de Práctica dentro del cascarón viejo, y el armazón de
 * sesión (`.k-app` a 100dvh) no se puede anidar dentro de `.kframe`.
 *
 * Las tres fases del flujo viven aquí porque comparten el estado que las
 * une: la cola, el hook de práctica y el envío de la ronda. La sesión ya
 * no tiene skin propio — es el mismo `<EstudiarView>` de la lectura, que
 * consume el mismo `useSentencePractice`. Con eso muere SentenceView.
 *
 * Práctica (/review) se queda con el selector de segmento y navega aquí,
 * igual que ya navegaba a /repaso.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { PronunciationReviewIn, RescheduledCard, StorySentence } from "../api/types";
import EstudiarView from "../components/EstudiarView";
import SessTop from "../components/SessTop";
import { autoFscaleStep } from "../lib/autoFscale";
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

const pad2 = (n: number) => String(n).padStart(2, "0");

// Adapt a PracticeItem's origin sentence to the StorySentence shape
// EstudiarView consumes. Practice items carry no per-word breakdown, so taps
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

export default function Pronunciar(): JSX.Element | null {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [fontScale] = useFontScale();

  // Igual que Story y Repaso: quien entra pasa { state: { from } } y la
  // salida vuelve ahí.
  const exitTo = (location.state as { from?: string } | null)?.from ?? "/";
  const salir = useCallback(() => navigate(exitTo), [navigate, exitTo]);

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

  const items = useMemo(() => queue?.items ?? [], [queue]);
  const total = items.length;
  const struggledN = useMemo(() => countByReason(items, "struggled"), [items]);
  const reviewN = total - struggledN;

  const [phase, setPhase] = useState<Phase>("setup");

  type SendState = "idle" | "sending" | "ok" | "failed";
  const [sendState, setSendState] = useState<SendState>("idle");
  const [rescheduled, setRescheduled] = useState<RescheduledCard[]>([]);
  // Se marca al CONFIRMAR éxito (no al disparar): un fallo deja reintentar en vez
  // de perder la reprogramación en silencio (spec §4.4).
  const sessionSubmittedRef = useRef(false);

  // EstudiarView consumes StorySentence; map once.
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
    onFinish: () => setPhase("summary"),
    // Keyboard shortcuts only while the session is on screen.
    keyboardEnabled: phase === "session",
  });

  const current = sentences[practice.currentIndex];
  // El mismo paso automático de tamaño que la lectura (spec F2 §5.1).
  const fscale = useMemo(
    () => (current ? fontScale * autoFscaleStep(current.target, fontScale) : fontScale),
    [current, fontScale],
  );

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
        // ref sigue en false → el botón «Reintentar» del bloque `failed` del
        // resumen re-invoca este mismo submitSession sin duplicar ni rehacer
        // la sesión (spec §4.4: "ofrecer reintento").
        setSendState("failed");
      });
  }, [items, sentences, practice.scoresBySentence, practice.simulatedIndices]);

  useEffect(() => {
    if (phase === "summary" && !sessionSubmittedRef.current && sendState === "idle") {
      submitSession();
    }
  }, [phase, sendState, submitSession]);

  const titulo = t("practice.segment.pron.title");

  // ---- CARGA / FALLO / VACÍO ---------------------------------------------
  if (phase === "setup" && (queue === null || loadFailed || total === 0)) {
    return (
      <div className="k-app">
        <SessTop titulo={titulo} right="" onExit={salir} />
        <div className="k-fill">
          {queue === null && !loadFailed ? (
            <span className="k-spinner" role="status" aria-label={t("practice.loading.wait")} />
          ) : loadFailed ? (
            <p className="k-error" role="alert">{t("practice.loading.error")}</p>
          ) : (
            <p className="k-note">{t("practice.loading.empty")}</p>
          )}
        </div>
        {queue !== null || loadFailed ? (
          <div className="k-dock">
            <div className="k-wrap">
              <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={salir}>
                {t("practice.summary.home")}
              </button>
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  // Past this point the queue is loaded and non-empty (guarded above). The
  // explicit null check narrows the type for the render branches below.
  if (queue === null) return null;

  // ---- SETUP --------------------------------------------------------------
  if (phase === "setup") {
    return (
      <div className="k-app">
        <SessTop titulo={titulo} right={pad2(total)} onExit={salir} />
        <div className="k-fill">
          <header className="k-hero k-hero--quiet">
            <span className="k-hero__tag">{t("practice.setup.kicker")}</span>
            <h1 className="k-hero__title">{t("practice.setup.title", { count: total })}</h1>
            <p className="k-hero__dek">{t("practice.setup.dek")}</p>
            <p className="k-hero__meta">
              <strong>{struggledN}</strong> {t("practice.setup.struggled")}
              <span aria-hidden="true">·</span>
              <strong>{reviewN}</strong> {t("practice.setup.review")}
            </p>
          </header>
          {/* Los tres rótulos no filtran nada (nunca lo hicieron: son texto,
              no controles), así que van de chip quieto. */}
          <p className="k-cap">{t("practice.setup.startBy")}</p>
          <div className="k-wrap">
            <span className="k-chip k-chip--static" data-selected="true">
              {t("practice.setup.chip.all", { count: total })}
            </span>
            <span className="k-chip k-chip--static">
              {t("practice.setup.chip.hard", { count: struggledN })}
            </span>
            <span className="k-chip k-chip--static">
              {t("practice.setup.chip.review", { count: reviewN })}
            </span>
          </div>
        </div>
        <div className="k-dock">
          <div className="k-wrap">
            <button
              type="button"
              className="k-btn k-btn--lg k-btn--block"
              onClick={() => {
                sessionSubmittedRef.current = false;
                setSendState("idle");
                setRescheduled([]);
                practice.reset();
                setPhase("session");
              }}
            >
              {t("practice.setup.start")}{" "}
              <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          </div>
          {/* La firma: de dónde salieron estas frases. El backend deja
              sourceTitle en blanco para colas de varias historias. */}
          <p className="k-note k-note--bare">
            {queue.sourceTitle
              ? t("practice.setup.from", { title: queue.sourceTitle })
              : t("practice.setup.fromMany")}
          </p>
        </div>
      </div>
    );
  }

  // ---- RESUMEN ------------------------------------------------------------
  if (phase === "summary") {
    const { clear, mid, revisit } = tallySummary(items, sentences, practice.scoresBySentence);
    // Glosa local por palabra-foco (reusa focusTx del item; el contrato del backend
    // NO devuelve traducción — spec §4.3 "contrato mínimo").
    const txByFocus: Record<string, string> = {};
    for (const it of items) txByFocus[it.focusText] = it.focusTx;

    return (
      <div className="k-app">
        <SessTop titulo={titulo} right="" onExit={salir} />
        <div className="k-fill">
          <header className="k-hero k-hero--quiet">
            <span className="k-hero__tag">{t("practice.summary.kicker")}</span>
            <h1 className="k-hero__title">{t("practice.summary.title", { count: total })}</h1>
            <p className="k-hero__dek">{t("practice.summary.dek")}</p>
            <p className="k-hero__meta">
              <strong>{clear}</strong> {t("practice.summary.stat.clear")}
              <span aria-hidden="true">·</span>
              <strong>{mid}</strong> {t("practice.summary.stat.ok")}
              <span aria-hidden="true">·</span>
              <strong>{revisit}</strong> {t("practice.summary.stat.bad")}
            </p>
          </header>

          {sendState === "ok" && rescheduled.length > 0 && (
            <>
              <p className="k-cap">
                {t("practice.summary.returns.title")}
                <span className="k-cap__count">{rescheduled.length}</span>
              </p>
              {/* La lista crece con la ronda; el cascarón no scrollea, así que
                  scrollea ella (gramática 12). */}
              <div className="k-live">
                <ul>
                  {rescheduled.map((r) => (
                    <li key={`${r.focusText}-${r.nextReviewAt}`} className="k-row k-row--quiet">
                      <span className="k-row__title">{r.focusText}</span>
                      <span className="k-row__meta">{humanizeNextReview(r.nextReviewAt)}</span>
                      {txByFocus[r.focusText] && (
                        <span className="k-row__sub">{txByFocus[r.focusText]}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}

          {/* En fallo NO fabricamos intervalos (spec §4.4): ocultamos la sección de
              próximos repasos y ofrecemos reintentar el MISMO POST. submitSession
              es idempotente desde aquí porque sessionSubmittedRef sigue en false
              (solo se marca al confirmar éxito), así que reintentar no duplica ni
              rehace la sesión — a diferencia de «Otra ronda». */}
          {sendState === "failed" && (
            <>
              <p className="k-error" role="alert">{t("practice.summary.send.failed")}</p>
              <div className="k-wrap">
                <button type="button" className="k-btn k-btn--ghost" onClick={() => submitSession()}>
                  {t("practice.summary.send.retry")}
                </button>
              </div>
            </>
          )}
        </div>
        <div className="k-dock">
          <div className="k-wrap">
            <button
              type="button"
              className="k-btn k-btn--ghost k-btn--block"
              onClick={() => {
                sessionSubmittedRef.current = false;
                setSendState("idle");
                setRescheduled([]);
                practice.reset();
                setPhase("setup");
              }}
            >
              {t("practice.summary.again")}
            </button>
            <button type="button" className="k-btn k-btn--block" onClick={() => navigate("/")}>
              {t("practice.summary.home")}{" "}
              <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---- SESIÓN -------------------------------------------------------------
  return (
    <div className="k-app">
      {current && (
        <EstudiarView
          storyTitle={titulo}
          onExit={() => setPhase("setup")}
          sentence={current}
          index={practice.currentIndex}
          total={total}
          targetLanguage={queue.targetLanguage}
          lemmaIndex={{}}
          wordsById={{}}
          activeWordKey={null}
          onWordTap={() => undefined}
          playing={practice.sentencePlaying}
          recording={practice.recording}
          micLevel={practice.micLevel}
          evaluating={practice.evaluating}
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
          onPrev={practice.goPrev}
          onNext={practice.goNext}
        />
      )}
    </div>
  );
}
