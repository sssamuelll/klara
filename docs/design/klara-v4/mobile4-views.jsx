/* global React, M2_TODAY, KLARA_TEMAS */
const { useState } = React;

/* ---------- marca e iconos ---------- */
function KM({ size = 16, speaking = false }) {
  return <span className="klara-mark" data-speaking={speaking ? "true" : "false"} style={{ fontSize: size }}><span className="glyph">K</span></span>;
}
function IcPlay({ s = 22 }) { return <svg width={s} height={s} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8.5 5.8v12.4l10-6.2z"></path></svg>; }
function IcPause({ s = 22 }) { return <svg width={s} height={s} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="7" y="6" width="3.4" height="12"></rect><rect x="13.6" y="6" width="3.4" height="12"></rect></svg>; }
function IcMic({ s = 20 }) {
  return <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true"><rect x="9.2" y="3.5" width="5.6" height="10" rx="2.8" fill="currentColor" stroke="none"></rect><path d="M6.2 11.5a5.8 5.8 0 0 0 11.6 0M12 17.5v3"></path></svg>;
}
function IcLib() { return <svg width="20" height="18" viewBox="0 0 20 18" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M3.5 2.5v13M8 2.5v13"></path><path d="M11.5 3l3.4 12.4" strokeLinecap="round"></path></svg>; }
function IcMas() { return <svg width="20" height="18" viewBox="0 0 20 18" fill="currentColor" aria-hidden="true"><circle cx="4" cy="9" r="1.7"></circle><circle cx="10" cy="9" r="1.7"></circle><circle cx="16" cy="9" r="1.7"></circle></svg>; }

/* ---------- chrome ---------- */
function TopLine({ right }) {
  return (
    <div className="m3-top">
      <span className="marca"><KM size={14} /><span className="wordmark">Klara</span></span>
      <span>{right}</span>
    </div>
  );
}
function TabBar({ route, go }) {
  const [menu, setMenu] = useState(false);
  const items = [{ id: "perfil", lbl: "Perfil" }, { id: "suscripcion", lbl: "Suscripción" }];
  return (
    <React.Fragment>
      {menu && <div className="m3-scrim" onClick={() => setMenu(false)}></div>}
      {menu && (
        <div className="m3-menu" role="menu" aria-label="Más opciones">
          {items.map((it) => (
            <button key={it.id} className="m3-menu-item" role="menuitem" data-active={route === it.id ? "true" : "false"} onClick={() => { setMenu(false); go(it.id); }}>
              <span>{it.lbl}</span><span className="ch">›</span>
            </button>
          ))}
        </div>
      )}
      <nav className="m3-tabbar m4" aria-label="Navegación">
        <button className="m3-tab" data-active={route === "inicio" ? "true" : "false"} onClick={() => { setMenu(false); go("inicio"); }}>
          <span className="ic"><IcLib /></span><span className="lbl">Inicio</span>
        </button>
        <button className="m3-tab" data-active={menu || route === "perfil" || route === "suscripcion" ? "true" : "false"} aria-haspopup="menu" aria-expanded={menu ? "true" : "false"} onClick={() => setMenu(!menu)}>
          <span className="ic"><IcMas /></span><span className="lbl">Más</span>
        </button>
      </nav>
    </React.Fragment>
  );
}

/* ---------- INICIO: la biblioteca ---------- */
function Inicio({ lista, go }) {
  const al = KLARA_TEMAS.aleman;
  const paso = al.pasos.find((p) => p.e === "ahora");
  return (
    <main className="m3-page">
      <TopLine right={`${M2_TODAY.fecha.split(" ").slice(0, 2).join(" ")} · ${M2_TODAY.numero}`} />
      <h1 className="m4-saludo">{M2_TODAY.saludo} <em>{M2_TODAY.nombre}</em>.</h1>
      <div className="m4-sec">Tu biblioteca</div>
      <div className="m4-lib">
        {lista.map((id) => {
          const c = KLARA_TEMAS[id];
          return (
            <button key={id} className="m4-tema" onClick={() => go("curso", id)}>
              <span className="f1"><span className="tit">{c.titulo}</span><span className="estado" data-hot={c.estado.includes("●") ? "true" : "false"}>{c.estado}</span></span>
              <span className="sub">{c.sub}</span>
              <span className="m4-bar"><i style={{ width: `${c.progreso * 100}%` }}></i></span>
            </button>
          );
        })}
        <button className="m4-add" onClick={() => go("nuevo")}>
          <span className="tile">+</span>
          <span><span className="tit">Nuevo tema</span><span className="sub">Un tema o tus apuntes — Klara arma el plan</span></span>
        </button>
      </div>
      <button className="m3-hero" style={{ marginTop: "auto" }} onClick={() => go(paso.ruta, "aleman")}>
        <span className="tag"><span>Continuar · {al.titulo}</span><span>{paso.meta}</span></span>
        <span className="fila">
          <span><h2>{paso.t}</h2><p className="dek">{paso.dek}</p></span>
          <span className="arrow">→</span>
        </span>
      </button>
    </main>
  );
}

/* ---------- PORTADA de curso ---------- */
function Portada({ curso, go }) {
  const paso = curso.pasos.find((p) => p.e === "ahora") || curso.pasos[0];
  return (
    <main className="m3-page">
      <div className="m4-backrow">
        <button className="m3-back" onClick={() => go("inicio")}>← Biblioteca</button>
        <span className="der">{curso.sub}</span>
      </div>
      <h1 className="m4-h1">{curso.titulo}</h1>
      <div className="m4-bar"><i style={{ width: `${curso.progreso * 100}%` }}></i></div>
      <div className="m4-sec">El plan de hoy · 4 pasos</div>
      <ol className="m3-plan" style={{ margin: 0 }}>
        {curso.pasos.map((p) => (
          <li key={p.n} data-e={p.e} onClick={() => go(p.ruta)}>
            <span className="n">{p.n}</span>
            <span className="tit">{p.t}</span>
            <span className="estado">{p.e === "hecha" ? "✓" : p.e === "ahora" ? "● ahora" : p.meta}</span>
          </li>
        ))}
      </ol>
      <ul className="m3-rows">
        <li onClick={() => go("mapa")} style={{ cursor: "pointer" }}><span className="n">→</span><span className="tit">El mapa del curso</span><span className="estado">Dónde vas ›</span></li>
        <li onClick={() => go("repaso")} style={{ cursor: "pointer" }}><span className="n">→</span><span className="tit">Repaso</span><span className="estado" style={{ color: "var(--accent)" }}>{curso.vencen} hoy ›</span></li>
      </ul>
      <button className="m3-hero" style={{ marginTop: "auto" }} onClick={() => go(paso.ruta)}>
        <span className="tag"><span>Ahora · {paso.n} de 04</span><span>{paso.meta}</span></span>
        <span className="fila">
          <span><h2>{paso.t}</h2><p className="dek">{paso.dek}</p></span>
          <span className="arrow">→</span>
        </span>
      </button>
    </main>
  );
}

/* ---------- MAPA genérico ---------- */
function MapaCurso({ curso, go }) {
  const M = curso.mapa;
  const x = M.x * 100;
  const n = M.stops.length;
  return (
    <main className="m3-page">
      <div className="m4-backrow">
        <button className="m3-back" onClick={() => go("curso")}>← {curso.titulo}</button>
        <span className="der">El mapa</span>
      </div>
      <h1 className="m4-h1">{M.h1[0]}<em>{M.h1[1]}</em>{M.h1[2]}</h1>
      <p className="m3-mapa-frase">{M.frase}</p>
      <div className="m3-cefr" role="img" aria-label={`Progreso: ${Math.round(x)}%`}>
        <span className="aqui" style={{ left: `${x}%` }}>Estás aquí</span>
        <div className="track"><div className="fill" style={{ width: `${x}%` }}></div><span className="dot" style={{ left: `${x}%` }}></span></div>
        {M.stops.map((l, i) => { const p = (i / (n - 1)) * 100; return <span key={l} className="stop" data-past={p <= x ? "true" : "false"} style={{ left: `${p}%` }}>{l}</span>; })}
      </div>
      <ul className="m3-rows">
        {M.rows.map((r) => <li key={r.n} data-e={r.e}><span className="n">{r.n}</span><span className="tit">{r.tit}</span><span className="estado">{r.estado}</span></li>)}
      </ul>
      <button className="m3-hero" style={{ marginTop: "auto" }} onClick={() => go("estudiar")}>
        <span className="tag"><span>Seguir donde vas</span><span>{curso.sub}</span></span>
        <span className="fila"><span><h2>{curso.sesTitulo}</h2></span><span className="arrow">→</span></span>
      </button>
    </main>
  );
}

/* ---------- PERFIL / SUSCRIPCIÓN ---------- */
function Perfil({ go }) {
  return (
    <main className="m3-page">
      <TopLine right="Perfil" />
      <h1 className="m4-h1" style={{ marginTop: 14 }}>{M2_TODAY.nombre} <em>Ruiz</em></h1>
      <p className="m3-mapa-frase">Tres temas en curso · desde enero de 2026</p>
      <ul className="m3-rows">
        <li><span className="n">01</span><span className="tit">Racha</span><span className="estado">21 días</span></li>
        <li><span className="n">02</span><span className="tit">Fichas en repaso</span><span className="estado">238</span></li>
        <li><span className="n">03</span><span className="tit">Tiempo con Klara</span><span className="estado">4 h 12 m</span></li>
        <li><span className="n">04</span><span className="tit">Recordatorio diario</span><span className="estado">08:30</span></li>
      </ul>
      <button className="m3-hero" style={{ marginTop: "auto" }} onClick={() => go("inicio")}>
        <span className="tag"><span>Hoy</span><span>Nº 128</span></span>
        <span className="fila">
          <span><h2>Volver a la biblioteca</h2><p className="dek">Te queda un paso sin hacer</p></span>
          <span className="arrow">→</span>
        </span>
      </button>
    </main>
  );
}
function Suscripcion() {
  return (
    <main className="m3-page">
      <TopLine right="Suscripción" />
      <h1 className="m4-h1" style={{ marginTop: 14 }}>Klara <em>anual</em></h1>
      <p className="m3-mapa-frase">Activa hasta el 12 de enero de 2027. Se renueva sola.</p>
      <ul className="m3-rows">
        <li><span className="n">01</span><span className="tit">Plan</span><span className="estado">Anual · 69 €</span></li>
        <li><span className="n">02</span><span className="tit">Próximo cobro</span><span className="estado">12 ene 2027</span></li>
        <li><span className="n">03</span><span className="tit">Método</span><span className="estado">•••• 4417</span></li>
        <li><span className="n">04</span><span className="tit">Temas y repaso</span><span className="estado">Sin límite</span></li>
      </ul>
      <button className="m3-hero" style={{ marginTop: "auto" }}>
        <span className="tag"><span>Gestionar</span><span>Cancela cuando quieras</span></span>
        <span className="fila">
          <span><h2>Cambiar de plan</h2><p className="dek">Mensual, anual o pausar unos meses</p></span>
          <span className="arrow">→</span>
        </span>
      </button>
    </main>
  );
}

Object.assign(window, { KM, IcPlay, IcPause, IcMic, IcLib, IcMas, TopLine, TabBar, Inicio, Portada, MapaCurso, Perfil, Suscripcion });
