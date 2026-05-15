import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { CardOut, Story, StoryListItem } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import { useMastheadDate, useGreeting } from "../lib/dateLabel";
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

function summarize(story: Story, fallbackDek: string): HomeStorySummary {
  const wordCount = story.content.sentences.reduce(
    (acc, s) => acc + s.target.trim().split(/\s+/).filter(Boolean).length,
    0
  );
  const minutes = Math.max(1, Math.round(wordCount / 60));
  const dek = story.content.sentences[0]?.native ?? fallbackDek;
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
  const { t } = useTranslation();
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
          if (!cancelled) setLatest(summarize(full, t("home.latest.fallbackDek")));
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
  }, [t]);

  const dateLabel = useMastheadDate();
  const hello = useGreeting();
  const city = "Nürnberg";

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
        <p className="home__sub">{t("home.sub")}</p>
      </div>

      <hr className="k-rule home__rule" />

      {loading ? (
        <div className="story-loading">
          <span className="k-mono">{t("common.loading")}</span>
        </div>
      ) : latest ? (
        <button className="home__feature" onClick={() => navigate(`/story/${latest.id}`)}>
          <div className="home__feature-meta">
            <span className="k-mono">{t("home.latest.kicker")}</span>
            <span className="k-level">{latest.level}</span>
          </div>
          <h2 className="home__feature-title">{latest.title}</h2>
          <p className="home__feature-dek">{latest.dek}</p>
          <div className="home__feature-foot">
            <div className="home__feature-stats">
              <span className="k-mono">{t("home.latest.minutes", { count: latest.minutes })}</span>
              <span className="home__dot" />
              <span className="k-mono">{t("home.latest.words", { count: latest.wordCount })}</span>
              {latest.newWordsCount > 0 && (
                <>
                  <span className="home__dot" />
                  <span className="k-mono">{t("home.latest.new", { count: latest.newWordsCount })}</span>
                </>
              )}
            </div>
            <span className="k-link">
              {t("home.latest.cta")} <span className="k-serif" style={{ fontStyle: "italic" }}>→</span>
            </span>
          </div>
        </button>
      ) : (
        <button className="home__feature" onClick={() => navigate("/story/new")}>
          <div className="home__feature-meta">
            <span className="k-mono">{t("home.firstFeature.kicker")}</span>
          </div>
          <h2 className="home__feature-title">{t("home.firstFeature.title")}</h2>
          <p className="home__feature-dek">{t("home.firstFeature.dek")}</p>
          <div className="home__feature-foot">
            <span className="k-link">
              {t("home.firstFeature.cta")} <span className="k-serif" style={{ fontStyle: "italic" }}>→</span>
            </span>
          </div>
        </button>
      )}

      <hr className="k-rule home__rule" />

      <section className="home__secondary">
        <button className="home__sec-item" onClick={() => navigate("/story/new")}>
          <span className="k-mono home__sec-num">01</span>
          <span className="home__sec-body">
            <span className="home__sec-title">{t("home.sec.newStory.title")}</span>
            <span className="home__sec-dek">{t("home.sec.newStory.dek")}</span>
          </span>
          <span className="home__sec-arrow k-serif">→</span>
        </button>
        <button className="home__sec-item" onClick={() => navigate("/review")}>
          <span className="k-mono home__sec-num">02</span>
          <span className="home__sec-body">
            <span className="home__sec-title">{t("home.sec.review.title")}</span>
            <span className="home__sec-dek">
              {dueCount === null
                ? t("home.sec.review.dek.unknown")
                : dueCount === 0
                ? t("home.sec.review.dek.none")
                : t("home.sec.review.dek.due", { count: dueCount })}
            </span>
          </span>
          <span className="home__sec-arrow k-serif">→</span>
        </button>
        <button className="home__sec-item" onClick={() => navigate("/chat")}>
          <span className="k-mono home__sec-num">03</span>
          <span className="home__sec-body">
            <span className="home__sec-title">{t("home.sec.chat.title")}</span>
            <span className="home__sec-dek">{t("home.sec.chat.dek")}</span>
          </span>
          <span className="home__sec-arrow k-serif">→</span>
        </button>
      </section>

      <footer className="home__foot">
        <Link to="/" className="home__sig" aria-label={t("home.footer.aria", { city })}>
          <KlaraMark size={16} />
          <span className="k-mono">{t("home.footer.edition", { city })}</span>
        </Link>
      </footer>
    </main>
  );
}
