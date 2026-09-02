import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import KlaraMark from "../components/KlaraMark";
import { api } from "../api/client";
import type { LearnerProfileOut } from "../api/types";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/preferences";
import { useUser } from "../lib/user";

export default function Perfil() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const { logout } = useAuth();
  const [theme, setTheme] = useTheme();
  const [aprendizaje, setAprendizaje] = useState<LearnerProfileOut | null>(null);

  useEffect(() => {
    let vivo = true;
    api
      .getLearningProfile()
      .then((p) => vivo && setAprendizaje(p))
      .catch(() => undefined);
    return () => {
      vivo = false;
    };
  }, []);

  // Tres estados, y ninguno cuenta saltos: «Completo» se ata a las 8 preguntas
  // de consumo (el servidor las resuelve), no a 23/23.
  const fecha = aprendizaje
    ? new Date(aprendizaje.updated_at).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
      })
    : "";
  const estadoAprendizaje = !aprendizaje
    ? t("perfil.aprendizaje.fila.sinLlenar")
    : aprendizaje.stale || !aprendizaje.synthesis
      ? t("perfil.aprendizaje.fila.pendiente")
      : aprendizaje.status === "completo"
        ? t("perfil.aprendizaje.fila.completo", { fecha })
        : t("perfil.aprendizaje.fila.aMedias", { fecha });

  return (
    <main className="k-page">
      <header className="k-topline">
        <span className="k-topline__mark"><KlaraMark size={14} /><span className="wordmark">Klara</span></span>
        <span className="k-topline__meta">{t("perfil.kicker")}</span>
      </header>
      <header className="k-hero k-hero--quiet">
        <h1 className="k-hero__title">{user?.display_name ?? "…"}</h1>
        <p className="k-hero__dek">{t("perfil.sub", { level: user?.level ?? "" })}</p>
      </header>
      <ul>
        <li>
          <button type="button" className="k-row" onClick={() => navigate("/perfil/aprendizaje")}>
            <span className="k-row__n">01</span>
            <span className="k-row__title">{t("perfil.aprendizaje.fila.titulo")}</span>
            <span className="k-row__meta">{estadoAprendizaje}</span>
            <span className="k-row__arrow" aria-hidden="true">›</span>
          </button>
        </li>
        <li>
          <button
            type="button"
            className="k-row"
            role="switch"
            aria-checked={theme === "dark"}
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          >
            <span className="k-row__n">02</span>
            <span className="k-row__title">{t("perfil.tema")}</span>
            <span className="k-row__meta">{theme === "light" ? t("perfil.temaClaro") : t("perfil.temaOscuro")}</span>
          </button>
        </li>
        <li>
          <button type="button" className="k-row" onClick={() => navigate("/settings")}>
            <span className="k-row__n">03</span>
            <span className="k-row__title">{t("perfil.editar")}</span>
            <span className="k-row__arrow" aria-hidden="true">›</span>
          </button>
        </li>
        <li>
          <button
            type="button"
            className="k-row"
            onClick={async () => { await logout(); navigate("/login", { replace: true }); }}
          >
            <span className="k-row__n">04</span>
            <span className="k-row__title">{t("perfil.salir")}</span>
            <span className="k-row__arrow" aria-hidden="true">›</span>
          </button>
        </li>
      </ul>
      <p className="k-cap k-cap--center" style={{ marginTop: "auto" }}>{t("perfil.pie")}</p>
    </main>
  );
}
