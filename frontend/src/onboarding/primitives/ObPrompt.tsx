import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  sub?: string;
}

export default function ObPrompt({ children, sub }: Props) {
  return (
    <>
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{children}</h1>
        {sub && <p className="k-hero__dek">{sub}</p>}
      </header>
      <hr className="k-hairline" />
    </>
  );
}
