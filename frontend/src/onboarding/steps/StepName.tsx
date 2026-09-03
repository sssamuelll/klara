import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../lib/auth";
import type { StepProps } from "../data";
import ObPrompt from "../primitives/ObPrompt";
import ObNav from "../primitives/ObNav";
import ObStep from "../primitives/ObStep";

type Props = Pick<StepProps, "data" | "setField" | "next" | "whisper">;

export default function StepName({ data, setField, next, whisper }: Props) {
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

  return (
    <ObStep
      whisper={whisper}
      nav={<ObNav onNext={() => void commit()} canNext={can} submitting={submitting} />}
    >
      <ObPrompt>¿Cómo te llamas?</ObPrompt>

      {/* El campo manuscrito: sin caja, solo el renglón (átomo 17). El <form>
          murió con el cascarón —no puede envolver `.k-fill` y `.k-dock`, que
          son hermanos—, así que Enter lo recoge el propio campo. */}
      <label className="k-field k-field--rule">
        <input
          ref={inputRef}
          className="k-field__input"
          value={data.name}
          onChange={(e) => setField("name", e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void commit();
            }
          }}
          placeholder="Samuel"
          autoComplete="given-name"
          maxLength={40}
          disabled={submitting}
        />
        <span className="k-field__rule" />
        <span className="k-field__hint">
          {trimmed ? `Encantada, ${trimmed}.` : "Como prefieras que te llame."}
        </span>
      </label>

      {error && <p className="k-error" role="alert">{error}</p>}
    </ObStep>
  );
}
