import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

export default function NuevoPlaceholder() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <main className="k-page">
      <header className="k-topline">
        <button type="button" className="k-btn k-btn--text" onClick={() => navigate("/")}>
          ← {t("biblioteca.titulo")}
        </button>
        <span className="k-topline__meta">{t("nuevo.kicker")}</span>
      </header>
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{t("nuevo.prontoTitulo")}</h1>
        <p className="k-hero__dek">{t("nuevo.prontoDek")}</p>
      </header>
    </main>
  );
}
