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
    <article className="qcard" data-type="gender_cloze">
      <header className="qcard__head">
        <span className="fin-cap">{t("story.finish.quiz.genderCloze.cap")}</span>
      </header>
      <div className="qcard__body">
        <p className="qcard__cloze">
          <span
            className="qcard__blank"
            data-state={picked ? (result?.correct ? "correct" : "revealed") : "empty"}
          >
            {result ? result.correctGender || "—" : "___"}
          </span>{" "}
          <span>{lemma}</span>
        </p>
        {en && <p className="qcard__en">{en}</p>}
        <p className="qcard__hint">{t("story.finish.quiz.genderCloze.prompt")}</p>
      </div>
      <footer className="qcard__foot">
        {!picked && (
          <div className="qcard__actions qcard__gender-opts">
            {GENDER_OPTIONS.map((a) => (
              <button key={a} type="button" className="qcard__gender-btn" onClick={() => onPick(a)}>
                {a}
              </button>
            ))}
          </div>
        )}
        {result && (
          <>
            <div className="qcard__result">
              <span className="qcard__verdict">
                {result.correct ? (
                  <em>{t("story.finish.quiz.genderCloze.correct")}</em>
                ) : result.correctGender ? (
                  t("story.finish.quiz.genderCloze.wrong", { correct: result.correctGender })
                ) : (
                  t("story.finish.quiz.genderCloze.failed")
                )}
              </span>
            </div>
            {ruleNote && <p className="qcard__rule">{ruleNote}</p>}
            <button type="button" className="fin-btn fin-btn--primary qcard__next" onClick={onNext}>
              {isLast ? t("story.finish.quiz.toSummary") : t("story.finish.quiz.next")}{" "}
              <span className="fin-arr">→</span>
            </button>
          </>
        )}
      </footer>
    </article>
  );
}
