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
      <header className="k-topline">
        <span className="k-topline__mark">
          <span className="wordmark">Klara</span>
        </span>
        <span className="landing__login">
          <span className="landing__login-q">{t("landing.hero.ctaLoginQuestion")}</span>
          <Link className="landing__login-a" to="/login">{t("landing.hero.ctaLoginAction")}</Link>
        </span>
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
        <h2 className="landing__wl-title">{t("waitlist.title")}</h2>
        <p className="landing__wl-body">{t("waitlist.body")}</p>
        {state === "ok" ? (
          <p className="landing__wl-body" role="status">{t("waitlist.success")}</p>
        ) : (
          // El formulario ya habla k-* aunque la portada siga en su dialecto:
          // era el único sitio fuera de /login que se colgaba de auth.css.
          <form onSubmit={onJoin}>
            <label className="k-field">
              <span className="k-field__label">{t("auth.login.emailLabel")}</span>
              <input
                className="k-field__input"
                type="email"
                autoComplete="email"
                placeholder={t("waitlist.placeholder")}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={state === "sending"}
              />
            </label>
            {state === "error" && (
              <div className="k-error" role="alert">{t(`waitlist.error.${errorKey}`)}</div>
            )}
            <div className="k-wrap">
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
