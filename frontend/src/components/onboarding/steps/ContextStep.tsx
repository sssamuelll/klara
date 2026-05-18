import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../../lib/auth";
import Step, { type StepProps } from "../Step";

type Props = Omit<StepProps, "title" | "children" | "continueDisabled" | "continueLabel">;

export default function ContextStep(props: Props) {
  const { t } = useTranslation();
  const { user, patchUser } = useAuth();
  const [value, setValue] = useState(user?.learning_context ?? "");
  const [error, setError] = useState<string | null>(null);
  const [localSubmitting, setLocalSubmitting] = useState(false);

  async function handleContinue() {
    const trimmed = value.trim();
    setLocalSubmitting(true);
    setError(null);
    try {
      await patchUser({ learning_context: trimmed ? trimmed : null });
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
      title={t("onboarding.context.title")}
      submitting={props.submitting || localSubmitting}
      onContinue={handleContinue}
    >
      {error && <div className="onboarding__error k-mono">{error}</div>}
      <label className="onboarding__field">
        <span className="k-mono">{t("onboarding.context.label")}</span>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          maxLength={500}
          rows={6}
          placeholder={t("onboarding.context.placeholder")}
        />
        <span className="k-mono onboarding__char-counter">{value.length} / 500</span>
      </label>
    </Step>
  );
}
