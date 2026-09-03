import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../api/client";

type WlState = "idle" | "sending" | "ok" | "error";

const PROMESAS = ["leer", "hablar", "repasar"] as const;

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

  // La portada entra en el cascarón: 430px, filetes laterales y el inset de
  // arriba los pone `.k-app`/`.k-page`, y el scroll —la portada es la única
  // ruta pública que crece— lo pone su `.k-live`, como las cinco de auth.
  return (
    <div className="k-app">
      <div className="k-page">
        <header className="k-topline">
          <span className="k-topline__mark">
            <span className="wordmark">Klara</span>
          </span>
          <span className="k-topline__meta">
            {t("landing.hero.ctaLoginQuestion")}{" "}
            <Link className="k-link" to="/login">{t("landing.hero.ctaLoginAction")}</Link>
          </span>
        </header>

        <main className="k-live">
          {/* El único titular de la portada. La itálica de la voz de Klara no
              se pierde: se muda del titular al cuerpo, que va entero en ella. */}
          <header className="k-hero k-hero--quiet">
            <h1 className="k-hero__title">{t("landing.hero.tagline")}</h1>
            <p className="k-hero__dek">{t("landing.hero.support")}</p>
          </header>
          <div className="k-wrap">
            <a className="k-btn" href="#waitlist">{t("landing.hero.ctaPrimary")}</a>
          </div>

          {PROMESAS.map((k) => (
            <div key={k}>
              <h2 className="k-cap k-cap--rule">{t(`landing.que.${k}.title`)}</h2>
              <p className="k-note k-note--bare">{t(`landing.que.${k}.body`)}</p>
            </div>
          ))}

          <section id="waitlist">
            <h2 className="k-cap k-cap--rule">{t("waitlist.title")}</h2>
            <p className="k-note k-note--bare">{t("waitlist.body")}</p>
            {state === "ok" ? (
              <p className="k-note k-note--bare" role="status">{t("waitlist.success")}</p>
            ) : (
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
            <p className="k-note k-note--mono k-note--bare">{t("waitlist.privacyNote")}</p>
          </section>

          <footer className="k-topline k-topline--foot">
            <span>{t("landing.footer.copyright")}</span>
            <a className="k-link" href="mailto:samueldarioballesteros@gmail.com">
              {t("landing.footer.contact")}
            </a>
          </footer>
        </main>
      </div>
    </div>
  );
}
