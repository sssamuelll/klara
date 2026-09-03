/**
 * Práctica — el selector de repaso. Tres puertas: fichas, pronunciar,
 * géneros.
 *
 * Ya no ejecuta ninguna sesión: las fichas viven en /repaso y la
 * pronunciación en /pronunciar, cada una con su propio `.k-app` (el
 * armazón de sesión no se puede anidar en el cascarón viejo). Géneros
 * sigue aquí en lo que le toque su migración.
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

  // ---- SEGMENT CHOOSER ---------------------------------------------------
  return (
    <main className="k-page kp-setup">
      <button className="story__back k-mono" onClick={() => navigate("/")}>
        {t("common.back")}
      </button>
      <header className="kp-setup__head">
        <h1 className="kp-setup__title">{t("practice.segment.title")}</h1>
      </header>
      <section className="kp-segments">
        {/* Las dos primeras son su propia superficie de sesión, no un
            segmento dentro del cascarón viejo. */}
        <button
          className="kp-segment"
          onClick={() => navigate("/repaso", { state: { from: "/review" } })}
        >
          <span className="kp-segment__title">{t("practice.segment.cards.title")}</span>
          <span className="kp-segment__dek">{t("practice.segment.cards.dek")}</span>
          <span className="kp-segment__arrow k-serif">→</span>
        </button>
        <button
          className="kp-segment"
          onClick={() => navigate("/pronunciar", { state: { from: "/review" } })}
        >
          <span className="kp-segment__title">{t("practice.segment.pron.title")}</span>
          <span className="kp-segment__dek">{t("practice.segment.pron.dek")}</span>
          <span className="kp-segment__arrow k-serif">→</span>
        </button>
        <button className="kp-segment" onClick={() => setGender(true)}>
          <span className="kp-segment__title">{t("practice.segment.gender.title")}</span>
          <span className="kp-segment__dek">{t("practice.segment.gender.dek")}</span>
          <span className="kp-segment__arrow k-serif">→</span>
        </button>
      </section>
    </main>
  );
}
