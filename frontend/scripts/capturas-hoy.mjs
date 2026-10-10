// Arnés visual de Hoy y Biblioteca (plan 2026-09-30, tarea 14; Hoy con una línea por idioma, plan 2026-10-09, tarea 19).
//
//   cd frontend && npm run build && PLAYWRIGHT_BROWSERS_PATH=D:/caches/ms-playwright node scripts/capturas-hoy.mjs
//
// Levanta `vite preview` sobre el dist que haya (no compila), simula la API y
// fotografía cada escenario en claro y oscuro, a 390×844, 390×667, 360×640 y 320×568. Escribe los
// PNG y un informe en .hoja-out/hoy/. Sale con 1 si algo desborda en horizontal,
// si hay controles de menos de 44px, si un nombre de idioma o un título no lleva su `lang` (o el texto
// de la interfaz sí), si el japonés no se dibuja con Noto Serif JP, si la línea al día tiene un botón
// o navega, si el toque en una línea no desbloquea el audio ANTES de abrir /sesion/:idioma, si Hoy no
// vuelve a pedir /today al volver a la app (o lo pide con la app oculta, o se vacía mientras refresca,
// o, si ese pedido falla, pone el banner de error sobre el plan que ya tenía), si una lista sin
// viñetas pierde su role="list", si una fuente no cargó o si la página lanza un error de JS. Sale con 2
// si falta el Playwright o el dist, o si el puerto 4175 ya está ocupado.
//
// Necesita PLAYWRIGHT_BROWSERS_PATH (aquí D:/caches/ms-playwright, con barras
// normales en Git Bash) y tarda unos 3 minutos: son 96 contextos nuevos, cada
// uno con la caché de fuentes fría.
//
// Usa el Playwright del arnés de design-sync (.ds-sync/, gitignored), como hoja.check.mjs.

import { spawn, execSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONT = resolve(HERE, "..");
const REPO = resolve(FRONT, "..");
const OUT = join(REPO, ".hoja-out", "hoy");
const PW = join(REPO, ".ds-sync/node_modules/playwright/index.mjs");
const PORT = 4175;
const BASE = `http://localhost:${PORT}`;

if (!existsSync(PW)) { console.error(`No está ${PW} (ver .design-sync/NOTES.md).`); process.exit(2); }
if (!existsSync(join(FRONT, "dist", "index.html"))) { console.error("No hay dist/: corre `npm run build`."); process.exit(2); }
const { chromium } = await import(pathToFileURL(PW).href);
mkdirSync(OUT, { recursive: true });

const user = { id: "u1", email: "samuel@example.com", is_superuser: false, display_name: "Samuel", level: "A2",
  native_language: "es", target_language: "de", learning_context: null, auth_methods: ["password"], needs_onboarding: false,
  study_languages: ["ja", "de", "en"] };
const modules = Array.from({ length: 8 }, (_, i) => ({ id: `m${i}`, sequence_order: i + 1, title: `Módulo ${i + 1}`,
  cefr_level: "A2", can_dos: [], grammatical_focus: [], encountered: 10, mastered: i < 2 ? 10 : 3, total: 10,
  gender_encountered: 0, gender_mastered: 0, gender_total: 0, stories_finished: i < 2 ? 3 : 1,
  stories_to_complete: 3, completed: i < 2, is_current: i === 2, unlocked: i <= 3, library_available: 2 }));
const due = Array.from({ length: 12 }, (_, i) => ({ id: `c${i}` }));

// Las líneas de GET /today (spec 2026-10-09 §5.1). `alDia`: el mapa terminado y ningún repaso; el servidor
// la marca `ahora`, con 0 minutos.
const linea = (over = {}) => ({ idioma: "ja", estado: "ahora", minutos: 18, repasos: 6,
  leccion: { id: "ja/hiragana/ka", titulo: "か き く け こ", bajada: "la fila de か: leerla, oírla y escribirla" },
  hecho: null, ...over });
const alDia = (over = {}) => linea({ leccion: null, repasos: 0, minutos: 0, ...over });
const aleman = (over = {}) => linea({ idioma: "de", minutos: 17, repasos: 14,
  leccion: { id: "de/cafe", titulo: "der Kaffee, die Tasse", bajada: "lo que pides en un café, cada cosa con su artículo" }, ...over });
const ingles = (over = {}) => linea({ idioma: "en", minutos: 15, repasos: 9,
  leccion: { id: "en/ship", titulo: "ship or sheep", bajada: "la /ɪ/ corta y la /iː/ larga" }, ...over });
const HECHA_JA = { estado: "hecha", hecho: { repasos: 6, leccion: "か き く け こ" } };
const HECHA_DE = { estado: "hecha", hecho: { repasos: 14, leccion: "der Kaffee, die Tasse" } };
const HECHA_EN = { estado: "hecha", hecho: { repasos: 9, leccion: "ship or sheep" } };
const LARGO = "Die Bundesausbildungsförderungsgesetzberatungsstelle am Samstag";

// El botón del héroe y no `.k-hero` a secas: el primero de esos en el DOM es el saludo
// (<header class="k-hero k-hero--quiet">).
const HEROE = "button.k-hero";
const PARADA = (n) => `.k-route__stop:nth-child(${n})`;

// `espera`: el selector que dice que los datos ya llegaron y la pantalla pintó lo que se
// fotografía. Nunca `.k-route`: el recorrido se pinta también mientras carga y cuando falla,
// y las medidas pasarían en vacío.
// `lang`: selector → el `lang` que tiene que llevar (texto en el idioma de estudio). `nativo`: lo que no
// lleva ninguno (texto de la interfaz, que hereda el idioma de la página). `noto`: lo que tiene que dibujarse
// con Noto Serif JP (el kana y el kanji; sin eso `lang="ja"` solo etiqueta, y el navegador pone la fuente
// del sistema). `sinBoton`: la parada que no abre nada.
const ESCENARIOS = {
  "entrar": { ruta: "/", espera: HEROE, lineas: [linea(), aleman({ estado: "pendiente" }), ingles({ estado: "pendiente" })],
    lang: { [`${HEROE} .k-hero__tag [lang]`]: "ja", [`${HEROE} .k-hero__title`]: "ja", [`${HEROE} .k-hero__dek [lang]`]: "ja",
      [`${PARADA(2)} .k-route__title`]: "de", [`${PARADA(3)} .k-route__title`]: "en" },
    nativo: [".k-hero--quiet .k-hero__title", `${HEROE} .k-hero__tag > span:last-child`],
    noto: [`${HEROE} .k-hero__tag [lang]`, `${HEROE} .k-hero__title`, `${HEROE} .k-hero__dek [lang]`] },
  "despues-del-japones": { ruta: "/", espera: HEROE, lineas: [linea(HECHA_JA), aleman(), ingles({ estado: "pendiente" })],
    lang: { [`${PARADA(1)} .k-route__title`]: "ja", [`${PARADA(1)} .k-route__sub [lang]`]: "ja", [`${HEROE} .k-hero__title`]: "de", [`${HEROE} .k-hero__tag [lang]`]: "de" },
    noto: [`${PARADA(1)} .k-route__title`, `${PARADA(1)} .k-route__sub [lang]`] },
  "una-linea": { ruta: "/", espera: HEROE, lineas: [linea()],
    lang: { [`${HEROE} .k-hero__title`]: "ja" }, noto: [`${HEROE} .k-hero__title`] },
  // Sin línea actual no hay héroe: lo que prueba que llegó `/today` es la primera parada hecha.
  "todo-hecho": { ruta: "/", espera: '.k-route__stop[data-state="done"]', lineas: [linea(HECHA_JA), aleman(HECHA_DE), ingles(HECHA_EN)],
    lang: { [`${PARADA(1)} .k-route__title`]: "ja" } },
  // La línea al día no abre nada: ni botón ni navegación, y la actual pasa a la siguiente con algo por hacer.
  "al-dia-antes": { ruta: "/", espera: HEROE, lineas: [alDia(), aleman({ estado: "pendiente" }), ingles({ estado: "pendiente" })],
    sinBoton: PARADA(1), lang: { [`${PARADA(1)} .k-route__title`]: "ja", [`${HEROE} .k-hero__title`]: "de" }, noto: [`${PARADA(1)} .k-route__title`] },
  "todas-al-dia": { ruta: "/", espera: '.k-route__stop[data-state="done"]', lineas: [alDia(), alDia({ idioma: "de", estado: "pendiente" })],
    sinBoton: PARADA(1) },
  "solo-repasos": { ruta: "/", espera: HEROE, lineas: [linea({ leccion: null, repasos: 12, minutos: 8 })],
    nativo: [`${HEROE} .k-hero__title`] },
  "titulo-largo": { ruta: "/", espera: HEROE, lineas: [aleman({ leccion: { id: "de/largo", titulo: LARGO, bajada: LARGO } }), linea({ estado: "pendiente" })],
    lang: { [`${HEROE} .k-hero__title`]: "de" } },
  "sin-idiomas": { ruta: "/", espera: ".k-note", lineas: [] },
  "biblioteca": { ruta: "/biblioteca", espera: ".k-shelf", lang: { ".k-cover__band": "de" }, lineas: null },
  "portada": { ruta: "/curso/aleman", espera: ".k-row", lineas: null },
  "error-de-carga": { ruta: "/", espera: ".k-error", todayStatus: 500, lineas: null },
};
const PANTALLAS = [[390, 844], [390, 667], [360, 640], [320, 568]];

// Un oyente ajeno en el puerto (un `vite preview` huérfano de otra corrida, por ejemplo) también
// respondería 200 y se fotografiaría otro servidor: mejor no empezar.
const responde = () => fetch(BASE, { signal: AbortSignal.timeout(2000) }).catch(() => null);
if (await responde()) {
  console.error(`El puerto ${PORT} ya está ocupado (¿un vite preview huérfano?). Ciérralo y vuelve a correr.`);
  process.exit(2);
}

// Un solo string con shell:true: con argumentos sueltos Node 24 avisa con DEP0190. Sin stdio
// heredado ni en pipe, para que el hijo no se bloquee con un pipe que nadie lee.
const servidor = spawn(`npx vite preview --port ${PORT} --strictPort`, { cwd: FRONT, shell: true, stdio: "ignore" });
function apagar() {
  if (process.platform === "win32") {
    try { execSync(`taskkill /pid ${servidor.pid} /T /F`, { stdio: "ignore" }); } catch { /* ya murió */ }
  } else {
    servidor.kill();
  }
}

// Igual que en hoja.check.mjs: `document.fonts.ready` resuelve antes de que el layout pida las caras
// (llegan de Google Fonts, y cada contexto arranca con la caché fría), así que se piden a mano. El
// `.catch` solo evita que una cara caída tumbe al resto: lo que devuelve la función son las familias
// que siguen sin cara cargada (o con una en error), para que el arnés lo diga en vez de fotografiar
// Georgia/Helvetica y medir los desbordes con otras métricas. Noto Serif JP solo se pide donde hay
// japonés (`japones`): el resto de la app no la descarga (index.html).
const FUENTES = ["Source Serif 4", "Inter Tight", "JetBrains Mono"];
const JAPONES = ["かきくけこ日本語", "日本語"];
async function esperarFuentes(page, japones) {
  return page.evaluate(async ([familias, ja, kana]) => {
    await Promise.all([
      '17px "Source Serif 4"', 'italic 17px "Source Serif 4"', '600 17px "Source Serif 4"',
      '500 15px "Inter Tight"', '12px "JetBrains Mono"', '500 12px "JetBrains Mono"',
      ...(ja ? [['400 17px "Noto Serif JP"', kana[0]], ['500 17px "Noto Serif JP"', kana[1]], ['600 17px "Noto Serif JP"', kana[1]]] : []),
    ].map((f) => (Array.isArray(f) ? document.fonts.load(f[0], f[1]) : document.fonts.load(f)).catch(() => null)));
    // `document.fonts.check()` devuelve true también cuando no hay ninguna @font-face de esa familia
    // (Google Fonts sin red), así que se miran las caras una a una.
    const caras = [...document.fonts].map((f) => ({ familia: f.family.replace(/^["']|["']$/g, ""), estado: f.status }));
    return (ja ? [...familias, "Noto Serif JP"] : familias).filter((fam) => {
      const suyas = caras.filter((c) => c.familia === fam);
      return !suyas.some((c) => c.estado === "loaded") || suyas.some((c) => c.estado === "error");
    });
  }, [FUENTES, japones, JAPONES]);
}

async function medir(page) {
  return page.evaluate(() => {
    const desbordes = [];
    // `.k-app` y no `html`: el cascarón tiene overflow:hidden, así que `html` nunca desborda y no
    // dice nada; `.k-app` sí puede, y es el que lleva la barra de pestañas.
    for (const el of document.querySelectorAll(".k-app, .k-live, .k-page")) {
      const d = el.scrollWidth - el.clientWidth;
      if (d > 0) desbordes.push({ el: el.className || el.tagName, d });
    }
    const chicos = [...document.querySelectorAll("button, a[href]")]
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.width > 0 && (r.width < 44 || r.height < 44))
      .map(({ el, r }) => ({ txt: el.textContent.trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) }));
    // `list-style: none` (las dos listas lo llevan) quita la semántica de lista en Safari/VoiceOver.
    const sinRolLista = [...document.querySelectorAll("ol.k-route, ul.k-shelf")].filter((el) => el.getAttribute("role") !== "list").length;
    return { desbordes, chicos, sinRolLista };
  });
}

// Con qué fuente dibujó Chromium el texto propio de cada elemento (CDP): `lang="ja"` etiqueta, pero
// solo una familia declarada en el propio elemento hace que `:lang(ja)` (tokens.css) le dé Noto Serif JP.
async function fuentesDe(ctx, page, selectores) {
  const cdp = await ctx.newCDPSession(page);
  const salida = {};
  try {
    await cdp.send("DOM.enable");
    await cdp.send("CSS.enable");
    const { root } = await cdp.send("DOM.getDocument", { depth: -1 });
    for (const sel of selectores) {
      const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: sel });
      if (!nodeId) { salida[sel] = null; continue; }
      const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId });
      salida[sel] = fonts.map((f) => f.familyName);
    }
  } finally {
    await cdp.detach().catch(() => {});
  }
  return salida;
}

// Sale de la app o vuelve a ella: `visibilitychange` con el estado que se diga. `null` quita el
// estado fingido y vuelve el del navegador, que en la página abierta es «visible».
const visibilidad = (page, estado) => page.evaluate((e) => {
  if (e) Object.defineProperty(document, "visibilityState", { configurable: true, get: () => e });
  else delete document.visibilityState;
  document.dispatchEvent(new Event("visibilitychange"));
}, estado);

const fallos = [];
const informe = {};
let browser;
// Todo lo que viene después del spawn va dentro del try: si falla la espera del servidor, el
// lanzamiento de Chromium o el cierre, el `finally` mata a `vite preview` igualmente. En Windows
// un hijo con shell:true sobrevive al throw del padre y el siguiente arranque lo toma por suyo.
try {
  // `vite preview` tarda en arrancar. Si el hijo muere antes de responder (`--strictPort` con el
  // puerto ocupado) o no da 200 en 30 s, se corta aquí en vez de seguir contra nada.
  let listo = false;
  for (let i = 0; i < 60 && !listo; i++) {
    if (servidor.exitCode !== null) throw new Error(`vite preview terminó con código ${servidor.exitCode} antes de responder (¿puerto ${PORT} ocupado?).`);
    listo = (await responde())?.ok === true;
    if (!listo) await new Promise((r) => setTimeout(r, 500));
  }
  if (!listo) throw new Error(`vite preview no respondió 200 en ${BASE} en 30 s.`);
  browser = await chromium.launch();
  for (const [nombre, esc] of Object.entries(ESCENARIOS)) {
    for (const scheme of ["light", "dark"]) {
      for (const [width, height] of PANTALLAS) {
        const clave = `${nombre}-${scheme}-${width}x${height}`;
        const hoyPedidos = []; // el `since` de cada GET /today
        const demora = { ms: 0 }; // cuánto se retrasa la respuesta de /today: para mirar la pantalla mientras refresca
        const falla = { status: esc.todayStatus ?? 0 }; // con qué estado responde /today (0: bien): para que falle solo un refetch
        const ctx = await browser.newContext({
          viewport: { width, height }, deviceScaleFactor: 2, locale: "es-ES",
          colorScheme: scheme, serviceWorkers: "block",
        });
        // Lo que importa de «el toque desbloquea el audio ANTES de abrir la sesión»: cuándo suena el play() del
        // elemento silencioso y cuándo cambia la historia, en el mismo reloj.
        await ctx.addInitScript(() => {
          window.__plays = [];
          window.__navs = [];
          const play = HTMLMediaElement.prototype.play;
          HTMLMediaElement.prototype.play = function (...a) {
            window.__plays.push({ t: performance.now(), path: location.pathname });
            return play.apply(this, a);
          };
          const push = history.pushState;
          history.pushState = function (state, t, url) {
            window.__navs.push({ t: performance.now(), url: String(url), from: state?.usr?.from ?? null });
            return push.apply(this, arguments);
          };
        });
        await ctx.route("**/api/v1/**", async (route) => {
          const req = route.request();
          const p = new URL(req.url()).pathname.replace(/^\/api\/v1/, "");
          if (p === "/today") hoyPedidos.push(new URL(req.url()).searchParams.get("since"));
          if (p === "/today" && demora.ms) await new Promise((r) => setTimeout(r, demora.ms));
          if (p === "/today" && falla.status) {
            return route.fulfill({ status: falla.status, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) });
          }
          let body = [];
          if (p === "/me") body = user;
          else if (p === "/modules") body = modules;
          else if (p.startsWith("/srs/cards/due")) body = due;
          else if (p === "/today") body = { lineas: esc.lineas ?? [] };
          return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
        });
        const page = await ctx.newPage();
        // Lo que no está simulado cae en `200 []` (arriba), así que un error de JS por datos
        // que no cuadran solo se ve aquí. Ve los del render, los efectos, los manejadores y las
        // promesas rechazadas; no los que se lancen dentro de un `setTimeout`, porque el reloj de
        // Playwright (`setFixedTime`, abajo) se los traga.
        const alError = (e) => fallos.push(`${clave}: error de JS en la página: ${e.message}`);
        page.on("pageerror", alError);
        await page.clock.setFixedTime(new Date("2026-09-30T17:40:00"));
        await page.goto(BASE + esc.ruta);
        await page.waitForSelector(esc.espera);
        const hayJapones = (esc.lineas ?? []).some((l) => l.idioma === "ja");
        const sinFuentes = await esperarFuentes(page, hayJapones);
        // El mismo aviso para todas las capturas: una sola línea en el informe.
        const avisoFuentes = `fuentes sin cargar (${sinFuentes.join(", ")}): ¿sin red para Google Fonts? Las capturas salen con las de respaldo y los desbordes se miden con otras métricas`;
        if (sinFuentes.length && !fallos.includes(avisoFuentes)) fallos.push(avisoFuentes);
        await page.waitForTimeout(500);
        await page.screenshot({ path: join(OUT, `${clave}.png`), animations: "disabled" });
        const m = await medir(page);
        informe[clave] = m;
        if (m.desbordes.length) fallos.push(`${clave}: desborda ${JSON.stringify(m.desbordes)}`);
        if (m.chicos.length) fallos.push(`${clave}: controles < 44px ${JSON.stringify(m.chicos)}`);
        if (m.sinRolLista) fallos.push(`${clave}: ${m.sinRolLista} lista(s) sin role="list"`);
        for (const [sel, esperado] of Object.entries(esc.lang ?? {})) {
          const lang = await page.locator(sel).first().getAttribute("lang");
          if (lang !== esperado) fallos.push(`${clave}: «${sel}» lleva lang=${JSON.stringify(lang)} y se espera ${JSON.stringify(esperado)}`);
        }
        for (const sel of esc.nativo ?? []) {
          if ((await page.locator(sel).first().getAttribute("lang")) !== null) fallos.push(`${clave}: «${sel}» es texto de la interfaz y lleva lang`);
        }
        if (esc.noto && !sinFuentes.includes("Noto Serif JP")) {
          const fuentes = await fuentesDe(ctx, page, esc.noto);
          for (const [sel, fs] of Object.entries(fuentes)) {
            // Son las fuentes del texto propio del elemento: el titular «か き く け こ» saca Noto para el kana y
            // Source Serif 4 para los espacios. Lo que no vale es que el kana (o el kanji) caiga en una fuente del sistema.
            if (!fs || !fs.some((f) => f.startsWith("Noto Serif JP"))) fallos.push(`${clave}: «${sel}» no se dibuja con Noto Serif JP (${JSON.stringify(fs)})`);
            else if (fs.some((f) => !f.startsWith("Noto Serif JP") && !FUENTES.includes(f))) fallos.push(`${clave}: «${sel}» mezcla una fuente del sistema (${JSON.stringify(fs)})`);
          }
        }
        if (esc.sinBoton) {
          // La línea al día no es un botón ni un enlace, no tiene mano y tocarla no abre nada.
          const parada = page.locator(esc.sinBoton);
          if ((await parada.locator("button, a").count()) !== 0) fallos.push(`${clave}: la línea al día tiene un botón o un enlace`);
          const fila = parada.locator(".k-route__row");
          if ((await fila.evaluate((x) => getComputedStyle(x).cursor)) !== "default") fallos.push(`${clave}: la línea al día tiene cursor de mano`);
          if (scheme === "light" && width === 390 && height === 844) {
            const antes = await page.evaluate(() => window.__navs.length);
            await fila.click();
            await page.waitForTimeout(300);
            if ((await page.evaluate(() => window.__navs.length)) !== antes) fallos.push(`${clave}: tocar la línea al día navega`);
          }
        }
        if (nombre === "entrar" && scheme === "light" && width === 390 && height === 844) {
          // Volver a la app: `visibilitychange` con la página visible pide /today otra vez, y con la
          // medianoche del día nuevo (el reloj salta al día siguiente); con la página oculta no pide nada.
          const antes = hoyPedidos.length;
          await visibilidad(page, "hidden");
          await page.waitForTimeout(600);
          if (hoyPedidos.length !== antes) fallos.push("volver a la app: pide /today con la app oculta");
          await page.clock.setFixedTime(new Date("2026-10-01T08:10:00"));
          demora.ms = 500;
          await visibilidad(page, null);
          await page.waitForTimeout(200);
          // El pedido sigue en vuelo: Hoy conserva el día que tenía, sin vaciarse ni parpadear.
          if ((await page.locator(HEROE).count()) !== 1) fallos.push("volver a la app: Hoy se vacía mientras refresca");
          await page.waitForTimeout(600);
          demora.ms = 0;
          if (hoyPedidos.length !== antes + 1) fallos.push(`volver a la app: ${hoyPedidos.length - antes} pedidos de /today (se espera 1)`);
          else if (!(Date.parse(hoyPedidos[antes]) > Date.parse(hoyPedidos[antes - 1]))) fallos.push("volver a la app: /today sigue pidiendo desde la medianoche de ayer");
          // Y si ese pedido falla con el plan a la vista: el plan se queda tal cual y el banner de
          // error (que es para cuando no hay plan que enseñar) no se pinta encima.
          await visibilidad(page, "hidden");
          falla.status = 500;
          const llego = page.waitForResponse((r) => r.url().includes("/api/v1/today"), { timeout: 3000 }).then(() => true, () => false);
          await visibilidad(page, null);
          if (!(await llego)) fallos.push("volver a la app: el pedido de /today que debia fallar no llego");
          await page.waitForTimeout(300); // que React procese el rechazo y pinte
          falla.status = 0;
          if ((await page.locator(HEROE).count()) !== 1) fallos.push("volver a la app: un pedido de /today que falla vacia Hoy");
          if ((await page.locator(".k-error").count()) !== 0) fallos.push("volver a la app: un pedido de /today que falla pone el banner de error sobre el plan");
          // El toque en el héroe abre /sesion/ja, que no está simulada (`200 []`) y puede lanzar un error
          // al pintarse: esa pantalla ya no es la que se prueba. Lo que importa es el orden: el audio se
          // desbloquea (el play() del wav silencioso) estando todavía en «/», antes de que cambie la historia.
          page.off("pageerror", alError);
          await page.locator(HEROE).click();
          await page.waitForURL("**/sesion/ja", { timeout: 3000 }).catch(() => {});
          const { plays, navs } = await page.evaluate(() => ({ plays: window.__plays, navs: window.__navs }));
          const nav = navs.find((n) => n.url === "/sesion/ja");
          if (!nav) fallos.push("toque: el héroe no abre /sesion/ja");
          else {
            if (nav.from !== "/") fallos.push(`toque: navega con state.from=${JSON.stringify(nav.from)} y se espera «/»`);
            if (!(plays.length && plays[0].path === "/" && plays[0].t <= nav.t)) fallos.push(`toque: el audio no se desbloquea antes de abrir la sesión (${JSON.stringify({ plays, nav })})`);
          }
        }
        await ctx.close();
      }
    }
  }
} finally {
  await browser?.close().catch(() => {});
  apagar();
}

writeFileSync(join(OUT, "informe.json"), JSON.stringify({ fallos, informe }, null, 2));
console.log(`${Object.keys(informe).length} capturas en ${OUT}`);
if (fallos.length) {
  console.error(fallos.join("\n"));
  process.exit(1);
}
console.log("Sin desbordes, sin controles chicos, el japonés en Noto Serif JP y cada idioma con su lang, la línea al día sin botón, el toque desbloquea el audio antes de abrir la sesión, Hoy se refresca al volver a la app y las listas llevan su role.");
