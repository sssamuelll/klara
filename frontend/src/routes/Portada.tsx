import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useCourseData } from "../lib/useCourseData";
import { languageLabel } from "../lib/languages";
import { useUser } from "../lib/user";

export default function Portada() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const { vm } = useCourseData();
  const titulo = user ? languageLabel(user.target_language) : "…";
  const pct = Math.round(vm.progreso * 100);

  return (
    <main className="k-page">
      <header className="k-topline">
        <button type="button" className="k-btn k-btn--text" onClick={() => navigate("/biblioteca")}>← {t("biblioteca.titulo")}</button>
        <span className="k-topline__meta">{t("biblioteca.cursoSub", { level: user?.level ?? "" })}</span>
      </header>
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{titulo}</h1>
      </header>
      <div className="k-bar k-bar--fill">
        <div
          className="k-bar__track"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={t("mapa.progressAria", { pct })}
        >
          <i className="k-bar__fill" style={{ width: `${vm.progreso * 100}%` }} />
        </div>
      </div>
      <ul>
        <li>
          <button type="button" className="k-row" onClick={() => navigate("/curso/aleman/mapa")}>
            <span className="k-row__n">→</span>
            <span className="k-row__title">{t("curso.mapaFila")}</span>
            <span className="k-row__meta">{t("curso.mapaFilaEstado")}</span>
            <span className="k-row__arrow" aria-hidden="true">›</span>
          </button>
        </li>
        <li>
          <button type="button" className="k-row" onClick={() => navigate("/gender")}>
            <span className="k-row__n">→</span>
            <span className="k-row__title">{t("curso.generoFila")}</span>
            <span className="k-row__meta">{t("curso.generoFilaEstado")}</span>
            <span className="k-row__arrow" aria-hidden="true">›</span>
          </button>
        </li>
      </ul>
    </main>
  );
}
