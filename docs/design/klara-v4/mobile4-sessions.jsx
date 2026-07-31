/* global React, KM, IcPlay, IcPause, IcMic */
const { useState: useStateS, useEffect: useEffectS, useRef: useRefS } = React;

const pad2 = (n) => String(n).padStart(2, "0");
const artClass = (a) => (a === "der" || a === "die" || a === "das") ? `m3-art-${a}` : "";

function SessTop({ titulo, right, onExit }) {
  return (
    <div className="m3-sess-top">
      <button className="m3-back" onClick={onExit}>← Salir</button>
      <span className="titulo">{titulo}</span>
      <span className="der">{right}</span>
    </div>
  );
}

/* ---------- ESTUDIAR: teleprompter genérico ---------- */
function Estudiar({ curso, go }) {
  const chunks = curso.chunks;
  const total = chunks.length;
  const [cur, setCur] = useStateS(0);
  const [playing, setPlaying] = useStateS(false);
  const [rec, setRec] = useStateS(false);
  const [fb, setFb] = useStateS(false);
  const [sheet, setSheet] = useStateS(null);
  const [enRepaso, setEnRepaso] = useStateS(false);
  const recTimer = useRefS(null);
  useEffectS(() => () => clearTimeout(recTimer.current), []);

  const s = chunks[cur];
  const words = s.tokens.filter((t) => t.type === "word");
  const warn = words.length ? words.reduce((a, b) => (b.text.length > a.text.length ? b : a)) : null;
  const next = () => { if (cur === total - 1) { go("curso"); return; } setCur(cur + 1); setFb(false); setRec(false); setPlaying(false); };
  const prev = () => { setCur(Math.max(0, cur - 1)); setFb(false); setRec(false); setPlaying(false); };
  const onMic = () => {
    if (rec) { clearTimeout(recTimer.current); setRec(false); return; }
    setPlaying(false); setRec(true);
    recTimer.current = setTimeout(() => { setRec(false); setFb(true); }, 1700);
  };

  return (
    <React.Fragment>
      <SessTop titulo={curso.sesTitulo} right={`${pad2(cur + 1)}/${pad2(total)}`} onExit={() => go("curso")} />
      <div className="m3-prog"><div className="segs">{chunks.map((_, i) => <span key={i} className="seg" data-done={i <= cur ? "true" : "false"}></span>)}</div></div>
      <div className="m3-lect">
        <p className="m3-oracion" key={cur}>
          {s.tokens.map((t, j) => t.type === "word"
            ? <span key={j} className="m3-w" onClick={() => { setSheet(t.word); setEnRepaso(false); }}>{t.text}</span>
            : <span key={j}>{t.text}</span>)}
        </p>
        <p className="m3-gloss" key={`g${cur}`}>{s.gloss}</p>
      </div>
      {!fb && (
        <div className="m3-dock">
          <div className="estadoK">
            {playing && <React.Fragment><KM size={13} speaking={true} /> K lee · despacio</React.Fragment>}
            {rec && <span style={{ color: "var(--accent)" }}>● Te escucho…</span>}
          </div>
          <div className="fila">
            <button className="m3-rbtn step" aria-label="Anterior" disabled={cur === 0} onClick={prev}>←</button>
            <button className="m3-rbtn play" aria-label={playing ? "Pausar" : "Escuchar"} onClick={() => { setPlaying(!playing); setRec(false); }}>{playing ? <IcPause s={24} /> : <IcPlay s={24} />}</button>
            {curso.conMic && <button className="m3-rbtn mic" data-on={rec ? "true" : "false"} aria-label="Decirlo en voz alta" onClick={onMic}><IcMic /></button>}
            <button className="m3-rbtn step" aria-label="Siguiente" onClick={next}>→</button>
          </div>
        </div>
      )}
      {fb && curso.fb && (
        <div className="m3-fb">
          <p className="nota">{curso.fb.pre}<em>{warn ? warn.text : ""}</em>{curso.fb.post}</p>
          <div className="acciones">
            <button className="k-btn k-btn--ghost" onClick={() => setFb(false)}>Otra vez</button>
            <button className="k-btn" onClick={next}>Continuar <span className="arrow">→</span></button>
          </div>
        </div>
      )}
      {sheet && (
        <React.Fragment>
          <div className="m3-scrim" onClick={() => setSheet(null)}></div>
          <div className="m3-sheet" role="dialog" aria-label={sheet.lemma}>
            <div className="grab"></div>
            <div className="fila1">
              <span className="lemma">{sheet.article && <span className={`art ${artClass(sheet.article)}`}>{sheet.article} </span>}{sheet.lemma}</span>
              <button className="m3-rbtn play" style={{ width: 46, height: 46 }} aria-label="Escuchar"><IcPlay s={18} /></button>
            </div>
            <p className="trad">{sheet.translation}</p>
            {sheet.example && <div className="ej" style={{ borderLeft: "1px solid var(--rule)", paddingLeft: 14, marginBottom: 16 }}><div style={{ fontFamily: "var(--font-serif)", fontSize: 15, lineHeight: 1.45 }}>{sheet.example.de}</div><div className="k-mono" style={{ fontSize: 10, marginTop: 3 }}>{sheet.example.es}</div></div>}
            <button className={enRepaso ? "k-btn" : "k-btn k-btn--ghost"} onClick={() => setEnRepaso(!enRepaso)}>{enRepaso ? "✓ En repaso" : "+ Añadir al repaso"}</button>
          </div>
        </React.Fragment>
      )}
    </React.Fragment>
  );
}

/* ---------- EXPLICAR: examen oral / Feynman / simulación ---------- */
function Explicar({ curso, go }) {
  const [oyendo, setOyendo] = useStateS(false);
  const E = curso.explicar;
  return (
    <React.Fragment>
      <SessTop titulo={curso.titulo} right={curso.pasos[2].meta} onExit={() => go("curso")} />
      <div className="m3-carta">
        <div className="m3-turno">
          <div className="quien"><KM size={14} speaking={true} /> Klara <span className="m4-modo">· {E.modo}</span></div>
          <p className="de">{E.texto}</p>
          <p className="es">{E.gloss}</p>
        </div>
        {E.corr && (
          <div className="m3-corr">
            <div className="linea"><span className="mal">{E.corr.mal}</span><span>→</span><span className="bien">{E.corr.bien}</span></div>
            <p className="nota">{E.corr.nota}</p>
          </div>
        )}
      </div>
      <div className="m3-dock hablar">
        <button className="m3-lado">{E.ayuda}</button>
        <div>
          <button className="m3-rbtn micgrande" data-on={oyendo ? "true" : "false"} aria-label="Hablar" onClick={() => setOyendo(!oyendo)}><IcMic s={26} /></button>
          <div className="miclbl" style={oyendo ? { color: "var(--accent)" } : null}>{oyendo ? "Te escucho…" : "Mantén pulsado para hablar"}</div>
        </div>
        <button className="m3-lado fin" onClick={() => go("curso")}>Terminar</button>
      </div>
    </React.Fragment>
  );
}

/* ---------- REPASO: fichas del curso ---------- */
function Repaso({ curso, go }) {
  const [idx, setIdx] = useStateS(0);
  const [pos, setPos] = useStateS(1);
  const [dorso, setDorso] = useStateS(false);
  const total = curso.vencen;
  const f = curso.fichas[idx % curso.fichas.length];
  const responder = () => { if (pos >= total) { go("curso"); return; } setIdx(idx + 1); setPos(pos + 1); setDorso(false); };
  return (
    <React.Fragment>
      <SessTop titulo={`Repaso · ${curso.titulo}`} right={`${pad2(pos)}/${pad2(total)}`} onExit={() => go("curso")} />
      <div className="m3-prog"><div className="segs"><span className="seg" data-done="true" style={{ flex: pos }}></span><span className="seg" style={{ flex: Math.max(total - pos, 0.001) }}></span></div></div>
      <main className="m3-page" style={{ paddingTop: 4 }}>
        <div className="m3-rep" style={{ padding: 0 }}>
          <div className="m3-ficha" onClick={() => setDorso(!dorso)}>
            {!dorso ? (
              <React.Fragment>
                <div className="centro">
                  {f.article && <span className={`art ${artClass(f.article)}`}>{f.article}</span>}
                  <span className="palabra">{f.w}</span>
                  <button className="m3-rbtn play" style={{ width: 44, height: 44, marginTop: 10 }} aria-label="Escuchar" onClick={(e) => e.stopPropagation()}><IcPlay s={17} /></button>
                </div>
                <div className="hint">Toca para girar</div>
              </React.Fragment>
            ) : (
              <div className="centro">
                <span className="posw">{f.article ? `${f.article} ${f.w}` : f.w} · {f.pos}</span>
                <span className="trad">{f.trad}</span>
                <div className="ej"><div className="de">{f.de}</div><div className="es">{f.es}</div></div>
              </div>
            )}
          </div>
          {dorso ? (
            <div className="m3-srs">
              <button onClick={responder}><span className="l">Otra vez</span><span className="d">1 día</span></button>
              <button className="bien" onClick={responder}><span className="l">Bien</span><span className="d">4 días</span></button>
              <button onClick={responder}><span className="l">Fácil</span><span className="d">9 días</span></button>
            </div>
          ) : (
            <div className="m3-srs" style={{ visibility: "hidden" }} aria-hidden="true">
              <button tabIndex={-1}><span className="l">·</span><span className="d">·</span></button>
            </div>
          )}
        </div>
      </main>
    </React.Fragment>
  );
}

Object.assign(window, { SessTop, Estudiar, Explicar, Repaso });
