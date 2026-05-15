import { useEffect, useState } from "react";
import { speechLocale } from "./languages";

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

function ttsUrl(text: string): string {
  return `/api/v1/tts?text=${encodeURIComponent(text)}`;
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

export function speak(text: string, language?: string): void {
  stop();
  if (!text.trim()) return;
  activeLocale = language ? speechLocale(language) : "de-DE";
  const a = new Audio(ttsUrl(text));
  a.preload = "auto";
  a.addEventListener("loadedmetadata", () => {
    if (audio === a && Number.isFinite(a.duration)) set({ duration: a.duration });
  });
  a.addEventListener("timeupdate", () => {
    if (audio !== a) return;
    const dur = a.duration || 1;
    set({ progress: a.currentTime / dur, duration: a.duration || state.duration });
  });
  a.addEventListener("ended", () => {
    if (audio === a) set({ text: null, playing: false, progress: 0, duration: 0 });
  });
  a.addEventListener("pause", () => {
    if (audio === a) set({ playing: false });
  });
  a.addEventListener("play", () => {
    if (audio === a) set({ playing: true });
  });
  audio = a;
  set({ text, playing: false, progress: 0, duration: 0 });
  a.play().catch((err) => {
    console.warn("TTS playback failed, falling back to Web Speech", err);
    fallbackWebSpeech(text, activeLocale);
  });
}

export function pause(): void {
  audio?.pause();
}

export function resume(): void {
  audio?.play().catch(() => undefined);
}

export function stop(): void {
  if (audio) {
    audio.pause();
    audio.currentTime = 0;
    audio = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  set({ text: null, playing: false, progress: 0, duration: 0 });
}

function fallbackWebSpeech(text: string, locale: string): void {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  const utter = new SpeechSynthesisUtterance(text);
  const langPrefix = locale.split("-")[0].toLowerCase();
  const voice = window.speechSynthesis
    .getVoices()
    .find((v) => v.lang?.toLowerCase().startsWith(langPrefix));
  if (voice) utter.voice = voice;
  utter.lang = voice?.lang ?? locale;
  utter.rate = 0.95;
  window.speechSynthesis.speak(utter);
}
