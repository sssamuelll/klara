import i18n from "../i18n";

/**
 * Display-only formatting for review intervals. The projection itself lives in
 * the backend FSRS engine and arrives precomputed in `CardOut.next_intervals`
 * (days per rating) — nothing here mirrors the scheduler anymore.
 */

/** Short localized label for an interval in days (recall.interval.* keys). */
export function formatInterval(days: number): string {
  const k = (s: string, count: number): string =>
    i18n.t(`recall.interval.${s}`, { count });
  // Cutoff at 30 min (not 60): the "again" step (~10 min) must read as
  // minutes and the learning "hard" step (~57.6 min, i.e. "~1h") must read
  // as hours — a 1h cutoff puts both under it since 57.6 < 60.
  if (days < 1 / 48) return k("minutes", Math.max(1, Math.round(days * 24 * 60)));
  if (days < 1) return k("hours", Math.max(1, Math.round(days * 24)));
  if (days < 7) {
    const d = Math.round(days);
    return k(d === 1 ? "day" : "days", d);
  }
  if (days < 30) return k("weeks", Math.max(1, Math.round(days / 7)));
  const m = Math.max(1, Math.round(days / 30));
  return k(m === 1 ? "month" : "months", m);
}
