import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import KlaraMark from "../components/KlaraMark";
import { useMastheadDate } from "../lib/dateLabel";
import { languageLabel } from "../lib/languages";
import { useCourseData } from "../lib/useCourseData";
import { useUser } from "../lib/user";

export default function Biblioteca() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const { vm } = useCourseData();
  const fecha = useMastheadDate();
  const tema = user ? languageLabel(user.target_language) : "…";
  const pct = Math.round(vm.progreso * 100);
  const vencen = vm.vencen ?? 0;
  const estado = vencen > 0 ? t("biblioteca.estadoDue", { count: vencen }) : t("biblioteca.estadoHoy");

  return (
    <main className="k-page">
      <header className="k-topline">
        <span className="k-topline__mark">
          <KlaraMark size={14} />
          <span className="wordmark">Klara</span>
        </span>
        <span className="k-topline__meta">{fecha}</span>
      </header>
      <div className="k-live">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">{t("biblioteca.titulo")}</h1>
        </header>
        <h2 className="k-cap k-cap--rule">{t("biblioteca.temas")}</h2>
        <ul className="k-shelf">
          <li>
            <button type="button" className="k-cover" onClick={() => navigate("/curso/aleman")}>
              <span className="k-cover__band">{tema}</span>
              <span className="k-cover__sub">{t("biblioteca.edicion")}</span>
            </button>
            <div className="k-bar k-bar--fill">
              <div
                className="k-bar__track"
                role="progressbar"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={t("mapa.progressAria", { pct })}
              >
                <i className="k-bar__fill" style={{ width: `${pct}%` }} />
              </div>
            </div>
            <span className="k-shelf__caption" data-accent={vencen > 0 ? "true" : undefined}>
              {user?.level ?? ""} · {estado}
            </span>
          </li>
          <li>
            <button type="button" className="k-cover k-cover--new" onClick={() => navigate("/nuevo")}>
              <span className="k-cover__plus" aria-hidden="true">+</span>
              <span className="k-cover__name">{t("biblioteca.nuevoTitulo")}</span>
            </button>
            <span className="k-shelf__caption">{t("biblioteca.nuevoPie")}</span>
          </li>
        </ul>
      </div>
    </main>
  );
}
