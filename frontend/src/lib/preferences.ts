import { useEffect, useState } from "react";
import { LANGUAGE_CODES, type LanguageCode } from "./languages";

export type Theme = "light" | "dark";
export type ReadMode = "immersive" | "marginalia" | "parallel";

const KEYS = {
  theme: "klara.theme",
  readMode: "klara.readMode",
  fontScale: "klara.fontScale",
  nativeLang: "klara.nativeLang",
} as const;

export function readCachedNativeLang(): LanguageCode | null {
  if (typeof window === "undefined") return null;
  try {
    const v = window.localStorage.getItem(KEYS.nativeLang);
    return v && (LANGUAGE_CODES as string[]).includes(v) ? (v as LanguageCode) : null;
  } catch {
    return null;
  }
}

// Best-effort match of navigator.language(s) to one of our supported codes.
// Used at first paint (no auth yet) so the login/signup screens render in the
// visitor's language, and to seed `native_language` for brand-new signups.
export function detectBrowserLang(): LanguageCode | null {
  if (typeof navigator === "undefined") return null;
  const candidates = (navigator.languages?.length ? navigator.languages : [navigator.language]) ?? [];
  for (const raw of candidates) {
    if (!raw) continue;
    const code = raw.toLowerCase().split("-")[0];
    if ((LANGUAGE_CODES as string[]).includes(code)) return code as LanguageCode;
  }
  return null;
}

export function writeCachedNativeLang(code: string | null | undefined): void {
  if (typeof window === "undefined") return;
  try {
    if (code) window.localStorage.setItem(KEYS.nativeLang, code);
    else window.localStorage.removeItem(KEYS.nativeLang);
  } catch {
    /* SSR / quota — non-fatal */
  }
}

function readLS<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  if (typeof window === "undefined") return fallback;
  const v = window.localStorage.getItem(key);
  return (allowed as readonly string[]).includes(v ?? "") ? (v as T) : fallback;
}

function readLSNumber(key: string, fallback: number, min: number, max: number): number {
  if (typeof window === "undefined") return fallback;
  const v = window.localStorage.getItem(key);
  if (!v) return fallback;
  const n = Number(v);
  if (Number.isNaN(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

const MODES = ["immersive", "marginalia", "parallel"] as const;

function readTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = window.localStorage.getItem(KEYS.theme);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(readTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (window.localStorage.getItem(KEYS.theme)) return;
      setThemeState(mq.matches ? "dark" : "light");
    };
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, []);

  const setTheme = (t: Theme) => {
    window.localStorage.setItem(KEYS.theme, t);
    setThemeState(t);
  };

  return [theme, setTheme];
}

export function useReadMode(): [ReadMode, (m: ReadMode) => void] {
  const [mode, setMode] = useState<ReadMode>(() => readLS(KEYS.readMode, MODES, "marginalia"));
  useEffect(() => {
    window.localStorage.setItem(KEYS.readMode, mode);
  }, [mode]);
  return [mode, setMode];
}

export function useFontScale(): [number, (n: number) => void] {
  const [scale, setScale] = useState<number>(() => readLSNumber(KEYS.fontScale, 1, 0.85, 1.3));
  useEffect(() => {
    window.localStorage.setItem(KEYS.fontScale, String(scale));
  }, [scale]);
  return [scale, setScale];
}
