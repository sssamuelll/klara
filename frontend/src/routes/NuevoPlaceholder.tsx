import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

export default function NuevoPlaceholder() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  return (
    <main className="m3-page">
      <div className="m4-backrow">
        <button className="m3-back" onClick={() => navigate("/")}>← {t("biblioteca.titulo")}</button>
        <span className="der">{t("nuevo.kicker")}</span>
      </div>
      <h1 className="m4-h1" style={{ marginTop: 14 }}>{t("nuevo.prontoTitulo")}</h1>
      <p className="m3-mapa-frase">{t("nuevo.prontoDek")}</p>
    </main>
  );
}
