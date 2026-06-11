/**
 * The session's target sound, per target language. v1 ships GERMAN ONLY —
 * each additional language must arrive WITH its Azure IPA phoneme validation
 * (the matching set lives server-side in services/speak_analysis.py;
 * FOCUS_PHONEME_SETS there is the source of truth for correctness, this
 * table is its display mirror).
 *
 * PROD-later: chosen by a scheduler from the learner's weak phonemes. That
 * scheduler's only future data source is the StudySession rows /speak/finish
 * writes today.
 */

export interface SpeakFocus {
  /** Display form of the sound ("ü") — shown in the chip, sent to the LLM. */
  sound: string;
  /** Display IPA ("[yː]") for the chip. */
  ipa: string;
  /** i18n key for the articulation tip (speak.focus.tip.*). */
  tipKey: string;
  /** Words that elicit the sound — steer the LLM, never shown raw. */
  examples: string[];
  /**
   * Klara's static opener, in the TARGET language (conversation data, not UI
   * copy — it stays German whatever the UI locale; the native gloss is the
   * i18n key speak.opener.native). Text-only in idle: no autoplay fight with
   * the browser (spec review F6).
   */
  openerTarget: string;
}

const FOCUS_BY_LANGUAGE: Record<string, SpeakFocus> = {
  de: {
    sound: "ü",
    ipa: "[yː]",
    tipKey: "speak.focus.tip.de_ue",
    examples: ["fünf", "Tür", "Bürgeramt", "über", "müde", "früh"],
    openerTarget: "Heute üben wir das ü. Wie war dein Tag — musstest du irgendwo warten?",
  },
};

/** null ⇒ Speak isn't available for this target language yet (honest gate). */
export function getSpeakFocus(targetLanguage: string): SpeakFocus | null {
  return FOCUS_BY_LANGUAGE[targetLanguage.split("-")[0].toLowerCase()] ?? null;
}
