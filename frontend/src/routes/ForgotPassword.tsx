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
      <main className="k-live">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">{t("auth.reset.forgotTitle")}</h1>
          <p className="k-hero__dek">{t("auth.reset.forgotSent")}</p>
        </header>
        <hr className="k-hairline" />
        <p className="k-note">{t("auth.reset.forgotSentHint")}</p>
        <footer className="k-topline k-topline--foot">
          <Link className="k-link" to="/login">{t("common.back")}</Link>
        </footer>
      </main>
    );
  }

  return (
    <main className="k-live">
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{t("auth.reset.forgotTitle")}</h1>
        <p className="k-hero__dek">{t("auth.reset.forgotBody")}</p>
      </header>
      <hr className="k-hairline" />

      {error && <div className="k-error" role="alert">{error}</div>}

      <form onSubmit={onSubmit}>
        <label className="k-field">
          <span className="k-field__label">{t("auth.login.emailLabel")}</span>
          <input
            className="k-field__input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
          />
        </label>

        <div className="k-wrap">
          <button type="submit" className="k-btn" disabled={submitting}>
            {t("auth.reset.forgotSubmit")}
          </button>
        </div>
      </form>

      <footer className="k-topline k-topline--foot">
        <Link className="k-link" to="/login">{t("common.back")}</Link>
      </footer>
    </main>
  );
}
