import { useEffect, useRef, useState, type FormEvent } from "react";
import { useAuth } from "../../lib/auth";
import type { StepProps } from "../data";
import ObPrompt from "../primitives/ObPrompt";
import ObNav from "../primitives/ObNav";

type Props = Pick<StepProps, "data" | "setField" | "next">;

export default function StepName({ data, setField, next }: Props) {
  const { patchUser } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const trimmed = data.name.trim();
  const can = trimmed.length >= 1;

  async function commit() {
    if (!can || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await patchUser({ display_name: trimmed });
      next();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Algo no salió bien.");
    } finally {
      setSubmitting(false);
    }
  }

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void commit();
  }

  return (
    <form className="ob-step ob-name" onSubmit={onSubmit}>
      <ObPrompt>¿Cómo te llamas?</ObPrompt>

      <div className="ob-name__input-wrap">
        <input
          ref={inputRef}
          className="ob-name__input"
          value={data.name}
          onChange={(e) => setField("name", e.target.value)}
          placeholder="Samuel"
          autoComplete="given-name"
          maxLength={40}
          disabled={submitting}
        />
        <span className="ob-name__rule" />
        <span className="ob-name__hint k-mono">
          {trimmed ? `Encantada, ${trimmed}.` : "Como prefieras que te llame."}
        </span>
      </div>

      {error && <div className="ob-error k-mono" role="alert">{error}</div>}

      <ObNav
        onNext={() => void commit()}
        canNext={can}
        submitting={submitting}
      />
    </form>
  );
}
