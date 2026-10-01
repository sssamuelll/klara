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

  // La pantalla sigue montada mientras la app está en segundo plano: al volver se pide el día otra
  // vez. `medianocheLocal()` se evalúa entonces, así que pasada la medianoche llega el día nuevo, y
  // `today` se queda a la vista mientras tanto (sin parpadeo de carga).
  useEffect(() => {
    const alVolver = () => {
      if (document.visibilityState === "visible") setIntento((n) => n + 1);
    };
    document.addEventListener("visibilitychange", alVolver);
    return () => document.removeEventListener("visibilitychange", alVolver);
  }, []);

  const vm = buildHoyVM(today);
  const tema = user ? languageLabel(user.target_language) : "…";
  // El idioma de estudio: el texto que está en él (el título de la historia, la frase, el tema) lo
  // declara con `lang`, para el lector de pantalla y para que el compuesto largo parta con guion.
  const idioma = user?.target_language;

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
          {/* El nombre accesible mezcla idiomas («Deutsch, Tu biblioteca»): el `lang` va solo en el tema, no en el botón. */}
          <button
            type="button"
            className="k-btn k-btn--text"
            aria-label={`${tema}, ${t("biblioteca.titulo")}`}
            onClick={() => navigate("/biblioteca")}
          >
            <span lang={idioma}>{tema}</span>
            <Chevron />
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
        {/* El error es solo para cuando no hay plan que enseñar: si falla el pedido de al volver a la
            app con uno a la vista, ese plan se queda tal cual, sin banner. */}
        {fallo && today === null && (
          <p className="k-error" role="alert">
            {t("hoy.error")}{" "}
            <button type="button" className="k-btn k-btn--text" onClick={() => setIntento((n) => n + 1)}>
              {t("hoy.reintentar")}
            </button>
          </p>
        )}
        {falloReclamo && <p className="k-error" role="alert">{t("module.claimError")}</p>}
        <ol className="k-route" role="list">
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
                  <PanelActual panel={vm.panel} ocupado={reclamando} idioma={idioma} onAccion={actuar} />
                </div>
              ) : (
                <FilaParada parada={p} idioma={idioma} onAccion={actuar} />
              )}
            </li>
          ))}
        </ol>
        <p className="k-route__end">{vm.todoHecho ? t("hoy.finHecho") : t("hoy.fin")}</p>
      </div>
    </main>
  );
}

function FilaParada({
  parada,
  idioma,
  onAccion,
}: {
  parada: Parada;
  idioma: string | undefined;
  onAccion: (a: Accion) => void;
}) {
  const { t } = useTranslation();
  // El título de la historia está en el idioma de estudio; lo demás del subtítulo, en el tuyo.
  const historia = parada.id === "leer" && parada.historia ? parada.historia : null;
  const sub =
    historia ??
    (parada.id === "repasar" && parada.vencen
      ? t("hoy.fichas", { count: parada.vencen })
      : t(`curso.paso.${parada.id}.dek`));
  return (
    <button type="button" className="k-route__row" onClick={() => onAccion(parada.accion)}>
      <span className="k-route__title">{t(`curso.paso.${parada.id}.titulo`)}</span>
      <span className="k-route__meta">
        {parada.estado === "done" ? t("hoy.hecho") : t(`curso.paso.${parada.id}.meta`)}
      </span>
      <span className="k-route__sub" lang={historia ? idioma : undefined}>{sub}</span>
    </button>
  );
}

function PanelActual({
  panel,
  ocupado,
  idioma,
  onAccion,
}: {
  panel: Panel;
  ocupado: boolean;
  idioma: string | undefined;
  onAccion: (a: Accion) => void;
}) {
  const { t } = useTranslation();
  const arte = panel.tipo === "leer" ? panel.arte : null;
  // El src que falló y no un booleano: si el día se refresca con otra historia, su ilustración
  // trae otro src y se intenta de nuevo; la de una imagen rota no suprime la siguiente.
  const [arteRota, setArteRota] = useState<string | null>(null);
  const tag = `${t(`curso.paso.${panel.tipo}.titulo`)} · ${t(`curso.paso.${panel.tipo}.meta`)}`;

  let titulo = "";
  let enIdioma = false; // el titular es texto en el idioma de estudio, no de la interfaz
  let dek: string | null = null;
  let cta: string | null = t("hoy.empezar");
  switch (panel.tipo) {
    case "leer":
      titulo = panel.estado === "request" ? t("hoy.pedir") : (panel.titulo ?? t("curso.paso.leer.dek"));
      enIdioma = panel.estado !== "request" && panel.titulo !== null;
      dek = panel.estado === "request" ? null : panel.subtitulo;
      cta = panel.estado === "continue" ? t("hoy.seguir") : panel.estado === "new" ? t("hoy.empezar") : null;
      break;
    case "pronunciar":
      titulo = panel.frase ? `„${panel.frase.target}“` : t("curso.paso.pronunciar.titulo");
      enIdioma = panel.frase !== null;
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
      {arte && arteRota !== arte && (
        <img className="k-hero__art" src={arte} alt="" onError={() => setArteRota(arte)} />
      )}
      <span className="k-hero__tag">
        <span>{tag}</span>
        {cta && <span>{cta}</span>}
      </span>
      <span className="k-hero__title" lang={enIdioma ? idioma : undefined}>{titulo}</span>
      <span className="k-hero__arrow" aria-hidden="true">→</span>
      {dek && <span className="k-hero__dek">{dek}</span>}
    </button>
  );
}

/** El ⌄ del tema. JetBrains Mono no trae U+2304 y caía a una «v» en la línea de base, así que se
    dibuja: caja de 16px (la de `.k-btn svg`), trazo de 1.5 y currentColor como los iconos de la
    barra de pestañas, y el dibujo a la altura de las versalitas mono (11px), arrimado a la
    izquierda de su caja para quedar junto a la palabra. */
function Chevron() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 7.8l4.4 4.4 4.4-4.4" />
    </svg>
  );
}
