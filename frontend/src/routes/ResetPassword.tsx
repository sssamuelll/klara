import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

export default function ResetPassword() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError(t("auth.signup.error.passwordMismatch"));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <main className="k-live">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">{t("auth.reset.resetTitle")}</h1>
          <p className="k-hero__dek">{t("auth.reset.success")}</p>
        </header>
        <hr className="k-hairline" />
        <div className="k-wrap">
          <Link className="k-btn" to="/login">{t("auth.reset.goLogin")}</Link>
        </div>
      </main>
    );
  }

  return (
    <main className="k-live">
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{t("auth.reset.resetTitle")}</h1>
      </header>
      <hr className="k-hairline" />

      {error && <div className="k-error" role="alert">{error}</div>}

      {!token && (
        <div className="k-error" role="alert">{t("auth.reset.error.missingToken")}</div>
      )}

      <form onSubmit={onSubmit}>
        <label className="k-field">
          <span className="k-field__label">{t("auth.reset.newPasswordLabel")}</span>
          <input
            className="k-field__input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting || !token}
          />
        </label>

        <label className="k-field">
          <span className="k-field__label">{t("auth.reset.confirmLabel")}</span>
          <input
            className="k-field__input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            disabled={submitting || !token}
          />
        </label>

        <div className="k-wrap">
          <button type="submit" className="k-btn" disabled={submitting || !token}>
            {t("auth.reset.submit")}
          </button>
        </div>
      </form>

      <footer className="k-topline k-topline--foot">
        <Link className="k-link" to="/login">{t("common.back")}</Link>
      </footer>
    </main>
  );
}
