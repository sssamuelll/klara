import i18n from "../i18n";

/**
 * Etiqueta localizada de "cuándo vuelve esta palabra". Reusa las MISMAS claves y
 * umbrales de la sección Schedule del Finish de historias (story.finish.summary
 * .schedule.*), que ya están espejadas en los 6 locales — sin claves nuevas. Los
 * umbrales (en días) replican backend routers/stories.py `_bucket_for`.
 */
export function humanizeNextReview(nextReviewAt: string): string {
  const delta = (new Date(nextReviewAt).getTime() - Date.now()) / 86_400_000; // días
  const k = (s: string): string => i18n.t(`story.finish.summary.schedule.${s}`);
  if (delta <= 1) return k("dueNow");
  if (delta <= 3) return k("soon");
  if (delta <= 7) return k("thisWeek");
  if (delta <= 14) return k("nextWeek");
  return k("later");
}
