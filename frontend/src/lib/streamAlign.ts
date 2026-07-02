/**
 * Aligns live streaming words (append-order, no index — see the backend
 * spec: offsets are temporal and lie) to reference word-token indices.
 *
 * Invariant: may under-paint (return null), never mispaints a position.
 * The authoritative `final` (or batch) repaints everything afterwards.
 */
import { wordTokensByIndex } from "./pronunciation";

const LOOKAHEAD = 3;

export function normalizeWord(w: string): string {
  return w.toLowerCase().trim();
}

export function createAligner(
  referenceText: string,
): (word: string, errorType: string) => number | null {
  const entries = Object.entries(wordTokensByIndex(referenceText))
    .map(([idx, w]) => ({ idx: Number(idx), norm: normalizeWord(w) }))
    .sort((a, b) => a.idx - b.idx);
  let pos = 0; // next unmatched reference token

  return (word, errorType) => {
    if (errorType === "Insertion") return null;
    const norm = normalizeWord(word);
    for (let j = 0; j < LOOKAHEAD && pos + j < entries.length; j++) {
      if (entries[pos + j].norm === norm) {
        const tokenIdx = entries[pos + j].idx;
        pos = pos + j + 1; // skipped tokens stay unpainted; final resolves them
        return tokenIdx;
      }
    }
    return null;
  };
}
