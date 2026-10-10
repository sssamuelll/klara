/**
 * El reproductor de lecciones (spec 2026-10-09 §5.4): la línea de un idioma
 * (repasos y la lección que sigue) o una lección repetida desde el mapa.
 *
 * Superficie suelta, como /repaso: pinta su propio `.k-app`. Aquí viven los
 * efectos (pedir la sesión, abrir y cerrar la corrida, mandar evidencias,
 * avanzar solo); las transiciones están en el reducer puro de `lib/sesion.ts`.
 */
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Evidencia, Faceta, SesionOut } from "../api/types";
import SessTop from "../components/SessTop";
import { DINAMICAS } from "../dinamicas/registro";
import type { Capacidades } from "../dinamicas/tipos";
import { apiBase } from "../lib/apiBase";
import { languageLabel } from "../lib/languages";
import {
  AUTO_AVANCE_MS,
  ENTRADA_MIN_MS,
  etiquetaItem,
  inicialSesion,
  necesita,
  porReforzar,
  sesionReducer,
  type Marca,
} from "../lib/sesion";
import { speak, stop, unlockAudio } from "../lib/tts";

const pad2 = (n: number) => String(n).padStart(2, "0");

type Carga = { s: SesionOut; run: string | null };

/**
 * Pide la sesión y, si trae actividades, abre su corrida. Fuera del componente a
 * propósito: el efecto de carga comparte la promesa entre sus dos pasadas de
 * StrictMode, y una función del componente no se podría compartir.
 */
async function cargar(
  idioma: string,
  unidad: string | undefined,
  leccion: string | undefined,
  conRepasos: boolean,
): Promise<Carga> {
  const deMapa = unidad && leccion ? { unidad, leccion } : null;
  const s = deMapa
    ? await api.leccion(idioma, deMapa.unidad, deMapa.leccion)
    : await api.sesion(idioma, conRepasos);
  if (s.actividades.length === 0) return { s, run: null };
  const run = await api.abrirRun({
    idioma,
    leccion_id: s.leccion?.id ?? null,
    origen: deMapa ? "mapa" : "hoy",
    repasos: s.actividades.filter((a) => a.repaso).length,
  });
  return { s, run: run.id };
}

export default function Sesion(): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { idioma = "", unidad, leccion } = useParams();
  const [params] = useSearchParams();
  const repetir = Boolean(unidad && leccion);
  const conRepasos = params.get("repasos") !== "0";
  const salirA = (location.state as { from?: string } | null)?.from ?? "/";
  const salir = useCallback(() => {
    stop();
    navigate(salirA);
  }, [navigate, salirA]);

  const [estado, dispatch] = useReducer(sesionReducer, inicialSesion);
  const [sesion, setSesion] = useState<SesionOut | null>(null);
  const [manana, setManana] = useState<number | null>(null);
  const [cierreFallido, setCierreFallido] = useState(false);
  const [intento, setIntento] = useState(0);
  // El id de la actividad para la que ya pasó AUTO_AVANCE_MS (ver el efecto de más abajo).
  const [apagarListoPara, setApagarListoPara] = useState<string | null>(null);
  const runId = useRef<string | null>(null);
  // La guarda del doble toque: una sola respuesta por actividad (Review Focus 1).
  const respondida = useRef<string | null>(null);
  // La carga en curso y la clave de lo que pidió. StrictMode (en desarrollo) monta
  // el efecto dos veces seguidas; si cada pasada pidiera por su cuenta, abriría
  // dos corridas y la primera se quedaría abierta para siempre.
  const carga = useRef<{ clave: string; promesa: Promise<Carga> } | null>(null);
  // Cuándo entró la actividad que está a la vista (ver ENTRADA_MIN_MS).
  const entroEn = useRef<{ id: string; t: number } | null>(null);
  // El cierre de la corrida en vuelo, si lo hay: uno a la vez, y «Otra lección» lo espera.
  const cierre = useRef<Promise<void> | null>(null);
  const montada = useRef(true);

  // Pedir la sesión y abrir su corrida. Se repite con «Reintentar» y con «Otra lección».
  useEffect(() => {
    let vivo = true;
    dispatch({ tipo: "cargando" });
    setManana(null);
    setCierreFallido(false);
    respondida.current = null;
    runId.current = null;
    // Los ids de actividad son posicionales (`a0`…): lo de la sesión anterior no vale para la nueva.
    setApagarListoPara(null);
    entroEn.current = null;
    cierre.current = null;
    const clave = [idioma, unidad, leccion, conRepasos, intento].join("|");
    if (carga.current?.clave !== clave) {
      carga.current = { clave, promesa: cargar(idioma, unidad, leccion, conRepasos) };
    }
    carga.current.promesa.then(
      ({ s, run }) => {
        if (!vivo) return;
        runId.current = run;
        setSesion(s);
        dispatch({ tipo: "cargada", actividades: s.actividades });
      },
      () => {
        if (vivo) dispatch({ tipo: "fallo" });
      },
    );
    return () => {
      vivo = false;
    };
  }, [idioma, unidad, leccion, conRepasos, intento]);

  // Cerrar la corrida y preguntar qué toca mañana. Sin el cierre la lección no queda hecha (spec §2.2):
  // mañana volverían la misma lección y su prueba, y FSRS se movería dos veces. Cerrar es idempotente en
  // el servidor, así que se reintenta una vez, y el id se queda hasta que el servidor lo confirma: si
  // falla, el final lo dice y lo vuelven a pedir «Reintentar», «Otra lección» y la salida. Una sola
  // petición en vuelo (StrictMode monta el efecto dos veces). Salir a mitad no cierra nada.
  const cerrar = useCallback((): Promise<void> => {
    const id = runId.current;
    if (id === null) return Promise.resolve();
    if (cierre.current) return cierre.current;
    setCierreFallido(false);
    const enVuelo = api
      .cerrarRun(id)
      .catch(() => api.cerrarRun(id))
      .then(
        (r) => {
          if (runId.current === id) runId.current = null;
          if (montada.current) setManana(r.manana);
        },
        () => {
          if (montada.current) setCierreFallido(true);
        },
      )
      .finally(() => {
        cierre.current = null;
      });
    cierre.current = enVuelo;
    return enVuelo;
  }, []);

  useEffect(() => {
    if (estado.fase === "fin") void cerrar();
  }, [estado.fase, cerrar]);

  // Irse del final pide el cierre que falte sin esperarlo: la petición sigue aunque cambie la ruta.
  const salirDelFin = () => {
    void cerrar();
    salir();
  };

  // Si acertó todo, sigue solo.
  useEffect(() => {
    if (estado.fase !== "resultado" || !estado.todoBien) return;
    const id = window.setTimeout(() => dispatch({ tipo: "seguir" }), AUTO_AVANCE_MS);
    return () => window.clearTimeout(id);
  }, [estado.fase, estado.todoBien, estado.idx]);

  // Al salir de la pantalla, que no siga sonando nada ni se pida nada después.
  useEffect(() => {
    montada.current = true;
    return () => {
      montada.current = false;
      stop();
    };
  }, []);

  const actividad =
    estado.fase === "actividad" || estado.fase === "resultado" ? estado.cola[estado.idx] : undefined;

  // Por cada actividad que entra: se apunta la hora (para ENTRADA_MIN_MS) y corre el plazo de
  // «Ahora no puedo …», que apaga una capacidad para el resto de la sesión y no tiene vuelta: no
  // aparece hasta que la actividad lleva AUTO_AVANCE_MS a la vista, así un doble toque no la alcanza.
  // Del plazo se guarda el id y no un booleano, para que al cambiar de actividad no haya ni un
  // cuadro con el botón de la anterior.
  const actividadId = actividad?.id;
  useEffect(() => {
    if (actividadId === undefined) return;
    entroEn.current = { id: actividadId, t: performance.now() };
    const id = window.setTimeout(() => setApagarListoPara(actividadId), AUTO_AVANCE_MS);
    return () => window.clearTimeout(id);
  }, [actividadId]);

  const onResultado = useCallback(
    (evidencias: Evidencia[]) => {
      if (!actividad || respondida.current === actividad.id) return;
      // El reducer solo acepta `[]` al presentar; en práctica o prueba no cuenta. Marcar antes
      // dejaría la actividad sin poder responderse.
      if (evidencias.length === 0 && actividad.modo !== "presentar") return;
      respondida.current = actividad.id;
      // Presentar no deja evidencia (spec §3.1): lo único que sale es «listo, sigue».
      const aGuardar = actividad.modo === "presentar" ? [] : evidencias;
      dispatch({ tipo: "resultado", evidencias: aGuardar });
      const run = runId.current;
      if (run === null || aGuardar.length === 0) return;
      const lote = aGuardar.map((e) => ({
        ...e,
        id: crypto.randomUUID(),
        run_id: run,
        dinamica: actividad.dinamica,
        modo: actividad.modo,
      }));
      // Mismo lote, mismos ids: el reintento no cuenta doble (idempotente en el servidor).
      api
        .evidencias(lote)
        .catch(() => api.evidencias(lote))
        .catch(() => dispatch({ tipo: "envioFallido" }));
    },
    [actividad],
  );

  const presentarListo = useCallback(() => {
    // Un segundo evento antes de que React repinte (la misma pasada) se ignora…
    if (!actividad || respondida.current === actividad.id) return;
    // …y uno que llega recién entrada la presentación es el segundo de un doble toque sobre la
    // anterior, no una lectura. Sin hora apuntada de ESTA actividad tampoco vale.
    const entro = entroEn.current;
    if (entro === null || entro.id !== actividad.id || performance.now() - entro.t < ENTRADA_MIN_MS) return;
    unlockAudio();
    respondida.current = actividad.id;
    dispatch({ tipo: "resultado", evidencias: [] });
  }, [actividad]);

  const capacidades = useMemo<Capacidades>(
    () => ({
      reproducir: (audio, opts) => {
        if (estado.apagadas.includes("escuchar")) return;
        speak(audio.texto, audio.idioma, {
          src: audio.src ? `${apiBase()}${audio.src}` : undefined,
          rate: opts?.lento ? 0.75 : 1,
        });
      },
      puede: (c) => !estado.apagadas.includes(c),
    }),
    [estado.apagadas],
  );

  // En escritorio: Enter o Espacio siguen.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Enter" && e.code !== "Space") return;
      // Una tecla sostenida no puede pasar una actividad tras otra, y Ctrl/Alt/Cmd son del navegador.
      if (e.repeat || e.ctrlKey || e.altKey || e.metaKey) return;
      // La tecla es del campo de texto, o del botón que tenga el foco fuera del dock («Salir»,
      // «Oír otra vez»…). Los del dock son de esta pantalla; y una opción ya respondida (`data-tone`)
      // ya no hace nada, así que ahí Enter y Espacio siguen.
      const en = e.target instanceof Element ? e.target : null;
      if (en?.closest("input, textarea, select, [contenteditable]")) return;
      const boton = en?.closest("button:not(:disabled)");
      if (boton && !boton.closest(".k-dock") && !boton.hasAttribute("data-tone")) return;
      if (estado.fase === "resultado") {
        e.preventDefault();
        dispatch({ tipo: "seguir" });
      } else if (estado.fase === "actividad" && actividad?.modo === "presentar") {
        e.preventDefault();
        presentarListo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [estado.fase, actividad, presentarListo]);

  const otraLeccion = () => {
    // El servidor elige la lección entre las que no tienen una corrida de Hoy terminada: si el
    // cierre de esta sigue en vuelo, devolvería la misma. Se espera ese cierre (y si había fallado, se
    // pide otra vez), acabe bien o mal; mientras, la pantalla de carga, para que el botón responda ya.
    dispatch({ tipo: "cargando" });
    void cerrar().then(() => {
      if (!montada.current) return;
      navigate(`/sesion/${idioma}?repasos=0`, { replace: true, state: { from: salirA } });
      setIntento((n) => n + 1);
    });
  };

  const nombre = languageLabel(idioma);

  if (estado.fase === "cargando") {
    return (
      <div className="k-app">
        <SessTop titulo={nombre} tituloLang={idioma} right="" onExit={salir} />
        <div className="k-fill">
          <span className="k-spinner" role="status" aria-label={t("sesion.cargando")} />
        </div>
      </div>
    );
  }

  if (estado.fase === "fallo" || estado.fase === "vacia") {
    const fallo = estado.fase === "fallo";
    return (
      <div className="k-app">
        <SessTop titulo={nombre} tituloLang={idioma} right="" onExit={salir} />
        <div className="k-fill">
          {fallo ? (
            <p className="k-error" role="alert">{t("sesion.fallo")}</p>
          ) : (
            <p className="k-note">{t("sesion.vacia")}</p>
          )}
        </div>
        <div className="k-dock">
          <div className="k-wrap">
            {fallo && (
              <button type="button" className="k-btn k-btn--ghost k-btn--block" onClick={() => setIntento((n) => n + 1)}>
                {t("sesion.reintentar")}
              </button>
            )}
            <button type="button" className="k-btn k-btn--block" onClick={salir}>
              {t("sesion.aHoy")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (estado.fase === "fin") {
    const reforzar = porReforzar(estado);
    const filas = Object.entries(estado.resumen);
    const hechas = estado.cola.length - estado.saltadas.length;
    return (
      <div className="k-app">
        <SessTop titulo={nombre} tituloLang={idioma} right="" onExit={salirDelFin} />
        <div className="k-fill">
          <div className="k-live">
            <header className="k-hero k-hero--quiet">
              <span className="k-hero__tag">
                <span lang={idioma}>{nombre}</span>
                <span>{t("sesion.fin.hecho")}</span>
              </span>
              <h1 className="k-hero__title" lang={sesion?.leccion ? idioma : undefined}>
                {sesion?.leccion?.titulo ?? t("sesion.repaso")}
              </h1>
              <p className="k-hero__dek">{t("sesion.fin.resumen", { count: hechas })}</p>
            </header>
            {filas.length > 0 && (
              <ul>
                {filas.map(([item, facetas]) => (
                  <li key={item}>
                    <div className="k-row k-row--quiet">
                      <span className="k-row__title" lang={idioma}>{etiquetaItem(item)}</span>
                      <span className="k-row__meta">
                        {(Object.entries(facetas) as [Faceta, Marca][])
                          .map(([f, m]) => `${t(`sesion.faceta.${f}`)} ${t(`sesion.marca.${m}`)}`)
                          .join(" · ")}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {reforzar.length > 0 && (
              <p className="k-note">{t("sesion.fin.reforzar", { items: reforzar.map(etiquetaItem).join(", ") })}</p>
            )}
            {manana !== null && <p className="k-note">{t("sesion.fin.manana", { count: manana })}</p>}
            {cierreFallido && (
              <p className="k-error" role="alert">
                {t("sesion.fin.noCerrada")}{" "}
                <button type="button" className="k-btn k-btn--text" onClick={() => void cerrar()}>
                  {t("sesion.reintentar")}
                </button>
              </p>
            )}
            {estado.enviosFallidos > 0 && (
              <p className="k-error" role="alert">{t("sesion.fin.noGuardadas", { count: estado.enviosFallidos })}</p>
            )}
          </div>
        </div>
        <div className="k-dock">
          <div className="k-wrap">
            {!repetir && sesion?.leccion && (
              <button type="button" className="k-btn k-btn--ghost k-btn--block" onClick={otraLeccion}>
                {t("sesion.fin.otra")}
              </button>
            )}
            <button type="button" className="k-btn k-btn--block" onClick={salirDelFin}>
              {t("sesion.aHoy")} <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!actividad) return <div className="k-app" />;

  const Dinamica = DINAMICAS[actividad.dinamica];
  const cap = necesita(actividad);
  const total = estado.cola.length;
  const titulo = `${nombre} · ${sesion?.leccion?.titulo ?? t("sesion.repaso")}`;
  const modo = actividad.repaso ? t("sesion.modo.repaso") : t(`sesion.modo.${actividad.modo}`);

  return (
    <div className="k-app">
      <SessTop
        titulo={titulo}
        tituloLang={sesion?.leccion ? idioma : undefined}
        right={`${pad2(estado.idx + 1)}/${pad2(total)}`}
        onExit={salir}
      />
      <div className="k-bar k-bar--segs">
        <div className="k-bar__track" role="progressbar" aria-valuenow={estado.idx + 1} aria-valuemin={0} aria-valuemax={total}>
          {estado.cola.map((a, i) => (
            <span
              key={a.id}
              className="k-bar__seg"
              data-state={
                i < estado.idx ? (estado.saltadas.includes(a.id) ? "skipped" : "done") : i === estado.idx ? "now" : undefined
              }
            />
          ))}
        </div>
      </div>

      <div className="k-fill">
        <p className="k-cap k-cap--center">{modo}</p>
        {Dinamica ? (
          <Dinamica
            key={actividad.id}
            contenido={actividad.contenido}
            modo={actividad.modo}
            capacidades={capacidades}
            onResultado={onResultado}
          />
        ) : (
          // Una dinámica que este frontend no conoce (uno viejo en caché con un catálogo nuevo): se salta,
          // sin evidencia, y la barra la marca saltada.
          <p className="k-error" role="alert">
            {t("sesion.desconocida")}{" "}
            <button type="button" className="k-btn k-btn--text" onClick={() => dispatch({ tipo: "saltar", id: actividad.id })}>
              {t("sesion.seguir")}
            </button>
          </p>
        )}
      </div>

      <div className="k-dock">
        <div className="k-dock__status">
          <p className="k-cap k-cap--center" role="status">
            {estado.fase === "resultado" ? (estado.todoBien ? t("sesion.bien") : t("sesion.mira")) : ""}
          </p>
        </div>
        <div className="k-wrap">
          {actividad.modo === "presentar" ? (
            <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={presentarListo}>
              {t("sesion.ahoraTu")} <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          ) : estado.fase === "resultado" && !estado.todoBien ? (
            <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={() => dispatch({ tipo: "seguir" })}>
              {t("sesion.seguir")} <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          ) : (
            // El alto de «Seguir →» lo reserva la fila (`.k-dock__status + .k-wrap`, átomo del dock).
            cap !== null &&
            estado.fase === "actividad" &&
            apagarListoPara === actividad.id && (
              <button
                type="button"
                className="k-btn k-btn--text"
                onClick={() => {
                  stop();
                  dispatch({ tipo: "apagar", capacidad: cap });
                }}
              >
                {t(`sesion.noPuedo.${cap}`)}
              </button>
            )
          )}
        </div>
      </div>
    </div>
  );
}
