import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import { api } from "../api/client";
import NameStep from "../components/onboarding/steps/NameStep";
import LanguagesStep from "../components/onboarding/steps/LanguagesStep";
import LevelStep from "../components/onboarding/steps/LevelStep";
import ContextStep from "../components/onboarding/steps/ContextStep";
import PasswordStep from "../components/onboarding/steps/PasswordStep";

export default function Onboarding() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, applyUserResponse } = useAuth();
  const [stepIndex, setStepIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const stepIds = useMemo(() => {
    const base = ["name", "languages", "level", "context"];
    if (user && !user.auth_methods.includes("password")) base.push("password");
    return base;
  }, [user?.auth_methods]);

  if (!user) {
    return <main className="k-page">{t("common.loading")}</main>;
  }

  const total = stepIds.length;

  function back() {
    setStepIndex((i) => Math.max(0, i - 1));
  }

  async function advance() {
    if (stepIndex < total - 1) {
      setStepIndex((i) => i + 1);
      return;
    }
    setSubmitting(true);
    try {
      const updated = await api.completeOnboarding();
      applyUserResponse(updated);
      navigate("/", { replace: true });
    } finally {
      setSubmitting(false);
    }
  }

  const stepProps = {
    index: stepIndex + 1,
    total,
    onBack: stepIndex > 0 ? back : undefined,
    onContinue: advance,
    submitting,
  };

  const id = stepIds[stepIndex];
  if (id === "name") return <NameStep {...stepProps} />;
  if (id === "languages") return <LanguagesStep {...stepProps} />;
  if (id === "level") return <LevelStep {...stepProps} />;
  if (id === "context") return <ContextStep {...stepProps} onSkip={advance} />;
  if (id === "password") return <PasswordStep {...stepProps} onSkip={advance} />;

  return <main className="k-page">{t("common.loading")}</main>;
}
