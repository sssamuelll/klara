import "../styles/recall-review.css";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { ReviewRating } from "../api/types";
import { speak } from "../lib/tts";
import { formatInterval, projectIntervals } from "../lib/srsProjection";
import { initialRecallState, recallReducer, restedCount } from "../lib/recallSession";

const RATINGS: ReviewRating[] = ["again", "hard", "good", "easy"];

interface Props {
  onExit: () => void;
  exitLabel: string;
}

export default function RecallReviewSession({ onExit, exitLabel }: Props): JSX.Element {
  const { t } = useTranslation();
  const [state, dispatch] = useReducer(recallReducer, initialRecallState);
  const shownAt = useRef<number>(0);

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
      void api.reviewCard(card.id, rating, elapsed).catch(() => undefined);
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
      <main className="rr">
        <p className="rr__loading k-mono">{t("recall.loading")}</p>
      </main>
    );
  }
  if (state.phase === "failed" || state.phase === "empty") {
    return (
      <main className="rr">
        <h1 className="rr__title">{t("recall.title")}</h1>
        <p className="rr__empty">{t(state.phase === "failed" ? "recall.failed" : "recall.empty")}</p>
        <button type="button" className="rr-done__cta" onClick={onExit}>
          {exitLabel}
        </button>
      </main>
    );
  }
  if (state.phase === "done") {
    return (
      <main className="rr" data-state="done">
        <section className="rr-done">
          <span className="rr-done__folio k-mono">{t("recall.done.kicker")}</span>
          <span className="rr-done__count">{state.cards.length}</span>
          <span className="rr-done__label">{t("recall.done.label")}</span>
          <div className="rr-done__ledger">
            <div className="rr-done__stat">
              <span className="rr-done__stat-n rr-done__stat-n--accent">{state.againCount}</span>
              <span className="rr-done__stat-l">{t("recall.done.again")}</span>
            </div>
            <div className="rr-done__stat">
              <span className="rr-done__stat-n">{restedCount(state)}</span>
              <span className="rr-done__stat-l">{t("recall.done.rest")}</span>
            </div>
          </div>
          <p className="rr-done__note">{t("recall.done.note")}</p>
          <span className="rr-done__sign">{t("recall.done.sign")}</span>
          <button type="button" className="rr-done__cta" onClick={onExit}>
            {t("recall.done.home")} →
          </button>
        </section>
      </main>
    );
  }

  // phase === "prompt" | "revealed"
  const intervals = projectIntervals(card);
  return (
    <main className="rr" data-state={state.phase}>
      <header className="rr-head">
        <button type="button" className="rr-head__exit k-mono" onClick={onExit}>
          {t("recall.exit")}
        </button>
        <div className="rr-head__title">
          <span className="rr-head__k">K</span>
          <span className="rr-head__name">{t("recall.title")}</span>
        </div>
        <span className="rr-head__meta k-mono">{t("recall.kicker")}</span>
      </header>

      <div className="rr-prog">
        <span className="rr-prog__count k-mono">
          {t("recall.progress", { done: state.idx + 1, total: state.cards.length })}
        </span>
      </div>

      <section className="rr-deck">
        <div className="rr-ficha">
          <div className="rr-ficha__inner">
            <div className="rr-ficha__face rr-ficha__face--front">
              <span className="rr-ficha__word">{card.lemma}</span>
              {card.gender && (
                <span className="rr-ficha__gender-cue k-mono">
                  <b>der</b> · <b>die</b> · <b>das</b> ?
                </span>
              )}
              <span className="rr-ficha__cue">{t("recall.cue")}</span>
              <button type="button" className="rr-listen k-mono" onClick={() => speak(card.lemma)}>
                <span className="rr-listen__tri" /> {t("recall.listen")}
              </button>
            </div>
            <div className="rr-ficha__face rr-ficha__face--back">
              <div className="rr-ficha__answer">
                {card.gender && <span className="rr-ficha__article">{card.gender}</span>}
                <span className="rr-ficha__answer-word">{card.lemma}</span>
                {card.translation && <span className="rr-ficha__tx">— {card.translation}</span>}
              </div>
              {card.example_target && (
                <>
                  <div className="rr-ficha__rule" />
                  <p className="rr-ficha__eg">{card.example_target}</p>
                </>
              )}
            </div>
          </div>
        </div>

        <div data-show="prompt" className="rr-deck__prompt">
          <button type="button" className="rr-flip" onClick={() => dispatch({ type: "flip" })}>
            {t("recall.flip")} <span className="rr-flip__arrow">↻</span>
          </button>
          <p className="rr-deck__hint">{t("recall.flipHint")}</p>
        </div>

        <div className="rr-rate" data-show="revealed">
          {RATINGS.map((r) => (
            <button
              key={r}
              type="button"
              className={`rr-rate__btn${r === "again" ? " rr-rate__btn--again" : ""}`}
              onClick={() => rate(r)}
            >
              <span className="rr-rate__lbl">{t(`recall.rate.${r}`)}</span>
              <span className="rr-rate__when k-mono">{formatInterval(intervals[r])}</span>
            </button>
          ))}
        </div>
        <p className="rr-deck__hint" data-show="revealed">
          {t("recall.rateHint")}
        </p>
      </section>
    </main>
  );
}
