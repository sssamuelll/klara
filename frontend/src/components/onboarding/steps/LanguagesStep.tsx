import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../../../lib/auth";
import { LANGUAGE_CODES, languageLabel } from "../../../lib/languages";
import type { LanguageCode } from "../../../api/types";
import Step, { type StepProps } from "../Step";

type Props = Omit<StepProps, "title" | "children" | "continueDisabled" | "continueLabel">;

export default function LanguagesStep(props: Props) {
  const { t } = useTranslation();
  const { user, patchUser } = useAuth();
  const [nativeLang, setNativeLang] = useState<LanguageCode>(user?.native_language ?? "es");
  const [targetLang, setTargetLang] = useState<LanguageCode>(user?.target_language ?? "de");
  const [error, setError] = useState<string | null>(null);
  const [localSubmitting, setLocalSubmitting] = useState(false);

  const sameLang = nativeLang === targetLang;
  const valid = !sameLang;

  async function handleContinue() {
    if (!valid) return;
    setLocalSubmitting(true);
    setError(null);
    try {
      await patchUser({ native_language: nativeLang, target_language: targetLang });
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
      title={t("onboarding.languages.title")}
      continueDisabled={!valid}
      submitting={props.submitting || localSubmitting}
      onContinue={handleContinue}
    >
      {error && <div className="onboarding__error k-mono">{error}</div>}
      {sameLang && (
        <div className="onboarding__error k-mono">{t("settings.error.sameLang")}</div>
      )}
      <label className="onboarding__field">
        <span className="k-mono">{t("onboarding.languages.native")}</span>
        <select
          value={nativeLang}
          onChange={(e) => setNativeLang(e.target.value as LanguageCode)}
        >
          {LANGUAGE_CODES.map((c) => (
            <option key={c} value={c}>{languageLabel(c)}</option>
          ))}
        </select>
      </label>
      <label className="onboarding__field">
        <span className="k-mono">{t("onboarding.languages.target")}</span>
        <select
          value={targetLang}
          onChange={(e) => setTargetLang(e.target.value as LanguageCode)}
        >
          {LANGUAGE_CODES.map((c) => (
            <option key={c} value={c}>{languageLabel(c)}</option>
          ))}
        </select>
      </label>
    </Step>
  );
}
