import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { tabActiva } from "../lib/tabs";

function IcHoy() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <path d="M8 3.5v17" />
      <circle cx="8" cy="9" r="2.5" fill="currentColor" stroke="none" />
      <path d="M13 9h7M13 15h5" />
    </svg>
  );
}
function IcLib() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 4.5v14M10 4.5v14" />
      <path d="M13.8 5.6 18 18.4" />
      <path d="M3.5 20.5h17" />
    </svg>
  );
}
function IcMas() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <circle cx="5.5" cy="12" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="18.5" cy="12" r="1.25" fill="currentColor" stroke="none" />
    </svg>
  );
}

export default function TabBar() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [menu, setMenu] = useState(false);
  const activa = tabActiva(pathname);
  const enPerfil = activa === "mas";

  useEffect(() => {
    if (!menu) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenu(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menu]);

  return (
    <>
      {menu && <div className="k-scrim" data-role="cerrar" onClick={() => setMenu(false)} />}
      {menu && (
        <div className="k-tabs__menu" role="menu" aria-label={t("tabbar.moreAria")}>
          <button
            type="button"
            className="k-tabs__menu-item"
            role="menuitem"
            data-active={enPerfil ? "true" : "false"}
            aria-current={enPerfil ? "page" : undefined}
            onClick={() => { setMenu(false); navigate("/perfil"); }}
          >
            {t("tabbar.perfil")}
            <span className="k-tabs__menu-ch" aria-hidden="true">›</span>
          </button>
        </div>
      )}
      <nav className="k-tabs k-tabs--3" aria-label={t("tabbar.navAria")}>
        <button
          type="button"
          className="k-tabs__tab"
          data-active={activa === "hoy" ? "true" : "false"}
          aria-current={activa === "hoy" ? "page" : undefined}
          onClick={() => { setMenu(false); navigate("/"); }}
        >
          <span className="k-tabs__ic" aria-hidden="true"><IcHoy /></span>
          <span className="k-tabs__lbl">{t("tabbar.hoy")}</span>
        </button>
        <button
          type="button"
          className="k-tabs__tab"
          data-active={activa === "biblioteca" ? "true" : "false"}
          aria-current={activa === "biblioteca" ? "page" : undefined}
          onClick={() => { setMenu(false); navigate("/biblioteca"); }}
        >
          <span className="k-tabs__ic" aria-hidden="true"><IcLib /></span>
          <span className="k-tabs__lbl">{t("tabbar.biblioteca")}</span>
        </button>
        <button
          type="button"
          className="k-tabs__tab"
          data-active={menu || enPerfil ? "true" : "false"}
          aria-current={enPerfil ? "page" : undefined}
          aria-haspopup="menu"
          aria-expanded={menu ? "true" : "false"}
          onClick={() => setMenu((v) => !v)}
        >
          <span className="k-tabs__ic" aria-hidden="true"><IcMas /></span>
          <span className="k-tabs__lbl">{t("tabbar.mas")}</span>
        </button>
      </nav>
    </>
  );
}
