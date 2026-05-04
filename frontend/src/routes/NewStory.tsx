import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import "./NewStory.css";

const SUGGESTIONS = [
  "panadería en Nürnberg",
  "primer día en el supermarkt",
  "viaje en U-Bahn",
  "café en Hauptmarkt",
  "trámite en el Bürgeramt",
  "domingo lluvioso",
];

export default function NewStory() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(t?: string) {
    setLoading(true);
    setError(null);
    try {
      const story = await api.createStory(t || topic || undefined);
      navigate(`/story/${story.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="new-story fade-in">
      <h2>Nueva historia</h2>
      <p className="muted">
        Elige un tema o déjalo en blanco para que Klara improvise algo cotidiano de Nürnberg.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <form
        className="new-story__form"
        onSubmit={(e) => {
          e.preventDefault();
          generate();
        }}
      >
        <input
          className="new-story__input"
          type="text"
          placeholder="Tema (opcional)…"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={loading}
          autoFocus
        />
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? <span className="spinner" /> : "Generar"}
        </button>
      </form>

      <div className="new-story__suggestions">
        <span className="dim">Sugerencias:</span>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            className="chip"
            onClick={() => {
              setTopic(s);
              generate(s);
            }}
            disabled={loading}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
