import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from ?? "/";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim().toLowerCase(), password);
      navigate(from, { replace: true });
    } catch {
      setError(t("auth.login.error.invalidCredentials"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="k-page snew">
      <div className="snew__head">
        <h1 className="snew__title">{t("auth.login.title")}</h1>
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

        <label className="k-mono" style={{ display: "block", marginTop: "1rem" }}>
          {t("auth.login.passwordLabel")}
        </label>
        <input
          className="snew__input"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={submitting}
        />

        <div className="snew__actions" style={{ marginTop: "1.5rem" }}>
          <button type="submit" className="k-btn" disabled={submitting}>
            {t("auth.login.submit")}
          </button>
          <a className="k-btn k-btn--ghost" href="/api/v1/auth/google/authorize">
            {t("auth.login.googleBtn")}
          </a>
        </div>

        <p className="k-mono" style={{ marginTop: "1.5rem", color: "var(--ink-3)" }}>
          <Link to="/forgot">{t("auth.login.forgotLink")}</Link>
        </p>
      </form>
    </main>
  );
}
