import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useCourseData } from "./Inicio";
import { languageLabel } from "../lib/languages";
import { useUser } from "../lib/user";

export default function Portada() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const { vm } = useCourseData();
  const titulo = user ? languageLabel(user.target_language) : "…";

  return (
    <main className="m3-page">
      <div className="m4-backrow">
        <button className="m3-back" onClick={() => navigate("/")}>← {t("biblioteca.titulo")}</button>
        <span className="der">{t("biblioteca.cursoSub", { level: user?.level ?? "" })}</span>
      </div>
      <h1 className="m4-h1">{titulo}</h1>
      <div className="m4-bar"><i style={{ width: `${vm.progreso * 100}%` }} /></div>
      <div className="m4-sec">{t("curso.planTitulo")}</div>
      <ol className="m3-plan" style={{ margin: 0 }}>
        {vm.pasos.map((p) => (
          <li key={p.n} data-e={p.e} onClick={() => navigate(p.to)} style={{ cursor: "pointer" }}>
            <span className="n">{p.n}</span>
            <span className="tit">{t(`curso.paso.${p.id}.titulo`)}</span>
            {/* ponytail: en Repasar el estado dice cuántas vencen — la forma corta
                de biblioteca, que es la que entra en la columna. */}
            <span className="estado">
              {p.e === "ahora"
                ? t("curso.ahora")
                : p.id === "repasar" && vm.vencen != null && vm.vencen > 0
                ? t("biblioteca.estadoDue", { count: vm.vencen })
                : t(`curso.paso.${p.id}.meta`)}
            </span>
          </li>
        ))}
      </ol>
      <ul className="m3-rows">
        <li onClick={() => navigate("/curso/aleman/mapa")} style={{ cursor: "pointer" }}>
          <span className="n">→</span>
          <span className="tit">{t("curso.mapaFila")}</span>
          <span className="estado">{t("curso.mapaFilaEstado")} ›</span>
        </li>
        <li onClick={() => navigate("/gender")} style={{ cursor: "pointer" }}>
          <span className="n">→</span>
          <span className="tit">{t("curso.generoFila")}</span>
          <span className="estado">{t("curso.generoFilaEstado")} ›</span>
        </li>
      </ul>
    </main>
  );
}
