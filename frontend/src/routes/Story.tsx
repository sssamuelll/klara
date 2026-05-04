import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Story } from "../api/types";
import SentenceView from "../components/SentenceView";
import { speakGerman, stopSpeaking } from "../lib/tts";
import "./Story.css";

export default function StoryView() {
  const { id } = useParams<{ id: string }>();
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setStory(null);
    setError(null);
    api
      .getStory(id)
      .then((s) => {
        if (!cancelled) setStory(s);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Error");
      });
    return () => {
      cancelled = true;
      stopSpeaking();
    };
  }, [id]);

  if (error) {
    return (
      <div className="fade-in">
        <div className="error-banner">{error}</div>
        <Link to="/" className="btn btn-ghost">
          ← Volver
        </Link>
      </div>
    );
  }

  if (!story) {
    return (
      <div className="story-loading fade-in">
        <span className="spinner" />
        <span className="muted">Generando historia…</span>
      </div>
    );
  }

  function readAll() {
    if (!story) return;
    const text = story.content.sentences.map((s) => s.de).join(" ");
    speakGerman(text);
  }

  return (
    <div className="story-view fade-in">
      <div className="story-view__head">
        <span className="story-view__level">{story.level}</span>
        <h2 className="story-view__title">{story.title}</h2>
        <button className="btn" onClick={readAll}>
          🔊 Leer todo
        </button>
      </div>

      <SentenceView story={story} />

      {story.target_words.length > 0 && (
        <div className="story-view__words">
          <h3>Palabras nuevas</h3>
          <ul>
            {story.target_words.map((w) => (
              <li key={w.id}>
                <strong>
                  {w.gender && w.pos === "noun" ? `${w.gender} ` : ""}
                  {w.lemma}
                </strong>
                {w.translation_es && <span className="muted"> — {w.translation_es}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="story-view__footer">
        <Link to="/story/new" className="btn btn-primary">
          Otra historia
        </Link>
        <Link to="/" className="btn btn-ghost">
          Volver al inicio
        </Link>
      </div>
    </div>
  );
}
