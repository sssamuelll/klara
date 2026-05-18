import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../../lib/auth";
import Step, { type StepProps } from "../Step";

type Props = Omit<StepProps, "title" | "children" | "continueDisabled" | "continueLabel">;

export default function NameStep(props: Props) {
  const { t } = useTranslation();
  const { user, patchUser } = useAuth();
  const [value, setValue] = useState(user?.display_name ?? "");
  const [error, setError] = useState<string | null>(null);
  const [localSubmitting, setLocalSubmitting] = useState(false);

  const trimmed = value.trim();
  const valid = trimmed.length > 0 && trimmed.length <= 100;

  async function handleContinue() {
    if (!valid) return;
    setLocalSubmitting(true);
    setError(null);
    try {
      await patchUser({ display_name: trimmed });
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
      title={t("onboarding.name.title")}
      continueDisabled={!valid}
      submitting={props.submitting || localSubmitting}
      onContinue={handleContinue}
    >
      {error && <div className="onboarding__error k-mono">{error}</div>}
      <label className="onboarding__field">
        <span className="k-mono">{t("onboarding.name.label")}</span>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          maxLength={100}
          placeholder={t("onboarding.name.placeholder")}
          autoFocus
        />
      </label>
    </Step>
  );
}
