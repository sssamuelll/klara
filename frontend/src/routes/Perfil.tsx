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
    <main className="m3-page">
      <div className="m3-top">
        <span className="marca"><KlaraMark size={14} /><span className="wordmark">Klara</span></span>
        <span>{t("perfil.kicker")}</span>
      </div>
      <h1 className="m4-h1" style={{ marginTop: 14 }}>{user?.display_name ?? "…"}</h1>
      <p className="m3-mapa-frase">{t("perfil.sub", { level: user?.level ?? "" })}</p>
      <ul className="m3-rows">
        <li onClick={() => navigate("/perfil/aprendizaje")} style={{ cursor: "pointer" }}>
          <span className="n">01</span>
          <span className="tit">{t("perfil.aprendizaje.fila.titulo")}</span>
          <span className="estado">{estadoAprendizaje} ›</span>
        </li>
        <li onClick={() => setTheme(theme === "light" ? "dark" : "light")} style={{ cursor: "pointer" }}>
          <span className="n">02</span>
          <span className="tit">{t("perfil.tema")}</span>
          <span className="estado">{theme === "light" ? t("perfil.temaClaro") : t("perfil.temaOscuro")} ›</span>
        </li>
        <li onClick={() => navigate("/settings")} style={{ cursor: "pointer" }}>
          <span className="n">03</span>
          <span className="tit">{t("perfil.editar")}</span>
          <span className="estado">›</span>
        </li>
        <li
          onClick={async () => { await logout(); navigate("/login", { replace: true }); }}
          style={{ cursor: "pointer" }}
        >
          <span className="n">04</span>
          <span className="tit">{t("perfil.salir")}</span>
          <span className="estado">›</span>
        </li>
      </ul>
      <div className="m3-statline">{t("perfil.pie")}</div>
    </main>
  );
}
