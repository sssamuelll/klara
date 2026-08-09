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
    <main className="m3-page">
      <div className="m3-top">
        <span className="marca"><KlaraMark size={14} /><span className="wordmark">Klara</span></span>
        <span>{fecha}</span>
      </div>
      <h1 className="m4-saludo">
        <Trans
          i18nKey="home.greeting.conNombre"
          values={{ hola, name: user?.display_name ?? "…" }}
          components={{ 1: <em /> }}
        />
      </h1>
      <div className="m4-sec">{t("biblioteca.titulo")}</div>
      <div className="m4-lib">
        <button className="m4-tema" onClick={() => navigate("/curso/aleman")}>
          <span className="f1">
            <span className="tit">{titulo}</span>
            <span className="estado" data-hot={vm.vencen != null && vm.vencen > 0 ? "true" : "false"}>
              {vm.vencen != null && vm.vencen > 0
                ? t("biblioteca.estadoDue", { count: vm.vencen })
                : t("biblioteca.estadoHoy")}
            </span>
          </span>
          <span className="sub">{t("biblioteca.cursoSub", { level: user?.level ?? "" })}</span>
          <span className="m4-bar"><i style={{ width: `${vm.progreso * 100}%` }} /></span>
        </button>
        <button className="m4-add" onClick={() => navigate("/nuevo")}>
          <span className="tile" aria-hidden="true">+</span>
          <span>
            <span className="tit">{t("biblioteca.nuevoTitulo")}</span>
            <span className="sub">{t("biblioteca.nuevoDek")}</span>
          </span>
        </button>
      </div>
      <button className="m3-hero" style={{ marginTop: "auto" }} onClick={() => navigate(paso.to)}>
        <span className="tag">
          <span>{t("biblioteca.heroTag", { curso: titulo })}</span>
          <span>{t(`curso.paso.${paso.id}.meta`)}</span>
        </span>
        <span className="fila">
          <span>
            <h2>{t(`curso.paso.${paso.id}.titulo`)}</h2>
            <p className="dek">{t(`curso.paso.${paso.id}.dek`)}</p>
          </span>
          <span className="arrow" aria-hidden="true">→</span>
        </span>
      </button>
    </main>
  );
}
