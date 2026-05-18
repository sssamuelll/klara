import type { CEFRLevel } from "../api/types";

/* ============================================================
   Types
   ============================================================ */

// Subset of backend LanguageCode that we offer as a native language in
// onboarding. Intentional product opinion: speakers of these are our first
// audience.
export type NativeLang = "es" | "en" | "pt" | "fr";

// Subset of backend LanguageCode that we offer as a target language. The
// original design module also listed "it", "nl", "sv" — those are filtered
// out here because the backend doesn't support them.
export type TargetLang = "de" | "en" | "fr" | "pt" | "ja";

export type Level = CEFRLevel;

export interface OnboardingData {
  name: string;
  native: NativeLang;
  target: TargetLang;
  level: Level | null;
  context: string;
  password: string;
  passwordConfirm: string;
}

export const INITIAL_DATA: OnboardingData = {
  name: "",
  native: "es",
  target: "de",
  level: null,
  context: "",
  password: "",
  passwordConfirm: "",
};

/* ============================================================
   Shared step prop shape
   ============================================================ */

export interface StepProps {
  data: OnboardingData;
  setField: <K extends keyof OnboardingData>(key: K, value: OnboardingData[K]) => void;
  next: () => void;
  prev: () => void;
}

/* ============================================================
   Language options
   ============================================================ */

export interface NativeLangOption {
  code: NativeLang;
  label: string;
}

export interface TargetLangOption {
  code: TargetLang;
  label: string;
  sub: string;
}

export const NATIVE_LANGS: NativeLangOption[] = [
  { code: "es", label: "Español" },
  { code: "en", label: "English" },
  { code: "pt", label: "Português" },
  { code: "fr", label: "Français" },
];

export const TARGET_LANGS: TargetLangOption[] = [
  { code: "de", label: "Deutsch", sub: "Alemán" },
  { code: "en", label: "English", sub: "Inglés" },
  { code: "fr", label: "Français", sub: "Francés" },
  { code: "pt", label: "Português", sub: "Portugués" },
  { code: "ja", label: "日本語", sub: "Japonés" },
];

/* ============================================================
   Levels
   ============================================================ */

export interface LevelOption {
  code: Level;
  title: string;
  phrase: string;
}

export const LEVELS: LevelOption[] = [
  { code: "A0", title: "Empiezo de cero.", phrase: "Aún no sé decir hola." },
  { code: "A1", title: "Hola, gracias, adiós.", phrase: "Puedo presentarme con esfuerzo." },
  { code: "A2", title: "Cosas básicas.", phrase: "Puedo pedir un café, hablar del clima." },
  { code: "B1", title: "Me defiendo.", phrase: "Trámites y charlas cotidianas, casi siempre bien." },
  { code: "B2", title: "Conversación real.", phrase: "Puedo discutir, opinar, leer noticias." },
  { code: "C1", title: "Casi como en casa.", phrase: "Disfruto novelas, podcasts, cine sin subtítulos." },
];

/* ============================================================
   Rotating context placeholder examples
   ============================================================ */

export const CONTEXT_EXAMPLES: string[] = [
  "Aprendo escuchando podcasts y leyendo prensa…",
  "Vivo en otro país desde hace seis meses, trabajo en una oficina…",
  "Quiero entender a mi suegra en el almuerzo del domingo…",
  "Me cuesta el orden de las palabras y el género de los sustantivos…",
];

/* ============================================================
   Klara's marginalia per chapter step (right column)
   Keys are step indices 1..5 — chapters only (welcome=0, done=last).
   ============================================================ */

export type Whisper = (data: OnboardingData) => string;

export const WHISPERS: Record<number, Whisper> = {
  1: (d) => {
    const trimmed = d.name.trim();
    return trimmed
      ? `Te llamaré ${trimmed.split(/\s+/)[0]}. Anotado.`
      : "El nombre con el que quieres ser leído.";
  },
  2: () => "Hablamos en tu idioma cuando hace falta. Lo demás, en el que quieras aprender.",
  3: () => "Empezaremos un escalón más abajo del que digas.",
  4: () => "Lo que escribas aquí lo lee Klara para elegir mejor.",
  5: () => "Puedes saltarlo y agregarla después en ajustes.",
};
