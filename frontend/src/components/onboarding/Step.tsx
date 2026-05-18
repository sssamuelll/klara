import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

export interface StepProps {
  index: number;
  total: number;
  title: string;
  children: ReactNode;
  onBack?: () => void;
  onContinue?: () => void;
  onSkip?: () => void;
  continueDisabled?: boolean;
  continueLabel?: string;
  submitting?: boolean;
}

export default function Step({
  index,
  total,
  title,
  children,
  onBack,
  onContinue,
  onSkip,
  continueDisabled,
  continueLabel,
  submitting,
}: StepProps) {
  const { t } = useTranslation();
  const stepCounter = `${String(index).padStart(2, "0")} / ${String(total).padStart(2, "0")}`;

  return (
    <main className="k-page onboarding">
      <div className="onboarding__head">
        <span className="k-mono onboarding__kicker">
          {t("onboarding.kicker")} · {stepCounter}
        </span>
        <h1 className="onboarding__title k-serif">{title}</h1>
      </div>
      <hr className="k-rule onboarding__rule" />
      <div className="onboarding__body">{children}</div>
      <hr className="k-rule onboarding__rule" />
      <div className="onboarding__footer">
        {onBack ? (
          <button type="button" className="k-link onboarding__back" onClick={onBack}>
            {t("onboarding.back")}
          </button>
        ) : (
          <span />
        )}
        <div className="onboarding__footer-right">
          {onSkip && (
            <button type="button" className="k-link onboarding__skip" onClick={onSkip}>
              {t("onboarding.skip")}
            </button>
          )}
          {onContinue && (
            <button
              type="button"
              className="k-link onboarding__continue"
              onClick={onContinue}
              disabled={continueDisabled || submitting}
            >
              {submitting ? t("common.loading") : (continueLabel ?? t("onboarding.continue"))}
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
