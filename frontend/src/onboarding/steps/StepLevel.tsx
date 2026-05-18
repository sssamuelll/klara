import { useState } from "react";
import { useAuth } from "../../lib/auth";
import { LEVELS, type StepProps } from "../data";
import ObPrompt from "../primitives/ObPrompt";
import ObNav from "../primitives/ObNav";

type Props = Pick<StepProps, "data" | "setField" | "next" | "prev">;

export default function StepLevel({ data, setField, next, prev }: Props) {
  const { patchUser } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const can = data.level !== null;

  async function commit() {
    if (!can || submitting || data.level === null) return;
    setSubmitting(true);
    setError(null);
    try {
      await patchUser({ level: data.level });
      next();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Algo no salió bien.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="ob-step ob-level">
      <ObPrompt sub="Klara empieza más fácil de lo que digas. Puedes cambiarlo cuando quieras.">
        ¿Dónde estás ahora?
      </ObPrompt>

      <div className="ob-level__grid" role="radiogroup" aria-label="Tu nivel">
        {LEVELS.map((lv) => (
          <button
            key={lv.code}
            type="button"
            role="radio"
            aria-checked={data.level === lv.code}
            className="ob-level__card"
            data-active={data.level === lv.code}
            onClick={() => setField("level", lv.code)}
            disabled={submitting}
          >
            <span className="ob-level__code k-mono">{lv.code}</span>
            <span className="ob-level__title">{lv.title}</span>
            <span className="ob-level__phrase k-serif">{lv.phrase}</span>
          </button>
        ))}
      </div>

      {error && <div className="ob-error k-mono" role="alert">{error}</div>}

      <ObNav
        onNext={() => void commit()}
        onPrev={prev}
        canNext={can}
        submitting={submitting}
      />
    </div>
  );
}
