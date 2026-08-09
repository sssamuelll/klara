/* Flujo del Perfil de Aprendizaje (F1.5).
 *
 * Guardar y sintetizar son dos cosas distintas y la pantalla lo refleja: el
 * PUT devuelve el perfil guardado de una, y la síntesis llega después (el
 * servidor la regenera en background). Salir no cancela nada.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { LearnerProfileOut } from "../api/types";
import { OB_PREGUNTAS } from "./catalog";
import { acumular, iniciarReloj, type Reloj } from "./timings";
import { Entrada, Pregunta, Sintesis, type Answers, type Respuesta } from "./views";

type Pantalla = "entrada" | "pregunta" | "sintesis";

/** Cuántas veces se pregunta por la síntesis antes de rendirse. La fila de
 *  Perfil queda en «pendiente» si no llegó; se reintenta al próximo guardado. */
const ESPERAS = 6;
const ESPERA_MS = 1500;

export default function PerfilAprendizaje() {
  const navigate = useNavigate();
  const [pantalla, setPantalla] = useState<Pantalla>("entrada");
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<Answers>({});
  const [perfil, setPerfil] = useState<LearnerProfileOut | null>(null);
  const [pendiente, setPendiente] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const timings = useRef<Record<string, number>>({});
  const reloj = useRef<Reloj | null>(null);
  const version = useRef<number | null>(null);
  // Recién salido del onboarding se vuelve a la app; entrando desde Perfil a
  // corregir, se vuelve a Perfil. Se decide al montar, no al salir.
  const volverA = useRef("/");

  // Precarga: reabrir el cuestionario desde Perfil trae las respuestas puestas
  // y entra en la primera de consumo sin responder (ayuda, no penitencia).
  useEffect(() => {
    let vivo = true;
    api
      .getLearningProfile()
      .then((p) => {
        if (!vivo || !p) return;
        setPerfil(p);
        setAnswers(p.answers as Answers);
        timings.current = { ...p.timings };
        version.current = p.version;
        volverA.current = "/perfil";
      })
      .catch(() => undefined);
    return () => {
      vivo = false;
    };
  }, []);

  /* --- timings: arranca al renderizar la pregunta, para al salir de ella --- */
  useEffect(() => {
    if (pantalla !== "pregunta") {
      reloj.current = null;
      return;
    }
    reloj.current = iniciarReloj();
    const onVis = () => {
      if (document.hidden) reloj.current?.pausar();
      else reloj.current?.reanudar();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [pantalla, idx]);

  const cerrarReloj = useCallback(() => {
    const r = reloj.current;
    if (!r) return;
    timings.current = acumular(timings.current, OB_PREGUNTAS[idx].id, r.cerrar());
    reloj.current = null;
  }, [idx]);

  const set = (id: string, v: Respuesta | ((prev: Respuesta | undefined) => Respuesta)) =>
    setAnswers((a) => ({ ...a, [id]: typeof v === "function" ? v(a[id]) : v }));

  const guardar = useCallback(
    async (finales: Answers) => {
      setGuardando(true);
      setPendiente(true);
      setPantalla("sintesis");
      try {
        const saved = await api.putLearningProfile(
          { answers: finales, timings: timings.current },
          version.current ?? undefined
        );
        setPerfil(saved);
        version.current = saved.version;

        // La síntesis llega después: se consulta hasta que deje de estar stale.
        for (let i = 0; i < ESPERAS; i++) {
          await new Promise((r) => setTimeout(r, ESPERA_MS));
          const fresco = await api.getLearningProfile().catch(() => null);
          if (fresco && !fresco.stale && fresco.synthesis) {
            setPerfil(fresco);
            version.current = fresco.version;
            break;
          }
        }
      } catch {
        // Guardar falló de verdad (red, 409): la pantalla lo dice sin perder
        // las respuestas — siguen en memoria y «Corregir» vuelve al cuestionario.
        setPerfil(null);
      } finally {
        setPendiente(false);
        setGuardando(false);
      }
    },
    []
  );

  const avanzar = (saltar: boolean) => {
    cerrarReloj();
    const q = OB_PREGUNTAS[idx];
    const proximas: Answers = saltar ? { ...answers, [q.id]: null } : answers;
    if (saltar) setAnswers(proximas);
    if (idx + 1 < OB_PREGUNTAS.length) {
      setIdx(idx + 1);
      return;
    }
    void guardar(proximas);
  };

  const atras = () => {
    cerrarReloj();
    if (idx === 0) setPantalla("entrada");
    else setIdx(idx - 1);
  };

  if (pantalla === "entrada") {
    return (
      <Entrada
        primerArranque={perfil === null}
        onEmpezar={() => {
          setIdx(0);
          setPantalla("pregunta");
        }}
        onLuego={() => navigate(volverA.current, { replace: true })}
      />
    );
  }

  if (pantalla === "pregunta") {
    return (
      <Pregunta
        q={OB_PREGUNTAS[idx]}
        idx={idx}
        answers={answers}
        onSet={set}
        onNext={() => avanzar(false)}
        onSkip={() => avanzar(true)}
        onBack={atras}
        ultima={idx === OB_PREGUNTAS.length - 1}
      />
    );
  }

  return (
    <Sintesis
      prosa={perfil?.synthesis ?? null}
      facts={perfil?.facts ?? null}
      pendiente={pendiente || guardando}
      onListo={() => navigate(volverA.current, { replace: true })}
      onCorregir={() => {
        setIdx(0);
        setPantalla("pregunta");
      }}
    />
  );
}
