import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

export default function ForgotPassword() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.forgotPassword(email.trim().toLowerCase());
      setSent(true);
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <main>
        <h1 className="auth-title">{t("auth.reset.forgotTitle")}</h1>
        <p className="auth-sub">{t("auth.reset.forgotSent")}</p>
        <p className="auth-sub">{t("auth.reset.forgotSentHint")}</p>
        <p className="auth-links">
          <Link to="/login">{t("common.back")}</Link>
        </p>
      </main>
    );
  }

  return (
    <main>
      <h1 className="auth-title">{t("auth.reset.forgotTitle")}</h1>
      <p className="auth-sub">{t("auth.reset.forgotBody")}</p>

      {error && <div className="k-error" role="alert">{error}</div>}

      <form className="auth-form" onSubmit={onSubmit}>
        <div>
          <label className="auth-label" htmlFor="forgot-email">
            {t("auth.login.emailLabel")}
          </label>
          <input
            id="forgot-email"
            className="auth-input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
          />
        </div>

        <div className="auth-actions">
          <button type="submit" className="k-btn" disabled={submitting}>
            {t("auth.reset.forgotSubmit")}
          </button>
        </div>
      </form>

      <p className="auth-links">
        <Link to="/login">{t("common.back")}</Link>
      </p>
    </main>
  );
}
