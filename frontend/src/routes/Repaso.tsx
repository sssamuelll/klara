/**
 * Repaso — la caja de fichas (SRS), vocabulario k-*.
 *
 * Superficie de sesión propia, como `/estudiar/:id`: cuelga fuera de
 * V4Shell y de LegacyShell y pinta su propio `.k-app`. Antes vivía como
 * segmento de Práctica dentro del cascarón viejo, y el armazón de sesión
 * (`.k-app` a 100dvh) no se puede anidar dentro de `.kframe`.
 *
 * Composición: línea superior + barra de segmentos + `.k-fill` con la ficha
 * volteable + `.k-dock` con la línea de ayuda y las acciones. El volteo, su
 * variante sin movimiento y la ficha entera son del átomo 3; ninguna clase
 * es de esta pantalla.
 */

import { useCallback, useEffect, useReducer, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { ReviewRating } from "../api/types";
import SessTop from "../components/SessTop";
import { tap } from "../lib/native";
import { speak } from "../lib/tts";
import { formatInterval } from "../lib/srsProjection";
import { initialRecallState, recallReducer, restedCount } from "../lib/recallSession";

const RATINGS: ReviewRating[] = ["again", "hard", "good", "easy"];

const pad2 = (n: number) => String(n).padStart(2, "0");

// Icono de trazo 1.5 del átomo 2; el tamaño lo pone `.k-btn svg`.
function IcSound() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4Z" />
      <path d="M15.5 9.5a3.5 3.5 0 0 1 0 5" />
      <path d="M18 7a7 7 0 0 1 0 10" />
    </svg>
  );
}

export default function Repaso(): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [state, dispatch] = useReducer(recallReducer, initialRecallState);
  const shownAt = useRef<number>(0);

  // Igual que Story: quien entra pasa { state: { from } } y la salida vuelve ahí.
  const exitTo = (location.state as { from?: string } | null)?.from ?? "/";
  const salir = useCallback(() => navigate(exitTo), [navigate, exitTo]);

  useEffect(() => {
    let alive = true;
    api
      .dueCards(50)
      .then((rows) => {
        if (!alive) return;
        dispatch({ type: "loaded", cards: rows });
        shownAt.current = performance.now();
      })
      .catch(() => alive && dispatch({ type: "failed" }));
    return () => {
      alive = false;
    };
  }, []);

  // Reset the per-card timer whenever a new card comes on screen.
  useEffect(() => {
    if (state.phase === "prompt") shownAt.current = performance.now();
  }, [state.idx, state.phase]);

  const card = state.cards[state.idx];

  const rate = useCallback(
    (rating: ReviewRating) => {
      if (!card) return;
      const elapsed = Math.max(0, Math.round((performance.now() - shownAt.current) / 1000));
      tap();
      void api.reviewCard(card.id, rating, elapsed).catch(() => dispatch({ type: "rateFailed" }));
      dispatch({ type: "rate", rating });
    },
    [card],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (state.phase === "prompt" && e.code === "Space") {
        e.preventDefault();
        dispatch({ type: "flip" });
      } else if (state.phase === "revealed" && ["1", "2", "3", "4"].includes(e.key)) {
        rate(RATINGS[Number(e.key) - 1]);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state.phase, rate]);

  if (state.phase === "loading") {
    return (
      <div className="k-app">
        <SessTop titulo={t("recall.title")} right="" onExit={salir} />
        <div className="k-fill">
          <span className="k-spinner" role="status" aria-label={t("recall.loading")} />
        </div>
      </div>
    );
  }

  // Vacío y fallo comparten forma y no comparten tono: no tener fichas hoy es
  // una nota, no un error (átomo 15 se reserva a lo que salió mal).
  if (state.phase === "failed" || state.phase === "empty") {
    const failed = state.phase === "failed";
    return (
      <div className="k-app">
        <SessTop titulo={t("recall.title")} right="" onExit={salir} />
        <div className="k-fill">
          {failed ? (
            <p className="k-error" role="alert">{t("recall.failed")}</p>
          ) : (
            <p className="k-note">{t("recall.empty")}</p>
          )}
        </div>
        <div className="k-dock">
          <div className="k-wrap">
            <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={salir}>
              {t("recall.done.home")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (state.phase === "done") {
    return (
      <div className="k-app">
        <SessTop titulo={t("recall.title")} right="" onExit={salir} />
        <div className="k-fill">
          <header className="k-hero k-hero--quiet">
            <span className="k-hero__tag">{t("recall.done.kicker")}</span>
            <h1 className="k-hero__title">{state.cards.length}</h1>
            <p className="k-hero__dek">{t("recall.done.label")}</p>
            <p className="k-hero__meta">
              <strong>{state.againCount}</strong> {t("recall.done.again")}
              <span aria-hidden="true">·</span>
              <strong>{restedCount(state)}</strong> {t("recall.done.rest")}
            </p>
          </header>
          <p className="k-note">{t("recall.done.note")}</p>
          {state.failedCount > 0 && (
            <p className="k-error" role="alert">
              {t("recall.done.unsaved", { count: state.failedCount })}
            </p>
          )}
          <p className="k-note k-note--bare">{t("recall.done.sign")}</p>
        </div>
        <div className="k-dock">
          <div className="k-wrap">
            <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={salir}>
              {t("recall.done.home")} <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // phase === "prompt" | "revealed"
  const intervals = card.next_intervals;
  const revealed = state.phase === "revealed";
  const total = state.cards.length;
  return (
    <div className="k-app">
      <SessTop
        titulo={t("recall.title")}
        right={`${pad2(state.idx + 1)}/${pad2(total)}`}
        onExit={salir}
      />
      <div className="k-bar k-bar--segs">
        <div
          className="k-bar__track"
          role="progressbar"
          aria-valuenow={state.idx + 1}
          aria-valuemin={0}
          aria-valuemax={total}
        >
          {Array.from({ length: total }, (_, i) => (
            <span
              key={i}
              className="k-bar__seg"
              data-state={i < state.idx ? "done" : i === state.idx ? "now" : undefined}
            />
          ))}
        </div>
      </div>

      <div className="k-fill">
        <div className="k-card k-card--flip" data-state={revealed ? "back" : "front"}>
          {/* Sin movimiento las caras se conmutan con `display` (átomo 3); quien
              no ve el volteo se entera por aquí de que la ficha cambió. */}
          <div className="k-card__inner" aria-live="polite">
            {/* La cara de espaldas sigue en el DOM (el volteo la necesita) y
                `backface-visibility` no la esconde del lector de pantalla ni
                del tabulador: la respuesta se leía antes de voltear y se podía
                tabular a un botón invisible. Sin movimiento la cara inactiva ya
                va en `display: none` y esto sobra sin estorbar. */}
            <div className="k-card__face" aria-hidden={revealed || undefined}>
              <p className="k-card__word">{card.lemma}</p>
              {card.gender && (
                <p className="k-card__cue">
                  <span className="k-card__article" data-gender="der">der</span>
                  {" · "}
                  <span className="k-card__article" data-gender="die">die</span>
                  {" · "}
                  <span className="k-card__article" data-gender="das">das</span>
                  {" ?"}
                </p>
              )}
              <p className="k-card__cue">{t("recall.cue")}</p>
              <button
                type="button"
                className="k-btn k-btn--ghost"
                tabIndex={revealed ? -1 : undefined}
                onClick={() => speak(card.lemma)}
              >
                <IcSound /> {t("recall.listen")}
              </button>
            </div>
            <div className="k-card__face" aria-hidden={!revealed || undefined}>
              <p className="k-card__answer">
                {card.gender && (
                  <span className="k-card__article" data-gender={card.gender}>{card.gender}</span>
                )}
                <span className="k-card__word">{card.lemma}</span>
                {card.translation && <span className="k-card__tx">— {card.translation}</span>}
              </p>
              {card.example_target && (
                <>
                  <hr className="k-card__rule" />
                  <p className="k-card__eg">{card.example_target}</p>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="k-dock">
        <div className="k-dock__status">
          <p className="k-cap k-cap--center">
            {t(revealed ? "recall.rateHint" : "recall.flipHint")}
          </p>
        </div>
        <div className="k-wrap">
          {revealed ? (
            RATINGS.map((r) => (
              <button
                key={r}
                type="button"
                className={`k-btn k-btn--block ${r === "again" ? "k-btn--accent" : "k-btn--ghost"}`}
                onClick={() => rate(r)}
              >
                {t(`recall.rate.${r}`)}
                <span className="k-btn__sub">{formatInterval(intervals[r])}</span>
              </button>
            ))
          ) : (
            <button
              type="button"
              className="k-btn k-btn--lg k-btn--block"
              onClick={() => dispatch({ type: "flip" })}
            >
              {t("recall.flip")} <span className="k-btn__arrow" aria-hidden="true">↻</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
