import i18n from "../i18n";
import type { CardOut, ReviewRating } from "../api/types";

/**
 * Client mirror of backend `schedule_next_review` (services/srs_engine.py, SM-2
 * lite). Projects the next interval (in days) each rating would produce for a
 * card, so the review buttons can show honest, per-card costs. If this drifts
 * from the backend, move the projection onto CardOut instead of mirroring here.
 */
const LEARNING_STATES = new Set(["new", "learning", "relearning"]);

export function projectIntervals(
  card: Pick<CardOut, "state" | "interval_days" | "ease">,
): Record<ReviewRating, number> {
  const again = 0.0069; // ~10 min, every state
  if (LEARNING_STATES.has(card.state)) {
    return { again, hard: 0.04, good: 1, easy: 4 };
  }
  const base = Math.max(card.interval_days, 1);
  return {
    again,
    hard: round2(base * 1.2),
    good: round2(base * card.ease),
    easy: round2(base * card.ease * 1.3),
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

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
  return k("months", Math.max(1, Math.round(days / 30)));
}
