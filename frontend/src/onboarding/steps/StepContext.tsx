import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import { CONTEXT_EXAMPLES, type StepProps } from "../data";
import ObPrompt from "../primitives/ObPrompt";
import ObNav from "../primitives/ObNav";
import ObStep from "../primitives/ObStep";

type Props = Pick<StepProps, "data" | "setField" | "next" | "prev" | "whisper">;

export default function StepContext({ data, setField, next, prev, whisper }: Props) {
  const { patchUser } = useAuth();
  const [exampleIdx, setExampleIdx] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = setInterval(
      () => setExampleIdx((i) => (i + 1) % CONTEXT_EXAMPLES.length),
      4200,
    );
    return () => clearInterval(t);
  }, []);

  async function commit() {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const trimmed = data.context.trim();
      await patchUser({ learning_context: trimmed.length === 0 ? null : trimmed });
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
          onSkip={next}
          skipLabel="Saltar"
          canNext={true}
          submitting={submitting}
        />
      }
    >
      <ObPrompt sub="Klara usa esto para elegir temas, vocabulario y tono. Es opcional.">
        Cuéntame algo de ti.
      </ObPrompt>

      <label className="k-field k-field--area">
        <textarea
          className="k-field__input"
          value={data.context}
          onChange={(e) => setField("context", e.target.value)}
          placeholder={CONTEXT_EXAMPLES[exampleIdx]}
          maxLength={500}
          rows={5}
          disabled={submitting}
        />
      </label>
      <p className="k-cap">
        <span className="k-cap__count">{data.context.length} / 500</span>
      </p>

      {error && <p className="k-error" role="alert">{error}</p>}
    </ObStep>
  );
}
