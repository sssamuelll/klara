import { useTranslation } from "react-i18next";

export function mastheadDate(locale: string, d: Date = new Date(), city = "Nürnberg"): string {
  const wd = new Intl.DateTimeFormat(locale, { weekday: "short" }).format(d);
  const dd = String(d.getDate()).padStart(2, "0");
  const mo = new Intl.DateTimeFormat(locale, { month: "short" }).format(d);
  const yyyy = d.getFullYear();
  return `${wd.toUpperCase()} ${dd} ${mo.toUpperCase()} ${yyyy} · ${city.toUpperCase()}`;
}

export function useMastheadDate(d: Date = new Date(), city = "Nürnberg"): string {
  const { i18n } = useTranslation();
  return mastheadDate(i18n.language, d, city);
}

export function useGreeting(d: Date = new Date()): string {
  const { t } = useTranslation();
  const h = d.getHours();
  if (h < 12) return t("home.greeting.morning");
  if (h < 19) return t("home.greeting.afternoon");
  return t("home.greeting.evening");
}
