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
    <main className="k-page snew">
      <div className="snew__head">
        <h1 className="snew__title">{t("auth.verify.title")}</h1>
      </div>
      {state === "verifying" && (
        <p className="k-mono">{t("common.loading")}</p>
      )}
      {state === "idle" && (
        <p className="k-mono" style={{ color: "var(--ink-3)" }}>
          {t("auth.signup.verifyEmailSent")}
        </p>
      )}
      {state === "ok" && (
        <p className="k-mono" style={{ color: "var(--ink-3)" }}>
          {t("auth.verify.success")}
        </p>
      )}
      {state === "fail" && (
        <div className="k-error" role="alert">
          {t("auth.verify.error")}
        </div>
      )}
      <p className="k-mono" style={{ marginTop: "1.5rem" }}>
        <Link to="/login">{t("common.back")}</Link>
      </p>
    </main>
  );
}
