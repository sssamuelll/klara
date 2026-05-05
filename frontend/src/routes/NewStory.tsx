import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import KlaraMark from "../components/KlaraMark";

const SUGGESTIONS = [
  "Panadería un sábado",
  "Cita en el Bürgeramt",
  "U-Bahn averiada",
  "Comprando un Deutschlandticket",
  "Vecino que toca timbre",
  "Médico de cabecera",
];

export default function NewStory() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(t: string) {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const story = await api.createStory(t.trim() || undefined);
      navigate(`/story/${story.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="k-page snew">
      <button className="snew__back k-mono" onClick={() => navigate("/")}>
        ← Volver
      </button>

      <div className="snew__head">
        <span className="k-mono">Pedido a Klara</span>
        <h1 className="snew__title">¿De qué hablamos hoy?</h1>
        <p className="snew__sub">Una palabra alcanza. O dejá que Klara elija.</p>
      </div>

      {error && <div className="k-error" role="alert">{error}</div>}

      <form
        className="snew__input-wrap"
        onSubmit={(e) => {
          e.preventDefault();
          generate(topic);
        }}
      >
        <input
          className="snew__input"
          placeholder="Una panadería un sábado a las 8…"
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
        <div className="k-mono">O elegí un tema</div>
        <div className="snew__chips">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              className="k-chip"
              data-selected={selected === s}
              onClick={() => {
                setSelected(s);
                setTopic(s);
              }}
              disabled={loading}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="snew__actions">
        <button
          type="button"
          className="k-btn"
          onClick={() => generate(topic)}
          disabled={loading}
        >
          {loading ? (
            <>
              <span className="k-spinner" /> Klara está escribiendo…
            </>
          ) : (
            <>
              Generar historia <span className="arrow">→</span>
            </>
          )}
        </button>
        <button
          type="button"
          className="k-btn k-btn--ghost"
          onClick={() => generate("")}
          disabled={loading}
        >
          Sorprendeme
        </button>
      </div>

      <div className="snew__klara">
        <KlaraMark size={14} />
        <span className="k-mono">Klara escribe a tu nivel</span>
      </div>
    </main>
  );
}
