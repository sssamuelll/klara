export type LanguageCode = "de" | "en" | "fr" | "ja" | "pt" | "es";

export interface LanguageInfo {
  label: string;
  speechLocale: string;
}

export const SUPPORTED_LANGUAGES: Record<LanguageCode, LanguageInfo> = {
  de: { label: "Deutsch", speechLocale: "de-DE" },
  en: { label: "English", speechLocale: "en-US" },
  fr: { label: "Français", speechLocale: "fr-FR" },
  ja: { label: "日本語", speechLocale: "ja-JP" },
  pt: { label: "Português", speechLocale: "pt-PT" },
  es: { label: "Español", speechLocale: "es-ES" },
};

export const LANGUAGE_CODES: LanguageCode[] = ["de", "en", "fr", "ja", "pt", "es"];

export function languageLabel(code: string): string {
  return SUPPORTED_LANGUAGES[code as LanguageCode]?.label ?? code;
}

export function speechLocale(code: string): string {
  return SUPPORTED_LANGUAGES[code as LanguageCode]?.speechLocale ?? code;
}
