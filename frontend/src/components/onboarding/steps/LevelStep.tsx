import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../../lib/auth";
import type { CEFRLevel } from "../../../api/types";
import Step, { type StepProps } from "../Step";

const LEVELS: CEFRLevel[] = ["A0", "A1", "A2", "B1", "B2", "C1"];

type Props = Omit<StepProps, "title" | "children" | "continueDisabled" | "continueLabel">;

export default function LevelStep(props: Props) {
  const { t } = useTranslation();
  const { user, patchUser } = useAuth();
  const [level, setLevel] = useState<CEFRLevel>(user?.level ?? "A0");
  const [error, setError] = useState<string | null>(null);
  const [localSubmitting, setLocalSubmitting] = useState(false);

  async function handleContinue() {
    setLocalSubmitting(true);
    setError(null);
    try {
      await patchUser({ level });
      props.onContinue?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    } finally {
      setLocalSubmitting(false);
    }
  }

  return (
    <Step
      {...props}
      title={t("onboarding.level.title")}
      submitting={props.submitting || localSubmitting}
      onContinue={handleContinue}
    >
      {error && <div className="onboarding__error k-mono">{error}</div>}
      <div className="onboarding__level-grid" role="radiogroup" aria-label={t("onboarding.level.title")}>
        {LEVELS.map((l) => (
          <button
            key={l}
            type="button"
            role="radio"
            aria-checked={level === l}
            className={`k-level onboarding__level${level === l ? " onboarding__level--active" : ""}`}
            onClick={() => setLevel(l)}
          >
            {l}
          </button>
        ))}
      </div>
    </Step>
  );
}
