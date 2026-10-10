// Abre dist/ a 360 px y falla si hay barra horizontal o el titular se corta.
import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 360, height: 740 } });
let bad = 0;
for (const file of ['dist/index.html', 'dist/es/index.html']) {
  await page.goto(pathToFileURL(path.resolve(file)).href);
  const r = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    titleRight: document.querySelector('.kl-hero__title').getBoundingClientRect().right,
  }));
  const ok = r.scrollWidth <= r.innerWidth && r.titleRight <= r.innerWidth;
  console.log(ok ? '✓' : '✗', file, r);
  if (!ok) bad++;
}
await browser.close();
process.exit(bad ? 1 : 0);
