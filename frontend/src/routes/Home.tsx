import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { CardOut, Story, StoryListItem } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import { mastheadDate, greeting } from "../lib/dateLabel";
import { useUser } from "../lib/user";

interface HomeStorySummary {
  id: string;
  level: string;
  title: string;
  dek: string;
  minutes: number;
  wordCount: number;
  newWordsCount: number;
}

function summarize(story: Story): HomeStorySummary {
  const wordCount = story.content.sentences.reduce(
    (acc, s) => acc + s.target.trim().split(/\s+/).filter(Boolean).length,
    0
  );
  const minutes = Math.max(1, Math.round(wordCount / 60));
  const dek = story.content.sentences[0]?.native ?? "Una pequeña escena de la vida diaria.";
  return {
    id: story.id,
    level: story.level,
    title: story.title,
    dek,
    minutes,
    wordCount,
    newWordsCount: story.target_words.length,
  };
}

export default function Home() {
  const navigate = useNavigate();
  const { user } = useUser();
  const [latest, setLatest] = useState<HomeStorySummary | null>(null);
  const [dueCount, setDueCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const list: StoryListItem[] = await api.listStories(1, 0);
        if (cancelled) return;
        if (list.length === 0) {
          setLatest(null);
        } else {
          const full = await api.getStory(list[0].id);
          if (!cancelled) setLatest(summarize(full));
        }
      } catch {
        if (!cancelled) setLatest(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
      try {
        const due: CardOut[] = await api.dueCards(50);
        if (!cancelled) setDueCount(due.length);
      } catch {
        if (!cancelled) setDueCount(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const dateLabel = mastheadDate();
  const hello = greeting();

  return (
    <main className="k-page home">
      <div className="home__masthead-block">
        <div className="k-mono home__date">{dateLabel}</div>
        <h1 className="home__greeting">
          <span className="home__greeting-line">{hello},</span>
          <span className="home__greeting-line home__greeting-line--name">
            {user?.display_name ?? "…"}.
          </span>
        </h1>
        <p className="home__sub">Tres minutos. Sin apuro.</p>
      </div>

      <hr className="k-rule home__rule" />

      {loading ? (
        <div className="story-loading">
          <span className="k-mono">Cargando…</span>
        </div>
      ) : latest ? (
        <button className="home__feature" onClick={() => navigate(`/story/${latest.id}`)}>
          <div className="home__feature-meta">
            <span className="k-mono">Última historia</span>
            <span className="k-level">{latest.level}</span>
          </div>
          <h2 className="home__feature-title">{latest.title}</h2>
          <p className="home__feature-dek">{latest.dek}</p>
          <div className="home__feature-foot">
            <div className="home__feature-stats">
              <span className="k-mono">{latest.minutes} min</span>
              <span className="home__dot" />
              <span className="k-mono">{latest.wordCount} palabras</span>
              {latest.newWordsCount > 0 && (
                <>
                  <span className="home__dot" />
                  <span className="k-mono">{latest.newWordsCount} nuevas</span>
                </>
              )}
            </div>
            <span className="k-link">
              Leer <span className="k-serif" style={{ fontStyle: "italic" }}>→</span>
            </span>
          </div>
        </button>
      ) : (
        <button className="home__feature" onClick={() => navigate("/story/new")}>
          <div className="home__feature-meta">
            <span className="k-mono">Primer pedido a Klara</span>
          </div>
          <h2 className="home__feature-title">Todavía no leíste nada.</h2>
          <p className="home__feature-dek">
            Pedile a Klara una micro-historia. Cinco minutos, sin apuro.
          </p>
          <div className="home__feature-foot">
            <span className="k-link">
              Empezar <span className="k-serif" style={{ fontStyle: "italic" }}>→</span>
            </span>
          </div>
        </button>
      )}

      <hr className="k-rule home__rule" />

      <section className="home__secondary">
        <button className="home__sec-item" onClick={() => navigate("/story/new")}>
          <span className="k-mono home__sec-num">01</span>
          <span className="home__sec-body">
            <span className="home__sec-title">Otra historia</span>
            <span className="home__sec-dek">Pedile a Klara un tema distinto.</span>
          </span>
          <span className="home__sec-arrow k-serif">→</span>
        </button>
        <button className="home__sec-item" onClick={() => navigate("/review")}>
          <span className="k-mono home__sec-num">02</span>
          <span className="home__sec-body">
            <span className="home__sec-title">Repaso de palabras</span>
            <span className="home__sec-dek">
              {dueCount === null
                ? "Las palabras que añadiste vuelven cuando estés por olvidarlas."
                : dueCount === 0
                ? "Nada por ahora. Volvé después de leer algo."
                : `${dueCount} ${dueCount === 1 ? "lista" : "listas"} para revisar.`}
            </span>
          </span>
          <span className="home__sec-arrow k-serif">→</span>
        </button>
        <button className="home__sec-item" onClick={() => navigate("/chat")}>
          <span className="k-mono home__sec-num">03</span>
          <span className="home__sec-body">
            <span className="home__sec-title">Hablar con Klara</span>
            <span className="home__sec-dek">Conversación libre, lo que tengas en la cabeza.</span>
          </span>
          <span className="home__sec-arrow k-serif">→</span>
        </button>
      </section>

      <footer className="home__foot">
        <Link to="/" className="home__sig" aria-label="Klara — Edición Nürnberg">
          <KlaraMark size={16} />
          <span className="k-mono">Klara — Edición Nürnberg</span>
        </Link>
      </footer>
    </main>
  );
}
