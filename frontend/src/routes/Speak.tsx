/**
 * Speak — "Hablar con Klara". Pronunciation-oriented voice conversation.
 *
 * One target sound per session (de: ü). Klara steers the chat so the sound
 * recurs, the backend scores HOW it sounded (per word/phoneme, unscripted
 * Azure assessment), and a sound correction is woven between the user's turn
 * and Klara's spoken reply. Ported from the design handoff (kc-* markup);
 * strings extracted to i18n (es is the source).
 *
 * STATE MACHINE (voice):
 *   idle ──(mic)──▶ listening ──(VAD silence | tap | 20s cap)──▶ thinking
 *     ▲                                                             │
 *     │                                          (turn OK)──▶ correction
 *     │  (noSpeech / lowConfidence / error → idle + hint)            │
 *     └──◀── speaking ◀──("seguir hablando", unmuted)────────────────┘
 *                │            ("decilo otra vez" → listening, retry)
 *                └─(TTS onDone | mic tap)──▶ idle
 *   ✕ Terminar ─▶ summary (per-sound stats; struggled words → Practice SRS)
 *   `transcript` is an orthogonal voice ⇄ text toggle.
 *
 * Every transition callback reads state through refs (VAD, timers and TTS
 * callbacks outlive the closure they were created in), stop paths are
 * single-flight, and one unmount effect owns all teardown — see the runtime
 * review in the PR for the five races these guards exist for.
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
import { speak, stop as stopTTS } from "../lib/tts";
import { getSpeakFocus, type SpeakFocus } from "../lib/speakFocus";

type VoiceState = "idle" | "listening" | "thinking" | "correction" | "speaking" | "summary";
type Who = "klara" | "you";

interface SpokenTurn {
  who: Who;
  time: string;
  target: string;
  native: string;
  fix?: string;
  /** "Decilo otra vez" takes show in the transcript but are NOT conversation
   *  context — the LLM would treat a lone retried word as a turn (plan F10). */
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
   ChatPresence — Klara's cursive K (breathing halo when speaking)
   inside a radial ring of 44 ticks. Ring/halo reaction is pure CSS
   via [data-state] (pages convention); "thinking" swaps the K for
   a three-dot pulse.
   ============================================================ */
function ChatPresence({ state, thinkingLabel }: { state: VoiceState; thinkingLabel: string }) {
  return (
    <div className="kc-presence" data-state={state}>
      <div className="kc-disc" />
      <div className="kc-ring" aria-hidden="true">
        {KC_TICKS.map((_, i) => (
          <span
            key={i}
            className="kc-tick"
            style={{ transform: `rotate(${i * (360 / KC_TICKS.length)}deg) translateY(-142px)` }}
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
        <KlaraMark size={128} speaking={state === "speaking"} />
      )}
    </div>
  );
}

/* ---- demo fixtures (QA via ?demo=<state>; mic is disabled in demo) ---- */
const DEMO_TURN: SpeakTurnResponse = {
  noSpeech: false,
  lowConfidence: false,
  recognizedText: "Im Bürgeramt musste ich fünf Minuten warten",
  tokens: [
    { t: "Im", s: "good", focus: false },
    { t: "Bürgeramt", s: "ok", focus: true },
    { t: "musste", s: "good", focus: false },
    { t: "ich", s: "good", focus: false },
    { t: "fünf", s: "bad", focus: true },
    { t: "Minuten", s: "good", focus: false },
    { t: "warten", s: "good", focus: false },
  ],
  scores: { accuracy: 71, fluency: 80, pronunciation: 74 },
  target: {
    word: "fünf",
    gloss: "cinco",
    focusAccuracy: 38,
    shouldIpa: "/fʏnf/",
    modelSentence: "Ich musste fünf Minuten warten.",
  },
  focusHit: true,
  focusClear: false,
  reply: {
    target: "Fünf Minuten — nicht schlecht. War die Tür schwer zu finden?",
    native: "Cinco minutos, no está mal. ¿Costó encontrar la puerta?",
  },
};

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
    ["listening", "thinking", "speaking", "correction", "summary"] as const
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

  const [transcript, setTranscript] = useState(demo === "transcript");
  const [muted, setMuted] = useState(false);
  const [turns, setTurns] = useState<SpokenTurn[]>([]);
  const [lastTurn, setLastTurn] = useState<SpeakTurnResponse | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [finish, setFinish] = useState<
    { status: "saved"; added: number; skipped: number } | { status: "failed" } | null
  >(null);
  const [now, setNow] = useState(() => Date.now());

  // Teardown owners — ONE place releases every resource (runtime review #5).
  const recorderRef = useRef<MicRecorder | null>(null);
  const vadCleanupRef = useRef<(() => void) | null>(null);
  const capTimerRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Race guards: mic-start TOCTOU (#2) and single-flight stop (#1).
  const micBusyRef = useRef(false);
  const stoppingRef = useRef(false);
  const unmountedRef = useRef(false);

  const mutedRef = useRef(muted);
  mutedRef.current = muted;
  const turnsRef = useRef(turns);
  turnsRef.current = turns;

  const retryWordRef = useRef<string | undefined>(undefined);
  const statsRef = useRef({ clear: 0, total: 0 });
  const struggledRef = useRef<Map<string, StruggledWord>>(new Map());
  const sessionStartRef = useRef(Date.now());
  const finishFiredRef = useRef(false);

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
    // StrictMode runs mount → cleanup → re-mount in dev: without this reset
    // the simulated unmount would permanently brand the REAL mount as dead
    // (every recorder cancelled on arrival, every response dropped).
    unmountedRef.current = false;
    return () => {
      unmountedRef.current = true;
      releaseRecording();
      abortRef.current?.abort();
      stopTTS();
    };
  }, [releaseRecording]);

  const sendTurn = useCallback(
    async (blob: Blob) => {
      if (!focus) return;
      // Capture-and-clear: a retry that ends in noSpeech/error must not brand
      // the user's NEXT ordinary take as a retry (review finding).
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
        // already aborted us and set "summary", this rejection is stale —
        // showing "you're offline" over the summary would be both a lie and
        // a state stomp (review finding).
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

      let fix: string | undefined;
      if (struggling && target) {
        struggledRef.current.set(target.word.toLowerCase(), {
          word: target.word,
          gloss: target.gloss,
          modelSentence: target.modelSentence,
        });
        fix = t("speak.transcript.fix", {
          sound: focus.sound,
          word: target.word,
          ipa: target.shouldIpa,
        });
      } else if (retryWord && target && target.word.toLowerCase() === retryWord.toLowerCase()) {
        struggledRef.current.delete(retryWord.toLowerCase());
        fix = t("speak.transcript.improved", { word: target.word, sound: focus.sound });
      }

      const newTurns: SpokenTurn[] = [
        {
          who: "you",
          time: timeLabel,
          target: resp.recognizedText,
          native: "",
          fix,
          excludeFromHistory: Boolean(retryWord),
        },
      ];
      if (resp.reply) {
        newTurns.push({
          who: "klara",
          time: timeLabel,
          target: resp.reply.target,
          native: resp.reply.native,
        });
      }
      setTurns((prev) => [...prev, ...newTurns]);
      setLastTurn(resp);
      setState("correction");
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

  const startListening = useCallback(async () => {
    if (demoActive || micBusyRef.current || stoppingRef.current) return;
    if (!["idle", "speaking", "correction"].includes(stateRef.current)) return;
    micBusyRef.current = true;
    stopTTS(); // never record over Klara's voice (useSentencePractice precedent)
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
      // Same ownership rule as the success branch above: if the user pressed
      // ✕ while the permission prompt hung, "summary" is not ours to stomp.
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

  const continueConversation = useCallback(() => {
    const reply = lastTurn?.reply;
    if (mutedRef.current || !reply) {
      setState("idle");
      return;
    }
    setState("speaking");
    speak(reply.target, targetLanguage, {
      // Transition ONLY if we still own the state — an interruption (mic tap,
      // model-play button) means someone else already moved the machine.
      onDone: () => setState((s) => (s === "speaking" ? "idle" : s)),
    });
  }, [lastTurn, setState, targetLanguage]);

  const retryWordAgain = useCallback(() => {
    retryWordRef.current = lastTurn?.target?.word;
    void startListening();
  }, [lastTurn, startListening]);

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
      // The summary must not claim "vuelven a Práctica" for a write that
      // never landed (review finding) — render the failure note instead.
      .catch(() => setFinish({ status: "failed" }));
  }, [demoActive, focus, releaseRecording, setState, targetLanguage]);

  const startOver = useCallback(() => {
    setTurns([]);
    setLastTurn(null);
    setHint(null);
    setFinish(null);
    statsRef.current = { clear: 0, total: 0 };
    struggledRef.current = new Map();
    retryWordRef.current = undefined;
    sessionStartRef.current = Date.now();
    finishFiredRef.current = false;
    setState("idle");
  }, [setState]);

  const toggleMute = useCallback(() => {
    setMuted((m) => {
      const next = !m;
      // Muting mid-reply silences Klara NOW; her onDone fires as
      // "interrupted" and the guard above returns the stage to idle.
      if (next && stateRef.current === "speaking") stopTTS();
      return next;
    });
  }, []);

  /* ---- language gate: Speak opens in German first (A3) ---- */
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

  const effTurn = demoActive ? DEMO_TURN : lastTurn;
  const effTurns: SpokenTurn[] = demoActive
    ? [
        {
          who: "klara",
          time: "20:31",
          target: "Guten Abend. Heute üben wir das ü.",
          native: t("speak.opener.native", { sound: focus.sound }),
        },
        {
          who: "you",
          time: "20:31",
          target: DEMO_TURN.recognizedText,
          native: "",
          fix: t("speak.transcript.fix", { sound: focus.sound, word: "fünf", ipa: "/fʏnf/" }),
        },
        {
          who: "klara",
          time: "20:32",
          target: DEMO_TURN.reply!.target,
          native: DEMO_TURN.reply!.native,
        },
      ]
    : turns;
  const stats = demoActive ? { clear: 5, total: 7 } : statsRef.current;
  const struggled = demoActive ? DEMO_STRUGGLED : [...struggledRef.current.values()];
  const minutes = Math.max(
    1,
    Math.round((demoActive ? 240_000 : now - sessionStartRef.current) / 60_000),
  );

  /* ---------- SESSION SUMMARY — by sound ---------- */
  if (state === "summary" && !transcript) {
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
                {/* Real SRS schedules aren't fetched here — "pronto" is the
                    honest label for a freshly added card (plan F12), and ONLY
                    for cards the server confirmed (an LLM hiccup leaves a word
                    without its model sentence → the server skips it). */}
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

  const stageCap =
    state === "idle"
      ? t("speak.stage.idleCap")
      : state === "listening"
        ? t("speak.stage.listeningCap")
        : state === "thinking"
          ? t("speak.stage.thinkingCap")
          : t("speak.stage.speakingCap");
  const stageTarget =
    state === "idle"
      ? focus.openerTarget
      : state === "speaking" && effTurn?.reply
        ? effTurn.reply.target
        : "";
  const stageNative =
    state === "idle"
      ? t("speak.opener.native", { sound: focus.sound })
      : state === "speaking" && effTurn?.reply
        ? effTurn.reply.native
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
        <button
          className="kc-top__tr k-mono"
          data-on={transcript}
          onClick={() => setTranscript((v) => !v)}
        >
          {transcript ? t("speak.controls.voice") : t("speak.controls.transcript")}
        </button>
      </div>

      {/* Focus chip — the sound we're tuning today. Always visible in voice. */}
      {!transcript && (
        <div className="kc-foco" title={t("speak.focus.titleAttr")}>
          <span className="kc-foco__dot" />
          <span className="k-mono kc-foco__cap">{t("speak.focus.cap")}</span>
          <span className="kc-foco__sound">{focus.sound}</span>
          <span className="k-mono kc-foco__ipa">{focus.ipa}</span>
        </div>
      )}

      {transcript ? (
        /* ---- TRANSCRIPT — letter column ---- */
        <div className="kc-transcript">
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
                <p className="kc-turn__de">{turn.target}</p>
                {turn.native && <p className="kc-turn__es">{turn.native}</p>}
                {turn.fix && <p className="kc-turn__fix">{turn.fix}</p>}
              </li>
            ))}
          </ul>
        </div>
      ) : state === "correction" && effTurn ? (
        /* ---- SOUND CORRECTION — the heart of Speak ---- */
        <div className="kc-stage kc-stage--corr">
          <div className="kc-corr">
            <span className="k-mono kc-corr__cap">{t("speak.correction.cap")}</span>
            <p className="kc-corr__line">
              {effTurn.tokens.map((tk, i) => (
                <span key={i}>
                  <span
                    className="kac-word kp-word"
                    data-score={tk.s}
                    data-focus={tk.focus ? "true" : undefined}
                  >
                    {tk.t}
                  </span>
                  {i < effTurn.tokens.length - 1 ? " " : "."}
                </span>
              ))}
            </p>

            {effTurn.target && (
              <div className="kc-corr__target">
                <button
                  className="kac-tool kac-tool--play kc-corr__play"
                  aria-label={t("speak.correction.playAria")}
                  onClick={() =>
                    speak(effTurn.target!.modelSentence ?? effTurn.target!.word, targetLanguage)
                  }
                >
                  <span className="kac-tri kac-tri--lg" />
                </button>
                <div className="kc-corr__detail">
                  <span className="kc-corr__word">{effTurn.target.word}</span>
                  <span className="kc-corr__ipa">
                    {t("speak.correction.targetIpa")}{" "}
                    <strong>{effTurn.target.shouldIpa}</strong>
                  </span>
                </div>
                <button
                  className="kac-feedback__btn kac-feedback__btn--strong"
                  onClick={retryWordAgain}
                >
                  ↻ {t("speak.correction.retry")}
                </button>
              </div>
            )}

            <p className="kc-corr__tip">
              <span className="k-mono kc-corr__tip-cap">{t("speak.correction.how")}</span>{" "}
              {t(focus.tipKey)}
            </p>

            {/* ONE rule-bearing wrapper for reply + continue — the prototype
                frames this band with a single top rule; a second one boxes
                Klara's reply into a competing card (visual audit). */}
            <div className="kc-corr__cont">
              {effTurn.reply && (
                <div className="kc-corr__cont-line">
                  <KlaraMark size={13} />
                  <span>«{effTurn.reply.target}»</span>
                </div>
              )}
              <button className="k-btn k-btn--ghost" onClick={continueConversation}>
                {t("speak.correction.continue")} <span className="arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* ---- VOICE STAGE — idle / listening / thinking / speaking ---- */
        <div className="kc-stage">
          <ChatPresence state={state} thinkingLabel={t("speak.stage.thinkingAria")} />
          <span className="kc-cap k-mono">{stageCap}</span>
          {stageTarget ? (
            <p className="kc-utter">{stageTarget}</p>
          ) : (
            <p className="kc-utter kc-utter--mute">·&nbsp;·&nbsp;·</p>
          )}
          {stageNative && <p className="kc-gloss">{stageNative}</p>}
        </div>
      )}

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
          (transcript
            ? t("speak.hint.transcript")
            : state === "idle"
              ? t("speak.hint.idle", { sound: focus.sound })
              : state === "listening"
                ? t("speak.hint.listening")
                : state === "correction"
                  ? t("speak.hint.correction")
                  : t("speak.hint.speaking"))}
      </p>
    </main>
  );
}
