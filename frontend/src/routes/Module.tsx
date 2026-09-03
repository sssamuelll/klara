import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../api/client";
import type { ModulePathItem, StoryListItem } from "../api/types";

export default function Module() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [mod, setMod] = useState<ModulePathItem | null | undefined>(undefined);
  const [stories, setStories] = useState<StoryListItem[]>([]);
  const [claiming, setClaiming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // ponytail: 8 modules — fetch the list and find; a by-id endpoint can
        // come when a language ships enough modules to matter.
        const mods = await api.listModules();
        if (cancelled) return;
        setMod(mods.find((m) => m.id === id) ?? null);
      } catch {
        if (!cancelled) setMod(null);
      }
      try {
        if (id) {
          const list = await api.listModuleStories(id);
          if (!cancelled) setStories(list);
        }
      } catch {
        /* list stays empty */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function readStory() {
    if (!id || claiming) return;
    setClaiming(true);
    setError(null);
    try {
      const story = await api.claimModuleStory(id);
      navigate(`/estudiar/${story.id}`, { state: { from: `/module/${id}` } });
    } catch (e) {
      // ApiError.message is `${status} ${statusText}: ${detail}` (see
      // client.ts) — the backend's "library.empty" detail code is a
      // contract string, not localized, so a substring match on the
      // composite message is safe.
      if (e instanceof ApiError && e.status === 404 && e.message.includes("library.empty")) {
        navigate(`/story/new?module=${id}`);
      } else {
        setError(t("module.claimError"));
      }
    } finally {
      setClaiming(false);
    }
  }

  const back = (
    <button type="button" className="k-btn k-btn--text" onClick={() => navigate("/")}>
      {t("module.back")}
    </button>
  );

  if (mod === undefined) {
    return (
      <main className="k-page">
        <span className="k-spinner" role="status" aria-label={t("common.loading")} />
      </main>
    );
  }
  if (mod === null) {
    return (
      <main className="k-page">
        {back}
        <p className="k-error" role="alert">{t("module.claimError")}</p>
      </main>
    );
  }

  const hasLibrary = mod.library_available > 0;
  return (
    <main className="k-page">
      {back}

      <header className="k-hero k-hero--quiet">
        <span className="k-level">{mod.cefr_level}</span>
        <h1 className="k-hero__title">{mod.title}</h1>
        <p className="k-hero__meta">
          <span>
            {t("module.storiesDone", {
              count: mod.stories_finished,
              total: mod.stories_to_complete,
            })}
          </span>
          <span>{t("module.mastered", { count: mod.mastered, total: mod.total })}</span>
          {mod.gender_total > 0 && (
            <span>
              {t("module.gender", { count: mod.gender_mastered, total: mod.gender_total })}
            </span>
          )}
        </p>
      </header>

      {(mod.can_dos.length > 0 || mod.grammatical_focus.length > 0) && (
        <div className="k-note">
          {mod.can_dos.length > 0 && (
            <p className="k-note__body">
              <strong className="k-note__cap">{t("module.canDo")}</strong> {mod.can_dos.join(" · ")}
            </p>
          )}
          {mod.grammatical_focus.length > 0 && (
            <p className="k-note__body">
              <strong className="k-note__cap">{t("module.grammarFocus")}</strong>{" "}
              {mod.grammatical_focus.join(" · ")}
            </p>
          )}
        </div>
      )}

      {error && <p className="k-error" role="alert">{error}</p>}

      <div className="k-wrap">
        <button
          type="button"
          className="k-btn"
          onClick={readStory}
          disabled={claiming}
          aria-busy={claiming}
        >
          {claiming ? (
            <span className="k-spinner" />
          ) : (
            <>
              {hasLibrary ? t("module.readStory") : t("module.noLibrary")}
              <span className="k-btn__arrow">→</span>
            </>
          )}
        </button>
        <button
          type="button"
          className="k-btn k-btn--ghost"
          onClick={() => navigate(`/story/new?module=${mod.id}`)}
          disabled={claiming}
        >
          {t("module.createStory")}
        </button>
      </div>

      {stories.length > 0 && (
        <>
          <p className="k-cap">{t("module.yourStories")}</p>
          <ul>
            {stories.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  className="k-row"
                  onClick={() =>
                    navigate(`/estudiar/${s.id}`, { state: { from: `/module/${id}` } })
                  }
                >
                  <span className="k-row__title">{s.title}</span>
                  <span className="k-row__arrow">→</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
