import { useEffect, useState } from "react";
import { useAuth } from "../../lib/auth";
import { CONTEXT_EXAMPLES, type StepProps } from "../data";
import ObPrompt from "../primitives/ObPrompt";
import ObNav from "../primitives/ObNav";

type Props = Pick<StepProps, "data" | "setField" | "next" | "prev">;

export default function StepContext({ data, setField, next, prev }: Props) {
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
    <div className="ob-step ob-context">
      <ObPrompt sub="Klara usa esto para elegir temas, vocabulario y tono. Es opcional.">
        Cuéntame algo de ti.
      </ObPrompt>

      <div className="ob-context__field">
        <textarea
          className="ob-context__textarea"
          value={data.context}
          onChange={(e) => setField("context", e.target.value)}
          placeholder={CONTEXT_EXAMPLES[exampleIdx]}
          maxLength={500}
          rows={5}
          disabled={submitting}
        />
        <div className="ob-context__foot">
          <span className="k-mono ob-context__count">
            {data.context.length} / 500
          </span>
        </div>
      </div>

      {error && <div className="ob-error k-mono" role="alert">{error}</div>}

      <ObNav
        onNext={() => void commit()}
        onPrev={prev}
        onSkip={next}
        skipLabel="Saltar"
        canNext={true}
        submitting={submitting}
      />
    </div>
  );
}
