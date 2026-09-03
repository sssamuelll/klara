import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { apiBase } from "../lib/apiBase";
import { useAuth } from "../lib/auth";
import {
  GoogleCancelled,
  GoogleNotConfigured,
  signInWithGoogleNative,
} from "../lib/googleNative";
import { isNative } from "../lib/native";

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { login, reload } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from ?? "/";

  // Google's OAuth gate 403s (disallowed_useragent) the iOS home-screen web
  // app — its UA lacks the Safari token. navigator.standalone is iOS-only,
  // so Android's installed PWA (normal Chrome UA, allowed) keeps the button;
  // email/password login works everywhere.
  const iosStandalone =
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
  // Inside the Capacitor shell the button stays, but it runs the native flow
  // below — Google blocks the web OAuth gate in a WebView too, and there
  // navigator.standalone is false, so this condition alone would not save us.
  const hideGoogle = iosStandalone && !isNative();

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

  async function onGoogle() {
    setError(null);
    try {
      if (isNative()) {
        await signInWithGoogleNative();
        await reload();
        navigate(from, { replace: true });
        return;
      }
      const resp = await fetch(`${apiBase()}/auth/google/authorize`, {
        credentials: "include",
      });
      if (!resp.ok) throw new Error(`http ${resp.status}`);
      const data = (await resp.json()) as { authorization_url?: string };
      if (!data.authorization_url) throw new Error("no authorization_url");
      window.location.href = data.authorization_url;
    } catch (err) {
      // Dismissing the account picker is not a failure worth a red banner.
      if (err instanceof GoogleCancelled) return;
      setError(
        err instanceof GoogleNotConfigured
          ? t("auth.login.error.googleNativeUnavailable")
          : t("auth.login.error.googleFailed"),
      );
    }
  }

  return (
    <main className="k-live">
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{t("auth.login.title")}</h1>
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

        <label className="k-field">
          <span className="k-field__label">{t("auth.login.passwordLabel")}</span>
          <input
            className="k-field__input"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
          />
        </label>

        <div className="k-wrap">
          <button type="submit" className="k-btn" disabled={submitting}>
            {t("auth.login.submit")}
          </button>
          {!hideGoogle && (
            <button
              type="button"
              className="k-btn k-btn--ghost"
              onClick={onGoogle}
              disabled={submitting}
            >
              {t("auth.login.googleBtn")}
            </button>
          )}
        </div>
      </form>

      <footer className="k-topline k-topline--foot">
        <Link className="k-link" to="/forgot">{t("auth.login.forgotLink")}</Link>
      </footer>
    </main>
  );
}
