import { useEffect, useState } from "react";
import { apiBase } from "./apiBase";
import { speechLocale } from "./languages";
import { authHeaders, isNative } from "./native";

export interface TTSState {
  text: string | null;
  playing: boolean;
  progress: number;
  duration: number;
}

type Listener = (state: TTSState) => void;

const listeners = new Set<Listener>();
let state: TTSState = { text: null, playing: false, progress: 0, duration: 0 };
let audio: HTMLAudioElement | null = null;
let activeLocale: string = "de-DE";

function emit() {
  for (const l of listeners) l(state);
}

function set(patch: Partial<TTSState>) {
  state = { ...state, ...patch };
  emit();
}

/**
 * "realtime" routes to the backend's low-latency TTS model — only Speak's
 * conversational replies want it. Everything else (story sentences, word
 * audio) defaults to the expressive narration model server-side.
 */
export type TTSMode = "narration" | "realtime";

/** A newer speak() won while this one was still downloading. */
export class TtsSuperseded extends Error {}

function ttsUrl(text: string, lang?: string, mode?: TTSMode): string {
  let url = `${apiBase()}/tts?text=${encodeURIComponent(text)}`;
  if (lang) url += `&lang=${encodeURIComponent(lang)}`;
  // Always explicit: the mode also VERSIONS the URL. TTS responses are
  // immutable-cached for a year, so without a new param existing devices
  // would keep replaying the old model's audio from the browser HTTP cache
  // and never hear the narration upgrade. el arnés de audio no vuelve a
  // construir esta URL: el modo entra aquí y en ningún otro sitio.
  url += `&mode=${mode ?? "narration"}`;
  return url;
}

let lastBlobUrl: string | null = null;

/**
 * Where the <audio> element should point. On the web that's the plain URL and
 * the cookie rides along; in the shell the token can't ride on <audio src>, so
 * we fetch with the header and hand over a blob. The previous blob is revoked
 * on every call — otherwise every played sentence leaks a few hundred KB.
 */
async function ttsSource(
  text: string,
  lang?: string,
  mode?: TTSMode,
  isStale: () => boolean = () => false,
): Promise<string> {
  const url = ttsUrl(text, lang, mode);
  if (!isNative()) return url;
  const resp = await fetch(url, {
    headers: await authHeaders(),
    signal: AbortSignal.timeout(15_000),
  });
  if (!resp.ok) throw new Error(`tts fetch failed: ${resp.status}`);
  const objectUrl = URL.createObjectURL(await resp.blob());
  if (isStale()) {
    // A newer speak() won while we were downloading. Drop only what we made:
    // lastBlobUrl now belongs to that newer call and may be playing.
    URL.revokeObjectURL(objectUrl);
    throw new TtsSuperseded("superseded");
  }
  if (lastBlobUrl) URL.revokeObjectURL(lastBlobUrl);
  lastBlobUrl = objectUrl;
  return objectUrl;
}

/** Test seam — do not use in app code. */
export const ttsSourceForTest = ttsSource;

/**
 * Why the playback finished. "interrupted" = stop() ran (a new speak(), a mic
 * tap, navigation) — callers driving a state machine usually treat it as
 * "stop transitioning, someone else owns the state now".
 */
export type TTSDoneReason = "ended" | "error" | "interrupted";

// Exactly-once completion callback for the CURRENT utterance. Speak's state
// machine hangs forever in "speaking" if any finish path (ended, playback
// error, Web Speech fallback, interruption) fails to fire — so every exit
// funnels through settleDone, which clears before calling.
//
// `generation` is the zombie guard: events from a superseded utterance keep
// arriving asynchronously (a pending play() rejects AFTER stop(); a canceled
// SpeechSynthesisUtterance fires onend on a queued task AFTER the next speak()
// registered its callback). Every async handler captures its generation and
// must not settle — or speak — on behalf of a later one.
let onDone: ((reason: TTSDoneReason) => void) | null = null;
let generation = 0;
let pauseRequested = false;

function settleDone(reason: TTSDoneReason): void {
  const cb = onDone;
  onDone = null;
  if (!cb) return;
  // Deferred: stop() runs synchronously inside speak() BEFORE the new
  // utterance registers its onDone/generation/listenerCtrl. A callback that
  // re-entered speak() from here would interleave with that half-initialized
  // state and orphan a listener controller on the shared unlocked element
  // (review finding). The slot above is already cleared, so exactly-once
  // holds; only the invocation moves to a microtask.
  queueMicrotask(() => cb(reason));
}

export function getTTSState(): TTSState {
  return state;
}

export function subscribeTTS(l: Listener): () => void {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

export function useTTS(): TTSState {
  const [s, setS] = useState<TTSState>(getTTSState);
  useEffect(() => subscribeTTS(setS), []);
  return s;
}

// ---- gesture-unlocked persistent element ----------------------------------
// Klara speaks UNPROMPTED after every turn (council decision: F6 revoked).
// Browsers only allow that on an element that has played inside a user
// gesture — so the mic tap "unlocks" one persistent Audio element, and every
// subsequent speak() reuses it via .src. Without this, Safari rejects each
// autoplay and the Web Speech robot voice becomes Klara's default voice.
let unlockedEl: HTMLAudioElement | null = null;
// Per-utterance listener scope: a REUSED element would otherwise accumulate
// one set of listeners per utterance forever.
let listenerCtrl: AbortController | null = null;

const SILENT_WAV =
  "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAAAAA=";

/** Call from inside a user gesture (the mic tap). Idempotent. */
export function unlockAudio(): void {
  if (unlockedEl || typeof window === "undefined") return;
  const a = new Audio(SILENT_WAV);
  // The play() call inside the gesture is what marks the element as
  // user-activated; whether the silent clip actually plays is irrelevant.
  a.play().catch(() => undefined);
  unlockedEl = a;
}

export function speak(
  text: string,
  language?: string,
  opts?: { rate?: number; mode?: TTSMode; onDone?: (reason: TTSDoneReason) => void },
): void {
  stop(); // settles any previous utterance's onDone as "interrupted"
  if (!text.trim()) {
    opts?.onDone?.("ended"); // nothing to say is a completed utterance
    return;
  }
  onDone = opts?.onDone ?? null;
  const gen = ++generation;
  pauseRequested = false;
  // One fallback attempt per utterance, whether the trigger was the error
  // event (load failure) or the play() rejection (autoplay) — on an outright
  // load failure BOTH fire, and double-speaking the reply is worse than none.
  let fellBack = false;
  const tryFallback = () => {
    if (gen !== generation || fellBack) return;
    fellBack = true;
    fallbackWebSpeech(text, activeLocale, gen);
  };
  activeLocale = language ? speechLocale(language) : "de-DE";
  const a = unlockedEl ?? new Audio();
  listenerCtrl = new AbortController();
  const sig = listenerCtrl.signal;
  a.preload = "auto";
  const rate = opts?.rate ?? 1;
  // Reset playback knobs every utterance — the element is reused.
  // preservesPitch keeps Klara's voice natural at non-1.0 rates instead of
  // pitching it up/down like a chipmunk/walrus. Supported in modern browsers;
  // older WebKit ignores it but still applies the rate.
  a.preservesPitch = true;
  a.playbackRate = rate;
  a.addEventListener(
    "loadedmetadata",
    () => {
      if (audio === a && Number.isFinite(a.duration)) set({ duration: a.duration });
    },
    { signal: sig },
  );
  a.addEventListener(
    "timeupdate",
    () => {
      if (audio !== a) return;
      const dur = a.duration || 1;
      set({ progress: a.currentTime / dur, duration: a.duration || state.duration });
    },
    { signal: sig },
  );
  a.addEventListener(
    "ended",
    () => {
      if (audio === a) {
        set({ text: null, playing: false, progress: 0, duration: 0 });
        settleDone("ended");
      }
    },
    { signal: sig },
  );
  let started = false;
  a.addEventListener(
    "error",
    () => {
      if (audio !== a) return;
      audio = null;
      set({ text: null, playing: false, progress: 0, duration: 0 });
      // Never played → outright load failure: give Web Speech one shot (it
      // settles). Mid-stream failure → settle as error; restarting the whole
      // reply from zero in a different voice is worse than stopping.
      if (started) settleDone("error");
      else tryFallback();
    },
    { signal: sig },
  );
  a.addEventListener(
    "pause",
    () => {
      if (audio === a) set({ playing: false });
    },
    { signal: sig },
  );
  a.addEventListener(
    "play",
    () => {
      if (audio === a) {
        started = true;
        set({ playing: true });
      }
    },
    { signal: sig },
  );
  audio = a;
  set({ text, playing: false, progress: 0, duration: 0 });
  void ttsSource(text, language, opts?.mode, () => gen !== generation)
    .then((src) => {
      if (gen !== generation) return;
      a.src = src;
      a.load();
      if (pauseRequested) return; // paused before the audio was even assigned
      a.play().catch((err) => {
        // A pending play() rejects (AbortError) when stop() or a newer speak()
        // paused this element — that utterance is dead; speaking its stale text
        // over whatever the user is doing now would be a real bug, not a fallback.
        if (gen !== generation) return;
        console.warn("TTS playback failed, falling back to Web Speech", err);
        if (audio === a) audio = null;
        tryFallback();
      });
    })
    .catch((err) => {
      if (gen !== generation || err instanceof TtsSuperseded) return;
      if (audio === a) audio = null;
      set({ text: null, playing: false, progress: 0, duration: 0 });
      tryFallback();
    });
}

export function pause(): void {
  pauseRequested = true;
  audio?.pause();
}

export function resume(): void {
  pauseRequested = false;
  audio?.play().catch(() => undefined);
}

export function stop(): void {
  generation++; // invalidate every async handler of the current utterance
  listenerCtrl?.abort(); // detach the utterance's listeners from the (reused) element
  listenerCtrl = null;
  if (audio) {
    audio.pause();
    audio.currentTime = 0;
    audio = null; // the unlocked element itself persists for the next speak()
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  set({ text: null, playing: false, progress: 0, duration: 0 });
  settleDone("interrupted");
}

function fallbackWebSpeech(text: string, locale: string, gen: number): void {
  if (typeof window === "undefined" || !window.speechSynthesis) {
    settleDone("error");
    return;
  }
  const utter = new SpeechSynthesisUtterance(text);
  const langPrefix = locale.split("-")[0].toLowerCase();
  const voice = window.speechSynthesis
    .getVoices()
    .find((v) => v.lang?.toLowerCase().startsWith(langPrefix));
  if (voice) utter.voice = voice;
  utter.lang = voice?.lang ?? locale;
  utter.rate = 0.95;
  // Web Speech is a routine path on Safari (autoplay rejection) — without
  // these, a Speak session would strand in "speaking" forever. The gen check
  // matters: speechSynthesis.cancel() fires the canceled utterance's onend on
  // a QUEUED task, i.e. after the next speak() already registered its onDone —
  // settling here would steal the new utterance's completion.
  utter.onend = () => {
    if (gen === generation) settleDone("ended");
  };
  utter.onerror = () => {
    if (gen === generation) settleDone("error");
  };
  window.speechSynthesis.speak(utter);
}
