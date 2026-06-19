import { useTranslation } from "react-i18next";
import PasswordSetForm from "./PasswordSetForm";

// Blocking screen for an onboarded owner who has no password yet. Reuses
// PasswordSetForm; on success, applyUserResponse updates auth_methods, which
// re-renders ProtectedRoute and lets the user through.
export default function OwnerPasswordGate() {
  const { t } = useTranslation();
  return (
    <main className="k-page snew">
      <div className="snew__head">
        <span className="k-mono">{t("settings.security.kicker")}</span>
        <h1 className="snew__title">{t("settings.security.title")}</h1>
      </div>
      <p className="snew__sub" style={{ marginTop: "0.5rem" }}>
        {t("settings.security.gateHint")}
      </p>
      <div style={{ marginTop: "1.5rem" }}>
        <PasswordSetForm />
      </div>
    </main>
  );
}
