/**
 * Teleprompter de Estudiar — vocabulario k-* (spec F2 §5.1).
 *
 * La oración es la protagonista; debajo, un `.k-dock` con su línea de
 * estado (quién actúa: Klara lee / te escucho / evaluando) y cuatro
 * botones redondos (← · play · mic · →). El feedback de pronunciación y
 * los errores de captura ocupan el mismo slot inferior (`.k-band`) en
 * sustitución del dock.
 *
 * Vive aparte de SentenceView (legacy) porque Practice comparte aquel
 * archivo y su segmento de pronunciación está fuera del alcance de F2.1;
 * el legacy muere cuando Practice se re-vista.
 *
 * Se conservan del legacy: tokenize/matchToken/buildBreakdownMap y la
 * derivación de señal por token (scoreByTokenIdx), el veredicto
 * (verdictKey) y la pista de la palabra floja (badWordTip). Caen del skin
 * (siguen vivos en el hook/teclado): waveform + tiempos, pill de barras,
 * panel de score /100 + leyenda de conteos, "Escuchar a Klara" del
 * feedback y los hints de teclado visibles.
 */

import { useMemo, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import type { StorySentence, StoryWord, WordBreakdown } from "../api/types";
import { dockStatus } from "../lib/estadoDock";
import type { PronunciationError, ScoreBand } from "../lib/pronunciation";
import type { MicLevel } from "../lib/silenceDetector";
import SessTop from "./SessTop";

interface Props {
  // Chapter context
  storyTitle: string;
  onExit: () => void;

  // Sentence content
  sentence: StorySentence;
  index: number;
  total: number;
  targetLanguage: string;

  // Word interaction (taps → translation popover, owned by parent)
  lemmaIndex: Record<string, string>;
  wordsById: Record<string, StoryWord>;
  activeWordKey: string | null;
  onWordTap: (word: StoryWord, key: string, el: HTMLElement) => void;
  /**
   * Tap handler for non-target words that came back in the sentence's
   * breakdown. Optional so historical stories without breakdowns keep
   * working — those words just stay non-clickable like before.
   */
  onBreakdownTap?: (entry: WordBreakdown, key: string, el: HTMLElement) => void;

  // Playback state
  playing: boolean;

  // Recording state
  recording: boolean;
  micLevel: MicLevel;

  // Evaluating state — between mic release and feedback arrival.
  evaluating: boolean;

  // Feedback state
  feedback?: Record<number, ScoreBand>;
  /** Live streaming bands while recording — same shape/classes as feedback. */
  liveBands?: Record<number, ScoreBand>;
  phoneticHints?: Record<string, string>;
  diagnosis?: { word: string; tip: string };
  /** Explicit loading signal from the hook: /diagnose is in-flight for this sentence. */
  diagnosing: boolean;

  // Speed
  rate: number;

  // Capture/scoring error (mic denied, no speech, service down…)
  pronError: PronunciationError | null;

  // Font scale for the sentence (user preference × automatic step).
  fscale: number;

  // Actions
  onPlayPause: () => void;
  onCycleSpeed: () => void;
  onRecordStart: () => void;
  onRecordStop: () => void;
  onRetry: () => void;
  onErrorDismiss: () => void;
  onPrev: () => void;
  onNext: () => void;
}

interface Tok {
  type: "word" | "space" | "punct";
  text: string;
}

const PUNCT_RE = /[.,!?;:„“”»«()¡¿—–\-]/g;

function tokenize(text: string): Tok[] {
  const re = /(\s+)|([.,!?;:„“”»«()¡¿—–\-]+)|([^\s.,!?;:„“”»«()¡¿—–\-]+)/g;
  const out: Tok[] = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
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
    if (clean === lemma || clean.includes(lemma) || lemma.includes(clean)) {
      return lemmaIndex[lemma];
    }
  }
  return null;
}

/**
 * Map a sentence's breakdown into a per-word lookup. Multi-word entries
 * (e.g. "por favor") get registered under each constituent so single-word
 * tokens still resolve to the same multi-word translation. Trade-off: a
 * tap on "por" vs "favor" both show the same popover. v1 limitation —
 * proper multi-token grouping is a follow-up.
 */
function buildBreakdownMap(
  breakdown: WordBreakdown[] | null | undefined,
): Map<string, WordBreakdown> | null {
  if (!breakdown || breakdown.length === 0) return null;
  const map = new Map<string, WordBreakdown>();
  for (const entry of breakdown) {
    const parts = entry.word.split(/\s+/);
    for (const part of parts) {
      const key = part.replace(PUNCT_RE, "").toLowerCase();
      if (!key) continue;
      // First entry wins — preserves the LLM's intended grouping when
      // the same word appears in multiple breakdown entries.
      if (!map.has(key)) map.set(key, entry);
    }
  }
  return map;
}

const pad2 = (n: number) => String(n).padStart(2, "0");

// Iconos de trazo 1.5 del átomo 2 (hoja.html §02). El tamaño lo pone
// `.k-rbtn svg`, por eso no llevan width/height.
function IcPlay() {
  return (
    <svg data-icon="play" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 5.4 19 12 8 18.6Z" />
    </svg>
  );
}
function IcPause() {
  return (
    <svg data-icon="pause" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <path d="M9.5 5.5v13M14.5 5.5v13" />
    </svg>
  );
}
function IcMic() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3.5a2.75 2.75 0 0 1 2.75 2.75v5.25a2.75 2.75 0 0 1-5.5 0V6.25A2.75 2.75 0 0 1 12 3.5Z" />
      <path d="M5.75 11.25v.5a6.25 6.25 0 0 0 12.5 0v-.5" />
      <path d="M12 18v2.5" />
    </svg>
  );
}
function IcPrev() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14.5 5.5 8 12l6.5 6.5" />
    </svg>
  );
}
function IcNext() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9.5 5.5 16 12l-6.5 6.5" />
    </svg>
  );
}

export default function EstudiarView({
  storyTitle,
  onExit,
  sentence,
  index,
  total,
  targetLanguage,
  lemmaIndex,
  wordsById,
  activeWordKey,
  onWordTap,
  onBreakdownTap,
  playing,
  recording,
  micLevel,
  evaluating,
  feedback,
  liveBands,
  phoneticHints,
  diagnosis,
  diagnosing,
  rate,
  pronError,
  fscale,
  onPlayPause,
  onCycleSpeed,
  onRecordStart,
  onRecordStop,
  onRetry,
  onErrorDismiss,
  onPrev,
  onNext,
}: Props): JSX.Element {
  const { t } = useTranslation();

  const tokens = useMemo(() => tokenize(sentence.target), [sentence.target]);
  const breakdownMap = useMemo(
    () => buildBreakdownMap(sentence.breakdown),
    [sentence.breakdown],
  );
  const showFeedback = Boolean(feedback) && !recording && !evaluating;

  // ---- Per-word score → underline class -----------------------------------
  // Map token index (in `tokens`) → ScoreBand, using the existing
  // wordTokenIndices contract: each WORD-type token gets sequentially mapped
  // to feedback[i], skipping spaces/punct.
  const scoreByTokenIdx = useMemo(() => {
    if (showFeedback && feedback) return feedback;
    if (recording && liveBands) return liveBands;
    return null;
  }, [feedback, showFeedback, recording, liveBands]);

  // Verdict picked by mean score (roughly: good=100, ok=70, bad=40)
  const verdictKey = useMemo(() => {
    if (!feedback) return null;
    const vals = Object.values(feedback);
    if (vals.length === 0) return null;
    const map = { good: 100, ok: 70, bad: 40 } as const;
    const avg = vals.reduce((s, v) => s + map[v], 0) / vals.length;
    if (avg >= 90) return "excellent";
    if (avg >= 80) return "good";
    if (avg >= 60) return "close";
    return "retry";
  }, [feedback]);

  // ---- Bad-word tip: stress hint + optional corrective diagnose ------------
  const badWordTip = useMemo(() => {
    if (!feedback) return null;
    // Focus the diagnosed worst word when we have it; else the first bad word.
    let focus: string | null = diagnosis?.word ?? null;
    if (focus === null) {
      for (let i = 0; i < tokens.length; i++) {
        const tok = tokens[i];
        if (tok.type === "word" && feedback[i] === "bad") {
          focus = tok.text;
          break;
        }
      }
    }
    if (focus === null) return null;
    const tip = diagnosis && diagnosis.word === focus ? diagnosis.tip : null;
    // Case-insensitive hint lookup: try exact key first, then fall back to a
    // lowercase match. Azure's WordScore.word casing may differ from the
    // sentence-token spelling that phonetic_hints.py uses as its key.
    const hint = phoneticHints
      ? (phoneticHints[focus] ??
          Object.entries(phoneticHints).find(
            ([k]) => k.toLowerCase() === focus!.toLowerCase(),
          )?.[1] ??
          null)
      : null;
    return { word: focus, hint, tip };
  }, [feedback, phoneticHints, tokens, diagnosis]);

  // ---- Dock status line (.k-dock__status) ----------------------------------
  const status = dockStatus({ playing, recording, evaluating, micLevel, rate });
  const nivelKey = (nivel: MicLevel) =>
    nivel === "quiet" ? "story.sentence.micLevel.quiet"
    : nivel === "loud" ? "story.sentence.micLevel.loud"
    : "estudiar.estadoK.teEscucho";

  // ---- Mic button (tap-to-toggle) ------------------------------------------
  // The button is tap-to-toggle: one tap starts recording, another stops.
  // Hold-to-talk lives on the M key (handled inside the hook).
  const onMicClick = () => {
    if (recording) void onRecordStop();
    else void onRecordStart();
  };

  return (
    <>
      <SessTop titulo={storyTitle} right={`${pad2(index + 1)}/${pad2(total)}`} onExit={onExit} />
      <div className="k-bar k-bar--segs">
        <div
          className="k-bar__track"
          role="progressbar"
          aria-valuenow={index + 1}
          aria-valuemin={0}
          aria-valuemax={total}
        >
          {Array.from({ length: total }, (_, i) => (
            <span
              key={i}
              className="k-bar__seg"
              data-state={i < index ? "done" : i === index ? "now" : undefined}
            />
          ))}
        </div>
      </div>
      <div className="k-fill">
        {/* Sentence (target language). Feedback bands are keyed by full token
            index (including spaces/punct), matching what bandsByTokenIndex
            returns from pronunciation.ts. `key={index}` re-triggers the
            page-in animation on every sentence change. */}
        <p className="k-stage" lang={targetLanguage} key={index} style={{ "--fscale": fscale } as CSSProperties}>
          {tokens.map((tok, i) => {
            if (tok.type !== "word") return <span key={i}>{tok.text}</span>;
            const wordId = matchToken(tok.text, lemmaIndex);
            const breakdownEntry =
              breakdownMap && !wordId
                ? breakdownMap.get(tok.text.replace(PUNCT_RE, "").toLowerCase()) ?? null
                : null;
            const band = scoreByTokenIdx?.[i];
            const key = `${index}-${i}`;
            const clickable = Boolean(wordId) || Boolean(breakdownEntry && onBreakdownTap);
            if (!clickable)
              return <span key={i} data-score={band}>{tok.text}</span>;
            return (
              <button
                key={i}
                type="button"
                className="k-word"
                data-score={band}
                data-active={activeWordKey === key ? "true" : undefined}
                onClick={(e) => {
                  if (wordId) onWordTap(wordsById[wordId], key, e.currentTarget);
                  else if (breakdownEntry && onBreakdownTap)
                    onBreakdownTap(breakdownEntry, key, e.currentTarget);
                }}
              >
                {tok.text}
              </button>
            );
          })}
        </p>

        {/* Translation (native language) */}
        <p className="k-note k-note--mono" key={`g${index}`}>{sentence.native}</p>
      </div>

      {pronError || showFeedback ? (
        <div className="k-band">
          {pronError ? (
            <>
              <p className="k-error" role="alert">{t(`pron.error.${pronError.kind}`)}</p>
              <div className="k-wrap">
                <button type="button" className="k-btn k-btn--ghost k-btn--block" onClick={onErrorDismiss}>
                  {t("story.sentence.feedback.retry")}
                </button>
                <button type="button" className="k-btn k-btn--block" onClick={onNext}>
                  {t("story.step.next")} <span className="k-btn__arrow" aria-hidden="true">→</span>
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="k-note" role="status">
                {verdictKey && t(`story.sentence.verdict.${verdictKey}`)}
                {badWordTip && (
                  <>
                    {" "}
                    {t("story.sentence.feedback.tipPrefix")}{" "}
                    <span className="k-note__right">{badWordTip.hint ?? badWordTip.word}</span>.
                  </>
                )}
                {badWordTip?.tip && <> {badWordTip.tip}</>}
                {diagnosing && !badWordTip?.tip && (
                  <> {t("story.sentence.feedback.diagnosing")}</>
                )}
              </p>
              <div className="k-wrap">
                <button type="button" className="k-btn k-btn--ghost k-btn--block" onClick={onRetry}>
                  {t("story.sentence.feedback.retry")}
                </button>
                <button type="button" className="k-btn k-btn--block" onClick={onNext}>
                  {t("story.step.next")} <span className="k-btn__arrow" aria-hidden="true">→</span>
                </button>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="k-dock">
          <div className="k-dock__status">
            <p className="k-cap k-cap--center">
              {status?.kind === "escuchando" && (
                <span className="k-cap__count" data-tone="live" role="status">
                  <span aria-hidden="true">● </span>
                  {t(nivelKey(status.nivel))}
                </span>
              )}
              {status?.kind === "evaluando" && (
                <span role="status">{t("estudiar.estadoK.evaluando")}</span>
              )}
              {status?.kind === "leyendo" && (
                <button
                  type="button"
                  className="k-btn k-btn--text"
                  onClick={onCycleSpeed}
                  aria-label={t("story.sentence.speedAria", { rate })}
                >
                  {t(status.despacio ? "estudiar.estadoK.leeDespacio" : "estudiar.estadoK.lee")}
                </button>
              )}
            </p>
          </div>
          <div className="k-dock__row">
            <button
              type="button"
              className="k-rbtn k-rbtn--sm"
              aria-label={t("story.step.prev")}
              disabled={index === 0}
              onClick={onPrev}
            >
              <IcPrev />
            </button>
            <button
              type="button"
              className="k-rbtn k-rbtn--ink k-rbtn--lg"
              data-state={playing ? "playing" : undefined}
              aria-label={playing ? t("story.sentence.pauseAria") : t("story.sentence.playAria")}
              onClick={onPlayPause}
            >
              <IcPlay />
              <IcPause />
            </button>
            <button
              type="button"
              className="k-rbtn k-rbtn--rec k-rbtn--md"
              data-on={recording ? "true" : "false"}
              aria-pressed={recording}
              aria-label={
                recording ? t("story.sentence.micAriaRecording") : t("story.sentence.micAria")
              }
              onClick={onMicClick}
            >
              <IcMic />
              <span className="k-rbtn__ring" aria-hidden="true"></span>
            </button>
            <button
              type="button"
              className="k-rbtn k-rbtn--sm"
              aria-label={index < total - 1 ? t("story.step.next") : t("story.step.finish")}
              onClick={onNext}
            >
              <IcNext />
            </button>
          </div>
        </div>
      )}
    </>
  );
}
