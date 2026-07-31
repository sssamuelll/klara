/* global React, ReactDOM, KLARA_TEMAS, TabBar, Inicio, Portada, MapaCurso, Perfil, Suscripcion, NuevoTema, PlanPropuesto, Estudiar, Explicar, Repaso */
const { useState: useStateA, useEffect: useEffectA } = React;

const M4_QS = new URLSearchParams(location.search);
const M4_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "light",
  "fontScale": 1.0
}/*EDITMODE-END*/;

function AppV4() {
  const [tweaks, setTweak] = window.useTweaks(M4_DEFAULTS);
  const [route, setRoute] = useStateA(M4_QS.get("route") || "inicio");
  const [cid, setCid] = useStateA(M4_QS.get("curso") || "aleman");
  const [lista, setLista] = useStateA(["aleman", "threejs"]);

  useEffectA(() => {
    document.documentElement.setAttribute("data-theme", M4_QS.get("theme") || tweaks.theme);
  }, [tweaks.theme]);

  const go = (r, c) => { if (c) setCid(c); setRoute(r); };
  const crear = () => { setLista((l) => (l.includes("entrevista") ? l : ["entrevista", ...l])); go("curso", "entrevista"); };
  const curso = KLARA_TEMAS[cid];

  const { TweaksPanel, TweakSection, TweakRadio, TweakSlider } = window;
  const conTabs = ["inicio", "curso", "mapa", "perfil", "suscripcion"].includes(route);

  return (
    <div className="m3-app" style={{ "--fscale": tweaks.fontScale }}>
      {route === "inicio" && <Inicio lista={lista} go={go} />}
      {route === "nuevo" && <NuevoTema go={go} />}
      {route === "plan" && <PlanPropuesto go={go} onStart={crear} />}
      {route === "curso" && <Portada curso={curso} go={go} />}
      {route === "mapa" && <MapaCurso curso={curso} go={go} />}
      {route === "perfil" && <Perfil go={go} />}
      {route === "suscripcion" && <Suscripcion go={go} />}
      {route === "estudiar" && <Estudiar curso={curso} go={go} />}
      {route === "explicar" && <Explicar curso={curso} go={go} />}
      {route === "repaso" && <Repaso curso={curso} go={go} />}
      {conTabs && <TabBar route={route} go={go} />}
      <TweaksPanel title="Tweaks">
        <TweakSection label="Apariencia" />
        <TweakRadio label="Modo" value={tweaks.theme} options={["light", "dark"]} onChange={(v) => setTweak("theme", v)} />
        <TweakSlider label="Tamaño" value={tweaks.fontScale} min={0.85} max={1.3} step={0.05} onChange={(v) => setTweak("fontScale", v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<AppV4 />);
