import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

type State = "idle" | "verifying" | "ok" | "fail";

export default function VerifyEmail() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [state, setState] = useState<State>(token ? "verifying" : "idle");

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api
      .verifyEmail(token)
      .then(() => {
        if (!cancelled) setState("ok");
      })
      .catch(() => {
        if (!cancelled) setState("fail");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="k-live">
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{t("auth.verify.title")}</h1>
        {/* Los tres estados que no son error son la misma bajada del titular
            con otro texto; el sistema no los distingue y no debe. */}
        {state === "verifying" && (
          <p className="k-hero__dek">{t("common.loading")}</p>
        )}
        {state === "idle" && (
          <p className="k-hero__dek">{t("auth.signup.verifyEmailSent")}</p>
        )}
        {state === "ok" && (
          <p className="k-hero__dek">{t("auth.verify.success")}</p>
        )}
      </header>
      <hr className="k-hairline" />

      {state === "ok" && (
        <div className="k-wrap">
          <Link className="k-btn" to="/login">{t("auth.reset.goLogin")}</Link>
        </div>
      )}
      {state === "fail" && (
        <div className="k-error" role="alert">
          {t("auth.verify.error")}
        </div>
      )}
      {state !== "ok" && (
        <footer className="k-topline k-topline--foot">
          <Link className="k-link" to="/login">{t("common.back")}</Link>
        </footer>
      )}
    </main>
  );
}
