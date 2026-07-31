/* global React, KM */
const { useState: useStateN, useEffect: useEffectN } = React;

const EJEMPLOS = ["Entrevista con la CEO de una startup berlinesa, en inglés", "Three.js para mi portfolio", "Anatomía del hombro"];

/* ---------- NUEVO TEMA: tema escrito o apuntes ---------- */
function NuevoTema({ go }) {
  const [txt, setTxt] = useStateN("");
  return (
    <main className="m3-page">
      <div className="m4-backrow">
        <button className="m3-back" onClick={() => go("inicio")}>← Biblioteca</button>
        <span className="der">Nuevo tema</span>
      </div>
      <h1 className="m4-h1" style={{ marginTop: 14 }}>¿Qué quieres <em>aprender</em>?</h1>
      <textarea className="m4-input" placeholder="Un tema, una meta, una fecha…" value={txt} onChange={(e) => setTxt(e.target.value)} aria-label="Tu tema"></textarea>
      <div className="m4-chips">
        {EJEMPLOS.map((e) => <button key={e} className="k-chip" data-selected={txt === e ? "true" : "false"} onClick={() => setTxt(e)}>{e}</button>)}
      </div>
      <div className="m4-o">o</div>
      <button className="m4-upload">
        <span className="tile" style={{ flex: "0 0 30px", height: 30, border: "1px dashed var(--ink-4)", borderRadius: "var(--r-xs)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--font-serif)", fontStyle: "italic" }}>↑</span>
        <span><span className="tit">Sube tus apuntes</span><span className="sub">PDF, notas, capturas — Klara los lee</span></span>
      </button>
      <button className="m3-hero" style={{ marginTop: "auto" }} disabled={!txt.trim()} onClick={() => go("plan")}>
        <span className="tag"><span>Klara lee y propone</span><span>~10 seg</span></span>
        <span className="fila"><span><h2>Crear mi plan</h2></span><span className="arrow">→</span></span>
      </button>
    </main>
  );
}

/* ---------- PLAN PROPUESTO ---------- */
function PlanPropuesto({ go, onStart }) {
  const [listo, setListo] = useStateN(false);
  useEffectN(() => { const t = setTimeout(() => setListo(true), 1600); return () => clearTimeout(t); }, []);
  const C = window.KLARA_TEMAS.entrevista;
  if (!listo) {
    return (
      <main className="m3-page">
        <div className="m4-pensando">
          <KM size={34} speaking={true} />
          <span className="txt">Klara está leyendo tu tema…</span>
        </div>
      </main>
    );
  }
  return (
    <main className="m3-page">
      <div className="m4-backrow">
        <button className="m3-back" onClick={() => go("nuevo")}>← Editar tema</button>
        <span className="der">Klara propone</span>
      </div>
      <h1 className="m4-h1" style={{ marginTop: 14 }}>{C.titulo}.</h1>
      <p className="m3-mapa-frase">{C.mapa.frase}</p>
      <ul className="m3-rows">
        {C.mapa.rows.map((r) => <li key={r.n} data-e={r.e}><span className="n">{r.n}</span><span className="tit">{r.tit}</span><span className="estado">{r.n === "D1" ? "Hoy" : r.estado === "—" ? "" : r.estado}</span></li>)}
      </ul>
      <div className="m4-sec">Cada día, 4 pasos</div>
      <p className="k-mono" style={{ fontSize: 10, margin: "6px 0 0" }}>{C.pasos.map((p) => p.t).join(" · ")} · ~16 min</p>
      <button className="m3-hero" style={{ marginTop: "auto" }} onClick={onStart}>
        <span className="tag"><span>Día 1 · listo</span><span>4 min</span></span>
        <span className="fila">
          <span><h2>Empezar ahora</h2><p className="dek">{C.pasos[0].dek}</p></span>
          <span className="arrow">→</span>
        </span>
      </button>
    </main>
  );
}

Object.assign(window, { NuevoTema, PlanPropuesto });
