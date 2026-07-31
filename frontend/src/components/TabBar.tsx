import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

function IcLib() {
  return (
    <svg width="20" height="18" viewBox="0 0 20 18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M3.5 2.5v13M8 2.5v13" />
      <path d="M11.5 3l3.4 12.4" strokeLinecap="round" />
    </svg>
  );
}
function IcMas() {
  return (
    <svg width="20" height="18" viewBox="0 0 20 18" fill="currentColor" aria-hidden="true">
      <circle cx="4" cy="9" r="1.7" /><circle cx="10" cy="9" r="1.7" /><circle cx="16" cy="9" r="1.7" />
    </svg>
  );
}

export default function TabBar() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [menu, setMenu] = useState(false);
  const enPerfil = pathname.startsWith("/perfil");

  return (
    <>
      {menu && <div className="m3-scrim" onClick={() => setMenu(false)} />}
      {menu && (
        <div className="m3-menu" role="menu" aria-label={t("tabbar.moreAria")}>
          <button
            className="m3-menu-item"
            role="menuitem"
            data-active={enPerfil ? "true" : "false"}
            onClick={() => { setMenu(false); navigate("/perfil"); }}
          >
            <span>{t("tabbar.perfil")}</span>
            <span className="ch">›</span>
          </button>
        </div>
      )}
      <nav className="m3-tabbar m4" aria-label={t("tabbar.navAria")}>
        <button
          className="m3-tab"
          data-active={pathname === "/" ? "true" : "false"}
          onClick={() => { setMenu(false); navigate("/"); }}
        >
          <span className="ic"><IcLib /></span>
          <span className="lbl">{t("tabbar.inicio")}</span>
        </button>
        <button
          className="m3-tab"
          data-active={menu || enPerfil ? "true" : "false"}
          aria-haspopup="menu"
          aria-expanded={menu ? "true" : "false"}
          onClick={() => setMenu((v) => !v)}
        >
          <span className="ic"><IcMas /></span>
          <span className="lbl">{t("tabbar.mas")}</span>
        </button>
      </nav>
    </>
  );
}
