// Arnés visual de Hoy y Biblioteca (plan 2026-09-30, tarea 14).
//
//   cd frontend && npm run build && node scripts/capturas-hoy.mjs
//
// Levanta `vite preview` sobre el dist que haya (no compila), simula la API y
// fotografía cada escenario en claro y oscuro, a 390×844 y a 390×667. Escribe los
// PNG y un informe en .hoja-out/hoy/. Sale con 1 si algo desborda en horizontal,
// si hay controles de menos de 44px, si la imagen rota deja un icono roto o si
// el doble toque reclama dos veces.
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

// `espera`: el selector que dice que la pantalla ya pintó lo que se fotografía (por defecto, el recorrido).
const ESCENARIOS = {
  "entrar": { ruta: "/", today: { now: "read", steps: NINGUNA, story: historia(), sentence: null, due: 12, module: null } },
  "despues-de-leer": { ruta: "/", today: { now: "pronounce", steps: { ...NINGUNA, read: true }, story: hecha,
    sentence: { target: "Der Bäcker öffnet um acht.", native: "El panadero abre a las ocho." }, due: 12, module: null } },
  "todo-hecho": { ruta: "/", today: { now: null, steps: { read: true, pronounce: true, speak: true, review: true },
    story: hecha, sentence: null, due: 0, module: null } },
  "sin-historia": { ruta: "/", today: { now: "read", steps: { ...NINGUNA, review: true },
    story: { state: "request", id: null, library_entry_id: null, module_id: null, title: null, subtitle: null, illustration_path: null },
    sentence: null, due: 0, module: null } },
  "titulo-largo": { ruta: "/", today: { now: "read", steps: NINGUNA,
    story: historia({ title: "Die Bundesausbildungsförderungsgesetzberatungsstelle am Samstag" }), sentence: null, due: 12, module: null } },
  "arte-rota": { ruta: "/", arteRota: true, today: { now: "read", steps: NINGUNA, story: historia(), sentence: null, due: 12, module: null } },
  "biblioteca": { ruta: "/biblioteca", espera: ".k-shelf", today: null },
  "portada": { ruta: "/curso/aleman", espera: ".k-row", today: null },
  // El recorrido se pinta también mientras carga y cuando falla: hay que esperar al párrafo del error.
  "error-de-carga": { ruta: "/", espera: ".k-error", todayStatus: 500, today: null },
};

const arte = readFileSync(ARTE);
const servidor = spawn("npx", ["vite", "preview", "--port", String(PORT), "--strictPort"], { cwd: FRONT, shell: true });
function apagar() {
  if (process.platform === "win32") {
    try { execSync(`taskkill /pid ${servidor.pid} /T /F`, { stdio: "ignore" }); } catch { /* ya murió */ }
  } else {
    servidor.kill();
  }
}
for (let i = 0; i < 60; i++) {
  try { if ((await fetch(BASE)).ok) break; } catch { /* todavía no */ }
  await new Promise((r) => setTimeout(r, 500));
}

// Igual que en hoja.check.mjs: `document.fonts.ready` resuelve antes de que el layout pida las caras
// (llegan de Google Fonts, y cada contexto arranca con la caché fría). Sin esto la captura sale con
// Georgia/Helvetica y los desbordes se miden con otras métricas.
async function esperarFuentes(page) {
  await page.evaluate(() => Promise.all([
    '17px "Source Serif 4"', 'italic 17px "Source Serif 4"', '600 17px "Source Serif 4"',
    '500 15px "Inter Tight"', '12px "JetBrains Mono"', '500 12px "JetBrains Mono"',
  ].map((f) => document.fonts.load(f).catch(() => null))));
}

async function medir(page) {
  return page.evaluate(() => {
    const desbordes = [];
    for (const el of [document.documentElement, ...document.querySelectorAll(".k-live, .k-page")]) {
      const d = el.scrollWidth - el.clientWidth;
      if (d > 0) desbordes.push({ el: el.className || el.tagName, d });
    }
    const chicos = [...document.querySelectorAll("button, a[href]")]
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.width > 0 && (r.width < 44 || r.height < 44))
      .map(({ el, r }) => ({ txt: el.textContent.trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) }));
    const rota = [...document.querySelectorAll("img.k-hero__art")].some((img) => img.complete && img.naturalWidth === 0);
    return { desbordes, chicos, rota };
  });
}

const fallos = [];
const informe = {};
const browser = await chromium.launch();
try {
  for (const [nombre, esc] of Object.entries(ESCENARIOS)) {
    for (const scheme of ["light", "dark"]) {
      for (const height of [844, 667]) {
        const clave = `${nombre}-${scheme}-${height}`;
        const reclamos = { n: 0 };
        const ctx = await browser.newContext({
          viewport: { width: 390, height }, deviceScaleFactor: 2, locale: "es-ES",
          colorScheme: scheme, serviceWorkers: "block",
        });
        await ctx.route("**/api/v1/**", async (route) => {
          const req = route.request();
          const p = new URL(req.url()).pathname.replace(/^\/api\/v1/, "");
          if (p.startsWith("/illustrations/")) {
            return esc.arteRota
              ? route.fulfill({ status: 404, body: "" })
              : route.fulfill({ status: 200, contentType: "image/jpeg", body: arte });
          }
          if (p === "/today" && esc.todayStatus) {
            return route.fulfill({ status: esc.todayStatus, contentType: "application/json", body: JSON.stringify({ detail: "boom" }) });
          }
          let body = [];
          let status = 200;
          if (p === "/me") body = user;
          else if (p === "/modules") body = modules;
          else if (p.startsWith("/srs/cards/due")) body = due;
          else if (p === "/today") body = esc.today;
          else if (p.startsWith("/modules/") && p.endsWith("/story") && req.method() === "POST") {
            reclamos.n += 1;
            status = 201;
            body = { id: "s-nueva", title: "Die Bäckerei am Samstag" };
          }
          return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
        });
        const page = await ctx.newPage();
        await page.clock.setFixedTime(new Date("2026-09-30T17:40:00"));
        await page.goto(BASE + esc.ruta);
        await page.waitForSelector(esc.espera ?? ".k-route");
        await esperarFuentes(page);
        await page.waitForTimeout(500);
        await page.screenshot({ path: join(OUT, `${clave}.png`), animations: "disabled" });
        const m = await medir(page);
        informe[clave] = m;
        if (m.desbordes.length) fallos.push(`${clave}: desborda ${JSON.stringify(m.desbordes)}`);
        if (m.chicos.length) fallos.push(`${clave}: controles < 44px ${JSON.stringify(m.chicos)}`);
        if (m.rota) fallos.push(`${clave}: icono de imagen rota`);
        if (nombre === "entrar" && scheme === "light" && height === 844) {
          // `button.k-hero` y no `.k-hero`: el primero de esos en el DOM es el saludo (<header class="k-hero k-hero--quiet">).
          await page.locator("button.k-hero").dblclick();
          await page.waitForTimeout(600);
          if (reclamos.n !== 1) fallos.push(`doble toque: ${reclamos.n} reclamos (se espera 1)`);
        }
        await ctx.close();
      }
    }
  }
} finally {
  await browser.close();
  apagar();
}

writeFileSync(join(OUT, "informe.json"), JSON.stringify({ fallos, informe }, null, 2));
console.log(`${Object.keys(informe).length} capturas en ${OUT}`);
if (fallos.length) {
  console.error(fallos.join("\n"));
  process.exit(1);
}
console.log("Sin desbordes, sin controles chicos, sin imagen rota, un solo reclamo.");
