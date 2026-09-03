import { useState } from "react";
import { api } from "../../api/client";
import { useAuth } from "../../lib/auth";
import type { StepProps } from "../data";
import ObPrompt from "../primitives/ObPrompt";
import ObNav from "../primitives/ObNav";
import ObStep from "../primitives/ObStep";
import ObField from "../primitives/ObField";

type Props = Pick<StepProps, "data" | "setField" | "next" | "prev" | "whisper">;

export default function StepPassword({ data, setField, next, prev, whisper }: Props) {
  const { applyUserResponse } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Mandatory: must be >= 8 and match (no skip).
  const valid = data.password.length >= 8 && data.password === data.passwordConfirm;

  const mismatch =
    data.password.length > 0 &&
    data.passwordConfirm.length > 0 &&
    data.password !== data.passwordConfirm;

  async function commit() {
    if (!valid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await api.setPassword(data.password);
      applyUserResponse(updated);
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
          canNext={valid}
          submitting={submitting}
        />
      }
    >
      <ObPrompt sub="Entraste con Google. Crea una contraseña como respaldo, por si pierdes el acceso a Google.">
        Crea tu contraseña
      </ObPrompt>

      <ObField label="Contraseña">
        <input
          type="password"
          className="k-field__input"
          value={data.password}
          onChange={(e) => setField("password", e.target.value)}
          placeholder="•••••••"
          autoComplete="new-password"
          disabled={submitting}
        />
      </ObField>
      <ObField label="Repítela" hint={mismatch ? "No coinciden." : null}>
        <input
          type="password"
          className="k-field__input"
          aria-invalid={mismatch || undefined}
          value={data.passwordConfirm}
          onChange={(e) => setField("passwordConfirm", e.target.value)}
          placeholder="•••••••"
          autoComplete="new-password"
          disabled={submitting}
        />
      </ObField>

      {error && <p className="k-error" role="alert">{error}</p>}
    </ObStep>
  );
}
