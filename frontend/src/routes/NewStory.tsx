import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../api/client";
import KlaraMark from "../components/KlaraMark";

const SUGGESTION_KEYS = [
  "newstory.chip.supermarket",
  "newstory.chip.doctorCall",
  "newstory.chip.publicTransport",
  "newstory.chip.streetEncounter",
  "newstory.chip.orderCoffee",
  "newstory.chip.officeErrand",
] as const;

export default function NewStory() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const moduleId = params.get("module") ?? undefined;
  const [topic, setTopic] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(text: string, origin: "chip" | "free" | "none") {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const story = await api.createStory(text.trim() || undefined, {
        moduleId,
        topicOrigin: text.trim() ? origin : "none",
      });
      navigate(`/estudiar/${story.id}`);
    } catch (e) {
      // Bidirectional fallback (spec §10): live generation failing must
      // offer the instant library story when one exists, instead of
      // dead-ending the module flow.
      if (e instanceof ApiError && e.status === 502 && moduleId) {
        try {
          const ready = await api.claimModuleStory(moduleId);
          navigate(`/estudiar/${ready.id}`);
          return;
        } catch {
          /* fall through to the normal error */
        }
      }
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="k-page">
      <button type="button" className="k-btn k-btn--text" onClick={() => navigate("/")}>
        {t("common.back")}
      </button>

      <header className="k-hero k-hero--quiet">
        <span className="k-hero__tag">{t("newstory.kicker")}</span>
        <h1 className="k-hero__title">{t("newstory.title")}</h1>
        <p className="k-hero__dek">{t("newstory.sub")}</p>
      </header>

      {error && <p className="k-error" role="alert">{error}</p>}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          generate(topic, selected === topic ? "chip" : "free");
        }}
      >
        {/* Manuscrito y no caja: lo que se escribe aquí es la respuesta a
            «¿de qué quieres que vaya?», no un dato de formulario (átomo 17). */}
        <label className="k-field k-field--rule">
          <input
            className="k-field__input"
            placeholder={t("newstory.input.placeholder")}
            aria-label={t("newstory.input.placeholder")}
            value={topic}
            onChange={(e) => {
              setTopic(e.target.value);
              setSelected(null);
            }}
            disabled={loading}
            autoFocus
          />
          <span className="k-field__rule" />
        </label>

        <p className="k-cap">{t("newstory.chips.label")}</p>
        <div className="k-wrap">
          {SUGGESTION_KEYS.map((k) => {
            const label = t(k);
            return (
              <button
                key={k}
                type="button"
                className="k-chip"
                data-selected={selected === label}
                onClick={() => {
                  setSelected(label);
                  setTopic(label);
                }}
                disabled={loading}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div className="k-wrap">
          <button
            type="submit"
            className="k-btn"
            disabled={loading}
            aria-busy={loading}
          >
            {loading ? (
              <>
                <span className="k-spinner" /> {t("newstory.generating")}
              </>
            ) : (
              <>
                {t("newstory.generate")} <span className="k-btn__arrow">→</span>
              </>
            )}
          </button>
          <button
            type="button"
            className="k-btn k-btn--ghost"
            onClick={() => generate("", "none")}
            disabled={loading}
          >
            {t("newstory.surprise")}
          </button>
        </div>
      </form>

      <p className="k-note k-note--bare">
        <KlaraMark size={14} /> {t("newstory.klaraAdapts")}
      </p>
    </main>
  );
}
