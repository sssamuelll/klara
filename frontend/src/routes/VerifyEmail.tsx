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
    <main>
      <h1 className="auth-title">{t("auth.verify.title")}</h1>
      {state === "verifying" && (
        <p className="auth-sub">{t("common.loading")}</p>
      )}
      {state === "idle" && (
        <p className="auth-sub">{t("auth.signup.verifyEmailSent")}</p>
      )}
      {state === "ok" && (
        <>
          <p className="auth-sub">{t("auth.verify.success")}</p>
          <div className="auth-actions">
            <Link className="k-btn" to="/login">{t("auth.reset.goLogin")}</Link>
          </div>
        </>
      )}
      {state === "fail" && (
        <div className="k-error" role="alert">
          {t("auth.verify.error")}
        </div>
      )}
      {state !== "ok" && (
        <p className="auth-links">
          <Link to="/login">{t("common.back")}</Link>
        </p>
      )}
    </main>
  );
}
