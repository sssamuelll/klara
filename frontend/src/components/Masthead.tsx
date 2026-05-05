import { Link, useLocation } from "react-router-dom";
import type { Theme } from "../lib/preferences";
import KlaraMark from "./KlaraMark";

interface Props {
  edition: string;
  theme: Theme;
  onToggleTheme: () => void;
}

export default function Masthead({ edition, theme, onToggleTheme }: Props) {
  const { pathname } = useLocation();
  const isHome = pathname === "/" || pathname.startsWith("/story");
  const isReview = pathname.startsWith("/review");
  const isChat = pathname.startsWith("/chat");
  const switchLabel = theme === "light" ? "Noche" : "Día";

  return (
    <header className="k-masthead">
      <Link to="/" className="lockup" aria-label="Klara — inicio">
        <KlaraMark size={20} />
        <span className="wordmark">Klara</span>
        <span className="edition">{edition}</span>
      </Link>
      <nav>
        <Link to="/" data-active={isHome}>Hoy</Link>
        <Link to="/review" data-active={isReview}>Repaso</Link>
        <Link to="/chat" data-active={isChat}>Hablar</Link>
        <button
          type="button"
          className="k-masthead__theme"
          onClick={onToggleTheme}
          aria-label={`Cambiar a modo ${theme === "light" ? "oscuro" : "claro"}`}
          title={`Cambiar a modo ${theme === "light" ? "oscuro" : "claro"}`}
        >
          {switchLabel}
        </button>
      </nav>
    </header>
  );
}
