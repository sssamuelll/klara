import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { CEFRLevel, LanguageCode } from "../api/types";
import { LANGUAGE_CODES, languageLabel } from "../lib/languages";
import { useAuth } from "../lib/auth";
import { patchUser, useUser } from "../lib/user";
import InvitationsPanel from "../components/InvitationsPanel";
import PasswordSetForm from "../components/PasswordSetForm";

const LEVELS: CEFRLevel[] = ["A0", "A1", "A2", "B1", "B2", "C1"];

export default function Settings() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user, loading } = useUser();
  const { logout } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [level, setLevel] = useState<CEFRLevel>("A0");
  const [nativeLang, setNativeLang] = useState<LanguageCode>("es");
  const [targetLang, setTargetLang] = useState<LanguageCode>("de");
  const [context, setContext] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pwSavedToast, setPwSavedToast] = useState(false);

  useEffect(() => {
    if (!user) return;
    setDisplayName(user.display_name);
    setLevel(user.level);
    setNativeLang(user.native_language);
    setTargetLang(user.target_language);
    setContext(user.learning_context ?? "");
  }, [user]);

  useEffect(() => {
    if (!pwSavedToast) return;
    const id = setTimeout(() => setPwSavedToast(false), 3000);
    return () => clearTimeout(id);
  }, [pwSavedToast]);

  const sameLang = nativeLang === targetLang;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (sameLang) {
      setError(t("settings.error.sameLang"));
      return;
    }
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await patchUser({
        display_name: displayName.trim() || undefined,
        level,
        native_language: nativeLang,
        target_language: targetLang,
        learning_context: context.trim() ? context.trim() : null,
      });
      setSaved(true);
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : t("common.unknownError"));
    } finally {
      setSaving(false);
    }
  }

  if (loading && !user) {
    return (
      <main className="k-page snew">
        <div className="story-loading">
          <span className="k-mono">{t("common.loading")}</span>
        </div>
      </main>
    );
  }

  return (
    <main className="k-page snew">
      <button className="snew__back k-mono" onClick={() => navigate("/")}>
        {t("common.back")}
      </button>

      <div className="snew__head">
        <span className="k-mono">{t("settings.kicker")}</span>
        <h1 className="snew__title">{t("settings.title")}</h1>
        <p className="snew__sub">{t("settings.sub")}</p>
      </div>

      {error && <div className="k-error" role="alert">{error}</div>}
      {saved && !error && (
        <div className="k-mono" style={{ color: "var(--ink-3)" }}>{t("settings.saved")}</div>
      )}

      <form onSubmit={onSubmit}>
        <label className="k-mono" style={{ display: "block", marginTop: "1rem" }}>
          {t("settings.field.name")}
        </label>
        <input
          className="snew__input"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          disabled={saving}
        />

        <label className="k-mono" style={{ display: "block", marginTop: "1.5rem" }}>
          {t("settings.field.level")}
        </label>
        <div className="snew__level">
          <input
            type="range"
            className="snew__range"
            min={0}
            max={LEVELS.length - 1}
            step={1}
            value={LEVELS.indexOf(level)}
            onChange={(e) => setLevel(LEVELS[Number(e.target.value)])}
            disabled={saving}
            aria-label={t("settings.field.levelAria")}
            aria-valuetext={level}
          />
          <div className="snew__level-marks k-mono">
            {LEVELS.map((l) => (
              <span key={l} data-active={l === level}>{l}</span>
            ))}
          </div>
        </div>

        <label className="k-mono" style={{ display: "block", marginTop: "1.5rem" }}>
          {t("settings.field.nativeLang")}
        </label>
        <select
          className="snew__input"
          style={sameLang ? { borderColor: "var(--accent, currentColor)" } : undefined}
          value={nativeLang}
          onChange={(e) => {
            const next = e.target.value as LanguageCode;
            setNativeLang(next);
            if (next === targetLang) {
              const fallback = LANGUAGE_CODES.find((c) => c !== next);
              if (fallback) setTargetLang(fallback);
            }
          }}
          disabled={saving}
        >
          {LANGUAGE_CODES.map((c) => (
            <option key={c} value={c}>{languageLabel(c)}</option>
          ))}
        </select>

        <label className="k-mono" style={{ display: "block", marginTop: "1.5rem" }}>
          {t("settings.field.targetLang")}
        </label>
        <select
          className="snew__input"
          style={sameLang ? { borderColor: "var(--accent, currentColor)" } : undefined}
          value={targetLang}
          onChange={(e) => setTargetLang(e.target.value as LanguageCode)}
          disabled={saving}
        >
          {LANGUAGE_CODES.map((c) => (
            <option key={c} value={c} disabled={c === nativeLang}>
              {languageLabel(c)}
            </option>
          ))}
        </select>
        {sameLang && (
          <div className="k-mono" style={{ color: "var(--ink-3)", marginTop: ".5rem" }}>
            {t("settings.sameLangWarn")}
          </div>
        )}

        <label className="k-mono" style={{ display: "block", marginTop: "1.5rem" }}>
          {t("settings.field.context")}
        </label>
        <textarea
          className="snew__input"
          rows={3}
          placeholder={t("settings.field.contextPlaceholder")}
          value={context}
          onChange={(e) => setContext(e.target.value)}
          disabled={saving}
          style={{ resize: "vertical" }}
        />

        <hr className="k-hairline" />

        <div className="snew__actions">
          <button type="submit" className="k-btn" disabled={saving || sameLang}>
            {saving ? t("settings.button.saving") : t("settings.button.save")}
          </button>
          <button
            type="button"
            className="k-btn k-btn--ghost"
            onClick={() => navigate("/")}
            disabled={saving}
          >
            {t("settings.button.cancel")}
          </button>
        </div>
      </form>

      <hr className="k-hairline" />

      <section style={{ marginTop: "1.5rem" }}>
        <h2 className="k-mono" style={{ fontSize: "0.9rem", color: "var(--ink-3)" }}>
          {t("settings.account.section")}
        </h2>

        <label className="k-mono" style={{ display: "block", marginTop: "1rem" }}>
          {t("settings.account.emailLabel")}
        </label>
        <input
          className="snew__input"
          value={user?.email ?? ""}
          readOnly
          disabled
        />

        <div className="snew__actions" style={{ marginTop: "1rem" }}>
          <button
            type="button"
            className="k-btn k-btn--ghost"
            onClick={() => navigate("/forgot")}
          >
            {t("settings.account.changePasswordBtn")}
          </button>
          <button
            type="button"
            className="k-btn k-btn--ghost"
            onClick={async () => {
              await logout();
              navigate("/login", { replace: true });
            }}
          >
            {t("settings.account.logoutBtn")}
          </button>
        </div>
      </section>

      {user?.is_superuser && (
        <>
          <hr className="k-hairline" />
          <InvitationsPanel />
        </>
      )}

      {user && !user.auth_methods.includes("password") && (
        <>
          <hr className="k-hairline" />
          <section style={{ marginTop: "1.5rem" }}>
            <span className="k-mono">{t("settings.security.kicker")}</span>
            <h2 className="k-mono" style={{ fontSize: "0.9rem", color: "var(--ink-3)", marginTop: "0.5rem" }}>
              {t("settings.security.title")}
            </h2>
            <p className="snew__sub" style={{ marginTop: "0.5rem" }}>
              {t("settings.security.hint")}
            </p>
            {pwSavedToast && (
              <div className="snew__toast k-mono" role="status">
                {t("settings.security.savedToast")}
              </div>
            )}
            <PasswordSetForm onSuccess={() => setPwSavedToast(true)} />
          </section>
        </>
      )}
    </main>
  );
}
