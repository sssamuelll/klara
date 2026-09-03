/**
 * La sesión de género, en el vocabulario k-*. Sus dos consumidores —`/gender`
 * y el segmento de Práctica— viven en el cascarón viejo de escritorio, así que
 * la pantalla es una `.k-page` (la de `global.css`) como sus vecinas de ese
 * mismo cascarón, y no el `.k-app` del teléfono.
 *
 * Las cinco fases comparten forma y no comparten tono, que es la doctrina que
 * fijó Repaso: el vacío es una nota, el fallo de carga es un error, y la carga
 * es el spinner suelto que ya usan Módulo y Pronunciar.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { GenderReviewItem } from "../api/types";
import GenderPicker from "./GenderPicker";

type Phase = "loading" | "failed" | "empty" | "session" | "summary";

interface GenderReviewSessionProps {
  onExit: () => void;
  exitLabel: string;
}

export default function GenderReviewSession({
  onExit,
  exitLabel,
}: GenderReviewSessionProps): JSX.Element {
  const { t } = useTranslation();

  const [items, setItems] = useState<GenderReviewItem[]>([]);
  const [phase, setPhase] = useState<Phase>("loading");
  const [idx, setIdx] = useState(0);
  const [correct, setCorrect] = useState(0);

  // Initial fetch (alive-guarded).
  useEffect(() => {
    let alive = true;
    api
      .genderReview()
      .then((rows) => {
        if (!alive) return;
        setItems(rows);
        setPhase(rows.length === 0 ? "empty" : "session");
      })
      .catch(() => {
        if (alive) setPhase("failed");
      });
    return () => {
      alive = false;
    };
  }, []);

  // "Another round" — refetch. User action; no alive guard.
  const restart = () => {
    setPhase("loading");
    setIdx(0);
    setCorrect(0);
    api
      .genderReview()
      .then((rows) => {
        setItems(rows);
        setPhase(rows.length === 0 ? "empty" : "session");
      })
      .catch(() => setPhase("failed"));
  };

  if (phase === "loading") {
    return (
      <main className="k-page">
        <span className="k-spinner" role="status" aria-label={t("genderReview.title")} />
      </main>
    );
  }

  if (phase === "failed" || phase === "empty") {
    return (
      <main className="k-page">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">{t("genderReview.title")}</h1>
        </header>
        {/* Comparten forma y no comparten tono (doctrina de Repaso): no tener
            géneros que repasar hoy es una nota, no un error. */}
        {phase === "failed" ? (
          <p className="k-error" role="alert">{t("genderReview.failed")}</p>
        ) : (
          <p className="k-note">{t("genderReview.empty")}</p>
        )}
        <div className="k-wrap">
          <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={onExit}>
            {exitLabel}
          </button>
        </div>
      </main>
    );
  }

  if (phase === "summary") {
    return (
      <main className="k-page">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">{t("genderReview.title")}</h1>
          {/* La cifra de la sesión va en el ledger del héroe (candidato 20). Sin
              `<strong>` porque la clave es una frase interpolada entera y
              partirla en dos serían seis traducciones por un peso. */}
          <p className="k-hero__meta">
            {t("genderReview.summary", { correct, total: items.length })}
          </p>
        </header>
        <div className="k-wrap">
          <button type="button" className="k-btn k-btn--block" onClick={restart}>
            {t("genderReview.again")}
          </button>
          <button type="button" className="k-btn k-btn--ghost k-btn--block" onClick={onExit}>
            {exitLabel}
          </button>
        </div>
      </main>
    );
  }

  // phase === "session"
  const item = items[idx];
  return (
    <main className="k-page">
      {/* La tira base, no `--session`: aquí no hay salida que colocar en una
          tercera pista, y el relleno con inset de esa variante es para las
          tiras que cuelgan del cascarón sin página. Durante la sesión el
          título deja de encabezar y pasa a orientar, como en Lectura, Repaso y
          el cierre; el titular vuelve en las otras cuatro fases. */}
      <header className="k-topline">
        <span className="k-topline__title">{t("genderReview.title")}</span>
        <span className="k-topline__meta">
          {t("genderReview.progress", { done: idx + 1, total: items.length })}
        </span>
      </header>
      <GenderPicker
        key={item.vocab_item_id}
        lemma={item.lemma}
        en={item.en}
        onGrade={(article) =>
          api.gradeGender({ vocab_item_id: item.vocab_item_id, picked_article: article })
        }
        onResult={(c) => {
          if (c) setCorrect((n) => n + 1);
        }}
        onNext={() => {
          if (idx + 1 < items.length) setIdx(idx + 1);
          else setPhase("summary");
        }}
        isLast={idx + 1 === items.length}
      />
    </main>
  );
}
