import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { Theme } from "../lib/preferences";
import { useAuth } from "../lib/auth";
import KlaraMark from "./KlaraMark";

interface Props {
  edition: string;
  theme: Theme;
  onToggleTheme: () => void;
}

export default function Masthead({ edition, theme, onToggleTheme }: Props) {
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isHome = pathname === "/" || pathname.startsWith("/story");
  const isReview = pathname.startsWith("/review");
  const isChat = pathname.startsWith("/chat");
  const isSettings = pathname.startsWith("/settings");
  const switchLabel = theme === "light" ? t("nav.theme.toDark") : t("nav.theme.toLight");
  const switchAria = theme === "light" ? t("nav.theme.aria.toDark") : t("nav.theme.aria.toLight");

  async function onLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="k-masthead">
      <Link to={user ? "/" : "/login"} className="lockup" aria-label={t("nav.brand.aria")}>
        <KlaraMark size={20} />
        <span className="wordmark">Klara</span>
        <span className="edition">{edition}</span>
      </Link>
      <nav>
        {user && !user.needs_onboarding && (
          <>
            <Link to="/" data-active={isHome}>{t("nav.home")}</Link>
            <Link to="/review" data-active={isReview}>{t("nav.review")}</Link>
            <Link to="/chat" data-active={isChat}>{t("nav.chat")}</Link>
            <Link to="/settings" data-active={isSettings}>{t("nav.settings")}</Link>
          </>
        )}
        <a
          className="k-masthead__star"
          href="https://github.com/sssamuelll/klara"
          target="_blank"
          rel="noopener noreferrer"
          aria-label={t("nav.star.aria")}
          title={t("nav.star.aria")}
        >
          <span className="k-masthead__star-icon" aria-hidden="true">★</span>
          <span className="k-masthead__star-label">{t("nav.star.label")}</span>
        </a>
        {user && (
          <button
            type="button"
            className="k-masthead__theme"
            onClick={onLogout}
            aria-label={t("settings.account.logoutBtn")}
            title={t("settings.account.logoutBtn")}
          >
            {t("settings.account.logoutBtn")}
          </button>
        )}
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
