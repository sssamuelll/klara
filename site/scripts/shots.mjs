// Capturas reales de la instancia de Samuel para la página. Uso, desde site/:
//   KLARA_EMAIL=… KLARA_PASSWORD=… node scripts/shots.mjs
// Opcional: KLARA_BASE (por defecto https://klara.sdar.dev) y KLARA_STORY
// (id de la historia a capturar en Leer; si falta, la primera de la biblioteca).
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';

const base = process.env.KLARA_BASE ?? 'https://klara.sdar.dev';
const { KLARA_EMAIL: email, KLARA_PASSWORD: password, KLARA_STORY: story } = process.env;
if (!email || !password) throw new Error('faltan KLARA_EMAIL y KLARA_PASSWORD');

await mkdir('art/shots', { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, colorScheme: 'dark' });
const page = await ctx.newPage();

await page.goto(`${base}/login`);
await page.locator('input[type="email"]').fill(email);
await page.locator('input[type="password"]').fill(password);
await page.locator('button[type="submit"]').click();
await page.waitForURL((u) => !u.pathname.endsWith('/login'), { timeout: 20_000 });

const shot = async (name, route, prepare) => {
  await page.goto(base + route);
  await page.waitForLoadState('networkidle');
  if (prepare) await prepare().catch((e) => console.warn(`${name}: ${e.message}; se captura sin eso`));
  await page.waitForTimeout(600);
  await page.screenshot({ path: `art/shots/${name}.png` });
  console.log('captura:', name, route);
};

// Hoy: el recorrido del día.
await shot('today', '/');

// Leer: la historia dada, o la primera de la biblioteca; se abre una palabra larga.
await shot('read', story ? `/story/${story}` : '/biblioteca', async () => {
  if (!story) {
    await page.locator('a[href^="/story/"]').first().click();
    await page.waitForLoadState('networkidle');
  }
  await page.locator('main').getByText(/\p{L}{6,}/u).first().click();
  await page.waitForTimeout(400);
});

await shot('speak', '/chat');
await shot('review', '/repaso');

await browser.close();
