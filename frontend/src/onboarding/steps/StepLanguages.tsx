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
import ObStep from "../primitives/ObStep";
import { ObInlineTrigger, ObSelectSheet } from "../primitives/ObInlineSelect";

type Props = Pick<StepProps, "data" | "setField" | "next" | "prev" | "whisper">;

const TARGET_SUB: Record<TargetLang, string> = {
  de: "Buena elección. El alemán recompensa la paciencia.",
  en: "Inglés: la lingua franca. Lo importante es matizarlo.",
  fr: "El francés es música con reglas.",
  pt: "Português: dulce y traicionero.",
  ja: "Japonés: paciencia y placer en partes iguales.",
};

export default function StepLanguages({ data, setField, next, prev, whisper }: Props) {
  const { patchUser } = useAuth();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<"native" | "target" | null>(null);

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
      <ObPrompt>¿Qué hablas y qué quieres aprender?</ObPrompt>

      {/* La frase que se rellena es un pasaje, y los dos valores son palabras
          del pasaje que se pueden tocar (átomo 14). */}
      <p className="k-stage">
        Hablo{" "}
        <ObInlineTrigger<NativeLang>
          value={data.native}
          options={NATIVE_LANGS}
          open={open === "native"}
          onOpen={() => setOpen("native")}
        />{" "}
        y quiero aprender{" "}
        <ObInlineTrigger<TargetLang>
          value={data.target}
          options={TARGET_LANGS}
          open={open === "target"}
          onOpen={() => setOpen("target")}
        />
        .
      </p>

      <p className="k-note">{TARGET_SUB[data.target]}</p>

      {error && <p className="k-error" role="alert">{error}</p>}

      {open === "native" && (
        <ObSelectSheet<NativeLang>
          title="Hablo"
          value={data.native}
          options={NATIVE_LANGS}
          onChange={(v) => setField("native", v)}
          onClose={() => setOpen(null)}
        />
      )}
      {open === "target" && (
        <ObSelectSheet<TargetLang>
          title="Quiero aprender"
          value={data.target}
          options={TARGET_LANGS}
          onChange={(v) => setField("target", v)}
          onClose={() => setOpen(null)}
        />
      )}
    </ObStep>
  );
}
