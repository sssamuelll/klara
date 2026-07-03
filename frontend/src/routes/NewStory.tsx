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
      navigate(`/story/${story.id}`);
    } catch (e) {
      // Bidirectional fallback (spec §10): live generation failing must
      // offer the instant library story when one exists, instead of
      // dead-ending the module flow.
      if (e instanceof ApiError && e.status === 502 && moduleId) {
        try {
          const ready = await api.claimModuleStory(moduleId);
          navigate(`/story/${ready.id}`);
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
    <main className="k-page snew">
      <button className="snew__back k-mono" onClick={() => navigate("/")}>
        {t("common.back")}
      </button>

      <div className="snew__head">
        <span className="k-mono">{t("newstory.kicker")}</span>
        <h1 className="snew__title">{t("newstory.title")}</h1>
        <p className="snew__sub">{t("newstory.sub")}</p>
      </div>

      {error && <div className="k-error" role="alert">{error}</div>}

      <form
        className="snew__input-wrap"
        onSubmit={(e) => {
          e.preventDefault();
          generate(topic, selected === topic ? "chip" : "free");
        }}
      >
        <input
          className="snew__input"
          placeholder={t("newstory.input.placeholder")}
          value={topic}
          onChange={(e) => {
            setTopic(e.target.value);
            setSelected(null);
          }}
          disabled={loading}
          autoFocus
        />
        <span className="snew__input-rule" />
      </form>

      <div className="snew__chips-block">
        <div className="k-mono">{t("newstory.chips.label")}</div>
        <div className="snew__chips">
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
      </div>

      <div className="snew__actions">
        <button
          type="button"
          className="k-btn"
          onClick={() => generate(topic, selected === topic ? "chip" : "free")}
          disabled={loading}
        >
          {loading ? (
            <>
              <span className="k-spinner" /> {t("newstory.generating")}
            </>
          ) : (
            <>
              {t("newstory.generate")} <span className="arrow">→</span>
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

      <div className="snew__klara">
        <KlaraMark size={14} />
        <span className="k-mono">{t("newstory.klaraAdapts")}</span>
      </div>
    </main>
  );
}
