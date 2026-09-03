import type { ReactNode } from "react";

interface Props {
  label: string;
  hint?: string | null;
  children: ReactNode;
}

export default function ObField({ label, hint, children }: Props) {
  return (
    <label className="k-field" data-error={hint ? "true" : undefined}>
      <span className="k-field__label">{label}</span>
      {children}
      {hint && <span className="k-field__hint">{hint}</span>}
    </label>
  );
}
