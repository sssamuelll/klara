import type { TFunction } from "i18next";

import type { GenderRule } from "../api/types";

/**
 * The localized suffix-rule note for a graded gender attempt, or null when no
 * showable rule applies. Extracted from StoryFinish so the in-story cloze and
 * the standalone review render the rule identically.
 */
export function genderRuleNote(
  t: TFunction,
  rule: GenderRule | null,
  correctGender: string | null,
  lemma: string,
): string | null {
  if (!rule || !correctGender) return null;
  const suffix = `-${rule.suffix}`;
  if (rule.is_exception) {
    return t("story.finish.quiz.genderCloze.rule.exception", {
      suffix,
      ruleGender: rule.rule_gender,
      gender: correctGender,
      lemma,
    });
  }
  if (rule.suffix_class === "hard") {
    return t("story.finish.quiz.genderCloze.rule.hard", { suffix, gender: rule.rule_gender });
  }
  return t("story.finish.quiz.genderCloze.rule.tendency", { suffix, gender: rule.rule_gender });
}
