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
      <main className="k-page snew">
        <div className="snew__head">
          <h1 className="snew__title">{t("auth.reset.forgotTitle")}</h1>
        </div>
        <p className="k-mono" style={{ color: "var(--ink-3)" }}>
          {t("auth.reset.forgotSent")}
        </p>
        <p className="k-mono" style={{ marginTop: "0.75rem", color: "var(--ink-3)" }}>
          {t("auth.reset.forgotSentHint")}
        </p>
        <p className="k-mono" style={{ marginTop: "1rem" }}>
          <Link to="/login">{t("common.back")}</Link>
        </p>
      </main>
    );
  }

  return (
    <main className="k-page snew">
      <div className="snew__head">
        <h1 className="snew__title">{t("auth.reset.forgotTitle")}</h1>
      </div>

      {error && <div className="k-error" role="alert">{error}</div>}

      <form onSubmit={onSubmit}>
        <label className="k-mono" style={{ display: "block", marginTop: "1rem" }}>
          {t("auth.login.emailLabel")}
        </label>
        <input
          className="snew__input"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={submitting}
        />

        <div className="snew__actions" style={{ marginTop: "1.5rem" }}>
          <button type="submit" className="k-btn" disabled={submitting}>
            {t("auth.reset.forgotSubmit")}
          </button>
        </div>

        <p className="k-mono" style={{ marginTop: "1.5rem", color: "var(--ink-3)" }}>
          <Link to="/login">{t("common.back")}</Link>
        </p>
      </form>
    </main>
  );
}
