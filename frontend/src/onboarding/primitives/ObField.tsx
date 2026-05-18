import type { ReactNode } from "react";

interface Props {
  label: string;
  hint?: string | null;
  children: ReactNode;
}

export default function ObField({ label, hint, children }: Props) {
  return (
    <label className="ob-field">
      <span className="k-mono ob-field__label">{label}</span>
      {children}
      {hint && <span className="ob-field__hint">{hint}</span>}
    </label>
  );
}
