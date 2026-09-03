import { useTranslation } from "react-i18next";
import PasswordSetForm from "./PasswordSetForm";

// Blocking screen for an onboarded owner who has no password yet. Reuses
// PasswordSetForm; on success, applyUserResponse updates auth_methods, which
// re-renders ProtectedRoute and lets the user through.
export default function OwnerPasswordGate() {
  const { t } = useTranslation();
  return (
    <main className="k-page">
      <header className="k-hero k-hero--quiet">
        <span className="k-hero__tag">{t("settings.security.kicker")}</span>
        <h1 className="k-hero__title">{t("settings.security.title")}</h1>
        <p className="k-hero__dek">{t("settings.security.gateHint")}</p>
      </header>
      <PasswordSetForm />
    </main>
  );
}
