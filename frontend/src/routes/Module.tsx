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
      navigate(`/story/${story.id}`);
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

  if (mod === undefined) {
    return (
      <main className="k-page">
        <div className="story-loading">
          <span className="k-mono">{t("common.loading")}</span>
        </div>
      </main>
    );
  }
  if (mod === null) {
    return (
      <main className="k-page">
        <button className="k-mono k-link" onClick={() => navigate("/")}>{t("module.back")}</button>
        <div className="k-error" role="alert">{t("module.claimError")}</div>
      </main>
    );
  }

  const hasLibrary = mod.library_available > 0;
  return (
    <main className="k-page">
      <button className="k-mono k-link" onClick={() => navigate("/")}>← {t("module.back")}</button>
      <div className="mod__head">
        <span className="k-level">{mod.cefr_level}</span>
        <h1 className="mod__title">{mod.title}</h1>
        <div className="mod__facts">
          {mod.can_dos.length > 0 && (
            <span className="mod__fact">
              <strong>{t("module.canDo")}:</strong> {mod.can_dos.join(" · ")}
            </span>
          )}
          {mod.grammatical_focus.length > 0 && (
            <span className="mod__fact">
              <strong>{t("module.grammarFocus")}:</strong> {mod.grammatical_focus.join(" · ")}
            </span>
          )}
          <span className="mod__fact k-mono">
            {t("module.storiesDone", { count: mod.stories_finished, total: mod.stories_to_complete })}
          </span>
          <span className="mod__fact k-mono">
            {t("module.mastered", { count: mod.mastered, total: mod.total })}
          </span>
          {mod.gender_total > 0 && (
            <span className="mod__fact k-mono">
              {t("module.gender", { count: mod.gender_mastered, total: mod.gender_total })}
            </span>
          )}
        </div>
      </div>

      {error && <div className="k-error" role="alert">{error}</div>}

      <div className="mod__actions">
        <button className="k-btn" onClick={readStory} disabled={claiming}>
          {claiming ? (
            <span className="k-spinner" />
          ) : hasLibrary ? (
            <>{t("module.readStory")} →</>
          ) : (
            <>{t("module.noLibrary")} →</>
          )}
        </button>
        <button
          className="k-btn k-btn--ghost"
          onClick={() => navigate(`/story/new?module=${mod.id}`)}
          disabled={claiming}
        >
          {t("module.createStory")}
        </button>
      </div>

      {stories.length > 0 && (
        <section className="mod__stories">
          <span className="k-mono path__kicker">{t("module.yourStories")}</span>
          {stories.map((s) => (
            <button key={s.id} className="mod__story" onClick={() => navigate(`/story/${s.id}`)}>
              <span>{s.title}</span>
              <span className="k-mono">→</span>
            </button>
          ))}
        </section>
      )}
    </main>
  );
}
