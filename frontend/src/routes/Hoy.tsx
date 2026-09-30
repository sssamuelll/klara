import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";
import { ApiError, api } from "../api/client";
import type { TodayOut } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import { useGreeting } from "../lib/dateLabel";
import { buildHoyVM, medianocheLocal, type Accion, type Panel, type Parada } from "../lib/hoyView";
import { languageLabel } from "../lib/languages";
import { useUser } from "../lib/user";

export default function Hoy() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const hola = useGreeting();
  const [today, setToday] = useState<TodayOut | null>(null);
  const [fallo, setFallo] = useState(false);
  const [intento, setIntento] = useState(0);
  const [reclamando, setReclamando] = useState(false);
  const [falloReclamo, setFalloReclamo] = useState(false);

  useEffect(() => {
    let cancelado = false;
    setFallo(false);
    api.today(medianocheLocal()).then(
      (d) => { if (!cancelado) setToday(d); },
      () => { if (!cancelado) setFallo(true); },
    );
    return () => { cancelado = true; };
  }, [intento]);

  const vm = buildHoyVM(today);
  const tema = user ? languageLabel(user.target_language) : "…";

  async function actuar(accion: Accion) {
    setFalloReclamo(false);
    if (accion.tipo === "ir") {
      navigate(accion.to, { state: { from: "/" } });
      return;
    }
    if (reclamando) return; // doble toque: un solo reclamo
    setReclamando(true);
    try {
      const story = await api.claimModuleStory(accion.moduleId);
      navigate(`/estudiar/${story.id}`, { state: { from: "/" } });
    } catch (e) {
      // El código "library.empty" viaja en el mensaje del ApiError (ver Module.tsx).
      if (e instanceof ApiError && e.status === 404 && e.message.includes("library.empty")) {
        navigate("/story/new", { state: { from: "/" } });
        return;
      }
      setReclamando(false);
      setFalloReclamo(true);
    }
  }

  return (
    <main className="k-page">
      <header className="k-topline">
        <span className="k-topline__mark">
          <button
            type="button"
            className="k-btn k-btn--text"
            aria-label={`${tema}, ${t("biblioteca.titulo")}`}
            onClick={() => navigate("/biblioteca")}
          >
            {tema} <span aria-hidden="true">⌄</span>
          </button>
          <span className="k-topline__meta">{t("biblioteca.cursoSub", { level: user?.level ?? "" })}</span>
        </span>
        <KlaraMark size={14} />
      </header>
      <div className="k-live">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">
            <Trans
              i18nKey="home.greeting.conNombre"
              values={{ hola, name: user?.display_name ?? "…" }}
              components={{ 1: <em /> }}
            />
          </h1>
        </header>
        <h2 className="k-cap k-cap--rule">
          {vm.todoHecho ? t("hoy.planHecho") : t("hoy.plan", { min: vm.minutos })}
        </h2>
        {fallo && (
          <p className="k-error" role="alert">
            {t("hoy.error")}{" "}
            <button type="button" className="k-btn k-btn--text" onClick={() => setIntento((n) => n + 1)}>
              {t("hoy.reintentar")}
            </button>
          </p>
        )}
        {falloReclamo && <p className="k-error" role="alert">{t("module.claimError")}</p>}
        <ol className="k-route">
          {vm.paradas.map((p) => (
            <li
              key={p.id}
              className="k-route__stop"
              data-state={p.estado}
              aria-current={p.estado === "now" ? "step" : undefined}
            >
              <span className="k-route__dot" aria-hidden="true" />
              {p.estado === "now" && vm.panel ? (
                <div className="k-route__body">
                  <span className="k-route__label">{t("hoy.estasAqui")}</span>
                  <PanelActual panel={vm.panel} ocupado={reclamando} onAccion={actuar} />
                </div>
              ) : (
                <FilaParada parada={p} onAccion={actuar} />
              )}
            </li>
          ))}
        </ol>
        <p className="k-route__end">{vm.todoHecho ? `${t("hoy.listo")} ${t("hoy.fin")}` : t("hoy.fin")}</p>
      </div>
    </main>
  );
}

function FilaParada({ parada, onAccion }: { parada: Parada; onAccion: (a: Accion) => void }) {
  const { t } = useTranslation();
  const sub =
    parada.id === "leer" && parada.historia
      ? parada.historia
      : parada.id === "repasar" && parada.vencen
        ? t("hoy.fichas", { count: parada.vencen })
        : t(`curso.paso.${parada.id}.dek`);
  return (
    <button type="button" className="k-route__row" onClick={() => onAccion(parada.accion)}>
      <span className="k-route__title">{t(`curso.paso.${parada.id}.titulo`)}</span>
      <span className="k-route__meta">
        {parada.estado === "done" ? t("hoy.hecho") : t(`curso.paso.${parada.id}.meta`)}
      </span>
      <span className="k-route__sub">{sub}</span>
    </button>
  );
}

function PanelActual({
  panel,
  ocupado,
  onAccion,
}: {
  panel: Panel;
  ocupado: boolean;
  onAccion: (a: Accion) => void;
}) {
  const { t } = useTranslation();
  const [arteRota, setArteRota] = useState(false);
  const tag = `${t(`curso.paso.${panel.tipo}.titulo`)} · ${t(`curso.paso.${panel.tipo}.meta`)}`;

  let titulo = "";
  let dek: string | null = null;
  let cta: string | null = t("hoy.empezar");
  switch (panel.tipo) {
    case "leer":
      titulo = panel.estado === "request" ? t("hoy.pedir") : (panel.titulo ?? t("curso.paso.leer.dek"));
      dek = panel.estado === "request" ? null : panel.subtitulo;
      cta = panel.estado === "continue" ? t("hoy.seguir") : panel.estado === "new" ? t("hoy.empezar") : null;
      break;
    case "pronunciar":
      titulo = panel.frase ? `„${panel.frase.target}“` : t("curso.paso.pronunciar.titulo");
      dek = panel.frase ? panel.frase.native : t("curso.paso.pronunciar.dek");
      break;
    case "hablar":
      titulo = t("curso.paso.hablar.dek");
      dek = null;
      break;
    case "repasar":
      titulo = t("hoy.fichas", { count: panel.vencen });
      dek = t("curso.paso.repasar.dek");
      break;
  }

  return (
    <button type="button" className="k-hero" disabled={ocupado} onClick={() => onAccion(panel.accion)}>
      {panel.tipo === "leer" && panel.arte && !arteRota && (
        <img className="k-hero__art" src={panel.arte} alt="" onError={() => setArteRota(true)} />
      )}
      <span className="k-hero__tag">
        <span>{tag}</span>
        {cta && <span>{cta}</span>}
      </span>
      <span className="k-hero__title">{titulo}</span>
      <span className="k-hero__arrow" aria-hidden="true">→</span>
      {dek && <span className="k-hero__dek">{dek}</span>}
    </button>
  );
}
