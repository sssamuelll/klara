import i18n from "i18next";
import { initReactI18next } from "react-i18next";
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

i18n.use(initReactI18next).init({
  resources,
  lng: "es",
  fallbackLng: "es",
  defaultNS: "common",
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
