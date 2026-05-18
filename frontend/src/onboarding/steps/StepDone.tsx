import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useAuth } from "../../lib/auth";
import KlaraMark from "../../components/KlaraMark";
import { NATIVE_LANGS, TARGET_LANGS, type OnboardingData } from "../data";

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
      navigate("/", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Algo no salió bien.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="ob-done">
      <div className="ob-done__mark">
        <KlaraMark size={120} speaking />
      </div>
      <h1 className="ob-done__title">
        Bienvenido,
        <span className="ob-done__name k-serif"> {name}</span>.
      </h1>
      <p className="ob-done__sub k-serif">
        {data.level
          ? `Empezaremos por ${data.level}. Tu primera historia te espera.`
          : "Tu primera historia te espera."}
      </p>

      <div className="ob-done__summary">
        <div className="ob-done__row">
          <span className="k-mono">Aprenderás</span>
          <span className="ob-done__row-val">{targetLabel}</span>
        </div>
        <div className="ob-done__row">
          <span className="k-mono">Desde</span>
          <span className="ob-done__row-val">{nativeLabel}</span>
        </div>
        <div className="ob-done__row">
          <span className="k-mono">Nivel</span>
          <span className="ob-done__row-val">{data.level ?? "Sin definir"}</span>
        </div>
      </div>

      {error && <div className="ob-error k-mono" role="alert">{error}</div>}

      <button
        type="button"
        className="ob-btn ob-btn--lg"
        onClick={() => void complete()}
        disabled={submitting}
        autoFocus
      >
        <span>Llévame a mi historia</span>
        <span className="ob-btn__arrow k-serif">→</span>
      </button>
    </div>
  );
}
