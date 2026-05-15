import { useTranslation } from "react-i18next";

export type PronScore = "good" | "ok" | "bad";
export type PronScores = Record<number, PronScore>;

interface Props {
  scores: PronScores;
  onRetry: () => void;
  onListen: () => void;
}

export default function PronunciationFeedback({ scores, onRetry, onListen }: Props) {
  const { t } = useTranslation();
  const vals = Object.values(scores);
  const good = vals.filter((v) => v === "good").length;
  const ok = vals.filter((v) => v === "ok").length;
  const bad = vals.filter((v) => v === "bad").length;
  const total = vals.length || 1;
  const pct = Math.round(((good + ok * 0.6) / total) * 100);

  let verdict = t("pron.verdict.excellent");
  if (pct < 60) verdict = t("pron.verdict.again");
  else if (pct < 80) verdict = t("pron.verdict.almost");
  else if (pct < 95) verdict = t("pron.verdict.good");

  return (
    <div className="pron">
      <div className="pron__head">
        <span className="pron__score">
          <span className="pron__score-num">{pct}</span>
          <span className="pron__score-unit k-mono">/100</span>
        </span>
        <span className="pron__verdict">{verdict}</span>
      </div>
      <div className="pron__breakdown">
        {good > 0 && (
          <span className="pron__pill" data-tone="good">
            {t("pron.pill.clear", { count: good })}
          </span>
        )}
        {ok > 0 && (
          <span className="pron__pill" data-tone="ok">
            {t("pron.pill.approx", { count: ok })}
          </span>
        )}
        {bad > 0 && (
          <span className="pron__pill" data-tone="bad">
            {t("pron.pill.review", { count: bad })}
          </span>
        )}
      </div>
      <div className="pron__actions">
        <button type="button" className="pron__btn" onClick={onListen}>
          <span className="pron__btn-icon">▸</span> {t("pron.btn.listen")}
        </button>
        <button type="button" className="pron__btn" onClick={onRetry}>
          ↻ {t("pron.btn.retry")}
        </button>
      </div>
    </div>
  );
}
