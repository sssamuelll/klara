import "../styles/gender-review.css";

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { GenderReviewItem } from "../api/types";
import GenderPicker from "../components/GenderPicker";

type Phase = "loading" | "failed" | "empty" | "session" | "summary";

export default function GenderReview(): JSX.Element {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [items, setItems] = useState<GenderReviewItem[]>([]);
  const [phase, setPhase] = useState<Phase>("loading");
  const [idx, setIdx] = useState(0);
  const [correct, setCorrect] = useState(0);

  // Initial fetch (alive-guarded, mirrors Practice.tsx).
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

  // "Another round" — refetch (now-mastered nouns are gone). User action; no alive guard.
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

  const goHome = () => navigate("/");

  if (phase === "loading") {
    return (
      <main className="gr">
        <p className="gr__loading">{t("genderReview.title")}</p>
      </main>
    );
  }

  if (phase === "failed" || phase === "empty") {
    return (
      <main className="gr">
        <h1 className="gr__title">{t("genderReview.title")}</h1>
        <p className="gr__empty">{t("genderReview.empty")}</p>
        <button type="button" className="fin-btn fin-btn--primary" onClick={goHome}>
          {t("genderReview.home")}
        </button>
      </main>
    );
  }

  if (phase === "summary") {
    return (
      <main className="gr">
        <h1 className="gr__title">{t("genderReview.title")}</h1>
        <p className="gr__summary">{t("genderReview.summary", { correct, total: items.length })}</p>
        <div className="gr__actions">
          <button type="button" className="fin-btn fin-btn--primary" onClick={restart}>
            {t("genderReview.again")}
          </button>
          <button type="button" className="fin-btn" onClick={goHome}>
            {t("genderReview.home")}
          </button>
        </div>
      </main>
    );
  }

  // phase === "session"
  const item = items[idx];
  return (
    <main className="gr">
      <header className="gr__head">
        <h1 className="gr__title">{t("genderReview.title")}</h1>
        <span className="gr__progress k-mono">
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
