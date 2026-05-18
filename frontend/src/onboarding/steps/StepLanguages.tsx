import { useState } from "react";
import { useAuth } from "../../lib/auth";
import {
  NATIVE_LANGS,
  TARGET_LANGS,
  type NativeLang,
  type StepProps,
  type TargetLang,
} from "../data";
import ObPrompt from "../primitives/ObPrompt";
import ObNav from "../primitives/ObNav";
import ObInlineSelect from "../primitives/ObInlineSelect";

type Props = Pick<StepProps, "data" | "setField" | "next" | "prev">;

const TARGET_SUB: Record<TargetLang, string> = {
  de: "Buena elección. El alemán recompensa la paciencia.",
  en: "Inglés: la lingua franca. Lo importante es matizarlo.",
  fr: "El francés es música con reglas.",
  pt: "Português: dulce y traicionero.",
  ja: "Japonés: paciencia y placer en partes iguales.",
};

export default function StepLanguages({ data, setField, next, prev }: Props) {
  const { patchUser } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Native is restricted to NativeLang and target to TargetLang, so any non-equal
  // pair is valid — but mirror the JSX check for defense-in-depth.
  const can =
    Boolean(data.native) &&
    Boolean(data.target) &&
    (data.native as string) !== (data.target as string);

  async function commit() {
    if (!can || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await patchUser({
        native_language: data.native,
        target_language: data.target,
      });
      next();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Algo no salió bien.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="ob-step ob-lang">
      <ObPrompt>¿Qué hablas y qué quieres aprender?</ObPrompt>

      <p className="ob-lang__sentence">
        <span>Hablo&nbsp;</span>
        <ObInlineSelect<NativeLang>
          value={data.native}
          onChange={(v) => setField("native", v)}
          options={NATIVE_LANGS}
        />
        <span>&nbsp;y quiero aprender&nbsp;</span>
        <ObInlineSelect<TargetLang>
          value={data.target}
          onChange={(v) => setField("target", v)}
          options={TARGET_LANGS}
        />
        <span>.</span>
      </p>

      <div className="ob-lang__sub k-serif">{TARGET_SUB[data.target]}</div>

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
