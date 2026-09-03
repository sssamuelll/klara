import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useAuth } from "../../lib/auth";
import { NATIVE_LANGS, TARGET_LANGS, type OnboardingData } from "../data";
import ObStep from "../primitives/ObStep";

interface Props {
  data: OnboardingData;
  /**
   * Called once `api.completeOnboarding()` resolves successfully so the shell
   * can clear localStorage before the route changes.
   */
  onCompleted?: () => void;
}

export default function StepDone({ data, onCompleted }: Props) {
  const { applyUserResponse } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const name = data.name.trim() || "lector";
  const targetLabel =
    (TARGET_LANGS.find((l) => l.code === data.target) ?? TARGET_LANGS[0]).label;
  const nativeLabel =
    (NATIVE_LANGS.find((l) => l.code === data.native) ?? NATIVE_LANGS[0]).label;

  async function complete() {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await api.completeOnboarding();
      applyUserResponse(updated);
      onCompleted?.();
      // Primer arranque = cuestionario de Perfil de Aprendizaje (F1.5, D-J).
      // No atrapa: todas sus preguntas se saltan y «Más tarde» entra a la app.
      navigate("/perfil/aprendizaje", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Algo no salió bien.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ObStep
      nav={
        <div className="k-wrap">
          <button
            type="button"
            className="k-btn k-btn--lg k-btn--block"
            onClick={() => void complete()}
            disabled={submitting}
            autoFocus
          >
            Llévame a mi historia{" "}
            <span className="k-btn__arrow" aria-hidden="true">→</span>
          </button>
        </div>
      }
    >
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">
          Bienvenido, <em>{name}</em>.
        </h1>
        <p className="k-hero__dek">
          {data.level
            ? `Empezaremos por ${data.level}. Tu primera historia te espera.`
            : "Tu primera historia te espera."}
        </p>
      </header>

      <hr className="k-hairline" />
      <ul>
        <li className="k-row k-row--quiet">
          <span className="k-row__n">Aprenderás</span>
          <span className="k-row__title">{targetLabel}</span>
        </li>
        <li className="k-row k-row--quiet">
          <span className="k-row__n">Desde</span>
          <span className="k-row__title">{nativeLabel}</span>
        </li>
        <li className="k-row k-row--quiet">
          <span className="k-row__n">Nivel</span>
          <span className="k-row__title">{data.level ?? "Sin definir"}</span>
        </li>
      </ul>
      <hr className="k-hairline" />

      {error && <p className="k-error" role="alert">{error}</p>}
    </ObStep>
  );
}
