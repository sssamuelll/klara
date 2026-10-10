import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError, api } from "../api/client";
import type { CEFRLevel, LanguageCode } from "../api/types";
import { alternarIdioma, estudioParaGuardar, type MapasCargados } from "../lib/idiomasEstudio";
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
  const [mapas, setMapas] = useState<MapasCargados>(null);
  const [intento, setIntento] = useState(0);
  const [estudio, setEstudio] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [recentlySetPw, setRecentlySetPw] = useState(false);

  useEffect(() => {
    if (!user) return;
    setDisplayName(user.display_name);
    setLevel(user.level);
    setNativeLang(user.native_language);
    setTargetLang(user.target_language);
    setContext(user.learning_context ?? "");
    setEstudio(user.study_languages);
  }, [user]);

  // Los idiomas que se pueden estudiar son los que tienen mapa (spec 2026-10-09 §5.6). Si no llegan, el
  // campo lo dice y deja reintentar: es la salida de Hoy para quien no tiene idioma elegido.
  useEffect(() => {
    let cancelado = false;
    setMapas(null);
    api.mapas().then(
      (m) => {
        if (!cancelado) setMapas(m);
      },
      () => {
        if (!cancelado) setMapas("fallo");
      },
    );
    return () => {
      cancelado = true;
    };
  }, [intento]);

  useEffect(() => {
    if (!recentlySetPw) return;
    const id = setTimeout(() => setRecentlySetPw(false), 3000);
    return () => clearTimeout(id);
  }, [recentlySetPw]);

  const sameLang = nativeLang === targetLang;
  // Con los mapas ya a la vista y ninguno, no hay nada que elegir: el campo no se pinta.
  const sinMapas = Array.isArray(mapas) && mapas.length === 0;

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
        study_languages: estudioParaGuardar(user?.study_languages ?? [], estudio, mapas),
      });
      setSaved(true);
    } catch (e2) {
      // 422 `study_languages.sin_mapa`: el `detail` es un código, no un mensaje para el aprendiz.
      const sinMapa = e2 instanceof ApiError && e2.message.includes("study_languages.sin_mapa");
      setError(e2 instanceof Error && !sinMapa ? e2.message : t("common.unknownError"));
    } finally {
      setSaving(false);
    }
  }

  if (loading && !user) {
    return (
      <main className="k-page">
        <span className="k-spinner" role="status" aria-label={t("common.loading")} />
      </main>
    );
  }

  return (
    <main className="k-page">
      <button type="button" className="k-btn k-btn--text" onClick={() => navigate("/")}>
        {t("common.back")}
      </button>

      <header className="k-hero k-hero--quiet">
        <span className="k-hero__tag">{t("settings.kicker")}</span>
        <h1 className="k-hero__title">{t("settings.title")}</h1>
        <p className="k-hero__dek">{t("settings.sub")}</p>
      </header>

      {error && <p className="k-error" role="alert">{error}</p>}
      {saved && !error && <p className="k-cap" role="status">{t("settings.saved")}</p>}

      <form onSubmit={onSubmit}>
        <label className="k-field">
          <span className="k-field__label">{t("settings.field.name")}</span>
          <input
            className="k-field__input"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            disabled={saving}
          />
        </label>

        {/* El nivel se elige igual que en el onboarding: seis rótulos cortos,
            uno solo elegido. El deslizador de `pages.css` muere aquí (era su
            único consumidor) y con él el candidato del contrato. */}
        <div className="k-field">
          <span className="k-field__label" id="ajustes-nivel">
            {t("settings.field.level")}
          </span>
          <div className="k-wrap" role="radiogroup" aria-labelledby="ajustes-nivel">
            {LEVELS.map((l) => (
              <button
                key={l}
                type="button"
                role="radio"
                aria-checked={l === level}
                className="k-chip"
                data-selected={l === level}
                onClick={() => setLevel(l)}
                disabled={saving}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        <label className="k-field" data-error={sameLang || undefined}>
          <span className="k-field__label">{t("settings.field.nativeLang")}</span>
          <select
            className="k-field__input"
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
        </label>

        <label className="k-field" data-error={sameLang || undefined}>
          <span className="k-field__label">{t("settings.field.targetLang")}</span>
          <select
            className="k-field__input"
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
          {sameLang && <span className="k-field__hint">{t("settings.sameLangWarn")}</span>}
        </label>

        {!sinMapas && (
          <div className="k-field">
            <span className="k-field__label" id="ajustes-estudio">
              {t("settings.field.studyLangs")}
            </span>
            {mapas === "fallo" ? (
              // Un `div` y no un `p`: el párrafo trae 1em (11px) de margen arriba y abajo, que en la columna del
              // campo no se funden y empujan lo de debajo 22px de más.
              <div className="k-error" role="alert">
                {t("settings.studyLangsError")}{" "}
                <button type="button" className="k-btn k-btn--text" onClick={() => setIntento((n) => n + 1)}>
                  {t("settings.studyLangsRetry")}
                </button>
              </div>
            ) : mapas === null ? (
              // El alto de una fila de chips, siempre reservado: lo de debajo no da un salto cuando llegan los
              // mapas. Invisible con `visibility` (conserva su caja; no hay átomo para un hueco), y con un espacio
              // duro dentro: un chip sin texto mide 44px y uno con texto, 45.
              <div className="k-wrap" aria-hidden="true">
                <span className="k-chip" style={{ visibility: "hidden" }}>{"\u00a0"}</span>
              </div>
            ) : (
              <div className="k-wrap" role="group" aria-labelledby="ajustes-estudio" aria-describedby="ajustes-estudio-pista">
                {mapas.map((m) => {
                  const marcado = estudio.includes(m.idioma);
                  // El último marcado no se puede quitar (el servidor pide al menos uno). `aria-disabled` lo dice
                  // sin apagar el chip: con `disabled` quedaría a 0.45, como uno que no se puede tocar.
                  const ultimo = marcado && estudio.length === 1;
                  return (
                    <button
                      key={m.idioma}
                      type="button"
                      className="k-chip"
                      aria-pressed={marcado}
                      aria-disabled={ultimo || undefined}
                      data-selected={marcado}
                      lang={m.idioma}
                      disabled={saving}
                      onClick={() => setEstudio((a) => alternarIdioma(a, m.idioma, mapas.map((x) => x.idioma)))}
                    >
                      {languageLabel(m.idioma)}
                    </button>
                  );
                })}
              </div>
            )}
            <span className="k-field__hint" id="ajustes-estudio-pista">{t("settings.studyLangsHint")}</span>
          </div>
        )}

        <label className="k-field k-field--area">
          <span className="k-field__label">{t("settings.field.context")}</span>
          <textarea
            className="k-field__input"
            rows={3}
            placeholder={t("settings.field.contextPlaceholder")}
            value={context}
            onChange={(e) => setContext(e.target.value)}
            disabled={saving}
          />
        </label>

        <div className="k-wrap">
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

      <section>
        <p className="k-cap k-cap--rule">{t("settings.account.section")}</p>

        <label className="k-field">
          <span className="k-field__label">{t("settings.account.emailLabel")}</span>
          <input className="k-field__input" value={user?.email ?? ""} readOnly disabled />
        </label>

        <div className="k-wrap">
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

      {user && (!user.auth_methods.includes("password") || recentlySetPw) && (
        <>
          <hr className="k-hairline" />
          <section>
            <p className="k-cap k-cap--rule">{t("settings.security.kicker")}</p>
            {/* El sistema tiene un solo nivel de titular y ya lo gasta la
                página (candidato 21): dentro de una sección, el rótulo de lo
                que se va a hacer es el `.k-note__cap` de su propia nota. Es lo
                mismo que la migración 13 hizo con los hechos del módulo. */}
            <p className="k-note">
              <strong className="k-note__cap">{t("settings.security.title")}</strong>
              {t("settings.security.hint")}
            </p>
            {recentlySetPw && (
              <p className="k-cap" role="status">{t("settings.security.savedToast")}</p>
            )}
            {!user.auth_methods.includes("password") && (
              <PasswordSetForm onSuccess={() => setRecentlySetPw(true)} />
            )}
          </section>
        </>
      )}
    </main>
  );
}
