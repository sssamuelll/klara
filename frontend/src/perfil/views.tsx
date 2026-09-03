/* Pantallas del Perfil de Aprendizaje (F1.5), en el vocabulario k-*.
 *
 * Venía del paquete de diseño «Onboarding v5» con sus clases propias, y era la
 * otra mitad del onboarding: la migración 8 pasó una y esta pasa la que
 * quedaba. Las dos son el mismo cuestionario, así que aquí no se inventa nada —
 * se copia la forma que ya tiene `ObStep`/`ObNav`: línea superior de sesión,
 * barra de segmentos, columna que scrollea y una nube de transporte al pie.
 *
 * Lo único que cambia de sitio es el cascarón: el cuestionario vive dentro de
 * `V4Frame`, o sea con barra de pestañas, así que la tira y la barra cuelgan de
 * `.k-app` (como en una sesión) y el cuerpo sigue en `.k-page`.
 *
 * Interacción que NO se puede perder al portar (viene del handoff):
 *  - los radio avanzan solos a los 240 ms; checkbox, triage y chips piden botón
 *  - salvo que la opción elegida sea «Otra cosa», que espera el texto
 *  - el pie dice «toca para seguir» cuando avanza solo, y muestra botón si no
 */

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import KlaraMark from "../components/KlaraMark";
import { OB_PREGUNTAS, type ObPregunta } from "./catalog";

export type Respuesta = string | string[] | Record<string, string> | null;
export type Answers = Record<string, Respuesta | undefined>;

const AUTO_MS = 240;

/** Vacía = sin responder. `null` (saltada) y `[]`/`{}` cuentan como vacías. */
export function esVacia(v: Respuesta | undefined): boolean {
  if (v === null || v === undefined || v === "") return true;
  if (Array.isArray(v)) return v.length === 0;
  if (typeof v === "object") return Object.keys(v).length === 0;
  return false;
}

/* ---------------------------------------------------------------- Entrada */

export function Entrada({
  primerArranque,
  onEmpezar,
  onLuego,
}: {
  primerArranque: boolean;
  onEmpezar: () => void;
  onLuego: () => void;
}) {
  const { t } = useTranslation();
  return (
    <main className="k-page">
      <header className="k-topline">
        <span className="k-topline__mark">
          <KlaraMark size={13} />
          <span className="wordmark">Klara</span>
        </span>
        <span className="k-topline__meta">{t("perfil.aprendizaje.kicker")}</span>
      </header>
      <div className="k-live">
        <p className="k-cap">{t("perfil.aprendizaje.entrada.antes")}</p>
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">
            {t("perfil.aprendizaje.entrada.h1pre")} <em>{t("perfil.aprendizaje.entrada.h1em")}</em>{" "}
            {t("perfil.aprendizaje.entrada.h1post")}
          </h1>
          <p className="k-hero__dek">{t("perfil.aprendizaje.entrada.lede")}</p>
          {/* Las tres cifras son el bloque de ledger que el candidato 20 cerró:
              van en la cifra del héroe, no en una tira propia al pie. */}
          <p className="k-hero__meta">
            <strong>{OB_PREGUNTAS.length}</strong> {t("perfil.aprendizaje.entrada.metaPreguntas")}
            <span aria-hidden="true">·</span>
            <strong>~5</strong> {t("perfil.aprendizaje.entrada.metaMinutos")}
            <span aria-hidden="true">·</span>
            <strong>0</strong> {t("perfil.aprendizaje.entrada.metaObligatorias")}
          </p>
        </header>
      </div>
      <div className="k-wrap">
        {primerArranque && (
          <button type="button" className="k-btn k-btn--text" onClick={onLuego}>
            {t("perfil.aprendizaje.entrada.masTarde")}
          </button>
        )}
        <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={onEmpezar}>
          {t("perfil.aprendizaje.entrada.empezar")}{" "}
          <span className="k-btn__arrow" aria-hidden="true">→</span>
        </button>
      </div>
    </main>
  );
}

/* ------------------------------------------------------------------ Barra */

/** 23 segmentos y cuatro estados. Los grupos por bloque no entran —el sistema
 *  tiene una barra de segmentos, no una de grupos con peso—: el bloque en el
 *  que estás lo dice el título de la línea superior, que es donde el sistema
 *  pone la orientación. El saltado sí entra: sin él una pregunta en blanco se
 *  vería igual que una por responder. */
function Barra({ idx, answers }: { idx: number; answers: Answers }) {
  return (
    <div className="k-bar k-bar--segs">
      <div
        className="k-bar__track"
        role="progressbar"
        aria-valuenow={idx + 1}
        aria-valuemin={1}
        aria-valuemax={OB_PREGUNTAS.length}
      >
        {OB_PREGUNTAS.map((q, i) => (
          <span
            key={q.id}
            className="k-bar__seg"
            data-state={
              i === idx
                ? "now"
                : i > idx
                  ? undefined
                  : esVacia(answers[q.id])
                    ? "skipped"
                    : "done"
            }
          />
        ))}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- Pregunta */

interface PreguntaProps {
  q: ObPregunta;
  idx: number;
  answers: Answers;
  onSet: (id: string, v: Respuesta | ((prev: Respuesta | undefined) => Respuesta)) => void;
  onNext: () => void;
  onSkip: () => void;
  onBack: () => void;
  ultima: boolean;
}

export function Pregunta({ q, idx, answers, onSet, onNext, onSkip, onBack, ultima }: PreguntaProps) {
  const { t } = useTranslation();
  const val = answers[q.id];
  const [escribiendo, setEscribiendo] = useState(false);
  const auto = useRef<number | undefined>(undefined);

  useEffect(() => {
    setEscribiendo(!!(q.escape && answers[q.escape]));
    // Un avance automático pendiente no puede dispararse tras cambiar de
    // pregunta: saltaría una sin que el usuario la vea.
    return () => window.clearTimeout(auto.current);
  }, [q.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const opOtra = q.otra !== undefined ? q.ops[q.otra] : null;
  const opNeg = q.excl !== undefined ? q.ops[q.excl] : null;
  const otraKey = `${q.id}_otra`;
  const otraSel =
    opOtra !== null &&
    (q.control === "radio" ? val === opOtra : Array.isArray(val) && val.includes(opOtra));

  const label = (n: number) => t(`perfil.aprendizaje.q.${q.id}.op.${n}`);

  const pickRadio = (op: string, i: number) => {
    onSet(q.id, op);
    if (q.otra === i) return; // «Otra cosa» espera el texto, no avanza
    auto.current = window.setTimeout(onNext, AUTO_MS);
  };

  const toggle = (op: string, i: number) =>
    onSet(q.id, (prev) => {
      const cur = Array.isArray(prev) ? prev : [];
      if (opNeg !== null && i === q.excl) return cur.includes(opNeg) ? [] : [opNeg];
      return cur.includes(op)
        ? cur.filter((x) => x !== op)
        : [...cur.filter((x) => x !== opNeg), op];
    });

  const setTri = (op: string, v: string) =>
    onSet(q.id, (prev) => {
      const cur = { ...((prev as Record<string, string>) || {}) };
      if (cur[op] === v) delete cur[op];
      else cur[op] = v;
      return cur;
    });

  const lleno =
    q.control === "triage"
      ? !esVacia(val)
      : q.control === "radio"
        ? !!val && (!otraSel || !!answers[otraKey])
        : Array.isArray(val) && val.length > 0;
  const autoAvanza = q.control === "radio" && !otraSel;

  /* Fragmento a propósito: la tira y la barra cuelgan de `.k-app` —como en
     cualquier sesión— y por eso la página deja de ser la primera hija y no
     repone el inset de arriba. Ningún envoltorio puede meterse en medio. */
  return (
    <>
      <header className="k-topline k-topline--session">
        <button
          type="button"
          className="k-btn k-btn--text k-topline__exit"
          onClick={onBack}
          aria-label={t("common.back")}
        >
          ←
        </button>
        <span className="k-topline__title">{t(`perfil.aprendizaje.bloque.${q.b}`)}</span>
        <span className="k-topline__meta">
          {String(idx + 1).padStart(2, "0")} / {OB_PREGUNTAS.length}
        </span>
      </header>
      <Barra idx={idx} answers={answers} />

      <main className="k-page">
        {/* `key` para que la columna vuelva a montar y el scroll arranque
            arriba en cada pregunta. La animación de paso no entra: lo que
            cambia ya lo dicen la barra y el contador (migraciones 7 y 8). */}
        <div className="k-live" key={q.id}>
          <header className="k-hero k-hero--quiet">
            <h1 className="k-hero__title">{t(`perfil.aprendizaje.q.${q.id}.label`)}</h1>
          </header>
          {q.whisper ? (
            <p className="k-note">{t(`perfil.aprendizaje.q.${q.id}.whisper`)}</p>
          ) : null}

          {q.control === "triage" ? (
            /* Los dos botones cuadrados de 46px pasan a chips, y con ellos se
               va la fila de encabezado: el chip dice «Sirve» o «No» en vez de
               un glifo bajo un rótulo, así que no hay dos columnas que rotular.
               Tampoco entra el «seleccionado negativo» —papel apagado y tinta
               baja—, que se leía como deshabilitado: cuál es cuál lo dice la
               posición y el rótulo, no una segunda manera de estar pulsado. */
            <ul>
              {q.ops.map((op, n) => {
                const tri = (val as Record<string, string>) || {};
                return (
                  <li key={op}>
                    <div className="k-row k-row--quiet">
                      <span className="k-row__title">{label(n)}</span>
                      {(["sirve", "no"] as const).map((v) => (
                        <button
                          key={v}
                          type="button"
                          className="k-chip"
                          data-selected={tri[op] === v ? "true" : "false"}
                          aria-pressed={tri[op] === v}
                          aria-label={`${label(n)}: ${t(`perfil.aprendizaje.triage.${v}`)}`}
                          onClick={() => setTri(op, v)}
                        >
                          {t(`perfil.aprendizaje.triage.${v}`)}
                        </button>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : q.control === "chips" ? (
            <>
              <div className="k-wrap">
                {q.ops.map((op, n) => (
                  <button
                    key={op}
                    type="button"
                    className="k-chip"
                    data-selected={Array.isArray(val) && val.includes(op) ? "true" : "false"}
                    aria-pressed={Array.isArray(val) && val.includes(op)}
                    onClick={() => toggle(op, n)}
                  >
                    {label(n)}
                  </button>
                ))}
                {/* El escape vive dentro de la nube: es una manera más de
                    contestar la misma pregunta, y en mono no se confunde con
                    una etiqueta. Cuando se abre, lo sustituye el campo. */}
                {!escribiendo && (
                  <button
                    type="button"
                    className="k-btn k-btn--text"
                    onClick={() => setEscribiendo(true)}
                  >
                    {t("perfil.aprendizaje.chips.escribir")}
                  </button>
                )}
              </div>
              {escribiendo && q.escape ? (
                <label className="k-field k-field--area k-field--rule">
                  <textarea
                    className="k-field__input"
                    placeholder={t("perfil.aprendizaje.chips.placeholder")}
                    maxLength={1000}
                    value={(answers[q.escape] as string) || ""}
                    onChange={(e) => onSet(q.escape as string, e.target.value)}
                    aria-label={t("perfil.aprendizaje.chips.escribir")}
                  />
                  <span className="k-field__rule" />
                </label>
              ) : null}
            </>
          ) : (
            <ul>
              {q.ops.map((op, n) => {
                const on = q.control === "radio" ? val === op : Array.isArray(val) && val.includes(op);
                // Negativa y «otra cosa» son la misma cosa para la pintura: no
                // son respuestas, son la salida (variante `--aside`).
                const aside = q.excl === n || q.otra === n;
                return (
                  <li key={op}>
                      <button
                        type="button"
                        className={aside ? "k-row k-row--aside" : "k-row"}
                        data-state={on ? "selected" : undefined}
                        role={q.control === "radio" ? "radio" : "checkbox"}
                        aria-checked={on}
                        onClick={() => (q.control === "radio" ? pickRadio(op, n) : toggle(op, n))}
                      >
                        <span className="k-row__mark" aria-hidden="true" />
                        <span className="k-row__title">{label(n)}</span>
                      </button>
                      {q.otra === n && on ? (
                        <label className="k-field k-field--rule">
                          <input
                            className="k-field__input"
                            autoFocus
                            placeholder={t("perfil.aprendizaje.otra.placeholder")}
                            maxLength={200}
                            value={(answers[otraKey] as string) || ""}
                            onChange={(e) => onSet(otraKey, e.target.value)}
                            aria-label={t("perfil.aprendizaje.otra.placeholder")}
                          />
                          <span className="k-field__rule" />
                        </label>
                      ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="k-wrap">
          <button type="button" className="k-btn k-btn--text" onClick={onSkip}>
            {t("perfil.aprendizaje.nav.saltar")}
          </button>
          {autoAvanza && !ultima ? (
            <span className="k-cap">{t("perfil.aprendizaje.nav.tocaParaSeguir")}</span>
          ) : (
            <button
              type="button"
              className="k-btn k-btn--lg k-btn--block"
              onClick={onNext}
              disabled={!lleno && !ultima}
            >
              {ultima ? t("perfil.aprendizaje.nav.guardar") : t("perfil.aprendizaje.nav.siguiente")}{" "}
              <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          )}
        </div>
      </main>
    </>
  );
}

/* -------------------------------------------------------------- Síntesis */

/** El servidor manda la prosa con la procedencia ya separada: lo anclado en
 *  conducta primero, y tras una línea en blanco lo autoevaluado. Si no viene
 *  la separación, todo se pinta como anclado — degradar hacia «sin margen» es
 *  lo seguro: nunca marca como dicho algo que no lo es. */
export function partirProsa(prosa: string | null): { anclado: string; dicho: string } {
  if (!prosa) return { anclado: "", dicho: "" };
  const [primero, ...resto] = prosa.trim().split(/\n\s*\n/);
  return { anclado: primero.trim(), dicho: resto.join("\n\n").trim() };
}

export function Sintesis({
  prosa,
  facts,
  pendiente,
  onListo,
  onCorregir,
}: {
  prosa: string | null;
  facts: Record<string, unknown> | null;
  pendiente: boolean;
  onListo: () => void;
  onCorregir: () => void;
}) {
  const { t } = useTranslation();
  const { anclado, dicho } = partirProsa(prosa);
  const entradas = Object.entries(facts || {});

  return (
    <main className="k-page">
      <header className="k-topline">
        <span className="k-topline__mark">
          {/* Sin `speaking`: aquí Klara no está sonando, está escribiendo, y el
              halo del átomo 16 es señal de audio (sus Notas prohíben el
              decorativo). Que está pensando lo dice la copia de espera. */}
          <KlaraMark size={13} />
          <span className="wordmark">Klara</span>
        </span>
        <span className="k-topline__meta">
          {pendiente
            ? t("perfil.aprendizaje.sintesis.guardado")
            : t("perfil.aprendizaje.sintesis.tuPerfil")}
        </span>
      </header>
      <div className="k-live">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">
            {t("perfil.aprendizaje.sintesis.h1pre")}{" "}
            <em>{t("perfil.aprendizaje.sintesis.h1em")}</em>
            {t("perfil.aprendizaje.sintesis.h1post")}
          </h1>
        </header>
        {pendiente ? (
          <p className="k-note k-note--bare" role="status">
            {t("perfil.aprendizaje.sintesis.esperando")}
          </p>
        ) : (
          <>
            {/* La procedencia se dice con el filete de la nota, no con una
                regla punteada nueva: lo observado va a plomo («arriba, lo que
                hiciste») y lo que dices de ti va al margen, que es como el
                sistema atribuye lo tuyo desde `.k-live__turn[data-who="you"]`.
                La leyenda ya lo decía con esas palabras. */}
            {anclado ? <p className="k-note k-note--bare">{anclado}</p> : null}
            {dicho ? <p className="k-note">{dicho}</p> : null}
            {/* La leyenda va sin filete: explica el margen, no está en él.
                Con el suyo propio —como en la hoja vieja— eran dos bloques al
                margen seguidos y el gesto que describe dejaba de leerse. */}
            {dicho ? (
              <p className="k-note k-note--mono k-note--bare">
                {t("perfil.aprendizaje.sintesis.leyenda")}
              </p>
            ) : null}
            {entradas.length ? (
              <>
                <h2 className="k-cap k-cap--rule">{t("perfil.aprendizaje.sintesis.anotado")}</h2>
                <ul>
                  {entradas.map(([k, v]) => (
                    <li key={k}>
                      <div className="k-row k-row--quiet">
                        <span className="k-row__n">{t(`perfil.aprendizaje.facts.${k}`, k)}</span>
                        <span className="k-row__title">
                          {Array.isArray(v) ? v.join(" · ") : String(v)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            <p className="k-note k-note--bare">{t("perfil.aprendizaje.sintesis.pie")}</p>
          </>
        )}
      </div>
      <div className="k-wrap">
        <button type="button" className="k-btn k-btn--ghost k-btn--block" onClick={onCorregir}>
          {t("perfil.aprendizaje.sintesis.corregir")}
        </button>
        <button type="button" className="k-btn k-btn--block" onClick={onListo}>
          {t("perfil.aprendizaje.sintesis.entendido")}
        </button>
      </div>
    </main>
  );
}
