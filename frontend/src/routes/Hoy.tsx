import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Linea, TodayOut } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import { useGreeting, useMastheadDate } from "../lib/dateLabel";
import { partirKana } from "../lib/dinamicas/trazo";
import { alDia, buildHoyVM, dekPanel, estadoParada, frase, medianocheLocal, subFila, type TextoLinea } from "../lib/hoyView";
import { languageLabel } from "../lib/languages";
import { unlockAudio } from "../lib/tts";
import { useUser } from "../lib/user";

/**
 * Hoy (spec 2026-10-09 §5.1): una línea por idioma de estudio. Cada línea son
 * los repasos de ese idioma y la lección que sigue en su mapa, en una sola
 * sesión. El orden lo pone el servidor; la primera con algo por hacer es
 * «estás aquí». Una línea al día (mapa terminado, ningún repaso) es una fila
 * sin botón: abrirla daría una sesión vacía.
 */
export default function Hoy() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const hola = useGreeting();
  const fecha = useMastheadDate();
  const [today, setToday] = useState<TodayOut | null>(null);
  const [fallo, setFallo] = useState(false);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let cancelado = false;
    setFallo(false);
    api.today(medianocheLocal()).then(
      (d) => {
        if (!cancelado) setToday(d);
      },
      () => {
        if (!cancelado) setFallo(true);
      },
    );
    return () => {
      cancelado = true;
    };
  }, [intento]);

  // La pantalla sigue montada con la app en segundo plano: al volver se pide el día otra vez,
  // y pasada la medianoche llega el día nuevo.
  useEffect(() => {
    const alVolver = () => {
      if (document.visibilityState === "visible") setIntento((n) => n + 1);
    };
    document.addEventListener("visibilitychange", alVolver);
    return () => document.removeEventListener("visibilitychange", alVolver);
  }, []);

  const vm = buildHoyVM(today);

  // La bajada y el título de la lección vienen del catálogo, con algún kana dentro: ahí va `ConKana`
  // (en «luego», la frase entera: la bajada ya viene interpolada).
  const texto = (x: TextoLinea): ReactNode => {
    switch (x.tipo) {
      case "alDia":
        return t("hoy.alDiaSub");
      case "soloRepasos":
        return t("hoy.soloRepasos");
      case "bajada":
        return <ConKana texto={frase(x.bajada)} />;
      case "luego":
        return <ConKana texto={t("hoy.luego", { repasos: t("hoy.repasos", { count: x.repasos }), bajada: x.bajada })} />;
      case "repasos": {
        const r = t("hoy.repasos", { count: x.repasos });
        return x.detalle ? (
          <>
            {r} · <ConKana texto={x.detalle} />
          </>
        ) : (
          r
        );
      }
    }
  };

  // El toque que abre la sesión desbloquea el audio: lo primero que suena es un kana.
  const abrir = (l: Linea) => {
    unlockAudio();
    navigate(`/sesion/${l.idioma}`, { state: { from: "/" } });
  };

  const rotulo = vm.todoHecho
    ? t("hoy.planHecho")
    : vm.algunaHecha
      ? t("hoy.quedan", { min: vm.minutos })
      : t("hoy.plan", { min: vm.minutos });

  const meta = (l: Linea) =>
    l.estado === "hecha" ? t("hoy.hecho") : alDia(l) ? t("hoy.alDia") : t("hoy.minutos", { min: l.minutos });

  return (
    <main className="k-page">
      <header className="k-topline">
        <span className="k-topline__mark">
          <KlaraMark size={14} />
          <span className="wordmark">Klara</span>
        </span>
        <span className="k-topline__meta">{fecha}</span>
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
        {today === null ? (
          // Sin día que enseñar: cargando, o el error. Si falla el pedido de al volver a la app con un
          // día a la vista, ese día se queda tal cual, sin banner.
          fallo ? (
            <p className="k-error" role="alert">
              {t("hoy.error")}{" "}
              <button type="button" className="k-btn k-btn--text" onClick={() => setIntento((n) => n + 1)}>
                {t("hoy.reintentar")}
              </button>
            </p>
          ) : (
            <span className="k-spinner" role="status" aria-label={t("common.loading")} />
          )
        ) : vm.sinIdiomas ? (
          <div className="k-note">
            <p className="k-note__body">{t("hoy.sinIdiomas")}</p>
            <div className="k-note__actions">
              <button type="button" className="k-btn k-btn--ghost" onClick={() => navigate("/settings")}>
                {t("hoy.irAjustes")}
              </button>
            </div>
          </div>
        ) : (
          <>
            <h2 className="k-cap k-cap--rule">{rotulo}</h2>
            <ol className="k-route" role="list">
              {vm.lineas.map((l) => {
                const estado = estadoParada(l, vm.ahora);
                return (
                  <li
                    key={l.idioma}
                    className="k-route__stop"
                    data-state={estado}
                    aria-current={estado === "now" ? "step" : undefined}
                  >
                    <span className="k-route__dot" aria-hidden="true" />
                    {estado === "now" ? (
                      <div className="k-route__body">
                        <span className="k-route__label">{t("hoy.estasAqui")}</span>
                        <button type="button" className="k-hero" onClick={() => abrir(l)}>
                          <span className="k-hero__tag">
                            <span>
                              <span lang={l.idioma}>{languageLabel(l.idioma)}</span> · {t("hoy.minutos", { min: l.minutos })}
                            </span>
                            <span>{t("hoy.empezar")}</span>
                          </span>
                          <span className="k-hero__title" lang={l.leccion ? l.idioma : undefined}>
                            {l.leccion?.titulo ?? t("hoy.repasos", { count: l.repasos })}
                          </span>
                          <span className="k-hero__arrow" aria-hidden="true">→</span>
                          <span className="k-hero__dek">{texto(dekPanel(l))}</span>
                        </button>
                      </div>
                    ) : (
                      <Fila linea={l} meta={meta(l)} sub={texto(subFila(l))} onAbrir={alDia(l) ? null : () => abrir(l)} />
                    )}
                  </li>
                );
              })}
            </ol>
            <p className="k-route__end">{vm.todoHecho ? t("hoy.finHecho") : t("hoy.fin")}</p>
          </>
        )}
      </div>
    </main>
  );
}

/** Una parada que no es el «estás aquí». Con `onAbrir` es un botón; sin él (la línea al día) es una fila quieta. */
function Fila({ linea, meta, sub, onAbrir }: { linea: Linea; meta: string; sub: ReactNode; onAbrir: (() => void) | null }) {
  const dentro = (
    <>
      <span className="k-route__title" lang={linea.idioma}>{languageLabel(linea.idioma)}</span>
      <span className="k-route__meta">{meta}</span>
      <span className="k-route__sub">{sub}</span>
    </>
  );
  return onAbrir ? (
    <button type="button" className="k-route__row" onClick={onAbrir}>
      {dentro}
    </button>
  ) : (
    <div className="k-route__row k-route__row--quiet">{dentro}</div>
  );
}

/** La bajada es español con algún kana dentro («la fila de か»): cada tramo de kana lleva su `lang="ja"`. */
function ConKana({ texto }: { texto: string }) {
  return (
    <>
      {partirKana(texto).map((p, i) =>
        p.ja ? (
          <span key={i} lang="ja">
            {p.texto}
          </span>
        ) : (
          p.texto
        ),
      )}
    </>
  );
}
