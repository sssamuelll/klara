import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { CardOut, ModulePathItem, Story, StoryListItem } from "../api/types";
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
  const [modules, setModules] = useState<ModulePathItem[] | null | undefined>(undefined);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setModules(undefined);
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
      try {
        const mods = await api.listModules();
        if (!cancelled) setModules(mods);
      } catch {
        if (!cancelled) setModules(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t]);

  const dateLabel = useMastheadDate();
  const hello = useGreeting();

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

      {!loading && modules !== undefined && (
        <section className="path">
          <span className="k-mono path__kicker">{t("path.kicker")}</span>
          {modules && modules.length > 0 ? (
            <ol className="path__list">
              {modules.map((m) => (
                <li key={m.id}>
                  <button
                    className={[
                      "path__node",
                      m.is_current ? "path__node--current" : "",
                      m.completed ? "path__node--completed" : "",
                      !m.unlocked && !m.completed ? "path__node--locked" : "",
                    ].join(" ")}
                    onClick={() => navigate(`/module/${m.id}`)}
                  >
                    <span className="k-mono path__num">
                      {String(m.sequence_order).padStart(2, "0")}
                    </span>
                    <span className="path__body">
                      <span className="path__title">
                        {m.title}
                        {m.completed && <span className="path__check" aria-hidden> ✓</span>}
                      </span>
                      <span className="path__meta k-mono">
                        {m.completed
                          ? t("path.completedTag")
                          : m.is_current
                          ? t("path.stories", { count: m.stories_finished, total: m.stories_to_complete })
                          : !m.unlocked
                          ? t("path.lockedTag")
                          : t("path.words", { count: m.encountered, total: m.total })}
                      </span>
                      <span className="path__bar" aria-hidden>
                        <span
                          className="path__bar-fast"
                          style={{ width: `${m.total ? (m.encountered / m.total) * 100 : 0}%` }}
                        />
                        <span
                          className="path__bar-slow"
                          style={{ width: `${m.total ? (m.mastered / m.total) * 100 : 0}%` }}
                        />
                      </span>
                    </span>
                    <span className="path__cta k-mono">
                      {m.is_current
                        ? t("path.continue")
                        : !m.unlocked && !m.completed
                        ? t("path.startAnyway")
                        : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          ) : (
            <p className="path__empty">{t("path.empty")}</p>
          )}
        </section>
      )}

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
        <button className="home__sec-item" onClick={() => navigate("/gender")}>
          <span className="k-mono home__sec-num">04</span>
          <span className="home__sec-body">
            <span className="home__sec-title">{t("home.sec.genderReview.title")}</span>
            <span className="home__sec-dek">{t("home.sec.genderReview.dek")}</span>
          </span>
          <span className="home__sec-arrow k-serif">→</span>
        </button>
      </section>

      <footer className="home__foot">
        <Link to="/" className="home__sig" aria-label={t("home.footer.aria")}>
          <KlaraMark size={16} />
          <span className="k-mono">{t("home.footer.edition")}</span>
        </Link>
      </footer>
    </main>
  );
}
