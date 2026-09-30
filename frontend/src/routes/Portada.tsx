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
        <button type="button" className="k-btn k-btn--text" onClick={() => navigate("/")}>← {t("biblioteca.titulo")}</button>
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
      <h2 className="k-cap k-cap--rule">{t("curso.planTitulo")}</h2>
      <ul>
        {vm.pasos.map((p) => (
          <li key={p.n}>
            <button
              type="button"
              className="k-row"
              data-state={p.e === "ahora" ? "now" : "pending"}
              onClick={() => navigate(p.to)}
            >
              <span className="k-row__n">{p.n}</span>
              <span className="k-row__title">{t(`curso.paso.${p.id}.titulo`)}</span>
              {/* ponytail: en Repasar el estado dice cuántas vencen — la forma corta
                  de biblioteca, que es la que entra en la columna. */}
              <span className="k-row__meta">
                {p.e === "ahora"
                  ? t("curso.ahora")
                  : p.id === "repasar" && vm.vencen != null && vm.vencen > 0
                  ? t("biblioteca.estadoDue", { count: vm.vencen })
                  : t(`curso.paso.${p.id}.meta`)}
              </span>
            </button>
          </li>
        ))}
        {/* ponytail: una sola lista — la fila extra necesita su filete superior, y
            con dos <ul> el `li:first-child > .k-row` del sistema se lo comía. */}
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
