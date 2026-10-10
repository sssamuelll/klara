// Capturas reales de la instancia de Samuel para la página. Uso, desde site/:
//   set -a; . ~/.klara-shots.env; set +a; node scripts/shots.mjs
// (el archivo trae KLARA_EMAIL y KLARA_PASSWORD; nunca van en la línea de comandos).
// Opcional: KLARA_BASE (por defecto https://klara.sdar.dev), KLARA_STORY (id de la
// historia para Leer; si falta, la más reciente del día en Hoy) y KLARA_SHOTS_DIR
// (carpeta de salida, por defecto art/shots).
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const base = process.env.KLARA_BASE ?? 'https://klara.sdar.dev';
const { KLARA_EMAIL: email, KLARA_PASSWORD: password, KLARA_STORY: story } = process.env;
const outDir = process.env.KLARA_SHOTS_DIR ?? 'art/shots';
if (!email || !password) throw new Error('faltan KLARA_EMAIL y KLARA_PASSWORD');

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: 'dark' });
const page = await ctx.newPage();

await page.goto(`${base}/login`);
await page.locator('input[type="email"]').fill(email);
await page.locator('input[type="password"]').fill(password);
await page.locator('button[type="submit"]').click();
await page.waitForURL((u) => !u.pathname.endsWith('/login'), { timeout: 20_000 });

const text = () => page.evaluate(() => document.body.innerText || '');

const shot = async (name, route, prepare) => {
  await page.goto(base + route);
  await page.waitForLoadState('networkidle');
  if (prepare) await prepare();
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(outDir, `${name}.png`) });
  console.log('captura:', name, route);
};

// Leer: la historia dada, o la de hoy desde la parada «Leer»; se toca una palabra
// de la primera frase para que salga el popover.
await shot('read', story ? `/story/${story}` : '/', async () => {
  if (!story) {
    await page.getByText(/^LEER\b/i).first().click();
    await page.waitForURL(/\/story\//, { timeout: 15_000 }).catch(() => {
      throw new Error('Leer: no hay historia de hoy; pide una en Hoy o pasa KLARA_STORY');
    });
    await page.waitForLoadState('networkidle');
  }
  const sentence = (await text()).split('\n').map((l) => l.trim()).find((l) => l.length > 12 && /[.!?]$/.test(l) && l !== l.toUpperCase());
  if (!sentence) throw new Error('Leer: no encontré la primera frase');
  await page.getByText(sentence, { exact: true }).first().click();
  await page.waitForTimeout(500);
  if (!/SUST\.|ADJ\.|VERB|\bf\.|\bm\.|\bn\./i.test(await text())) throw new Error('Leer: la palabra no abrió el popover');
});

await shot('speak', '/chat');
await shot('review', '/repaso');

// Hoy va de última y con una comprobación positiva: la edición tiene que decir el
// texto nuevo (#190). Mientras producción muestre el nombre viejo, no se captura.
await shot('today', '/', async () => {
  if (!/Edición Alemania|Germany edition/i.test(await text())) {
    throw new Error('Hoy: la edición en producción todavía no dice «Alemania»; despliega #190 antes de capturar');
  }
});

await browser.close();
