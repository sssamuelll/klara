/**
 * Práctica — el selector de repaso. Tres puertas: fichas, pronunciar,
 * géneros.
 *
 * Ya no ejecuta ninguna sesión: las fichas viven en /repaso y la
 * pronunciación en /pronunciar, cada una con su propio `.k-app` (el
 * armazón de sesión no se puede anidar en el cascarón viejo). Géneros
 * sigue aquí porque su sesión sí cabe en una página.
 *
 * This REPLACES the old /review stub — Practice IS the review.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import GenderReviewSession from "../components/GenderReviewSession";

export default function Practice() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [gender, setGender] = useState(false);

  // ---- SEGMENT: gender (reuses the standalone /gender session) -----------
  if (gender) {
    return (
      <GenderReviewSession onExit={() => setGender(false)} exitLabel={t("practice.segment.back")} />
    );
  }

  // Las dos primeras son su propia superficie de sesión, no un segmento
  // dentro del cascarón viejo; la tercera se abre aquí mismo.
  const puertas = [
    {
      k: "cards",
      title: t("practice.segment.cards.title"),
      dek: t("practice.segment.cards.dek"),
      go: () => navigate("/repaso", { state: { from: "/review" } }),
    },
    {
      k: "pron",
      title: t("practice.segment.pron.title"),
      dek: t("practice.segment.pron.dek"),
      go: () => navigate("/pronunciar", { state: { from: "/review" } }),
    },
    {
      k: "gender",
      title: t("practice.segment.gender.title"),
      dek: t("practice.segment.gender.dek"),
      go: () => setGender(true),
    },
  ];

  // ---- SEGMENT CHOOSER ---------------------------------------------------
  return (
    <main className="k-page">
      <button type="button" className="k-btn k-btn--text" onClick={() => navigate("/")}>
        {t("common.back")}
      </button>

      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{t("practice.segment.title")}</h1>
      </header>

      <div className="k-wrap">
        {puertas.map((p) => (
          <button key={p.k} type="button" className="k-row k-row--boxed" onClick={p.go}>
            <span className="k-row__title">{p.title}</span>
            <span className="k-row__sub">{p.dek}</span>
            <span className="k-row__arrow">→</span>
          </button>
        ))}
      </div>
    </main>
  );
}
