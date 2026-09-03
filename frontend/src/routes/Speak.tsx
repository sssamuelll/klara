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
 * Vocabulario k-*: superficie de sesión propia, como `/estudiar/:id` y
 * `/repaso` — pinta su propio `.k-app` y por eso cuelga fuera de LegacyShell
 * (el armazón de sesión es 100dvh y no se anida en `.kframe`). Composición:
 * línea superior + `.k-fill` con el escenario `.k-presence` y la columna
 * `.k-live` + `.k-dock` con el estado, los redondos y la guía. Ninguna clase
 * es de esta pantalla; `speak.css` murió con la migración 5.
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

import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { SpeakTurnResponse } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import { useAuth } from "../lib/auth";
import { onAppPause } from "../lib/native";
import {
  startMicRecording,
  type MicRecorder,
  type PronunciationError,
} from "../lib/pronunciation";
import { classifyScoreError } from "../lib/pronunciation";
import { micLevelKey, startSilenceDetector, type MicLevel } from "../lib/silenceDetector";
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

const TICKS = Array.from({ length: 44 });

function clockLabel(d: Date): string {
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function elapsedLabel(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

// Iconos de trazo 1.5 del átomo 2; el tamaño lo pone `.k-rbtn svg`.
function IcSound({ off = false }: { off?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4Z" />
      {off ? (
        <path d="M15.5 9.5l5 5M20.5 9.5l-5 5" />
      ) : (
        <>
          <path d="M15.5 9.5a3.5 3.5 0 0 1 0 5" />
          <path d="M18 7a7 7 0 0 1 0 10" />
        </>
      )}
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
function IcClose() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}
function IcPlay() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 5.4 19 12 8 18.6Z" />
    </svg>
  );
}

/* ============================================================
   El escenario — la K de Klara dentro del anillo reactivo,
   compacto y PERSISTENTE: escuchar, pensar y hablar son ritmos
   de este mismo objeto (`.k-presence[data-state]`), nunca cambios
   de contenido. La K solo cede su sitio a los puntos al pensar.
   ============================================================ */
function Escenario({ state, thinkingLabel }: { state: VoiceState; thinkingLabel: string }) {
  return (
    <div className="k-presence" data-state={state}>
      <span className="k-presence__disc" />
      <span className="k-presence__ring" aria-hidden="true">
        {TICKS.map((_, i) => (
          <span
            key={i}
            className="k-presence__tick"
            style={{ "--a": `${i * (360 / TICKS.length)}deg` } as CSSProperties}
          >
            <i style={{ animationDelay: `${(i % 11) * 70}ms` }} />
          </span>
        ))}
      </span>
      {state === "thinking" ? (
        <span className="k-presence__think" aria-label={thinkingLabel}>
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
  const location = useLocation();
  const { t } = useTranslation();
  const { user } = useAuth();
  const [searchParams] = useSearchParams();

  const targetLanguage = user?.target_language ?? "de";
  const focus: SpeakFocus | null = getSpeakFocus(targetLanguage);

  // Igual que Story y Repaso: quien entra pasa { state: { from } } y la salida
  // vuelve ahí; el Masthead entra sin estado y la salida cae en Inicio.
  const exitTo = (location.state as { from?: string } | null)?.from ?? "/";

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
  const [micLevel, setMicLevel] = useState<MicLevel>("silent");
  const [finish, setFinish] = useState<
    { status: "saved"; added: number; skipped: number } | { status: "failed" } | null
  >(null);
  const [now, setNow] = useState(() => Date.now());

  // Teardown owners — ONE place releases every resource.
  const recorderRef = useRef<MicRecorder | null>(null);
  const epochRef = useRef(0);
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
  // #127: groups this session's speak_turns rows server-side (no session row
  // exists until /finish, so identity is client-generated).
  const sessionIdRef = useRef(crypto.randomUUID());
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
    epochRef.current += 1;
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

  useEffect(() => onAppPause(releaseRecording), [releaseRecording]);

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
          sessionId: sessionIdRef.current,
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
    setMicLevel("silent");
    setState("listening");
    const epoch = epochRef.current;
    try {
      const rec = await startMicRecording();
      // The world may have moved while getUserMedia was pending (second tap,
      // unmount, ✕): release the orphan or the mic indicator stays lit.
      if (
        epoch !== epochRef.current ||
        unmountedRef.current ||
        stateRef.current !== "listening"
      ) {
        rec.cancel();
        return;
      }
      recorderRef.current = rec;
      vadCleanupRef.current = startSilenceDetector(
        rec.analyser,
        () => void stopTurn(),
        { onLevel: setMicLevel },
      );
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
        sessionId: sessionIdRef.current,
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
    sessionIdRef.current = crypto.randomUUID();
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

  const salir = useCallback(() => navigate(exitTo), [navigate, exitTo]);

  const lineaSuperior = (centro: JSX.Element | null) => (
    <header className="k-topline k-topline--session">
      <button type="button" className="k-btn k-btn--text k-topline__exit" onClick={salir}>
        {t("common.exit")}
      </button>
      {centro}
      <span className="k-topline__meta">
        {clockLabel(new Date(now))} · {elapsedLabel(now - sessionStartRef.current)}
      </span>
    </header>
  );

  /* ---- language gate: Speak opens in German first ---- */
  if (!focus) {
    return (
      <div className="k-app">
        {lineaSuperior(null)}
        <div className="k-fill">
          <header className="k-hero k-hero--quiet">
            <span className="k-hero__tag">{t("speak.gate.kicker")}</span>
            <h1 className="k-hero__title">{t("speak.gate.title")}</h1>
            <p className="k-hero__dek">{t("speak.gate.dek")}</p>
          </header>
        </div>
        <div className="k-dock">
          <div className="k-wrap">
            <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={salir}>
              {t("speak.summary.home")}
            </button>
          </div>
        </div>
      </div>
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
      <div className="k-app">
        {lineaSuperior(null)}
        <div className="k-fill">
          {/* Candidato 20 (bloque de cifra) sigue fuera: el cierre se compone
              con el héroe silencioso, igual que decidió Repaso. */}
          <header className="k-hero k-hero--quiet">
            <span className="k-hero__tag">{t("speak.summary.kicker")}</span>
            <h1 className="k-hero__title">
              {t("speak.summary.titlePre")}
              <em>{focus.sound}</em>
              {t("speak.summary.titlePost")}
            </h1>
            <p className="k-hero__dek">{t("speak.summary.dek", { minutes, sound: focus.sound })}</p>
            <p className="k-hero__meta">
              <strong>
                {stats.clear}/{stats.total}
              </strong>{" "}
              {t("speak.summary.stat.clear", { sound: focus.sound })}
              <span aria-hidden="true">·</span>
              <strong>{minutes}</strong> {t("speak.summary.stat.minutes")}
              <span aria-hidden="true">·</span>
              <strong>{toPractice}</strong> {t("speak.summary.stat.toPractice")}
            </p>
          </header>

          <h2 className="k-cap">
            <span>{t("speak.summary.returns")}</span>
            <span className="k-cap__count">{struggled.length}</span>
          </h2>
          <div className="k-live">
            <ul>
              {struggled.map((w) => (
                <li key={w.word}>
                  <div className="k-row k-row--quiet">
                    <span className="k-row__title" lang={targetLanguage}>
                      {w.word}
                    </span>
                    <span className="k-row__meta">
                      {saved?.status === "saved" && w.modelSentence ? t("speak.summary.soon") : "—"}
                    </span>
                    {w.gloss && <span className="k-row__sub">{w.gloss}</span>}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {saved?.status === "failed" && (
            <p className="k-error" role="alert">
              {t("speak.summary.saveFailed")}
            </p>
          )}
          {saved?.status === "saved" && saved.skipped > 0 && (
            <p className="k-note">{t("speak.summary.partial", { count: saved.skipped })}</p>
          )}
        </div>

        <div className="k-dock">
          <div className="k-wrap">
            <button type="button" className="k-btn k-btn--block" onClick={startOver}>
              {t("speak.summary.again")}{" "}
              <span className="k-btn__arrow" aria-hidden="true">
                →
              </span>
            </button>
            <button
              type="button"
              className="k-btn k-btn--ghost k-btn--block"
              onClick={() => navigate("/")}
            >
              {t("speak.summary.home")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Quién actúa ahora, en la línea de estado del dock. En reposo va vacía: lo
  // que hay que hacer lo dice la guía de abajo, y repetirlo aquí sería un eco.
  const stageCap =
    state === "listening"
      ? // The mic verdict replaces the caption only once it has something to
        // say; "silent" keeps the neutral copy so the medallion doesn't nag
        // before the user has spoken.
        micLevel === "silent"
        ? t("speak.stage.listeningCap")
        : t(micLevelKey(micLevel))
      : state === "thinking"
        ? t("speak.stage.thinkingCap")
        : state === "speaking"
          ? t("speak.stage.speakingCap")
          : "";

  const guia =
    state === "idle"
      ? t("speak.hint.idle", { sound: focus.sound })
      : state === "listening"
        ? t("speak.hint.listening")
        : state === "thinking"
          ? t("speak.hint.thinking")
          : t("speak.hint.speaking");

  return (
    <div className="k-app">
      {lineaSuperior(
        <span className="k-chip k-chip--static" title={t("speak.focus.titleAttr")}>
          <span className="k-chip__dot" aria-hidden="true" />
          {t("speak.focus.cap")} {focus.sound}
        </span>,
      )}

      {/* La superficie única: el escenario arriba, la conversación debajo. */}
      <div className="k-fill">
        <Escenario state={state} thinkingLabel={t("speak.stage.thinkingAria")} />

        <div className="k-live" ref={columnRef}>
          <p className="k-cap">{t("speak.transcript.cap", { sound: focus.sound })}</p>
          <ul>
            {effTurns.map((turn, i) => (
              <li key={i} className="k-live__turn" data-who={turn.who}>
                <p className="k-cap">
                  {turn.who === "klara" ? (
                    <KlaraMark size={13} />
                  ) : (
                    <span>{t("speak.transcript.you")}</span>
                  )}
                  <span className="k-cap__count">{turn.time}</span>
                </p>
                <p className="k-live__said" lang={targetLanguage}>
                  {turn.note
                    ? turn.target.split(/(\s+)/).map((part, j) =>
                        // Azure's display transcript carries punctuation
                        // ("fünf," / "fünf.") — strip the edges or a
                        // sentence-final focus word loses its underline.
                        part
                          .replace(/^[\p{P}\p{S}]+|[\p{P}\p{S}]+$/gu, "")
                          .toLowerCase() === turn.note!.word.toLowerCase() ? (
                          <span key={j} data-active="true">
                            {part}
                          </span>
                        ) : (
                          <span key={j}>{part}</span>
                        ),
                      )
                    : turn.target}
                </p>
                {turn.native && <p className="k-note k-note--mono">{turn.native}</p>}

                {turn.note && (
                  /* El apunte — tejido bajo el turno, nunca una pantalla. */
                  <div className="k-note" data-state="fix">
                    <span className="k-note__cap">{t("speak.note.cap")}</span>
                    <p className="k-note__body">
                      {t("speak.note.lead", { sound: focus.sound, word: turn.note.word })}{" "}
                      <span className="k-note__right">{turn.note.shouldIpa}</span>
                    </p>
                    <p className="k-note__body">
                      <span className="k-note__cap">{t("speak.note.how")}</span> {t(focus.tipKey)}
                    </p>
                    {turn.showLegend && (
                      <p className="k-note__body">
                        {t("speak.note.legend", { sound: focus.sound })}
                      </p>
                    )}
                    {/* Los dos controles quedan inertes con el micrófono abierto
                        o un turno en vuelo: sonar el modelo sobre el micrófono
                        abierto puntuaría la voz de Klara como la del usuario. */}
                    <div className="k-note__actions">
                      <button
                        type="button"
                        className="k-rbtn k-rbtn--sm"
                        aria-label={t("speak.note.playAria")}
                        disabled={state === "listening" || state === "thinking"}
                        onClick={() =>
                          speak(turn.note!.modelSentence ?? turn.note!.word, targetLanguage, {
                            mode: "realtime",
                          })
                        }
                      >
                        <IcPlay />
                      </button>
                      <button
                        type="button"
                        className="k-btn k-btn--ghost"
                        disabled={state === "listening" || state === "thinking"}
                        onClick={() => retryWordAgain(turn.note!.word)}
                      >
                        {t("speak.note.retry")}
                        <span className="k-btn__arrow" aria-hidden="true">
                          ↻
                        </span>
                      </button>
                    </div>
                  </div>
                )}
                {turn.clearWord && (
                  <span className="k-chip k-chip--static" data-tone="good">
                    <span className="k-chip__dot" aria-hidden="true" />
                    {t("speak.note.clear", { sound: focus.sound, word: turn.clearWord })}
                  </span>
                )}
                {turn.improvedWord && (
                  <span className="k-chip k-chip--static" data-tone="good">
                    <span className="k-chip__dot" aria-hidden="true" />
                    {t("speak.transcript.improved", {
                      sound: focus.sound,
                      word: turn.improvedWord,
                    })}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="k-dock">
        <div className="k-dock__status">
          <p className="k-cap k-cap--center">
            {stageCap && (
              <span className="k-cap__count" data-tone={state === "listening" ? "live" : undefined}>
                {stageCap}
              </span>
            )}
          </p>
        </div>

        {/* silenciar a Klara · el micrófono (protagonista) · terminar */}
        <div className="k-dock__row">
          <button
            type="button"
            className="k-rbtn"
            data-on={muted}
            aria-pressed={muted}
            onClick={toggleMute}
            aria-label={muted ? t("speak.controls.unmuteAria") : t("speak.controls.muteAria")}
          >
            <IcSound off={muted} />
          </button>
          <button
            type="button"
            className="k-rbtn k-rbtn--rec k-rbtn--ink k-rbtn--lg"
            data-on={state === "listening"}
            aria-pressed={state === "listening"}
            onClick={onMic}
            aria-label={t("speak.controls.micAria")}
          >
            <IcMic />
            <span className="k-rbtn__ring" aria-hidden="true" />
          </button>
          <button
            type="button"
            className="k-rbtn"
            onClick={endSession}
            aria-label={t("speak.controls.endAria")}
          >
            <IcClose />
          </button>
        </div>

        {hint ? (
          <p className="k-error" role="alert">
            {hint}
          </p>
        ) : (
          <p className="k-note k-note--bare">{guia}</p>
        )}
      </div>
    </div>
  );
}
