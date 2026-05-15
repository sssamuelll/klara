import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { readCachedNativeLang } from "../lib/preferences";
import es from "../locales/es/common.json";
import en from "../locales/en/common.json";
import de from "../locales/de/common.json";
import fr from "../locales/fr/common.json";
import ja from "../locales/ja/common.json";
import pt from "../locales/pt/common.json";

export const resources = {
  es: { common: es },
  en: { common: en },
  de: { common: de },
  fr: { common: fr },
  ja: { common: ja },
  pt: { common: pt },
} as const;

// Bootstrap with the cached native language so returning users see their UI in
// the right locale on first paint (and the first GET /me carries the correct
// Accept-Language). Falls back to es for first-time visitors.
i18n.use(initReactI18next).init({
  resources,
  lng: readCachedNativeLang() ?? "es",
  fallbackLng: "es",
  defaultNS: "common",
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
