import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import { detectBrowserLang } from "../lib/preferences";

type InviteState = "active" | "expired" | "used" | "revoked";

interface InvitePublic {
  email: string | null;
  expires_at: string;
  state: InviteState;
}

export default function Signup() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { signup } = useAuth();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite");

  const [invite, setInvite] = useState<InvitePublic | null>(null);
  const [inviteLoading, setInviteLoading] = useState<boolean>(Boolean(inviteToken));
  const [inviteError, setInviteError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Validate the invite token on mount; bail fast if it's stale or unknown.
  useEffect(() => {
    if (!inviteToken) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`/api/v1/invitations/${inviteToken}`);
        if (!r.ok) {
          if (!cancelled) setInviteError(t("auth.signup.error.inviteInvalid"));
          return;
        }
        const body: InvitePublic = await r.json();
        if (cancelled) return;
        setInvite(body);
        if (body.email) setEmail(body.email);
        if (body.state !== "active") {
          const key =
            body.state === "expired"
              ? "auth.signup.error.inviteExpired"
              : body.state === "used"
              ? "auth.signup.error.inviteUsed"
              : "auth.signup.error.inviteRevoked";
          setInviteError(t(key));
        }
      } catch {
        if (!cancelled) setInviteError(t("auth.signup.error.inviteInvalid"));
      } finally {
        if (!cancelled) setInviteLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [inviteToken, t]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError(t("auth.signup.error.passwordMismatch"));
      return;
    }
    if (!inviteToken) return;
    setSubmitting(true);
    setError(null);
    try {
      await signup({
        email: email.trim().toLowerCase(),
        password,
        native_language: detectBrowserLang() ?? undefined,
        invite_token: inviteToken,
      });
      navigate("/", { replace: true });
    } catch (e2) {
      const msg = e2 instanceof Error ? e2.message : String(e2);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  // No token → invitation-only gate.
  if (!inviteToken) {
    return (
      <main className="k-page snew">
        <div className="snew__head">
          <h1 className="snew__title">{t("auth.signup.inviteOnly.title")}</h1>
        </div>
        <p className="k-mono" style={{ marginTop: "1rem", color: "var(--ink-3)" }}>
          {t("auth.signup.inviteOnly.body")}
        </p>
        <p className="k-mono" style={{ marginTop: "1rem" }}>
          <Link to="/login">{t("auth.signup.loginLink")}</Link>
        </p>
      </main>
    );
  }

  if (inviteLoading) {
    return (
      <main className="k-page snew">
        <p className="k-mono">{t("common.loading")}</p>
      </main>
    );
  }

  if (inviteError) {
    return (
      <main className="k-page snew">
        <div className="snew__head">
          <h1 className="snew__title">{t("auth.signup.inviteOnly.title")}</h1>
        </div>
        <div className="k-error" role="alert">{inviteError}</div>
        <p className="k-mono" style={{ marginTop: "1rem" }}>
          <Link to="/login">{t("auth.signup.loginLink")}</Link>
        </p>
      </main>
    );
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
          disabled={submitting || Boolean(invite?.email)}
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
        </div>

        <p className="k-mono" style={{ marginTop: "1.5rem", color: "var(--ink-3)" }}>
          <Link to="/login">{t("auth.signup.loginLink")}</Link>
        </p>
      </form>
    </main>
  );
}
