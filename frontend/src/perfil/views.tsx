/* Pantallas del Perfil de Aprendizaje (F1.5).
 *
 * Porte del paquete de diseño «Onboarding v5» sin retoques visuales: las
 * clases y la estructura del DOM son las suyas (perfil-aprendizaje.css entra
 * tal cual). Lo único que cambia es que el texto sale de i18n en vez de estar
 * incrustado, y que los valores guardados son los IDs del catálogo.
 *
 * Interacción que NO se puede perder al portar (viene del handoff):
 *  - los radio avanzan solos a los 240 ms; checkbox, triage y chips piden botón
 *  - salvo que la opción elegida sea «Otra cosa», que espera el texto
 *  - el pie dice «toca para seguir» cuando avanza solo, y muestra botón si no
 */

import { Fragment, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import KlaraMark from "../components/KlaraMark";
import { OB_BLOQUES, OB_PREGUNTAS, type ObPregunta } from "./catalog";

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
      <div className="ob5-entrada">
        <div className="ob5-kicker">{t("perfil.aprendizaje.entrada.antes")}</div>
        <h1 className="ob5-h1">
          {t("perfil.aprendizaje.entrada.h1pre")} <em>{t("perfil.aprendizaje.entrada.h1em")}</em>{" "}
          {t("perfil.aprendizaje.entrada.h1post")}
        </h1>
        <p className="ob5-lede">{t("perfil.aprendizaje.entrada.lede")}</p>
        <div className="ob5-meta">
          <div>
            <b>{OB_PREGUNTAS.length}</b>
            {t("perfil.aprendizaje.entrada.metaPreguntas")}
          </div>
          <div>
            <b>~5</b>
            {t("perfil.aprendizaje.entrada.metaMinutos")}
          </div>
          <div>
            <b>0</b>
            {t("perfil.aprendizaje.entrada.metaObligatorias")}
          </div>
        </div>
        <div className="ob5-cta">
          {primerArranque ? (
            <button className="ob5-mute" onClick={onLuego}>
              {t("perfil.aprendizaje.entrada.masTarde")}
            </button>
          ) : (
            <span />
          )}
          <button className="k-btn" onClick={onEmpezar}>
            {t("perfil.aprendizaje.entrada.empezar")} <span className="arrow">→</span>
          </button>
        </div>
      </div>
    </main>
  );
}

/* ----------------------------------------------------------------- Ticks */

/** 23 marcas agrupadas por bloque. Tres estados y ningún contador de saltos:
 *  el progreso informa, no reprocha (D-A). */
function Ticks({ idx, answers }: { idx: number; answers: Answers }) {
  return (
    <div className="ob5-ticks">
      {OB_BLOQUES.map((b) => (
        <div
          className="ob5-grupo"
          key={b.id}
          style={{ "--w": b.n } as React.CSSProperties}
        >
          {OB_PREGUNTAS.filter((q) => q.b === b.id).map((q) => {
            const i = OB_PREGUNTAS.indexOf(q);
            const s = i === idx ? "now" : i > idx ? "" : esVacia(answers[q.id]) ? "skip" : "done";
            return <span className="ob5-tick" key={q.id} data-s={s} />;
          })}
        </div>
      ))}
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

  return (
    <main className="k-page">
      <div className="ob5-top">
        <button
          type="button"
          className="k-btn k-btn--text"
          onClick={onBack}
          style={{ justifySelf: "start" }}
          aria-label={t("common.back")}
        >
          ←
        </button>
        <span className="bloque">{t(`perfil.aprendizaje.bloque.${q.b}`)}</span>
        <span className="cuenta">
          {String(idx + 1).padStart(2, "0")} / {OB_PREGUNTAS.length}
        </span>
      </div>
      <Ticks idx={idx} answers={answers} />

      <div className="ob5-q" key={q.id}>
        <h2 className="ob5-label">{t(`perfil.aprendizaje.q.${q.id}.label`)}</h2>
        {q.whisper ? (
          <p className="ob5-whisper">{t(`perfil.aprendizaje.q.${q.id}.whisper`)}</p>
        ) : null}

        {q.control === "triage" ? (
          <div className="ob5-opts">
            <div className="ob5-trihead">
              <span />
              <span>{t("perfil.aprendizaje.triage.sirve")}</span>
              <span>{t("perfil.aprendizaje.triage.no")}</span>
            </div>
            {q.ops.map((op, n) => {
              const tri = (val as Record<string, string>) || {};
              return (
                <div className="ob5-tri" key={op} data-set={tri[op] ? "true" : "false"}>
                  <span className="n">{label(n)}</span>
                  <button
                    className="si"
                    data-on={tri[op] === "sirve" ? "true" : "false"}
                    onClick={() => setTri(op, "sirve")}
                    aria-pressed={tri[op] === "sirve"}
                    aria-label={`${label(n)}: ${t("perfil.aprendizaje.triage.sirve")}`}
                  >
                    ✓
                  </button>
                  <button
                    className="no"
                    data-on={tri[op] === "no" ? "true" : "false"}
                    onClick={() => setTri(op, "no")}
                    aria-pressed={tri[op] === "no"}
                    aria-label={`${label(n)}: ${t("perfil.aprendizaje.triage.no")}`}
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </div>
        ) : q.control === "chips" ? (
          <div className="ob5-cloudwrap">
            <div className="ob5-cloud">
              {q.ops.map((op, n) => (
                <button
                  key={op}
                  className="k-chip"
                  data-selected={Array.isArray(val) && val.includes(op) ? "true" : "false"}
                  aria-pressed={Array.isArray(val) && val.includes(op)}
                  onClick={() => toggle(op, n)}
                >
                  {label(n)}
                </button>
              ))}
            </div>
            {escribiendo && q.escape ? (
              <textarea
                className="ob5-area"
                placeholder={t("perfil.aprendizaje.chips.placeholder")}
                maxLength={1000}
                value={(answers[q.escape] as string) || ""}
                onChange={(e) => onSet(q.escape as string, e.target.value)}
                aria-label={t("perfil.aprendizaje.chips.escribir")}
              />
            ) : (
              <button className="ob5-mute" onClick={() => setEscribiendo(true)}>
                {t("perfil.aprendizaje.chips.escribir")}
              </button>
            )}
          </div>
        ) : (
          <div className="ob5-opts">
            {q.ops.map((op, n) => {
              const on = q.control === "radio" ? val === op : Array.isArray(val) && val.includes(op);
              return (
                <Fragment key={op}>
                  <button
                    className="ob5-opt"
                    data-on={on ? "true" : "false"}
                    data-nega={q.excl === n ? "true" : "false"}
                    data-otra={q.otra === n ? "true" : "false"}
                    role={q.control === "radio" ? "radio" : "checkbox"}
                    aria-checked={on}
                    onClick={() => (q.control === "radio" ? pickRadio(op, n) : toggle(op, n))}
                  >
                    <span className={`ob5-mark ${q.control === "radio" ? "radio" : "check"}`}>✓</span>
                    <span className="txt">{label(n)}</span>
                  </button>
                  {q.otra === n && on ? (
                    <input
                      className="ob5-otra"
                      autoFocus
                      placeholder={t("perfil.aprendizaje.otra.placeholder")}
                      maxLength={200}
                      value={(answers[otraKey] as string) || ""}
                      onChange={(e) => onSet(otraKey, e.target.value)}
                      aria-label={t("perfil.aprendizaje.otra.placeholder")}
                    />
                  ) : null}
                </Fragment>
              );
            })}
          </div>
        )}
      </div>

      <div className="ob5-foot">
        <button className="ob5-mute" onClick={onSkip}>
          {t("perfil.aprendizaje.nav.saltar")}
        </button>
        {autoAvanza && !ultima ? (
          <span className="ob5-hint">{t("perfil.aprendizaje.nav.tocaParaSeguir")}</span>
        ) : (
          <button className="k-btn" onClick={onNext} disabled={!lleno && !ultima}>
            {ultima ? t("perfil.aprendizaje.nav.guardar") : t("perfil.aprendizaje.nav.siguiente")}{" "}
            <span className="arrow">→</span>
          </button>
        )}
      </div>
    </main>
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
          <KlaraMark size={13} speaking={pendiente} />
          <span className="wordmark">Klara</span>
        </span>
        <span className="k-topline__meta">{pendiente ? t("perfil.aprendizaje.sintesis.guardado") : t("perfil.aprendizaje.sintesis.tuPerfil")}</span>
      </header>
      <div className="ob5-sint">
        <h1 className="ob5-h1" style={{ marginTop: 18 }}>
          {t("perfil.aprendizaje.sintesis.h1pre")}{" "}
          <em>{t("perfil.aprendizaje.sintesis.h1em")}</em>
          {t("perfil.aprendizaje.sintesis.h1post")}
        </h1>
        {pendiente ? (
          <div className="ob5-esperando">
            <KlaraMark size={20} speaking />
            {t("perfil.aprendizaje.sintesis.esperando")}
          </div>
        ) : (
          <>
            <div className="ob5-prosa">
              {anclado ? <p>{anclado}</p> : null}
              {dicho ? <p className="ob5-dicho">{dicho}</p> : null}
            </div>
            {dicho ? <p className="ob5-leyenda">{t("perfil.aprendizaje.sintesis.leyenda")}</p> : null}
            {entradas.length ? (
              <div className="ob5-facts">
                <h2 className="k-cap k-cap--rule">{t("perfil.aprendizaje.sintesis.anotado")}</h2>
                {entradas.map(([k, v]) => (
                  <div className="ob5-fact" key={k}>
                    <span className="k">{t(`perfil.aprendizaje.facts.${k}`, k)}</span>
                    <span className="v">{Array.isArray(v) ? v.join(" · ") : String(v)}</span>
                  </div>
                ))}
              </div>
            ) : null}
            <p className="ob5-pie">{t("perfil.aprendizaje.sintesis.pie")}</p>
          </>
        )}
      </div>
      <div className="ob5-acciones">
        <button className="k-btn k-btn--ghost" onClick={onCorregir}>
          {t("perfil.aprendizaje.sintesis.corregir")}
        </button>
        <button className="k-btn" onClick={onListo}>
          {t("perfil.aprendizaje.sintesis.entendido")}
        </button>
      </div>
    </main>
  );
}
