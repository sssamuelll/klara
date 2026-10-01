// Arnés visual de Hoy y Biblioteca (plan 2026-09-30, tarea 14).
//
//   cd frontend && npm run build && PLAYWRIGHT_BROWSERS_PATH=D:/caches/ms-playwright node scripts/capturas-hoy.mjs
//
// Levanta `vite preview` sobre el dist que haya (no compila), simula la API y
// fotografía cada escenario en claro y oscuro, a 390×844 y a 390×667. Escribe los
// PNG y un informe en .hoja-out/hoy/. Sale con 1 si algo desborda en horizontal,
// si hay controles de menos de 44px, si la imagen rota deja un icono roto, si el
// doble toque reclama dos veces, si Hoy no vuelve a pedir /today al volver a la app
// (o lo pide con la app oculta, o se vacía mientras refresca), si una imagen rota deja
// sin ilustración a la historia siguiente, si el alemán no lleva lang="de" (o el texto
// de la interfaz sí), si una lista sin viñetas pierde su role="list", si una fuente no
// cargó o si la página lanza un error de JS. Sale con 2 si falta el Playwright o el
// dist, o si el puerto 4175 ya está ocupado.
//
// Necesita PLAYWRIGHT_BROWSERS_PATH (aquí D:/caches/ms-playwright, con barras
// normales en Git Bash) y tarda unos 2 minutos: son 36 contextos nuevos, cada
// uno con la caché de fuentes fría.
//
// Usa el Playwright del arnés de design-sync (.ds-sync/, gitignored), como hoja.check.mjs.

import { spawn, execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONT = resolve(HERE, "..");
const REPO = resolve(FRONT, "..");
const OUT = join(REPO, ".hoja-out", "hoy");
const PW = join(REPO, ".ds-sync/node_modules/playwright/index.mjs");
const ARTE = join(REPO, "docs/design/klara-hoy/ilustracion-flash.jpg");
const PORT = 4175;
const BASE = `http://localhost:${PORT}`;

if (!existsSync(PW)) { console.error(`No está ${PW} (ver .design-sync/NOTES.md).`); process.exit(2); }
if (!existsSync(join(FRONT, "dist", "index.html"))) { console.error("No hay dist/: corre `npm run build`."); process.exit(2); }
const { chromium } = await import(pathToFileURL(PW).href);
mkdirSync(OUT, { recursive: true });

const user = { id: "u1", email: "samuel@example.com", is_superuser: false, display_name: "Samuel", level: "A2",
  native_language: "es", target_language: "de", learning_context: null, auth_methods: ["password"], needs_onboarding: false };
const modules = Array.from({ length: 8 }, (_, i) => ({ id: `m${i}`, sequence_order: i + 1, title: `Módulo ${i + 1}`,
  cefr_level: "A2", can_dos: [], grammatical_focus: [], encountered: 10, mastered: i < 2 ? 10 : 3, total: 10,
  gender_encountered: 0, gender_mastered: 0, gender_total: 0, stories_finished: i < 2 ? 3 : 1,
  stories_to_complete: 3, completed: i < 2, is_current: i === 2, unlocked: i <= 3, library_available: 2 }));
const due = Array.from({ length: 12 }, (_, i) => ({ id: `c${i}` }));

const NINGUNA = { read: false, pronounce: false, speak: false, review: false };
const historia = (over = {}) => ({ state: "new", id: null, library_entry_id: "e1", module_id: "m2",
  title: "Die Bäckerei am Samstag", subtitle: "Una panadería, un sábado a las ocho.",
  illustration_path: "/illustrations/muestra", ...over });
const hecha = historia({ state: "done", id: "s1", library_entry_id: null });

// El botón del héroe y no `.k-hero` a secas: el primero de esos en el DOM es el saludo
// (<header class="k-hero k-hero--quiet">). También es lo que espera y toca el doble toque.
const HEROE = "button.k-hero";

// `espera`: el selector que dice que los datos ya llegaron y la pantalla pintó lo que se
// fotografía. Nunca `.k-route`: el recorrido se pinta también mientras carga y cuando falla
// (con `today` en null todas las paradas salen pendientes), y las medidas pasarían en vacío.
// `de` y `nativo`: lo que tiene que llevar `lang="de"` (texto en el idioma de estudio) y lo que
// no (texto de la interfaz, que hereda el idioma de la página).
const ESCENARIOS = {
  "entrar": { ruta: "/", espera: HEROE, de: [`${HEROE} .k-hero__title`, ".k-topline button span"],
    today: { now: "read", steps: NINGUNA, story: historia(), sentence: null, due: 12, module: null } },
  "despues-de-leer": { ruta: "/", espera: HEROE, de: [`${HEROE} .k-hero__title`, '.k-route__stop[data-state="done"] .k-route__sub'],
    today: { now: "pronounce", steps: { ...NINGUNA, read: true }, story: hecha,
    sentence: { target: "Der Bäcker öffnet um acht.", native: "El panadero abre a las ocho." }, due: 12, module: null } },
  // Sin parada actual no hay héroe: lo que prueba que llegó `/today` es la primera parada hecha.
  "todo-hecho": { ruta: "/", espera: '.k-route__stop[data-state="done"]', today: { now: null, steps: { read: true, pronounce: true, speak: true, review: true },
    story: hecha, sentence: null, due: 0, module: null } },
  "sin-historia": { ruta: "/", espera: HEROE, nativo: [`${HEROE} .k-hero__title`], today: { now: "read", steps: { ...NINGUNA, review: true },
    story: { state: "request", id: null, library_entry_id: null, module_id: null, title: null, subtitle: null, illustration_path: null },
    sentence: null, due: 0, module: null } },
  "titulo-largo": { ruta: "/", espera: HEROE, today: { now: "read", steps: NINGUNA,
    story: historia({ title: "Die Bundesausbildungsförderungsgesetzberatungsstelle am Samstag" }), sentence: null, due: 12, module: null } },
  // El héroe existe; es la <img> la que se quita al fallar, y de eso se ocupa el chequeo de imagen rota.
  // `relevo`: lo que responde /today al volver a la app (otra historia, con una ilustración que sí carga).
  "arte-rota": { ruta: "/", espera: HEROE, arteRota: true,
    today: { now: "read", steps: NINGUNA, story: historia(), sentence: null, due: 12, module: null },
    relevo: { now: "read", steps: NINGUNA, story: historia({ illustration_path: "/illustrations/otra" }), sentence: null, due: 12, module: null } },
  "biblioteca": { ruta: "/biblioteca", espera: ".k-shelf", de: [".k-cover__band"], today: null },
  "portada": { ruta: "/curso/aleman", espera: ".k-row", today: null },
  "error-de-carga": { ruta: "/", espera: ".k-error", todayStatus: 500, today: null },
};

const arte = readFileSync(ARTE);

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
// Georgia/Helvetica y medir los desbordes con otras métricas.
const FUENTES = ["Source Serif 4", "Inter Tight", "JetBrains Mono"];
async function esperarFuentes(page) {
  return page.evaluate(async (familias) => {
    await Promise.all([
      '17px "Source Serif 4"', 'italic 17px "Source Serif 4"', '600 17px "Source Serif 4"',
      '500 15px "Inter Tight"', '12px "JetBrains Mono"', '500 12px "JetBrains Mono"',
    ].map((f) => document.fonts.load(f).catch(() => null)));
    // `document.fonts.check()` devuelve true también cuando no hay ninguna @font-face de esa familia
    // (Google Fonts sin red), así que se miran las caras una a una.
    const caras = [...document.fonts].map((f) => ({ familia: f.family.replace(/^["']|["']$/g, ""), estado: f.status }));
    return familias.filter((fam) => {
      const suyas = caras.filter((c) => c.familia === fam);
      return !suyas.some((c) => c.estado === "loaded") || suyas.some((c) => c.estado === "error");
    });
  }, FUENTES);
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
    const rota = [...document.querySelectorAll("img.k-hero__art")].some((img) => img.complete && img.naturalWidth === 0);
    // `list-style: none` (las dos listas lo llevan) quita la semántica de lista en Safari/VoiceOver.
    const sinRolLista = [...document.querySelectorAll("ol.k-route, ul.k-shelf")].filter((el) => el.getAttribute("role") !== "list").length;
    return { desbordes, chicos, rota, sinRolLista };
  });
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
      for (const height of [844, 667]) {
        const clave = `${nombre}-${scheme}-${height}`;
        const reclamos = { n: 0 };
        const hoyPedidos = []; // el `since` de cada GET /today
        const demora = { ms: 0 }; // cuánto se retrasa la respuesta de /today: para mirar la pantalla mientras refresca
        const ctx = await browser.newContext({
          viewport: { width: 390, height }, deviceScaleFactor: 2, locale: "es-ES",
          colorScheme: scheme, serviceWorkers: "block",
        });
        await ctx.route("**/api/v1/**", async (route) => {
          const req = route.request();
          const p = new URL(req.url()).pathname.replace(/^\/api\/v1/, "");
          if (p.startsWith("/illustrations/")) {
            return esc.arteRota && !p.endsWith("/otra")
              ? route.fulfill({ status: 404, body: "" })
              : route.fulfill({ status: 200, contentType: "image/jpeg", body: arte });
          }
          if (p === "/today") hoyPedidos.push(new URL(req.url()).searchParams.get("since"));
          if (p === "/today" && demora.ms) await new Promise((r) => setTimeout(r, demora.ms));
          if (p === "/today" && esc.todayStatus) {
            return route.fulfill({ status: esc.todayStatus, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) });
          }
          let body = [];
          let status = 200;
          if (p === "/me") body = user;
          else if (p === "/modules") body = modules;
          else if (p.startsWith("/srs/cards/due")) body = due;
          else if (p === "/today") body = esc.relevo && hoyPedidos.length > 1 ? esc.relevo : esc.today;
          else if (p.startsWith("/modules/") && p.endsWith("/story") && req.method() === "POST") {
            reclamos.n += 1;
            status = 201;
            body = { id: "s-nueva", title: "Die Bäckerei am Samstag" };
          }
          return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
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
        const sinFuentes = await esperarFuentes(page);
        // El mismo aviso para las 36 capturas: una sola línea en el informe.
        const avisoFuentes = `fuentes sin cargar (${sinFuentes.join(", ")}): ¿sin red para Google Fonts? Las capturas salen con las de respaldo y los desbordes se miden con otras métricas`;
        if (sinFuentes.length && !fallos.includes(avisoFuentes)) fallos.push(avisoFuentes);
        await page.waitForTimeout(500);
        await page.screenshot({ path: join(OUT, `${clave}.png`), animations: "disabled" });
        const m = await medir(page);
        informe[clave] = m;
        if (m.desbordes.length) fallos.push(`${clave}: desborda ${JSON.stringify(m.desbordes)}`);
        if (m.chicos.length) fallos.push(`${clave}: controles < 44px ${JSON.stringify(m.chicos)}`);
        if (m.rota) fallos.push(`${clave}: icono de imagen rota`);
        if (m.sinRolLista) fallos.push(`${clave}: ${m.sinRolLista} lista(s) sin role="list"`);
        for (const sel of esc.de ?? []) {
          if ((await page.locator(sel).first().getAttribute("lang")) !== "de") fallos.push(`${clave}: «${sel}» no lleva lang="de"`);
        }
        for (const sel of esc.nativo ?? []) {
          if ((await page.locator(sel).first().getAttribute("lang")) !== null) fallos.push(`${clave}: «${sel}» es texto de la interfaz y lleva lang`);
        }
        if (esc.relevo) {
          // La imagen de la historia se rompió (404). Al volver a la app con otra historia, la ilustración
          // de esa se pinta: la imagen rota de la anterior no la suprime.
          await visibilidad(page, null);
          const pinta = await page.waitForFunction(() => {
            const i = document.querySelector("img.k-hero__art");
            return !!i && i.complete && i.naturalWidth > 0;
          }, null, { timeout: 3000 }).then(() => true, () => false);
          if (!pinta) fallos.push(`${clave}: al volver con otra historia no se pinta su ilustración (¿no se vuelve a pedir /today, o la imagen rota quedó pegada?)`);
        }
        if (nombre === "entrar" && scheme === "light" && height === 844) {
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
          // El reclamo navega a /estudiar/s-nueva, que no está simulada (`200 []`) y lanza un error
          // al pintarse: esa pantalla ya no es la que se prueba.
          page.off("pageerror", alError);
          await page.locator(HEROE).dblclick();
          await page.waitForTimeout(600);
          if (reclamos.n !== 1) fallos.push(`doble toque: ${reclamos.n} reclamos (se espera 1)`);
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
console.log("Sin desbordes, sin controles chicos, sin imagen rota, un solo reclamo, Hoy se refresca al volver a la app, el alemán lleva lang y las listas su role.");
