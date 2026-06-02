/**
 * Practice ("Pronunciar") queue — data model + MOCK source.
 *
 * Scope (this PR): frontend only, with a hard-coded mock queue. In the next
 * PR this is swapped for `GET /api/v1/practice/queue`, which returns the same
 * `PracticeItem[]` shape — so the swap is trivial: replace `buildMockQueue`
 * with a fetch and keep everything downstream unchanged.
 *
 * The scheduler (backend) produces the queue from two sources:
 *   - reason "struggled" → words the learner mispronounced recently.
 *   - reason "review"    → items due by spaced repetition (SRS).
 *
 * Per the product decision: the queue is modelled to carry an origin sentence
 * plus level-generated alternatives. The mock only fills the origin sentence
 * (`variants` empty); variety-by-level arrives with the endpoint. Origin
 * sentence first, variety later.
 */

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

// ---------------------------------------------------------------------------
// MOCK QUEUE — mirrors the handoff's SAMPLE_STORY (Bürgeramt, A2→B1) and the
// hard-coded PRACTICE_PICK. Shaped exactly like the future endpoint payload
// so the real fetch is a drop-in. DELETE-ME-ON-ENDPOINT marks the seam.
// ---------------------------------------------------------------------------

const MOCK_SOURCE_TITLE = "El sello que tarda diez minutos.";

interface MockPick {
  target: string;
  native: string;
  focusText: string;
  focusTx: string;
  reason: PracticeReason;
}

// Origin sentences + focus words, lifted from the handoff sample so the
// mock reads like real content. Order = the scheduler's intended order.
const MOCK_PICKS: MockPick[] = [
  {
    target: "Die Nummer auf dem Bildschirm wechselt. Ich bin dran.",
    native: "El número en la pantalla cambia. Es mi turno.",
    focusText: "dran",
    focusTx: "es mi turno",
    reason: "struggled",
  },
  {
    target: "Guten Tag. Ich möchte mich anmelden.",
    native: "Buenos días. Necesito registrar mi domicilio.",
    focusText: "anmelden",
    focusTx: "registrar(se)",
    reason: "review",
  },
  {
    target:
      "Reisepass, Mietvertrag und Wohnungsgeberbestätigung?",
    native: "¿Pasaporte, contrato de alquiler y la confirmación del propietario?",
    focusText: "Wohnungsgeberbestätigung",
    focusTx: "confirmación del propietario",
    reason: "struggled",
  },
  {
    target: "Sie nickt, ohne aufzusehen.",
    native: "Ella asiente sin levantar la vista.",
    focusText: "nickt",
    focusTx: "asentir con la cabeza",
    reason: "review",
  },
  {
    target: "Ich reiche ihr die drei Papiere, geordnet, wie Klara es mir gesagt hat.",
    native: "Le entrego los tres papeles, ordenados como Klara me dijo.",
    focusText: "reiche",
    focusTx: "alcanzar, entregar",
    reason: "struggled",
  },
  {
    target: "Zehn Minuten. Setzen Sie sich.",
    native: "Diez minutos. Tome asiento.",
    focusText: "Setzen",
    focusTx: "sentar",
    reason: "review",
  },
];

/**
 * Build today's practice queue. MOCK: returns a fixed set shaped like the
 * future endpoint. Swap this body for `await api.getPracticeQueue()` in the
 * 2nd PR; nothing downstream changes.
 */
export function buildMockQueue(): PracticeQueue {
  return {
    targetLanguage: "de",
    sourceTitle: MOCK_SOURCE_TITLE,
    items: MOCK_PICKS.map((p) => ({
      sentence: { target: p.target, native: p.native },
      variants: [], // populated by the endpoint (2nd PR), not the mock.
      source: MOCK_SOURCE_TITLE,
      focusText: p.focusText,
      focusTx: p.focusTx,
      reason: p.reason,
    })),
  };
}

export function countByReason(items: PracticeItem[], reason: PracticeReason): number {
  return items.filter((i) => i.reason === reason).length;
}
