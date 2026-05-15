import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Theme } from "../lib/preferences";
import KlaraMark from "./KlaraMark";

interface Props {
  edition: string;
  theme: Theme;
  onToggleTheme: () => void;
}

export default function Masthead({ edition, theme, onToggleTheme }: Props) {
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const isHome = pathname === "/" || pathname.startsWith("/story");
  const isReview = pathname.startsWith("/review");
  const isChat = pathname.startsWith("/chat");
  const isSettings = pathname.startsWith("/settings");
  const switchLabel = theme === "light" ? t("nav.theme.toDark") : t("nav.theme.toLight");
  const switchAria = theme === "light" ? t("nav.theme.aria.toDark") : t("nav.theme.aria.toLight");

  return (
    <header className="k-masthead">
      <Link to="/" className="lockup" aria-label={t("nav.brand.aria")}>
        <KlaraMark size={20} />
        <span className="wordmark">Klara</span>
        <span className="edition">{edition}</span>
      </Link>
      <nav>
        <Link to="/" data-active={isHome}>{t("nav.home")}</Link>
        <Link to="/review" data-active={isReview}>{t("nav.review")}</Link>
        <Link to="/chat" data-active={isChat}>{t("nav.chat")}</Link>
        <Link to="/settings" data-active={isSettings}>{t("nav.settings")}</Link>
        <button
          type="button"
          className="k-masthead__theme"
          onClick={onToggleTheme}
          aria-label={switchAria}
          title={switchAria}
        >
          {switchLabel}
        </button>
      </nav>
    </header>
  );
}
