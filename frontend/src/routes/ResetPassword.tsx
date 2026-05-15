import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

export default function ResetPassword() {
  const { t } = useTranslation();
  const navigate = useNavigate();
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
      setTimeout(() => navigate("/login", { replace: true }), 1500);
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <main className="k-page snew">
        <div className="snew__head">
          <h1 className="snew__title">{t("auth.reset.resetTitle")}</h1>
        </div>
        <p className="k-mono" style={{ color: "var(--ink-3)" }}>
          {t("auth.reset.success")}
        </p>
      </main>
    );
  }

  return (
    <main className="k-page snew">
      <div className="snew__head">
        <h1 className="snew__title">{t("auth.reset.resetTitle")}</h1>
      </div>

      {error && <div className="k-error" role="alert">{error}</div>}

      <form onSubmit={onSubmit}>
        <label className="k-mono" style={{ display: "block", marginTop: "1rem" }}>
          {t("auth.reset.newPasswordLabel")}
        </label>
        <input
          className="snew__input"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={submitting || !token}
        />

        <label className="k-mono" style={{ display: "block", marginTop: "1rem" }}>
          {t("auth.reset.confirmLabel")}
        </label>
        <input
          className="snew__input"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          disabled={submitting || !token}
        />

        <div className="snew__actions" style={{ marginTop: "1.5rem" }}>
          <button type="submit" className="k-btn" disabled={submitting || !token}>
            {t("auth.reset.submit")}
          </button>
        </div>

        <p className="k-mono" style={{ marginTop: "1.5rem", color: "var(--ink-3)" }}>
          <Link to="/login">{t("common.back")}</Link>
        </p>
      </form>
    </main>
  );
}
