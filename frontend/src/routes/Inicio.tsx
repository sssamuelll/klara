import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { CardOut, ModulePathItem, StoryListItem } from "../api/types";
import { buildCourseVM, type CourseVM } from "../lib/courseView";
import { useGreeting, useMastheadDate } from "../lib/dateLabel";
import { languageLabel } from "../lib/languages";
import { useUser } from "../lib/user";
import KlaraMark from "../components/KlaraMark";

export function useCourseData(): { vm: CourseVM } {
  const [vm, setVm] = useState<CourseVM>(() =>
    buildCourseVM({ modules: null, due: null, latestStoryId: null })
  );
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [modules, due, stories] = await Promise.all([
        api.listModules().catch(() => null),
        // ponytail: el 50 es explícito — el default del cliente es 20 y capa el badge.
        api.dueCards(50).catch(() => null),
        api.listStories(1, 0).catch(() => [] as StoryListItem[]),
      ]);
      if (cancelled) return;
      setVm(
        buildCourseVM({
          modules: modules as ModulePathItem[] | null,
          due: due as CardOut[] | null,
          latestStoryId: stories[0]?.id ?? null,
        })
      );
    })();
    return () => { cancelled = true; };
  }, []);
  return { vm };
}

export default function Inicio() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const { vm } = useCourseData();
  const fecha = useMastheadDate();
  const hola = useGreeting();
  const paso = vm.pasos.find((p) => p.e === "ahora") ?? vm.pasos[0];
  const titulo = user ? languageLabel(user.target_language) : "…";

  return (
    <main className="k-page">
      <header className="k-topline">
        <span className="k-topline__mark"><KlaraMark size={14} /><span className="wordmark">Klara</span></span>
        <span className="k-topline__meta">{fecha}</span>
      </header>
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">
          <Trans
            i18nKey="home.greeting.conNombre"
            values={{ hola, name: user?.display_name ?? "…" }}
            components={{ 1: <em /> }}
          />
        </h1>
      </header>
      <h2 className="k-cap k-cap--rule">{t("biblioteca.titulo")}</h2>
      <ul>
        <li>
          <button
            type="button"
            className="k-row"
            data-state={vm.vencen != null && vm.vencen > 0 ? "now" : undefined}
            onClick={() => navigate("/curso/aleman")}
          >
            <span className="k-row__title">{titulo}</span>
            <span className="k-row__meta">
              {vm.vencen != null && vm.vencen > 0
                ? t("biblioteca.estadoDue", { count: vm.vencen })
                : t("biblioteca.estadoHoy")}
            </span>
            <span className="k-row__sub">{t("biblioteca.cursoSub", { level: user?.level ?? "" })}</span>
            <span className="k-bar k-bar--fill">
              <span
                className="k-bar__track"
                role="progressbar"
                aria-label={t("mapa.progressAria", { pct: Math.round(vm.progreso * 100) })}
                aria-valuenow={Math.round(vm.progreso * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <i className="k-bar__fill" style={{ width: `${vm.progreso * 100}%` }} />
              </span>
            </span>
          </button>
        </li>
        <li>
          <button type="button" className="k-row" onClick={() => navigate("/nuevo")}>
            <span className="k-row__n" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14" /></svg>
            </span>
            <span className="k-row__title">{t("biblioteca.nuevoTitulo")}</span>
            <span className="k-row__sub">{t("biblioteca.nuevoDek")}</span>
          </button>
        </li>
      </ul>
      <button type="button" className="k-hero" style={{ marginTop: "auto" }} onClick={() => navigate(paso.to, { state: { from: "/" } })}>
        <span className="k-hero__tag">
          <span>{t("biblioteca.heroTag", { curso: titulo })}</span>
          <span>{t(`curso.paso.${paso.id}.meta`)}</span>
        </span>
        <span className="k-hero__title">{t(`curso.paso.${paso.id}.titulo`)}</span>
        <span className="k-hero__arrow" aria-hidden="true">→</span>
        <span className="k-hero__dek">{t(`curso.paso.${paso.id}.dek`)}</span>
      </button>
    </main>
  );
}
