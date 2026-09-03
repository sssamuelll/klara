import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { apiBase } from "../lib/apiBase";
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
        const r = await fetch(`${apiBase()}/invitations/${inviteToken}`);
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
      <main className="k-live">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">{t("auth.signup.inviteOnly.title")}</h1>
          <p className="k-hero__dek">{t("auth.signup.inviteOnly.body")}</p>
        </header>
        <hr className="k-hairline" />
        <div className="k-wrap">
          <Link className="k-btn" to="/login">{t("auth.signup.loginLink")}</Link>
        </div>
      </main>
    );
  }

  if (inviteLoading) {
    return (
      <main className="k-live">
        <p className="k-note" role="status">{t("common.loading")}</p>
      </main>
    );
  }

  if (inviteError) {
    return (
      <main className="k-live">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">{t("auth.signup.inviteOnly.title")}</h1>
        </header>
        <hr className="k-hairline" />
        <div className="k-error" role="alert">{inviteError}</div>
        <div className="k-wrap">
          <Link className="k-btn" to="/login">{t("auth.signup.loginLink")}</Link>
        </div>
      </main>
    );
  }

  return (
    <main className="k-live">
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{t("auth.signup.invitedTitle")}</h1>
        <p className="k-hero__dek">{t("auth.signup.invitedSub")}</p>
      </header>
      <hr className="k-hairline" />

      {error && <div className="k-error" role="alert">{error}</div>}

      <form onSubmit={onSubmit}>
        <label className="k-field">
          <span className="k-field__label">{t("auth.signup.emailLabel")}</span>
          <input
            className="k-field__input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting || Boolean(invite?.email)}
          />
        </label>

        <label className="k-field">
          <span className="k-field__label">{t("auth.signup.passwordLabel")}</span>
          <input
            className="k-field__input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
          />
        </label>

        <label className="k-field">
          <span className="k-field__label">{t("auth.signup.confirmLabel")}</span>
          <input
            className="k-field__input"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            disabled={submitting}
          />
        </label>

        <div className="k-wrap">
          <button type="submit" className="k-btn" disabled={submitting}>
            {t("auth.signup.submit")}
          </button>
        </div>
      </form>

      <footer className="k-topline k-topline--foot">
        <Link className="k-link" to="/login">{t("auth.signup.loginLink")}</Link>
      </footer>
    </main>
  );
}
