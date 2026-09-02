import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { moduleRowEstado } from "../lib/courseView";
import { useCourseData } from "./Inicio";
import { languageLabel } from "../lib/languages";
import { useUser } from "../lib/user";

// ponytail: el data-e viejo traducido al enumerado del átomo 4; nada de lógica nueva.
const ESTADO = {
  dominado: "mastered",
  encurso: "now",
  proximo: "pending",
  futuro: "locked",
} as const;

export default function MapaCurso() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const { vm } = useCourseData();
  const titulo = user ? languageLabel(user.target_language) : "…";
  const x = vm.progreso * 100;
  const stops = ["A0", "A1", "A2", "B1"]; // ponytail: escala fija del curso de; por-curso llega con F3

  return (
    <main className="k-page">
      <header className="k-topline">
        <button type="button" className="k-btn k-btn--text" onClick={() => navigate("/curso/aleman")}>
          ← {titulo}
        </button>
        <span className="k-topline__meta">{t("mapa.kicker")}</span>
      </header>
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">
          {t("mapa.h1pre")} <em>{user?.level ?? ""}</em>.
        </h1>
      </header>
      {/* Cinta, punto e hitos son hermanos de la pista: dentro de role="progressbar" no se anuncian. */}
      <div className="k-bar k-bar--milestones">
        {/* La cinta va sobre el punto: mismo left en línea que el punto (contrato, tabla del átomo 5). */}
        <span className="k-cap" style={{ left: `${x}%` }}>
          {t("mapa.aqui")}
        </span>
        <div
          className="k-bar__track"
          role="progressbar"
          aria-label={t("mapa.progressAria", { pct: Math.round(x) })}
          aria-valuenow={Math.round(x)}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <i className="k-bar__fill" style={{ width: `${x}%` }} />
        </div>
        <span className="k-bar__dot" style={{ left: `${x}%` }} />
        {stops.map((l, i) => {
          const p = (i / (stops.length - 1)) * 100;
          return (
            <span key={l} className="k-bar__stop" data-past={p <= x ? "true" : "false"} style={{ left: `${p}%` }}>
              {l}
            </span>
          );
        })}
      </div>
      {/* ponytail: sin sort — GET /modules ya ordena por sequence_order asc. */}
      <ul>
        {vm.modules?.map((m) => {
          const estado = ESTADO[moduleRowEstado(m)];
          return (
            <li key={m.id}>
              <button
                type="button"
                className="k-row"
                data-state={estado}
                aria-disabled={estado === "locked" || undefined}
                onClick={() => navigate(`/module/${m.id}`)}
              >
                <span className="k-row__n">{String(m.sequence_order).padStart(2, "0")}</span>
                <span className="k-row__title">{m.title}</span>
                <span className="k-row__meta">
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
          );
        })}
      </ul>
    </main>
  );
}
