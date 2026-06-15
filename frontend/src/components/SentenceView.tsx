/**
 * Audio-centric sentence view.
 *
 * Replaces the wireframe-era SentenceStep (three action cards on the right
 * over a half-empty column). The sentence is the protagonist; below it sits
 * a waveform with a playhead, and below that, a horizontal toolbar with
 * speed · play · pronounce. Four mutually exclusive states share the slot
 * under the waveform:
 *
 *   idle      → toolbar visible + kbd hint
 *   playing   → toolbar (play → pause), playhead animates, bars light up
 *   recording → bermellón pill with 16 live-RMS bars + Detener
 *   feedback  → score panel + per-word underlines on the sentence
 *
 * State derived from props — no internal mode machine; the parent (Story)
 * owns audio, recording, scoring, and navigation.
 */

import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import type { StorySentence, StoryWord, WordBreakdown } from "../api/types";
import { startAudioBars } from "../lib/audioBars";
import type { ScoreBand } from "../lib/pronunciation";
import { getWaveform } from "../lib/waveform";

type SentenceState = "idle" | "playing" | "recording" | "evaluating" | "feedback";

interface Props {
  // Chapter context
  storyTitle: string;
  storyLevel: string;
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
  progress: number; // 0..1
  duration: number; // seconds; 0 while unknown

  // Recording state
  recording: boolean;
  micAnalyser: AnalyserNode | null;

  // Evaluating state — between mic release and feedback arrival. Shows a
  // spinner pill in the same slot as the recording pill so the user has a
  // continuous visual thread: pill (recording) → pill (evaluating) → panel
  // (feedback), instead of pill → idle → panel.
  evaluating: boolean;

  // Feedback state
  feedback?: Record<number, ScoreBand>;
  phoneticHints?: Record<string, string>;

  // Speed
  rate: number;

  // Actions
  onPlayPause: () => void;
  onCycleSpeed: () => void;
  onRecordStart: () => void;
  onRecordStop: () => void;
  onRetry: () => void;
  onListenFromFeedback: () => void;
  onPrev: () => void;
  onNext: () => void;
  canPrev: boolean;
  canNext: boolean;
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

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const total = Math.floor(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function deriveState(args: {
  recording: boolean;
  evaluating: boolean;
  feedback: boolean;
  playing: boolean;
}): SentenceState {
  // Order matters: recording beats everything (user is mid-take); evaluating
  // beats feedback (a fresh take is being scored even if a previous panel
  // was up); feedback beats playing (the panel takes the slot back from
  // the toolbar); playing beats idle.
  if (args.recording) return "recording";
  if (args.evaluating) return "evaluating";
  if (args.feedback) return "feedback";
  if (args.playing) return "playing";
  return "idle";
}

const FALLBACK_BARS: number[] = Array.from({ length: 64 }, (_, i) => {
  // Same deterministic seno + noise generator the handoff's index.html used,
  // so the visual stays consistent when no audio has loaded yet.
  const x = i / 63;
  const env = Math.max(0, Math.sin(Math.PI * Math.min(1, Math.max(0, (x - 0.06) / 0.78))));
  const n = (Math.sin(i * 1.7) + 1) / 2;
  return Math.max(0.12, env * 0.65 + n * 0.35);
});

export default function SentenceView({
  storyTitle,
  storyLevel,
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
  progress,
  duration,
  recording,
  micAnalyser,
  evaluating,
  feedback,
  phoneticHints,
  rate,
  onPlayPause,
  onCycleSpeed,
  onRecordStart,
  onRecordStop,
  onRetry,
  onListenFromFeedback,
  onPrev,
  onNext,
  canPrev,
  canNext,
}: Props): JSX.Element {
  const { t } = useTranslation();

  const tokens = useMemo(() => tokenize(sentence.target), [sentence.target]);
  const breakdownMap = useMemo(
    () => buildBreakdownMap(sentence.breakdown),
    [sentence.breakdown],
  );
  const showFeedback = Boolean(feedback) && !recording && !evaluating;
  const state = deriveState({
    recording,
    evaluating: evaluating && !recording,
    feedback: showFeedback,
    playing,
  });

  // ---- Waveform (Klara's voice, 64 buckets) -------------------------------
  const [bars, setBars] = useState<number[]>(FALLBACK_BARS);

  useEffect(() => {
    let cancelled = false;
    setBars(FALLBACK_BARS);
    getWaveform(sentence.target, targetLanguage)
      .then((data) => {
        if (!cancelled) setBars(data);
      })
      .catch(() => {
        // Network or decode failure — keep the placeholder. Bars are
        // decorative; this is not user-facing.
      });
    return () => {
      cancelled = true;
    };
  }, [sentence.target, targetLanguage]);

  // ---- Recording bars (live RMS) ------------------------------------------
  const recBarsRef = useRef<HTMLSpanElement[]>([]);
  useEffect(() => {
    if (!recording || !micAnalyser) return;
    return startAudioBars(micAnalyser, recBarsRef.current);
  }, [recording, micAnalyser]);

  // ---- Per-word score → underline class -----------------------------------
  // Map token index (in `tokens`) → ScoreBand, using the existing
  // wordTokenIndices contract: each WORD-type token gets sequentially mapped
  // to feedback[i], skipping spaces/punct.
  const scoreByTokenIdx = useMemo(() => {
    if (!showFeedback || !feedback) return null;
    return feedback;
  }, [feedback, showFeedback]);

  // Counts for the feedback legend
  const counts = useMemo(() => {
    if (!feedback) return { good: 0, ok: 0, bad: 0 };
    const c = { good: 0, ok: 0, bad: 0 };
    for (const v of Object.values(feedback)) c[v]++;
    return c;
  }, [feedback]);

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

  const score = useMemo(() => {
    if (!feedback) return null;
    const vals = Object.values(feedback);
    if (vals.length === 0) return null;
    const map = { good: 100, ok: 70, bad: 40 } as const;
    return Math.round(vals.reduce((s, v) => s + map[v], 0) / vals.length);
  }, [feedback]);

  // ---- Bad-word tip with optional phonetic hint ---------------------------
  // Show ONE bad word, with the LLM-generated stress hint if we have it.
  const badWordTip = useMemo(() => {
    if (!feedback) return null;
    // Walk tokens in order to pick the FIRST bad word. Feedback is keyed by
    // full token index (matches bandsByTokenIndex).
    for (let i = 0; i < tokens.length; i++) {
      const tok = tokens[i];
      if (tok.type !== "word") continue;
      if (feedback[i] === "bad") {
        const hint = phoneticHints?.[tok.text];
        return { word: tok.text, hint: hint ?? null };
      }
    }
    // No "bad" word? Don't show a tip — verdict alone is fine.
    return null;
  }, [feedback, phoneticHints, tokens]);

  // ---- Playhead position --------------------------------------------------
  const playheadStyle: CSSProperties = useMemo(() => {
    const pct = Math.max(0, Math.min(1, progress));
    return { left: `${(pct * 100).toFixed(2)}%` };
  }, [progress]);

  const activeBarIdx = Math.floor(progress * bars.length);
  const currentTimeLabel = formatTime((duration || 0) * progress);
  const totalTimeLabel = formatTime(duration || 0);

  // ---- Mic button (tap-to-toggle) ----------------------------------------
  // The button is tap-to-toggle: one tap starts recording, another stops.
  // Hold-to-talk lives on the M key (handled in Story.tsx) — using
  // hold-to-talk on the button was fragile (pointer drift off the button
  // cancelled the take). The pill's ⏹ Detener button is an additional
  // stop affordance during recording.
  const onMicClick = () => {
    if (recording) onRecordStop();
    else onRecordStart();
  };

  // ---- Speed pill display label -------------------------------------------
  const rateLabel = `${rate}×`;

  return (
    <section className="ksentence" data-state={state}>
      {/* Chapter bar */}
      <div className="k-chapter">
        <button type="button" className="k-chapter__exit" onClick={onExit}>
          {t("common.exit")}
        </button>
        <div className="k-chapter__title">
          <span className="k-chapter__k">K</span>
          <span className="k-chapter__name">{storyTitle}</span>
        </div>
        <span className="k-chapter__level">● {storyLevel}</span>
      </div>

      {/* Progress */}
      <div className="k-prog">
        <span className="k-prog__count">
          {String(index + 1).padStart(2, "0")}{" "}
          <span className="k-prog__slash">/</span> {String(total).padStart(2, "0")}
        </span>
        <div className="k-prog__track">
          {Array.from({ length: total }).map((_, i) => (
            <span
              key={i}
              className="k-prog__pip"
              data-state={i < index ? "done" : i === index ? "now" : "next"}
            />
          ))}
        </div>
      </div>

      {/* Audio-centric stage */}
      <div className="k-stage">
        {/* Sentence (target language). Feedback bands are keyed by full token
            index (including spaces/punct), matching what bandsByTokenIndex
            returns from pronunciation.ts. */}
        <p className="k-stage__de">
          {tokens.map((tok, i) => {
            if (tok.type === "space") {
              return (
                <span key={i} className="k-tok-space">
                  {tok.text}
                </span>
              );
            }
            if (tok.type === "punct") {
              return (
                <span key={i} className="k-tok-punct">
                  {tok.text}
                </span>
              );
            }
            const wordId = matchToken(tok.text, lemmaIndex);
            const breakdownEntry =
              breakdownMap && !wordId
                ? breakdownMap.get(tok.text.replace(PUNCT_RE, "").toLowerCase()) ?? null
                : null;
            const score = scoreByTokenIdx?.[i];
            const key = `${index}-${i}`;
            const isActive = activeWordKey === key;
            const onClick = wordId
              ? (e: React.MouseEvent<HTMLButtonElement>) =>
                  onWordTap(wordsById[wordId], key, e.currentTarget)
              : breakdownEntry && onBreakdownTap
                ? (e: React.MouseEvent<HTMLButtonElement>) =>
                    onBreakdownTap(breakdownEntry, key, e.currentTarget)
                : undefined;
            const clickable = Boolean(wordId) || Boolean(breakdownEntry && onBreakdownTap);
            return (
              <button
                key={i}
                type="button"
                className="k-tok"
                data-active={isActive ? "true" : undefined}
                data-score={score}
                data-matched={Boolean(wordId)}
                data-breakdown={breakdownEntry ? "true" : undefined}
                onClick={onClick}
                disabled={!clickable}
              >
                {tok.text}
              </button>
            );
          })}
        </p>

        {/* Translation (native language) */}
        <p className="k-stage__es">{sentence.native}</p>

        {/* Waveform timeline */}
        <div className="k-wave" aria-hidden="true">
          <div className="k-wave__bars">
            {bars.map((h, i) => (
              <span
                key={i}
                className="k-wave__bar"
                data-active={i <= activeBarIdx ? "true" : undefined}
                style={{ height: `${Math.round(h * 100)}%` }}
              />
            ))}
            <span className="k-wave__playhead" style={playheadStyle} />
          </div>
          <div className="k-wave__foot">
            <span className="k-wave__time">{currentTimeLabel}</span>
            <span className="k-wave__time">{totalTimeLabel}</span>
          </div>
        </div>

        {/* Toolbar — idle / playing */}
        <div className="k-toolbar" data-show="idle playing">
          <button
            type="button"
            className="k-tool k-tool--speed"
            onClick={onCycleSpeed}
            aria-label={t("story.sentence.speedAria", { rate: rateLabel })}
          >
            <span className="k-tri" />
            <span className="k-tool__lbl">{rateLabel}</span>
          </button>
          <button
            type="button"
            className="k-tool k-tool--play"
            onClick={onPlayPause}
            aria-label={
              playing ? t("story.sentence.pauseAria") : t("story.sentence.playAria")
            }
          >
            <span className="k-tri k-tri--lg" data-icon="play" />
            <span className="k-pause" data-icon="pause" />
          </button>
          <button
            type="button"
            className="k-tool k-tool--mic"
            onClick={onMicClick}
            aria-label={
              recording
                ? t("story.sentence.micAriaRecording")
                : t("story.sentence.micAria")
            }
          >
            <span className="k-mic" />
            <span className="k-tool__lbl">{t("story.step.pronounce")}</span>
          </button>
        </div>

        {/* Recording pill */}
        <div className="k-rec" data-show="recording">
          <span className="k-rec__dot" />
          <span className="k-rec__bars" aria-hidden="true">
            {Array.from({ length: 16 }).map((_, i) => (
              <span
                key={i}
                className="k-rec__bar"
                ref={(el) => {
                  if (el) recBarsRef.current[i] = el;
                }}
                style={{ height: "30%" }}
              />
            ))}
          </span>
          <span className="k-rec__lbl">{t("story.sentence.listening")}</span>
          <button
            type="button"
            className="k-rec__stop"
            onClick={onRecordStop}
            aria-label={t("story.sentence.stopAria")}
          >
            ⏹ {t("story.sentence.stop")}
          </button>
        </div>

        {/* Evaluating pill — shown between mic release and feedback arrival.
            Same slot as the recording pill so the transition feels continuous. */}
        <div
          className="k-eval"
          data-show="evaluating"
          role="status"
          aria-live="polite"
        >
          <span className="k-eval__spinner" aria-hidden="true" />
          <span className="k-eval__lbl">{t("story.sentence.evaluating")}</span>
        </div>

        {/* Feedback panel */}
        <div
          className="k-feedback"
          data-show="feedback"
          role="status"
          aria-live="polite"
        >
          <div className="k-feedback__head">
            <span className="k-feedback__score">
              {score ?? 0}
              <span className="k-feedback__unit">/100</span>
            </span>
            <span className="k-feedback__verdict">
              {verdictKey && t(`story.sentence.verdict.${verdictKey}`)}
              {badWordTip && (
                <>
                  {" "}
                  {badWordTip.hint ? (
                    <>
                      {t("story.sentence.feedback.tipPrefix")}{" "}
                      <em>{badWordTip.hint}</em>.
                    </>
                  ) : (
                    <>
                      {t("story.sentence.feedback.tipPrefix")}{" "}
                      <em>{badWordTip.word}</em>.
                    </>
                  )}
                </>
              )}
            </span>
          </div>
          <div className="k-feedback__legend">
            <span className="k-feedback__pill" data-tone="good">
              {t("story.sentence.feedback.legend.clear", { count: counts.good })}
            </span>
            <span className="k-feedback__pill" data-tone="ok">
              {t("story.sentence.feedback.legend.ok", { count: counts.ok })}
            </span>
            <span className="k-feedback__pill" data-tone="bad">
              {t("story.sentence.feedback.legend.bad", { count: counts.bad })}
            </span>
          </div>
          <div className="k-feedback__actions">
            <button
              type="button"
              className="k-feedback__btn"
              onClick={onListenFromFeedback}
            >
              ▸ {t("story.sentence.feedback.listen")}
            </button>
            <button
              type="button"
              className="k-feedback__btn k-feedback__btn--strong"
              onClick={onRetry}
            >
              ↻ {t("story.sentence.feedback.retry")}
            </button>
          </div>
        </div>

        {/* Idle hint */}
        <p className="k-hint" data-show="idle">
          <kbd>SPACE</kbd> {t("story.sentence.hint.listen")} ·{" "}
          <kbd>M</kbd> {t("story.sentence.hint.talk")} ·{" "}
          <kbd>←</kbd> <kbd>→</kbd> {t("story.sentence.hint.navigate")}
        </p>
      </div>

      {/* Step nav */}
      <nav className="k-stepnav">
        <button
          type="button"
          className="k-stepnav__btn k-stepnav__btn--prev"
          onClick={onPrev}
          disabled={!canPrev}
        >
          <span className="k-stepnav__arrow">←</span>{" "}
          {t("story.step.prev")}
        </button>
        <button
          type="button"
          className="k-stepnav__btn k-stepnav__btn--next"
          onClick={onNext}
        >
          {canNext ? t("story.step.next") : t("story.step.finish")}{" "}
          <span className="k-stepnav__arrow">→</span>
        </button>
      </nav>
    </section>
  );
}
