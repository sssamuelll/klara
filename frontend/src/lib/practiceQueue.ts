/**
 * Practice ("Pronunciar") queue — data model + fetch.
 *
 * The queue is served by `GET /api/v1/practice/queue` and deserializes
 * straight into `PracticeQueue` (the backend emits the camelCase field names
 * this contract expects). The component layer is endpoint-agnostic: it calls
 * `loadPracticeQueue()` and renders whatever `PracticeItem[]` comes back.
 *
 * The scheduler (backend) produces the queue from two sources:
 *   - reason "struggled" → words the learner mispronounced recently.
 *   - reason "review"    → items due by spaced repetition (SRS).
 *
 * Scope today: the endpoint is STRUGGLED-ONLY — `variants` arrives empty and
 * no "review" items are produced yet (SRS-due items are deferred until the
 * origin-sentence resolution for an SRS lemma is settled). The contract
 * already carries both, so neither this type nor the component changes when
 * review items and variety-by-level land.
 */

import { api } from "../api/client";
import type { LanguageCode } from "./languages";

export type PracticeReason = "struggled" | "review";

/** Sentence shape a Practice item carries — matches StorySentence's spoken/
 * scored contract (`target` is the line said aloud; `native` is the gloss). */
export interface PracticeSentence {
  target: string;
  native: string;
}

export interface PracticeItem {
  /** The origin sentence: the line the learner actually read. */
  sentence: PracticeSentence;
  /**
   * Level-generated alternative phrasings of the same focus word. Empty in
   * the mock; populated by the queue endpoint (2nd PR) to add variety without
   * re-reading the origin story. Origin sentence is always `sentence`.
   */
  variants: PracticeSentence[];
  /** Title of the story this line came from. */
  source: string;
  /** The word to "nail" in this item. */
  focusText: string;
  /** Its translation in the learner's native language. */
  focusTx: string;
  /** Why this item is in today's set. */
  reason: PracticeReason;
}

export interface PracticeQueue {
  items: PracticeItem[];
  /** Target language of the items (what the mic scores against). */
  targetLanguage: LanguageCode;
  /** Source story title, for the setup/summary signature line. */
  sourceTitle: string;
}

/**
 * Fetch today's practice queue from `GET /api/v1/practice/queue`. The payload
 * is already in `PracticeQueue` shape, so this is a thin pass-through; the
 * function exists as the single seam the component talks to.
 */
export async function loadPracticeQueue(): Promise<PracticeQueue> {
  return api.getPracticeQueue();
}

export function countByReason(items: PracticeItem[], reason: PracticeReason): number {
  return items.filter((i) => i.reason === reason).length;
}
