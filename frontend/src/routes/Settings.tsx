import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { CEFRLevel, LanguageCode } from "../api/types";
import { LANGUAGE_CODES, languageLabel } from "../lib/languages";
import { patchUser, useUser } from "../lib/user";

const LEVELS: CEFRLevel[] = ["A0", "A1", "A2", "B1", "B2", "C1"];

export default function Settings() {
  const navigate = useNavigate();
  const { user, loading } = useUser();
  const [displayName, setDisplayName] = useState("");
  const [level, setLevel] = useState<CEFRLevel>("A0");
  const [nativeLang, setNativeLang] = useState<LanguageCode>("es");
  const [targetLang, setTargetLang] = useState<LanguageCode>("de");
  const [context, setContext] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!user) return;
    setDisplayName(user.display_name);
    setLevel(user.level);
    setNativeLang(user.native_language);
    setTargetLang(user.target_language);
    setContext(user.learning_context ?? "");
  }, [user]);

  const sameLang = nativeLang === targetLang;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (sameLang) {
      setError("El idioma nativo y el idioma a aprender deben ser diferentes.");
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
      setError(e2 instanceof Error ? e2.message : "Error desconocido");
    } finally {
      setSaving(false);
    }
  }

  if (loading && !user) {
    return (
      <main className="k-page snew">
        <div className="story-loading">
          <span className="k-mono">Cargando…</span>
        </div>
      </main>
    );
  }

  return (
    <main className="k-page snew">
      <button className="snew__back k-mono" onClick={() => navigate("/")}>
        ← Volver
      </button>

      <div className="snew__head">
        <span className="k-mono">Ajustes</span>
        <h1 className="snew__title">Tu perfil con Klara</h1>
        <p className="snew__sub">Klara adapta las historias a estos datos.</p>
      </div>

      {error && <div className="k-error" role="alert">{error}</div>}
      {saved && !error && (
        <div className="k-mono" style={{ color: "var(--ink-3)" }}>Guardado ✓</div>
      )}

      <form onSubmit={onSubmit}>
        <label className="k-mono" style={{ display: "block", marginTop: "1rem" }}>
          Nombre
        </label>
        <input
          className="snew__input"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          disabled={saving}
        />

        <label className="k-mono" style={{ display: "block", marginTop: "1.5rem" }}>
          Nivel CEFR
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
            aria-label="Nivel CEFR"
            aria-valuetext={level}
          />
          <div className="snew__level-marks k-mono">
            {LEVELS.map((l) => (
              <span key={l} data-active={l === level}>{l}</span>
            ))}
          </div>
        </div>

        <label className="k-mono" style={{ display: "block", marginTop: "1.5rem" }}>
          Idioma nativo (lo que hablás)
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
          Idioma que querés aprender
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
            Elegí un idioma distinto al nativo.
          </div>
        )}

        <label className="k-mono" style={{ display: "block", marginTop: "1.5rem" }}>
          Contexto (opcional)
        </label>
        <textarea
          className="snew__input"
          rows={3}
          placeholder="ej: lo uso para el trabajo, viajo seguido, me interesa la cocina…"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          disabled={saving}
          style={{ resize: "vertical" }}
        />

        <hr className="k-hairline" />

        <div className="snew__actions">
          <button type="submit" className="k-btn" disabled={saving || sameLang}>
            {saving ? "Guardando…" : "Guardar"}
          </button>
          <button
            type="button"
            className="k-btn k-btn--ghost"
            onClick={() => navigate("/")}
            disabled={saving}
          >
            Cancelar
          </button>
        </div>
      </form>
    </main>
  );
}
