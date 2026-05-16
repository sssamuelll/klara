import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import { detectBrowserLang } from "../lib/preferences";

export default function Signup() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError(t("auth.signup.error.passwordMismatch"));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await signup({
        email: email.trim().toLowerCase(),
        password,
        native_language: detectBrowserLang() ?? undefined,
      });
      navigate("/", { replace: true });
    } catch (e2) {
      const msg = e2 instanceof Error ? e2.message : String(e2);
      if (msg.includes("403")) {
        setError(t("auth.signup.error.allowlist"));
      } else {
        setError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="k-page snew">
      <div className="snew__head">
        <h1 className="snew__title">{t("auth.signup.title")}</h1>
      </div>

      {error && <div className="k-error" role="alert">{error}</div>}

      <form onSubmit={onSubmit}>
        <label className="k-mono" style={{ display: "block", marginTop: "1rem" }}>
          {t("auth.signup.emailLabel")}
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
          {t("auth.signup.passwordLabel")}
        </label>
        <input
          className="snew__input"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={submitting}
        />

        <label className="k-mono" style={{ display: "block", marginTop: "1rem" }}>
          {t("auth.signup.confirmLabel")}
        </label>
        <input
          className="snew__input"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          disabled={submitting}
        />

        <div className="snew__actions" style={{ marginTop: "1.5rem" }}>
          <button type="submit" className="k-btn" disabled={submitting}>
            {t("auth.signup.submit")}
          </button>
          <a className="k-btn k-btn--ghost" href="/api/v1/auth/google/authorize">
            {t("auth.signup.googleBtn")}
          </a>
        </div>

        <p className="k-mono" style={{ marginTop: "1.5rem", color: "var(--ink-3)" }}>
          <Link to="/login">{t("auth.signup.loginLink")}</Link>
        </p>
      </form>
    </main>
  );
}
