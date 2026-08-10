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
      <main>
        <h1 className="auth-title">{t("auth.reset.resetTitle")}</h1>
        <p className="auth-sub">{t("auth.reset.success")}</p>
        <div className="auth-actions">
          <Link className="k-btn" to="/login">{t("auth.reset.goLogin")}</Link>
        </div>
      </main>
    );
  }

  return (
    <main>
      <h1 className="auth-title">{t("auth.reset.resetTitle")}</h1>

      {error && <div className="k-error" role="alert">{error}</div>}

      {!token && (
        <div className="k-error" role="alert">{t("auth.reset.error.missingToken")}</div>
      )}

      <form className="auth-form" onSubmit={onSubmit}>
        <div>
          <label className="auth-label" htmlFor="reset-password">
            {t("auth.reset.newPasswordLabel")}
          </label>
          <input
            id="reset-password"
            className="auth-input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting || !token}
          />
        </div>

        <div>
          <label className="auth-label" htmlFor="reset-confirm">
            {t("auth.reset.confirmLabel")}
          </label>
          <input
            id="reset-confirm"
            className="auth-input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            disabled={submitting || !token}
          />
        </div>

        <div className="auth-actions">
          <button type="submit" className="k-btn" disabled={submitting || !token}>
            {t("auth.reset.submit")}
          </button>
        </div>
      </form>

      <p className="auth-links">
        <Link to="/login">{t("common.back")}</Link>
      </p>
    </main>
  );
}
