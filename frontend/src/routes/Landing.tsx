import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../api/client";

type WlState = "idle" | "sending" | "ok" | "error";

export default function Landing() {
  const { t, i18n } = useTranslation();
  const [email, setEmail] = useState("");
  const [state, setState] = useState<WlState>("idle");
  const [errorKey, setErrorKey] = useState<"invalid" | "network">("network");

  async function onJoin(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    try {
      await api.joinWaitlist(email.trim().toLowerCase(), i18n.language);
      setState("ok");
    } catch (err) {
      setErrorKey(err instanceof ApiError && err.status === 422 ? "invalid" : "network");
      setState("error");
    }
  }

  return (
    <div className="landing">
      <header className="m3-top">
        <span className="marca">
          <span className="wordmark">Klara</span>
        </span>
        <Link to="/login">{t("landing.hero.ctaLogin")}</Link>
      </header>

      <section>
        <h1 className="landing__tagline">{t("landing.hero.tagline")}</h1>
        <p className="landing__support">{t("landing.hero.support")}</p>
        <a className="k-btn" href="#waitlist">{t("landing.hero.ctaPrimary")}</a>
      </section>

      <section>
        {(["leer", "hablar", "repasar"] as const).map((k) => (
          <div className="landing__bloque" key={k}>
            <h2>{t(`landing.que.${k}.title`)}</h2>
            <p>{t(`landing.que.${k}.body`)}</p>
          </div>
        ))}
      </section>

      <section id="waitlist" className="landing__wl">
        <h2 className="auth-title">{t("waitlist.title")}</h2>
        <p className="landing__support">{t("waitlist.body")}</p>
        {state === "ok" ? (
          <p className="auth-sub" role="status">{t("waitlist.success")}</p>
        ) : (
          <form className="auth-form" onSubmit={onJoin}>
            <div>
              <label className="auth-label" htmlFor="wl-email">{t("auth.login.emailLabel")}</label>
              <input
                id="wl-email"
                className="auth-input"
                type="email"
                autoComplete="email"
                placeholder={t("waitlist.placeholder")}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={state === "sending"}
              />
            </div>
            {state === "error" && (
              <div className="k-error" role="alert">{t(`waitlist.error.${errorKey}`)}</div>
            )}
            <div className="auth-actions">
              <button type="submit" className="k-btn" disabled={state === "sending"}>
                {t("waitlist.submit")}
              </button>
            </div>
          </form>
        )}
        <p className="landing__wl-note">{t("waitlist.privacyNote")}</p>
      </section>

      <footer className="landing__footer">
        <span>{t("landing.footer.copyright")}</span>
        <a href="mailto:samueldarioballesteros@gmail.com">{t("landing.footer.contact")}</a>
      </footer>
    </div>
  );
}
