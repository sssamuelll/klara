export type PronScore = "good" | "ok" | "bad";
export type PronScores = Record<number, PronScore>;

interface Props {
  scores: PronScores;
  onRetry: () => void;
  onListen: () => void;
}

export default function PronunciationFeedback({ scores, onRetry, onListen }: Props) {
  const vals = Object.values(scores);
  const good = vals.filter((v) => v === "good").length;
  const ok = vals.filter((v) => v === "ok").length;
  const bad = vals.filter((v) => v === "bad").length;
  const total = vals.length || 1;
  const pct = Math.round(((good + ok * 0.6) / total) * 100);

  let verdict = "Excelente.";
  if (pct < 60) verdict = "Probemos de nuevo.";
  else if (pct < 80) verdict = "Casi.";
  else if (pct < 95) verdict = "Muy bien.";

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
            {good} clara{good > 1 ? "s" : ""}
          </span>
        )}
        {ok > 0 && (
          <span className="pron__pill" data-tone="ok">
            {ok} aproximada{ok > 1 ? "s" : ""}
          </span>
        )}
        {bad > 0 && (
          <span className="pron__pill" data-tone="bad">
            {bad} a revisar
          </span>
        )}
      </div>
      <div className="pron__actions">
        <button type="button" className="pron__btn" onClick={onListen}>
          <span className="pron__btn-icon">▸</span> Escuchar a Klara
        </button>
        <button type="button" className="pron__btn" onClick={onRetry}>
          ↻ Otra vez
        </button>
      </div>
    </div>
  );
}
