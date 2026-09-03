import { useState } from "react";
import { useAuth } from "../../lib/auth";
import { LEVELS, type StepProps } from "../data";
import ObPrompt from "../primitives/ObPrompt";
import ObNav from "../primitives/ObNav";
import ObStep from "../primitives/ObStep";

type Props = Pick<StepProps, "data" | "setField" | "next" | "prev" | "whisper">;

export default function StepLevel({ data, setField, next, prev, whisper }: Props) {
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
    <ObStep
      whisper={whisper}
      nav={
        <ObNav
          onNext={() => void commit()}
          onPrev={prev}
          canNext={can}
          submitting={submitting}
        />
      }
    >
      <ObPrompt sub="Klara empieza más fácil de lo que digas. Puedes cambiarlo cuando quieras.">
        ¿Dónde estás ahora?
      </ObPrompt>

      {/* La nube es la que reparte: en 430px cada ficha se lleva su renglón,
          y el hueco de 8px lo pone `.k-wrap`, no el markup. */}
      <div className="k-wrap" role="radiogroup" aria-label="Tu nivel">
        {LEVELS.map((lv) => (
          <button
            key={lv.code}
            type="button"
            role="radio"
            aria-checked={data.level === lv.code}
            className="k-row k-row--boxed"
            data-state={data.level === lv.code ? "selected" : undefined}
            onClick={() => setField("level", lv.code)}
            disabled={submitting}
          >
            <span className="k-level k-level--bare" data-active={data.level === lv.code}>
              {lv.code}
            </span>
            <span className="k-row__title">{lv.title}</span>
            <span className="k-row__sub">{lv.phrase}</span>
          </button>
        ))}
      </div>

      {error && <p className="k-error" role="alert">{error}</p>}
    </ObStep>
  );
}
