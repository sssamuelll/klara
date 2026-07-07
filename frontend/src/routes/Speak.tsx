/**
 * Speak — "Hablar con Klara". Pronunciation-oriented voice conversation.
 *
 * v2, per council consensus (2026-06-12): THE CONVERSATION IS THE CARRIER.
 * One persistent surface — the compact presence (K) pinned above a running
 * column of turns; nothing swaps full-screen except the final summary.
 * - Klara speaks UNPROMPTED the moment a turn returns (F6 revoked; the mic
 *   tap unlocks one persistent Audio element so Safari allows it).
 * - The correction never interrupts: it renders as "el apunte" — a margin
 *   note under the user's turn (target word, IPA, model audio, retry, tip) —
 *   and is OMITTED when the focus sound came out clear (a quiet line says so).
 * - Zero mandatory taps per turn. Target: ≤5s p50 stop-to-voice.
 *
 * STATE MACHINE (voice):
 *   idle ──(mic)──▶ listening ──(VAD silence | tap | 20s cap)──▶ thinking
 *     ▲                                                             │
 *     │   (noSpeech / lowConfidence / error → idle + hint)          │
 *     │                                      (turn OK: turns append │
 *     │                                       to the column)        │
 *     └──◀── speaking ◀──(auto: reply && !muted)────────────────────┘
 *                │            (muted or no reply → idle directly)
 *                └─(TTS onDone | mic tap)──▶ idle | listening
 *   ✕ Terminar ─▶ summary (the only full page; struggled words → SRS)
 *
 * Every transition callback reads state through refs, stop paths are
 * single-flight, and one unmount effect owns all teardown (see the v1
 * runtime review; those guards survive unchanged).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { SpeakTurnResponse } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import { useAuth } from "../lib/auth";
import {
  startMicRecording,
  type MicRecorder,
  type PronunciationError,
} from "../lib/pronunciation";
import { classifyScoreError } from "../lib/pronunciation";
import { startSilenceDetector } from "../lib/silenceDetector";
import { speak, stop as stopTTS, unlockAudio } from "../lib/tts";
import { getSpeakFocus, type SpeakFocus } from "../lib/speakFocus";

type VoiceState = "idle" | "listening" | "thinking" | "speaking" | "summary";
type Who = "klara" | "you";

/** El apunte — the margin note under a struggled turn. */
interface TurnNote {
  word: string;
  shouldIpa: string;
  modelSentence: string | null;
}

interface SpokenTurn {
  who: Who;
  time: string;
  target: string;
  native: string;
  note?: TurnNote;
  /** Focus word that came out clear this turn — quiet acknowledgment line. */
  clearWord?: string;
  /** Retried word that now sounds right. */
  improvedWord?: string;
  /** First note of the session explains the underline once. */
  showLegend?: boolean;
  /** Retry takes show in the column but are NOT conversation context (F10). */
  excludeFromHistory?: boolean;
}

interface StruggledWord {
  word: string;
  gloss: string | null;
  modelSentence: string | null;
}

/** Hard cap on one recording — same guard as useMicScorer. */
const HARD_CAP_MS = 20_000;
const MAX_HISTORY_TURNS = 8;
const CLEAR_THRESHOLD = 70;

const KC_TICKS = Array.from({ length: 44 });

function clockLabel(d: Date): string {
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function elapsedLabel(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/* ============================================================
   ChatPresence — Klara's K inside the reactive tick ring,
   compact and PERSISTENT: listening/thinking/speaking are
   rhythms of this one object (CSS [data-state]), never content
   swaps. The K only yields to the dots while thinking.
   ============================================================ */
function ChatPresence({ state, thinkingLabel }: { state: VoiceState; thinkingLabel: string }) {
  return (
    <div className="kc-presence kc-presence--sm" data-state={state}>
      <div className="kc-disc" />
      <div className="kc-ring" aria-hidden="true">
        {KC_TICKS.map((_, i) => (
          <span
            key={i}
            className="kc-tick"
            style={{ transform: `rotate(${i * (360 / KC_TICKS.length)}deg) translateY(-78px)` }}
          >
            <i className="kc-tick__bar" style={{ animationDelay: `${(i % 11) * 70}ms` }} />
          </span>
        ))}
      </div>
      {state === "thinking" ? (
        <span className="kc-think" aria-label={thinkingLabel}>
          <i />
          <i />
          <i />
        </span>
      ) : (
        <KlaraMark size={64} speaking={state === "speaking"} />
      )}
    </div>
  );
}

/* ---- demo fixtures (QA via ?demo=<state>; mic is disabled in demo) ---- */
const DEMO_TURNS: SpokenTurn[] = [
  {
    who: "klara",
    time: "20:31",
    target: "Heute üben wir das ü. Wie war dein Tag — musstest du irgendwo warten?",
    native: "Hoy afinamos la ü. ¿Qué tal tu día? ¿Tuviste que esperar en algún sitio?",
  },
  {
    who: "you",
    time: "20:31",
    target: "Im Bürgeramt musste ich fünf Minuten warten",
    native: "",
    note: { word: "fünf", shouldIpa: "/fʏnf/", modelSentence: "Ich musste fünf Minuten warten." },
    showLegend: true,
  },
  {
    who: "klara",
    time: "20:32",
    target: "Fünf Minuten — nicht schlecht. War die Tür schwer zu finden?",
    native: "Cinco minutos, no está mal. ¿Costó encontrar la puerta?",
  },
  {
    who: "you",
    time: "20:32",
    target: "Nein, die Tür war gleich um die Ecke",
    native: "",
    clearWord: "Tür",
  },
];

const DEMO_STRUGGLED: StruggledWord[] = [
  { word: "fünf", gloss: "cinco", modelSentence: "Ich musste fünf Minuten warten." },
  { word: "Bürgeramt", gloss: "oficina de registro", modelSentence: "Das Bürgeramt ist heute offen." },
];

export default function Speak() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user } = useAuth();
  const [searchParams] = useSearchParams();

  const targetLanguage = user?.target_language ?? "de";
  const focus: SpeakFocus | null = getSpeakFocus(targetLanguage);

  const demo = searchParams.get("demo");
  const demoActive = demo !== null;
  const initialState: VoiceState = (
    ["listening", "thinking", "speaking", "summary"] as const
  ).includes(demo as never)
    ? (demo as VoiceState)
    : "idle";

  const [state, setStateRaw] = useState<VoiceState>(initialState);
  const stateRef = useRef(state);
  const setState = useCallback((next: VoiceState | ((s: VoiceState) => VoiceState)) => {
    setStateRaw((prev) => {
      const value = typeof next === "function" ? next(prev) : next;
      stateRef.current = value;
      return value;
    });
  }, []);

  const [muted, setMuted] = useState(false);
  const [turns, setTurns] = useState<SpokenTurn[]>([]);
  const [hint, setHint] = useState<string | null>(null);
  const [finish, setFinish] = useState<
    { status: "saved"; added: number; skipped: number } | { status: "failed" } | null
  >(null);
  const [now, setNow] = useState(() => Date.now());

  // Teardown owners — ONE place releases every resource.
  const recorderRef = useRef<MicRecorder | null>(null);
  const vadCleanupRef = useRef<(() => void) | null>(null);
  const capTimerRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Race guards: mic-start TOCTOU and single-flight stop.
  const micBusyRef = useRef(false);
  const stoppingRef = useRef(false);
  const unmountedRef = useRef(false);

  const mutedRef = useRef(muted);
  mutedRef.current = muted;
  const turnsRef = useRef(turns);
  turnsRef.current = turns;
  const columnRef = useRef<HTMLDivElement | null>(null);

  const retryWordRef = useRef<string | undefined>(undefined);
  const legendShownRef = useRef(false);
  const statsRef = useRef({ clear: 0, total: 0 });
  const struggledRef = useRef<Map<string, StruggledWord>>(new Map());
  const sessionStartRef = useRef(Date.now());
  const finishFiredRef = useRef(false);

  // The opener is Klara's first line IN the column (text only — her voice
  // first plays after the first turn, which the mic gesture has unlocked).
  useEffect(() => {
    if (demoActive || !focus) return;
    setTurns((prev) =>
      prev.length > 0
        ? prev
        : [
            {
              who: "klara",
              time: clockLabel(new Date()),
              target: focus.openerTarget,
              native: t("speak.opener.native", { sound: focus.sound }),
            },
          ],
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoActive, focus?.sound]);

  const releaseRecording = useCallback(() => {
    vadCleanupRef.current?.();
    vadCleanupRef.current = null;
    if (capTimerRef.current !== null) {
      window.clearTimeout(capTimerRef.current);
      capTimerRef.current = null;
    }
    recorderRef.current?.cancel();
    recorderRef.current = null;
  }, []);

  useEffect(() => {
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(tick);
  }, []);

  useEffect(() => {
    // StrictMode runs mount → cleanup → re-mount in dev: reset the flag so
    // the simulated unmount can't brand the real mount as dead.
    unmountedRef.current = false;
    return () => {
      unmountedRef.current = true;
      releaseRecording();
      abortRef.current?.abort();
      stopTTS();
    };
  }, [releaseRecording]);

  // The column is the conversation — keep its tail in view as it grows.
  useEffect(() => {
    const el = columnRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns, state]);

  const sendTurn = useCallback(
    async (blob: Blob) => {
      if (!focus) return;
      // Capture-and-clear: a retry that ends in noSpeech/error must not brand
      // the user's NEXT ordinary take as a retry.
      const retryWord = retryWordRef.current;
      retryWordRef.current = undefined;
      const abort = new AbortController();
      abortRef.current = abort;
      let resp: SpeakTurnResponse;
      try {
        resp = await api.speakTurn(blob, {
          language: targetLanguage,
          focusSound: focus.sound,
          focusExamples: focus.examples,
          history: turnsRef.current
            .filter((turn) => !turn.excludeFromHistory)
            .slice(-MAX_HISTORY_TURNS)
            .map((turn) => ({ who: turn.who, text: turn.target })),
          retryWord,
          signal: abort.signal,
        });
      } catch (e) {
        // Only the owner of "thinking" may move the machine: if ✕ Terminar
        // already aborted us and set "summary", this rejection is stale.
        if (unmountedRef.current || stateRef.current !== "thinking") return;
        const perr: PronunciationError =
          e instanceof DOMException && (e.name === "AbortError" || e.name === "TimeoutError")
            ? { kind: "network" }
            : classifyScoreError(e);
        setHint(t(`pron.error.${perr.kind}`));
        setState("idle");
        return;
      } finally {
        abortRef.current = null;
      }
      if (unmountedRef.current || stateRef.current !== "thinking") return;

      if (resp.noSpeech) {
        setHint(t("speak.hint.noSpeech"));
        setState("idle");
        return;
      }
      if (resp.lowConfidence) {
        setHint(t("speak.hint.lowConfidence"));
        setState("idle");
        return;
      }

      const timeLabel = clockLabel(new Date());
      const target = resp.target;
      const struggling = target !== null && target.focusAccuracy < CLEAR_THRESHOLD;

      if (!retryWord && resp.focusHit) {
        statsRef.current.total += 1;
        if (resp.focusClear) statsRef.current.clear += 1;
      }

      const userTurn: SpokenTurn = {
        who: "you",
        time: timeLabel,
        target: resp.recognizedText,
        native: "",
        excludeFromHistory: Boolean(retryWord),
      };

      if (struggling && target) {
        struggledRef.current.set(target.word.toLowerCase(), {
          word: target.word,
          gloss: target.gloss,
          modelSentence: target.modelSentence,
        });
        userTurn.note = {
          word: target.word,
          shouldIpa: target.shouldIpa,
          modelSentence: target.modelSentence,
        };
        if (!legendShownRef.current) {
          legendShownRef.current = true;
          userTurn.showLegend = true;
        }
      } else if (retryWord && target && target.word.toLowerCase() === retryWord.toLowerCase()) {
        struggledRef.current.delete(retryWord.toLowerCase());
        userTurn.improvedWord = target.word;
      } else if (resp.focusHit && resp.focusClear && target) {
        // The coach also confirms — quietly, woven into the column.
        userTurn.clearWord = target.word;
      }

      const newTurns: SpokenTurn[] = [userTurn];
      if (resp.reply) {
        newTurns.push({
          who: "klara",
          time: timeLabel,
          target: resp.reply.target,
          native: resp.reply.native,
        });
      }
      setTurns((prev) => [...prev, ...newTurns]);

      // F6 revoked: Klara takes the floor the moment her reply exists —
      // no tap, no gate. The mic tap that started this turn unlocked the
      // audio element, so autoplay is permitted.
      const reply = resp.reply;
      if (reply && !mutedRef.current) {
        setState("speaking");
        speak(reply.target, targetLanguage, {
          // Conversational reply: latency beats narration polish here.
          mode: "realtime",
          // Transition ONLY if we still own the state — an interruption
          // (mic tap, model-play button) means someone else moved it.
          onDone: () => setState((s) => (s === "speaking" ? "idle" : s)),
        });
      } else {
        setState("idle");
      }
    },
    [focus, setState, t, targetLanguage],
  );

  /** All stop paths (VAD, hard cap, mic tap) funnel here — single-flight. */
  const stopTurn = useCallback(async () => {
    if (stoppingRef.current || stateRef.current !== "listening") return;
    stoppingRef.current = true;
    try {
      vadCleanupRef.current?.();
      vadCleanupRef.current = null;
      if (capTimerRef.current !== null) {
        window.clearTimeout(capTimerRef.current);
        capTimerRef.current = null;
      }
      const rec = recorderRef.current;
      recorderRef.current = null;
      if (!rec) {
        setState("idle");
        return;
      }
      setState("thinking");
      const blob = await rec.stop();
      if (unmountedRef.current) return;
      if (!blob || blob.size === 0) {
        setHint(t("speak.hint.noSpeech"));
        setState("idle");
        return;
      }
      await sendTurn(blob);
    } finally {
      stoppingRef.current = false;
    }
  }, [sendTurn, setState, t]);

  const startListening = useCallback(async (retryWord?: string) => {
    if (demoActive || micBusyRef.current || stoppingRef.current) return;
    if (!["idle", "speaking"].includes(stateRef.current)) return;
    micBusyRef.current = true;
    // Committed ONLY after the guards pass: arming the ref before a rejected
    // start would brand the take already in flight — or the user's next
    // ordinary tap — as a retry (review finding). An ordinary tap clears it.
    retryWordRef.current = retryWord;
    unlockAudio(); // the gesture that authorizes every later auto-play
    stopTTS(); // never record over Klara's voice
    setHint(null);
    setState("listening");
    try {
      const rec = await startMicRecording();
      // The world may have moved while getUserMedia was pending (second tap,
      // unmount, ✕): release the orphan or the mic indicator stays lit.
      if (unmountedRef.current || stateRef.current !== "listening") {
        rec.cancel();
        return;
      }
      recorderRef.current = rec;
      vadCleanupRef.current = startSilenceDetector(rec.analyser, () => void stopTurn());
      capTimerRef.current = window.setTimeout(() => void stopTurn(), HARD_CAP_MS);
    } catch (e) {
      // Same ownership rule as the success branch: if the user pressed ✕
      // while the permission prompt hung, "summary" is not ours to stomp.
      if (unmountedRef.current || stateRef.current !== "listening") return;
      const perr = e as PronunciationError;
      setHint(t(`pron.error.${perr.kind ?? "mic_unavailable"}`));
      setState("idle");
    } finally {
      micBusyRef.current = false;
    }
  }, [demoActive, setState, stopTurn, t]);

  const onMic = useCallback(() => {
    if (demoActive) return;
    if (stateRef.current === "listening") void stopTurn();
    else void startListening();
  }, [demoActive, startListening, stopTurn]);

  const retryWordAgain = useCallback(
    (word: string) => {
      void startListening(word);
    },
    [startListening],
  );

  const endSession = useCallback(() => {
    releaseRecording();
    stopTTS();
    abortRef.current?.abort();
    setState("summary");
    if (finishFiredRef.current || demoActive || !focus) return;
    finishFiredRef.current = true;
    const words = [...struggledRef.current.values()].slice(0, 8);
    if (words.length === 0) {
      setFinish({ status: "saved", added: 0, skipped: 0 });
      return;
    }
    api
      .speakFinish({
        language: targetLanguage,
        focusSound: focus.sound,
        clearCount: statsRef.current.clear,
        totalCount: statsRef.current.total,
        durationSeconds: Math.round((Date.now() - sessionStartRef.current) / 1000),
        words,
      })
      .then((r) => setFinish({ status: "saved", added: r.added, skipped: r.skipped }))
      .catch(() => setFinish({ status: "failed" }));
  }, [demoActive, focus, releaseRecording, setState, targetLanguage]);

  const startOver = useCallback(() => {
    setTurns(
      focus
        ? [
            {
              who: "klara",
              time: clockLabel(new Date()),
              target: focus.openerTarget,
              native: t("speak.opener.native", { sound: focus.sound }),
            },
          ]
        : [],
    );
    setHint(null);
    setFinish(null);
    statsRef.current = { clear: 0, total: 0 };
    struggledRef.current = new Map();
    retryWordRef.current = undefined;
    legendShownRef.current = false;
    sessionStartRef.current = Date.now();
    finishFiredRef.current = false;
    setState("idle");
  }, [focus, setState, t]);

  const toggleMute = useCallback(() => {
    setMuted((m) => {
      const next = !m;
      // Muting mid-reply silences Klara NOW; her onDone fires as
      // "interrupted" and the guard returns the stage to idle.
      if (next && stateRef.current === "speaking") stopTTS();
      return next;
    });
  }, []);

  /* ---- language gate: Speak opens in German first ---- */
  if (!focus) {
    return (
      <main className="k-page placeholder">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("common.back")}
        </button>
        <div className="ph__head">
          <span className="k-mono">{t("speak.gate.kicker")}</span>
          <h1 className="ph__title">{t("speak.gate.title")}</h1>
          <p className="ph__dek">{t("speak.gate.dek")}</p>
        </div>
      </main>
    );
  }

  const effTurns = demoActive ? DEMO_TURNS : turns;
  const stats = demoActive ? { clear: 5, total: 7 } : statsRef.current;
  const struggled = demoActive ? DEMO_STRUGGLED : [...struggledRef.current.values()];
  const minutes = Math.max(
    1,
    Math.round((demoActive ? 240_000 : now - sessionStartRef.current) / 60_000),
  );

  /* ---------- SESSION SUMMARY — the only full page ---------- */
  if (state === "summary") {
    const saved = demoActive
      ? { status: "saved" as const, added: struggled.length, skipped: 0 }
      : finish;
    const toPractice = saved?.status === "saved" ? saved.added : "—";
    return (
      <main className="k-page kp-summary">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("speak.controls.exit")}
        </button>
        <header className="kp-sum__head">
          <div className="kp-sum__sig">
            <span className="kp-sum__k">K</span>
            <span className="k-mono">{t("speak.summary.kicker")}</span>
          </div>
          <h1 className="kp-sum__title">
            {t("speak.summary.titlePre")}
            <em className="kc-em">{focus.sound}</em>
            {t("speak.summary.titlePost")}
          </h1>
          <p className="kp-sum__dek">{t("speak.summary.dek", { minutes, sound: focus.sound })}</p>
        </header>

        <section className="kp-sum__stats">
          <div className="kp-stat">
            <span className="kp-stat__n">
              {stats.clear}
              <span className="kp-stat__of">/{stats.total}</span>
            </span>
            <span className="k-mono">{t("speak.summary.stat.clear", { sound: focus.sound })}</span>
          </div>
          <span className="kp-stat__rule" />
          <div className="kp-stat">
            <span className="kp-stat__n">{minutes}</span>
            <span className="k-mono">{t("speak.summary.stat.minutes")}</span>
          </div>
          <span className="kp-stat__rule" />
          <div className="kp-stat">
            <span className="kp-stat__n">{toPractice}</span>
            <span className="k-mono">{t("speak.summary.stat.toPractice")}</span>
          </div>
        </section>

        <hr className="k-hairline" />

        <section className="kp-returns">
          <header className="kp-returns__head">
            <span className="k-mono">{t("speak.summary.returns")}</span>
            <span className="k-mono kp-returns__count">{struggled.length}</span>
          </header>
          <ul className="kp-returns__list">
            {struggled.map((w) => (
              <li key={w.word} className="kp-returns__item">
                <span className="kp-returns__word">{w.word}</span>
                <span className="kp-returns__tx">{w.gloss ?? ""}</span>
                <span className="kp-returns__next k-mono">
                  {saved?.status === "saved" && w.modelSentence ? t("speak.summary.soon") : "—"}
                </span>
              </li>
            ))}
          </ul>
          {saved?.status === "failed" && (
            <p className="kc-hint" role="alert">
              {t("speak.summary.saveFailed")}
            </p>
          )}
          {saved?.status === "saved" && saved.skipped > 0 && (
            <p className="kc-hint">{t("speak.summary.partial", { count: saved.skipped })}</p>
          )}
        </section>

        <footer className="kp-sum__cta">
          <button className="k-btn" onClick={startOver}>
            {t("speak.summary.again")} <span className="arrow">→</span>
          </button>
          <button className="k-btn k-btn--ghost" onClick={() => navigate("/")}>
            {t("speak.summary.home")}
          </button>
        </footer>
      </main>
    );
  }

  // No cap in idle — the focus chip in the top bar already names the session
  // (a second "FOCO DE HOY" under the medallion would just be an echo).
  const stageCap =
    state === "listening"
      ? t("speak.stage.listeningCap")
      : state === "thinking"
        ? t("speak.stage.thinkingCap")
        : state === "speaking"
          ? t("speak.stage.speakingCap")
          : "";

  return (
    <main className="k-page kc-page" data-state={state}>
      <div className="kc-top">
        <button className="story__back k-mono" onClick={() => navigate("/")}>
          {t("speak.controls.exit")}
        </button>
        <span className="kc-top__time k-mono">
          {clockLabel(new Date(now))} · {elapsedLabel(now - sessionStartRef.current)}
        </span>
        <div className="kc-foco" title={t("speak.focus.titleAttr")}>
          <span className="kc-foco__dot" />
          <span className="k-mono kc-foco__cap">{t("speak.focus.cap")}</span>
          <span className="kc-foco__sound">{focus.sound}</span>
          <span className="k-mono kc-foco__ipa">{focus.ipa}</span>
        </div>
      </div>

      {/* The one persistent surface: presence above, the conversation below. */}
      <div className="kc-live">
        <div className="kc-live__presence">
          <ChatPresence state={state} thinkingLabel={t("speak.stage.thinkingAria")} />
          <span className="kc-cap k-mono">{stageCap}</span>
        </div>

        <div className="kc-live__column" ref={columnRef}>
          <span className="k-mono kc-transcript__cap">
            {t("speak.transcript.cap", { sound: focus.sound })}
          </span>
          <ul className="kc-turns">
            {effTurns.map((turn, i) => (
              <li key={i} className="kc-turn" data-who={turn.who}>
                <div className="kc-turn__meta">
                  {turn.who === "klara" ? (
                    <KlaraMark size={13} />
                  ) : (
                    <span className="kc-turn__you k-mono">{t("speak.transcript.you")}</span>
                  )}
                  <span className="k-mono kc-turn__time">{turn.time}</span>
                </div>
                <p className="kc-turn__de">
                  {turn.note
                    ? turn.target.split(/(\s+)/).map((part, j) =>
                        // Azure's display transcript carries punctuation
                        // ("fünf," / "fünf.") — strip the edges or a
                        // sentence-final focus word loses its underline.
                        part
                          .replace(/^[\p{P}\p{S}]+|[\p{P}\p{S}]+$/gu, "")
                          .toLowerCase() === turn.note!.word.toLowerCase() ? (
                          <span key={j} className="kc-live-focus">
                            {part}
                          </span>
                        ) : (
                          <span key={j}>{part}</span>
                        ),
                      )
                    : turn.target}
                </p>
                {turn.native && <p className="kc-turn__es">{turn.native}</p>}

                {turn.note && (
                  /* El apunte — woven under the turn, never a screen. */
                  <div className="kc-note">
                    <div className="kc-note__line">
                      <span className="k-mono kc-note__cap">{t("speak.note.cap")}</span>
                      <span className="kc-note__lead">
                        {t("speak.note.lead", { sound: focus.sound, word: turn.note.word })}{" "}
                        <strong>{turn.note.shouldIpa}</strong>
                      </span>
                    </div>
                    {/* Both actions are inert while the mic is open or a turn
                        is in flight: playing the model over an open mic would
                        score Klara's voice as the user's (review finding). */}
                    <div className="kc-note__actions">
                      <button
                        className="kac-tool kac-tool--play kc-note__play"
                        aria-label={t("speak.note.playAria")}
                        disabled={state === "listening" || state === "thinking"}
                        onClick={() =>
                          speak(turn.note!.modelSentence ?? turn.note!.word, targetLanguage, {
                            mode: "realtime",
                          })
                        }
                      >
                        <span className="kac-tri" />
                      </button>
                      <button
                        className="kac-feedback__btn"
                        disabled={state === "listening" || state === "thinking"}
                        onClick={() => retryWordAgain(turn.note!.word)}
                      >
                        ↻ {t("speak.note.retry")}
                      </button>
                    </div>
                    <p className="kc-note__tip">
                      <span className="k-mono kc-note__tip-cap">{t("speak.note.how")}</span>{" "}
                      {t(focus.tipKey)}
                    </p>
                    {turn.showLegend && (
                      <p className="kc-note__legend">
                        {t("speak.note.legend", { sound: focus.sound })}
                      </p>
                    )}
                  </div>
                )}
                {turn.clearWord && (
                  <p className="kc-turn__fix" data-tone="clear">
                    {t("speak.note.clear", { sound: focus.sound, word: turn.clearWord })}
                  </p>
                )}
                {turn.improvedWord && (
                  <p className="kc-turn__fix" data-tone="clear">
                    {t("speak.transcript.improved", {
                      sound: focus.sound,
                      word: turn.improvedWord,
                    })}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Controls — mute (Klara's voice) · mic (protagonist) · end */}
      <div className="kc-controls">
        <button
          className="kc-ctrl"
          data-on={muted}
          onClick={toggleMute}
          aria-label={muted ? t("speak.controls.unmuteAria") : t("speak.controls.muteAria")}
        >
          <span className={muted ? "kc-mute kc-mute--off" : "kc-mute"}>
            <span className="kac-mic" />
          </span>
        </button>
        <button
          className="kc-ctrl kc-ctrl--mic"
          data-on={state === "listening"}
          onClick={onMic}
          aria-label={t("speak.controls.micAria")}
        >
          <span className="kac-mic" />
        </button>
        <button
          className="kc-ctrl kc-ctrl--end"
          onClick={endSession}
          aria-label={t("speak.controls.endAria")}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          >
            <path d="M3 3l10 10M13 3L3 13" />
          </svg>
        </button>
      </div>

      <p className="kc-hint">
        {hint ??
          (state === "idle"
            ? t("speak.hint.idle", { sound: focus.sound })
            : state === "listening"
              ? t("speak.hint.listening")
              : state === "thinking"
                ? t("speak.hint.thinking")
                : t("speak.hint.speaking"))}
      </p>
    </main>
  );
}
