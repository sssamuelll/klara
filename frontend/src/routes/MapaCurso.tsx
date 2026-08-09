import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { moduleRowEstado } from "../lib/courseView";
import { useCourseData } from "./Inicio";
import { languageLabel } from "../lib/languages";
import { useUser } from "../lib/user";

export default function MapaCurso() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const { vm } = useCourseData();
  const titulo = user ? languageLabel(user.target_language) : "…";
  const x = vm.progreso * 100;
  const stops = ["A0", "A1", "A2", "B1"]; // ponytail: escala fija del curso de; por-curso llega con F3

  return (
    <main className="m3-page">
      <div className="m4-backrow">
        <button className="m3-back" onClick={() => navigate("/curso/aleman")}>← {titulo}</button>
        <span className="der">{t("mapa.kicker")}</span>
      </div>
      <h1 className="m4-h1">
        {t("mapa.h1pre")} <em>{user?.level ?? ""}</em>.
      </h1>
      <div className="m3-cefr" role="img" aria-label={t("mapa.progressAria", { pct: Math.round(x) })}>
        <span className="aqui" style={{ left: `${x}%` }}>{t("mapa.aqui")}</span>
        <div className="track">
          <div className="fill" style={{ width: `${x}%` }} />
          <span className="dot" style={{ left: `${x}%` }} />
        </div>
        {stops.map((l, i) => {
          const p = (i / (stops.length - 1)) * 100;
          return (
            <span key={l} className="stop" data-past={p <= x ? "true" : "false"} style={{ left: `${p}%` }}>
              {l}
            </span>
          );
        })}
      </div>
      {/* ponytail: sin sort — GET /modules ya ordena por sequence_order asc. */}
      <ul className="m3-rows">
        {vm.modules?.map((m) => (
          <li key={m.id} data-e={moduleRowEstado(m)}>
            <button type="button" className="m3-rowbtn" onClick={() => navigate(`/module/${m.id}`)}>
              <span className="n">{String(m.sequence_order).padStart(2, "0")}</span>
              <span className="tit">{m.title}</span>
              <span className="estado">
                {m.completed
                  ? "✓"
                  : m.is_current
                  ? t("mapa.encurso", { done: m.stories_finished, total: m.stories_to_complete })
                  : m.unlocked
                  ? t("mapa.proximo")
                  : "—"}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
