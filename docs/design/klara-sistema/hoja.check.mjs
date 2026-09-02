// Chequeo de la hoja de componentes: renderiza hoja.html en los dos temas y
// falla si el vocabulario rompe una restricción del brief (§5 estados, §7).
//
//   node docs/design/klara-sistema/hoja.check.mjs [--out <dir>]
//
// Escribe capturas (light/dark, teléfono/escritorio) y hoja.inline.html (CSS
// inlineado, para publicarla como artefacto) en --out (default: ./.hoja-out).
//
// ponytail: usa el Playwright del arnés de design-sync (.ds-sync/, gitignored,
// ver .design-sync/NOTES.md). Si esto pasa a ser gate de CI, playwright entra
// como devDependency de frontend/ y este import se vuelve `from "playwright"`.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "../../..");
const HOJA = join(HERE, "hoja.html");
const STYLES = join(REPO, "frontend/src/styles");
const PW = join(REPO, ".ds-sync/node_modules/playwright/index.mjs");

const outIdx = process.argv.indexOf("--out");
const OUT = resolve(outIdx > 0 ? process.argv[outIdx + 1] : join(REPO, ".hoja-out"));

if (!existsSync(PW)) {
  console.error(`No está ${PW}. Instala el arnés (.design-sync/NOTES.md) o añade playwright a frontend/.`);
  process.exit(2);
}
const { chromium } = await import(pathToFileURL(PW).href);

// Estados obligatorios por átomo (slugs = data-estado en la hoja): los del §5
// del brief más las variantes que fija CONTRATO.md.
const ESTADOS = {
  "boton": ["solido", "fantasma", "acento", "texto", "deshabilitado", "cargando", "con-flecha", "grande", "bloque"],
  "boton-redondo": ["reposo", "tinta", "activo", "grabando", "deshabilitado", "ya-sono", "sm", "md", "lg"],
  "ficha": ["frente", "reverso", "con-ejemplo", "vacia", "plana", "anclada"],
  "fila": ["pendiente", "ahora", "hecha", "bloqueada", "dominada", "seleccionada", "con-caja", "quieta"],
  "barra-progreso": ["segmentos", "continua", "hitos"],
  "cinta-seccion": ["sola", "con-contador", "con-regla", "centrada"],
  "marca-nivel": ["A0", "A1", "A2", "B1", "B2", "C1", "C2", "sin-caja"],
  "chip": ["reposo", "seleccionado", "deshabilitado", "estatico"],
  "hoja-inferior": ["entrando", "reposo"],
  "barra-pestanas": ["2", "3", "4", "activo", "con-menu"],
  "linea-superior": ["marca", "sesion", "pie"],
  "bloque-heroe": ["activo", "deshabilitado", "quieto"],
  "nota-margen": ["glosa", "correccion", "mono", "sin-filete"],
  "palabra-puntuada": ["bien", "regular", "mal", "activa"],
  "error": ["en-linea"],
  "marca": ["quieta", "hablando"],
  "campo-texto": ["reposo", "foco", "error", "deshabilitado", "area", "manuscrito"],
};

// document.fonts.ready resuelve antes de que el layout pida las caras; hay que
// pedirlas a mano o la captura sale con Georgia/Helvetica.
async function esperarFuentes(page) {
  await page.evaluate(() => Promise.all([
    '17px "Source Serif 4"', 'italic 17px "Source Serif 4"', '600 17px "Source Serif 4"',
    '500 15px "Inter Tight"', '12px "JetBrains Mono"', '500 12px "JetBrains Mono"',
  ].map((f) => document.fonts.load(f).catch(() => null))));
  await page.waitForTimeout(250);
}

const fallos = [];
const fallo = (m) => { fallos.push(m); console.error("✗ " + m); };
const ok = (m) => console.log("✓ " + m);

// --- 1. Sin colores literales en sistema.css (solo var(--…)) ---
const sistema = readFileSync(join(STYLES, "sistema.css"), "utf8");
const literales = [...sistema.matchAll(/#[0-9a-fA-F]{3,8}\b|\b(?:oklch|oklab|rgba?|hsla?|color)\(/g)];
if (literales.length) fallo(`sistema.css tiene ${literales.length} colores literales: ${literales.slice(0, 5).map((m) => m[0]).join(", ")}…`);
else ok("sistema.css: cero colores literales");

// --- 2. Render en los dos temas ---
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const url = pathToFileURL(HOJA).href;

for (const tema of ["light", "dark"]) {
  for (const [nombre, vp] of [["tel", { width: 390, height: 844 }], ["esc", { width: 1180, height: 900 }]]) {
    const page = await browser.newPage({ viewport: vp, deviceScaleFactor: 2 });
    const errores = [];
    page.on("pageerror", (e) => errores.push(String(e)));
    await page.goto(`${url}?theme=${tema}`);
    await esperarFuentes(page);
    if (errores.length) fallo(`[${tema}/${nombre}] errores JS: ${errores.join(" | ")}`);

    const r = await page.evaluate((ESTADOS) => {
      const out = { faltan: [], chicos: [], atomosFuera: [], scrollX: document.documentElement.scrollWidth, ancho: innerWidth, tema: document.documentElement.getAttribute("data-theme") };
      const cards = [...document.querySelectorAll(".hoja-card")];
      const vistos = new Set();
      for (const c of cards) {
        const atom = c.dataset.atom;
        if (!ESTADOS[atom]) { out.atomosFuera.push(atom); continue; }
        vistos.add(atom);
        // Una figure puede documentar varios estados a la vez (los siete niveles, los tres tamaños): data-estado="A0 A1 …".
        const tiene = new Set([...c.querySelectorAll(".hoja-estado")].flatMap((f) => (f.dataset.estado ?? "").split(/\s+/).filter(Boolean)));
        for (const e of ESTADOS[atom]) if (!tiene.has(e)) out.faltan.push(`${atom}:${e}`);
        // §7.2 objetivos táctiles ≥ 44px, sin excepciones
        const sel = 'button, a[href], [role="button"], input:not([type=hidden]), select, textarea, summary';
        for (const el of c.querySelectorAll(".hoja-estado__muestra " + sel)) {
          const b = el.getBoundingClientRect();
          if (b.width === 0 && b.height === 0) continue; // oculto a propósito
          // Solo .k-word es inline: su ancho es el de la palabra (CONTRATO, trampa 6); se mide el alto.
          const inline = getComputedStyle(el).display === "inline";
          if ((!inline && b.width < 44) || b.height < 44) out.chicos.push(`${atom}/${el.closest(".hoja-estado")?.dataset.estado}: ${el.tagName.toLowerCase()}.${[...el.classList].join(".")} ${Math.round(b.width)}×${Math.round(b.height)}`);
        }
      }
      out.atomosSinCard = Object.keys(ESTADOS).filter((a) => !vistos.has(a));
      return out;
    }, ESTADOS);

    if (r.tema !== tema) fallo(`[${tema}/${nombre}] data-theme=${r.tema}, esperaba ${tema}`);
    if (nombre === "tel" && tema === "light") {
      if (r.atomosSinCard.length) fallo(`átomos sin tarjeta: ${r.atomosSinCard.join(", ")}`);
      if (r.atomosFuera.length) fallo(`tarjetas con data-atom desconocido: ${r.atomosFuera.join(", ")}`);
      if (r.faltan.length) fallo(`estados del brief §5 que faltan: ${r.faltan.join(", ")}`);
      else ok("los 16 átomos con todos los estados de §5");
    }
    if (r.scrollX > r.ancho) fallo(`[${tema}/${nombre}] scroll horizontal: ${r.scrollX}px en un viewport de ${r.ancho}px`);
    if (r.chicos.length) fallo(`[${tema}/${nombre}] objetivos < 44px: ${r.chicos.join("; ")}`);
    else ok(`[${tema}/${nombre}] todos los objetivos táctiles ≥ 44px`);

    await page.screenshot({ path: join(OUT, `hoja-${tema}-${nombre}.png`), fullPage: true });
    // Una captura por tarjeta (solo en teléfono): es lo que revisan los ojos, humanos o no.
    if (nombre === "tel") {
      for (const card of await page.locator(".hoja-card").all()) {
        const atom = await card.getAttribute("data-atom");
        await card.screenshot({ path: join(OUT, `card-${atom}-${tema}.png`) });
      }
    }
    await page.close();
  }
}

// --- 3. prefers-reduced-motion: nada animado (§7.6) ---
{
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" });
  await page.goto(`${url}?theme=light`);
  await esperarFuentes(page);
  const vivas = await page.evaluate(() => document.getAnimations().filter((a) => (a.effect?.getTiming().duration ?? 0) > 0).length);
  if (vivas) fallo(`con reduced-motion siguen ${vivas} animaciones con duración > 0`);
  else ok("reduced-motion: cero animaciones");
  await page.close();
}
await browser.close();

// --- 4. hoja.inline.html: CSS inlineado para publicarla como artefacto ---
{
  const inline = (cssPath, seen = new Set()) => {
    if (seen.has(cssPath)) return "";
    seen.add(cssPath);
    return readFileSync(cssPath, "utf8").replace(/@import\s+(?:url\()?["']?([^"')]+)["']?\)?\s*;/g, (m, ref) =>
      ref.startsWith("http") ? "" : inline(join(dirname(cssPath), ref), seen));
  };
  let html = readFileSync(HOJA, "utf8");
  html = html.replace(/<link[^>]+href="([^"]+\.css)"[^>]*>/g, (m, href) =>
    href.startsWith("http") ? m : `<style>\n${inline(join(HERE, href))}\n</style>`);
  // Sin cascarón <html>/<head>/<body>: el visor de artefactos pone el suyo y un navegador los infiere.
  html = html.replace(/<!doctype html>\s*|<\/?html[^>]*>\s*|<\/?head>\s*|<\/?body>\s*|<meta charset="utf-8">\s*|<meta name="viewport"[^>]*>\s*/gi, "");
  writeFileSync(join(OUT, "hoja.inline.html"), html);
  ok(`escrito ${join(OUT, "hoja.inline.html")} + 4 capturas`);
}

console.log("\nRESUMEN " + JSON.stringify({ fallos }));
if (fallos.length) { console.error(`\n${fallos.length} fallo(s)`); process.exit(1); }
console.log("\nhoja: todo en orden");
