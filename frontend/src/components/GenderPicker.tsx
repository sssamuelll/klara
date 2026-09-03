/**
 * La pregunta de artículo (der/die/das), compartida por el quiz de fin de
 * historia y por la sesión de género. Vocabulario k-*: es una ficha plana
 * (átomo 3) con el hueco del pasaje puntuado (átomo 14) y sus acciones en el
 * pie de la ficha, porque sus dos consumidores viven en cascarones distintos.
 */

import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { GenderAttemptOut, GenderRule } from "../api/types";
import { genderRuleNote } from "../lib/genderRuleNote";

const GENDER_OPTIONS = ["der", "die", "das"] as const;

interface GenderPickerProps {
  lemma: string;
  en?: string | null;
  onGrade: (article: "der" | "die" | "das") => Promise<GenderAttemptOut>;
  onResult: (correct: boolean) => void;
  onNext: () => void;
  isLast: boolean;
}

export default function GenderPicker({
  lemma,
  en,
  onGrade,
  onResult,
  onNext,
  isLast,
}: GenderPickerProps): JSX.Element {
  const { t } = useTranslation();
  const lockRef = useRef(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [result, setResult] = useState<{
    correct: boolean;
    correctGender: string | null;
    rule: GenderRule | null;
  } | null>(null);

  const onPick = (article: "der" | "die" | "das") => {
    if (lockRef.current) return;
    lockRef.current = true;
    setPicked(article);
    void onGrade(article)
      .then((r) => {
        setResult({ correct: r.was_correct, correctGender: r.correct_gender, rule: r.rule ?? null });
        onResult(r.was_correct);
      })
      .catch(() => {
        // Couldn't verify: grade as wrong-unknown but still advance — never strand the user.
        setResult({ correct: false, correctGender: null, rule: null });
        onResult(false);
      });
  };

  const ruleNote = result ? genderRuleNote(t, result.rule, result.correctGender, lemma) : null;

  return (
    <article className="k-card k-card--flat" data-type="gender_cloze">
      <header className="k-card__head">
        <span className="k-cap">{t("story.finish.quiz.genderCloze.cap")}</span>
      </header>
      <div className="k-card__body">
        {/* La línea de respuesta del átomo 3, no el pasaje: este componente se
            usa también fuera de `.k-app` (la sesión de género) y `.k-stage` va
            acotado al cascarón. El artículo trae su color por `data-gender`. */}
        <p className="k-card__answer">
          <span className="k-card__article" data-gender={result?.correctGender ?? undefined}>
            {result ? result.correctGender || "—" : "___"}
          </span>
          <span className="k-card__word">{lemma}</span>
        </p>
        {en && <p className="k-note">{en}</p>}
        {/* La prosa en el cuerpo y los controles en el pie: el pie reparte a los
            extremos y estrangula cualquier nota que se meta ahí. */}
        {!picked && (
          <p className="k-note k-note--bare">{t("story.finish.quiz.genderCloze.prompt")}</p>
        )}
        {result && (
          <>
            <p className="k-note k-note--bare">
              {result.correct
                ? t("story.finish.quiz.genderCloze.correct")
                : result.correctGender
                  ? t("story.finish.quiz.genderCloze.wrong", { correct: result.correctGender })
                  : t("story.finish.quiz.genderCloze.failed")}
            </p>
            {ruleNote && <p className="k-note">{ruleNote}</p>}
          </>
        )}
      </div>
      <hr className="k-card__rule" />
      <footer className="k-card__foot">
        {!picked ? (
          // Hijos directos del pie: `--block` los reparte en tercios. Dentro de
          // un `.k-wrap` la base sería del 50 % y tres no cuadran.
          GENDER_OPTIONS.map((a) => (
            <button
              key={a}
              type="button"
              className="k-btn k-btn--ghost k-btn--block"
              onClick={() => onPick(a)}
            >
              {a}
            </button>
          ))
        ) : (
          result && (
            <button type="button" className="k-btn k-btn--block" onClick={onNext}>
              {isLast ? t("story.finish.quiz.toSummary") : t("story.finish.quiz.next")}{" "}
              <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          )
        )}
      </footer>
    </article>
  );
}
