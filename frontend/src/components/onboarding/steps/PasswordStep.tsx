import { useTranslation } from "react-i18next";
import PasswordSetForm from "../../PasswordSetForm";
import Step, { type StepProps } from "../Step";

type Props = Omit<
  StepProps,
  "title" | "children" | "continueDisabled" | "continueLabel" | "onContinue"
>;

export default function PasswordStep(props: Props) {
  const { t } = useTranslation();

  return (
    <Step
      {...props}
      title={t("onboarding.password.title")}
      // El "Continuar" del Step se omite: PasswordSetForm gestiona su propio
      // submit. Tras éxito llama onSuccess -> props.onSkip que en el shell es
      // `advance` (avanza al siguiente paso o completa onboarding).
      onContinue={undefined}
    >
      <p className="onboarding__hint">{t("onboarding.password.hint")}</p>
      <PasswordSetForm
        submitLabel={t("onboarding.continue")}
        onSuccess={() => props.onSkip?.()}
      />
    </Step>
  );
}
