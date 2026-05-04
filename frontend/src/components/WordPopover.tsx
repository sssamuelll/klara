import { useState } from "react";
import type { StoryWord } from "../api/types";
import { api } from "../api/client";
import { speakGerman } from "../lib/tts";
import "./WordPopover.css";

interface Props {
  word: StoryWord;
  onClose: () => void;
}

export default function WordPopover({ word, onClose }: Props) {
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function addToDeck() {
    setAdding(true);
    setError(null);
    try {
      await api.addCard(word.id);
      setAdded(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setAdding(false);
    }
  }

  const display =
    word.gender && word.pos === "noun"
      ? `${word.gender} ${word.lemma}${word.plural ? `, –${word.plural}` : ""}`
      : word.lemma;

  return (
    <div className="word-popover-backdrop" onClick={onClose}>
      <div className="word-popover" onClick={(e) => e.stopPropagation()}>
        <button className="word-popover__close" onClick={onClose} aria-label="Cerrar">
          ✕
        </button>

        <div className="word-popover__lemma">
          <span>{display}</span>
          <button
            className="word-popover__speak"
            onClick={() => speakGerman(word.lemma)}
            aria-label="Escuchar"
          >
            🔊
          </button>
        </div>

        {word.translation_es && (
          <div className="word-popover__translation">{word.translation_es}</div>
        )}

        {word.example_de && (
          <div className="word-popover__example">
            <span className="dim">Ej:</span> {word.example_de}{" "}
            <button
              className="word-popover__example-speak"
              onClick={() => speakGerman(word.example_de!)}
              aria-label="Escuchar ejemplo"
            >
              🔊
            </button>
          </div>
        )}

        {error && <div className="error-banner">{error}</div>}

        <div className="word-popover__actions">
          {added ? (
            <div className="word-popover__added">✓ Añadida al SRS</div>
          ) : (
            <button className="btn btn-primary" disabled={adding} onClick={addToDeck}>
              {adding ? <span className="spinner" /> : "+ Agregar al SRS"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
