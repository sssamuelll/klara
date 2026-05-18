import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  sub?: string;
}

export default function ObPrompt({ children, sub }: Props) {
  return (
    <header className="ob-prompt">
      <h1 className="ob-prompt__title">{children}</h1>
      {sub && <p className="ob-prompt__sub k-serif">{sub}</p>}
      <hr className="ob-prompt__rule" />
    </header>
  );
}
