# Sitio de Klara en GitHub Pages: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** publicar en `https://sssamuelll.github.io/klara/` (y `/es/`) una página estática de una hoja que cuenta qué es Klara y manda al repo, con el tema `klara` sobre neobrutalistcomponents y sin JavaScript en el navegador.

**Architecture:** una app Vite + React 19 en `site/`, separada del frontend de la app. React se usa solo en el build: `vite build` produce el CSS y los assets, `vite build --ssr` produce `render(lang)`, y `prerender.mjs` inyecta el HTML en los dos cascarones y quita todo `<script>`. Un workflow de Pages construye y despliega `site/dist` en cada push a `main` que toque `site/**`.

**Tech Stack:** Node 22 (CI) / 24 (local), Vite 8, @vitejs/plugin-react 6, React 19.3, TypeScript 6, neobrutalistcomponents 1.2.0, @fontsource-variable (Source Serif 4, Inter Tight, JetBrains Mono), Pillow 12 (imágenes, local), Playwright (capturas, local), GitHub Actions + Pages.

**Spec:** `docs/superpowers/specs/2026-10-10-sitio-github-pages-design.md`

## Global Constraints

- Todo lo nuevo vive en `site/` y `.github/workflows/pages.yml`. Nada en `frontend/` ni `backend/` se toca.
- La página publicada no sirve JavaScript: `dist/index.html` y `dist/es/index.html` no contienen `<script`.
- Fuentes autoalojadas: ninguna petición a `fonts.googleapis.com` ni `fonts.gstatic.com`.
- El copy es el del spec § 4, letra por letra; el de la app **(app)** no se cambia.
- Tema `klara` con los valores del spec § 5 y los diecisiete pares de contraste del contrato de la librería por encima de su mínimo (4,5 texto, 3 UI) en los valores de noche.
- Pesos: `hero.webp` ≤ 300 KB; cada captura ≤ 120 KB.
- `base: './'`; cada página referencia sus assets en relativo (`./` en `/`, `../` en `/es/`).
- Las capturas son de la cuenta de Samuel, sin Ajustes, sin nombre ni correo visibles, sin retoques.
- Actions se enciende solo para `pages.yml`; `CI`, `CodeQL` y `Build & Deploy` siguen `disabled_manually`.
- Desviación declarada del spec § 7: las fuentes entran por los paquetes `@fontsource-variable/*` (woff2 dentro de `dist/assets/`), no por `public/fonts/` + `fonts.css`. Mismo resultado (D7), menos pasos. La Tarea 5 anota la desviación en el spec.

## Review Focus

1. **Un rastreador o un navegador sin JavaScript** ve la hoja entera: el HTML publicado lleva el contenido renderizado y ningún `<script`. Prueba en la Tarea 1 (`check.mjs`: texto del hero presente, cero scripts).
2. **Un teléfono de 360 px** no muestra barra horizontal ni corta el titular: prueba en la Tarea 3 (`scripts/overflow.mjs` con Playwright a 360 px, `scrollWidth <= innerWidth`).
3. **La página `/es/`** encuentra su CSS, su ilustración y sus capturas con rutas `../`: prueba en la Tarea 3 (`check.mjs` resuelve cada `href`/`src` relativo contra la carpeta del HTML).
4. **Un lector de pantalla** entiende las capturas: todo `<img>` lleva `alt` (vacío solo en la ilustración decorativa). Prueba en la Tarea 3 (`check.mjs`).
5. **Google no recibe una petición por visita**: ninguna URL de Google Fonts en `dist/`. Prueba en la Tarea 2 (`check.mjs`).

---

### Task 1: El esqueleto que ya produce HTML sin JavaScript

**Files:**
- Create: `site/package.json`, `site/tsconfig.json`, `site/vite.config.ts`, `site/index.html`, `site/es/index.html`, `site/src/entry-client.tsx`, `site/src/entry-server.tsx`, `site/src/styles.ts`, `site/src/copy.ts`, `site/src/Page.tsx`, `site/src/page.css`, `site/src/theme/klara.css`, `site/prerender.mjs`, `site/check.mjs`, `site/public/favicon.svg`
- Modify: `.gitignore` (raíz del repo)

**Interfaces:**
- Produces: `copy[lang]` (`site/src/copy.ts`, tipo `PageCopy`), `Page({ lang })` (`site/src/Page.tsx`), `render(lang): string` (`site/src/entry-server.tsx`), `npm run build` → `site/dist/index.html` + `site/dist/es/index.html`, `npm run check` → `site/check.mjs`.
- La Tarea 2 rellena `klara.css`; la Tarea 3 completa `Page.tsx`, `copy.ts` y `page.css`. Esta tarea deja el hero y la cabecera, nada más.

- [ ] **Step 1: Ignorar la salida del sitio**

Añadir al final de `.gitignore` (raíz):

```
site/node_modules/
site/dist/
site/dist-ssr/
site/art/shots/*.png
```

- [ ] **Step 2: `site/package.json`**

```json
{
  "name": "klara-site",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build && vite build --ssr src/entry-server.tsx --outDir dist-ssr && node prerender.mjs",
    "check": "node check.mjs",
    "preview": "vite preview"
  },
  "dependencies": {
    "@fontsource-variable/inter-tight": "^5.3.0",
    "@fontsource-variable/jetbrains-mono": "^5.3.0",
    "@fontsource-variable/source-serif-4": "^5.3.0",
    "neobrutalistcomponents": "^1.2.0",
    "react": "^19.3.0",
    "react-dom": "^19.3.0"
  },
  "devDependencies": {
    "@types/react": "^19.2.0",
    "@types/react-dom": "^19.2.0",
    "@vitejs/plugin-react": "^6.1.2",
    "typescript": "~6.0.3",
    "vite": "^8.3.4"
  }
}
```

- [ ] **Step 3: `site/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "types": ["vite/client"]
  },
  "include": ["src"]
}
```

- [ ] **Step 4: `site/vite.config.ts`**

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

// Dos páginas estáticas (en, es). `isSsrBuild` es true en `vite build --ssr`,
// donde la entrada la pone la CLI y rollupOptions.input no debe estorbar.
export default defineConfig(({ isSsrBuild }) => ({
  plugins: [react()],
  base: './',
  build: {
    rollupOptions: isSsrBuild
      ? {}
      : {
          input: {
            en: fileURLToPath(new URL('./index.html', import.meta.url)),
            es: fileURLToPath(new URL('./es/index.html', import.meta.url)),
          },
        },
  },
  ssr: { noExternal: ['neobrutalistcomponents'] },
}));
```

- [ ] **Step 5: los dos cascarones**

`site/index.html`:

```html
<!doctype html>
<html lang="en" style="color-scheme: dark">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Klara · Your study library</title>
    <meta name="description" content="Read, speak, review. Every course is shaped to the way you learn." />
    <meta name="theme-color" content="#16181C" />
    <link rel="icon" href="./favicon.svg" type="image/svg+xml" />
    <link rel="alternate" hreflang="en" href="https://sssamuelll.github.io/klara/" />
    <link rel="alternate" hreflang="es" href="https://sssamuelll.github.io/klara/es/" />
    <link rel="alternate" hreflang="x-default" href="https://sssamuelll.github.io/klara/" />
    <meta property="og:type" content="website" />
    <meta property="og:url" content="https://sssamuelll.github.io/klara/" />
    <meta property="og:title" content="Klara · Your study library" />
    <meta property="og:description" content="Read, speak, review. Every course is shaped to the way you learn." />
    <meta property="og:image" content="https://sssamuelll.github.io/klara/og.jpg" />
    <meta name="twitter:card" content="summary_large_image" />
  </head>
  <body>
    <div id="root"><!--app--></div>
    <script type="module" src="/src/entry-client.tsx"></script>
  </body>
</html>
```

`site/es/index.html`:

```html
<!doctype html>
<html lang="es" style="color-scheme: dark">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Klara · Tu biblioteca de estudio</title>
    <meta name="description" content="Lees, hablas, repasas. Cada curso se arma a la forma en que aprendes tú." />
    <meta name="theme-color" content="#16181C" />
    <link rel="icon" href="../favicon.svg" type="image/svg+xml" />
    <link rel="alternate" hreflang="en" href="https://sssamuelll.github.io/klara/" />
    <link rel="alternate" hreflang="es" href="https://sssamuelll.github.io/klara/es/" />
    <link rel="alternate" hreflang="x-default" href="https://sssamuelll.github.io/klara/" />
    <meta property="og:type" content="website" />
    <meta property="og:url" content="https://sssamuelll.github.io/klara/es/" />
    <meta property="og:title" content="Klara · Tu biblioteca de estudio" />
    <meta property="og:description" content="Lees, hablas, repasas. Cada curso se arma a la forma en que aprendes tú." />
    <meta property="og:image" content="https://sssamuelll.github.io/klara/og.jpg" />
    <meta name="twitter:card" content="summary_large_image" />
  </head>
  <body>
    <div id="root"><!--app--></div>
    <script type="module" src="/src/entry-client.tsx"></script>
  </body>
</html>
```

`site/public/favicon.svg`: copiar `frontend/public/favicon.svg` tal cual (`cp frontend/public/favicon.svg site/public/favicon.svg`).

- [ ] **Step 6: entradas y estilos**

`site/src/styles.ts`:

```ts
// Todo el CSS entra por aquí (solo lo importa entry-client; el build SSR no lo necesita).
import '@fontsource-variable/source-serif-4/index.css';
import '@fontsource-variable/source-serif-4/wght-italic.css';
import '@fontsource-variable/inter-tight/index.css';
import '@fontsource-variable/jetbrains-mono/index.css';
import 'neobrutalistcomponents/styles.css';
import './theme/klara.css';
import './page.css';
```

`site/src/entry-client.tsx` (solo para `vite dev`; el prerender lo quita):

```tsx
import { createRoot } from 'react-dom/client';
import './styles';
import { Page } from './Page';
import type { Lang } from './copy';

const lang: Lang = document.documentElement.lang === 'es' ? 'es' : 'en';
createRoot(document.getElementById('root')!).render(<Page lang={lang} />);
```

`site/src/entry-server.tsx`:

```tsx
import { renderToStaticMarkup } from 'react-dom/server';
import { Page } from './Page';
import type { Lang } from './copy';

export function render(lang: Lang): string {
  return renderToStaticMarkup(<Page lang={lang} />);
}
```

- [ ] **Step 7: el copy, por ahora solo cabecera y hero**

`site/src/copy.ts`:

```ts
export type Lang = 'en' | 'es';

export interface PageCopy {
  /** Prefijo relativo a los assets de `public/` desde esta página. */
  assetBase: './' | '../';
  homeHref: string;
  thisLabel: string;
  otherLabel: string;
  otherLang: Lang;
  otherHref: string;
  navLabel: string;
  code: string;
  hero: { title: string; dek: string };
}

export const copy: Record<Lang, PageCopy> = {
  en: {
    assetBase: './',
    homeHref: './',
    thisLabel: 'EN',
    otherLabel: 'ES',
    otherLang: 'es',
    otherHref: './es/',
    navLabel: 'Language and code',
    code: 'Code',
    hero: {
      title: 'Your study library',
      dek: 'Read, speak, review. Every course is shaped to the way you learn.',
    },
  },
  es: {
    assetBase: '../',
    homeHref: './',
    thisLabel: 'ES',
    otherLabel: 'EN',
    otherLang: 'en',
    otherHref: '../',
    navLabel: 'Idioma y código',
    code: 'Código',
    hero: {
      title: 'Tu biblioteca de estudio',
      dek: 'Lees, hablas, repasas. Cada curso se arma a la forma en que aprendes tú.',
    },
  },
};
```

- [ ] **Step 8: la página mínima**

`site/src/Page.tsx`:

```tsx
import { NeoProvider } from 'neobrutalistcomponents';
import { copy, type Lang } from './copy';

export const REPO = 'https://github.com/sssamuelll/klara';

export function Page({ lang }: { lang: Lang }) {
  const t = copy[lang];
  return (
    <NeoProvider theme="klara" mode="dark">
      <div className="kl">
        <header className="kl-mast">
          <a className="kl-brand" href={t.homeHref}>
            <span className="kl-k" aria-hidden="true">K</span>
            <span className="kl-word">Klara</span>
          </a>
          <nav className="kl-nav" aria-label={t.navLabel}>
            <span className="kl-nav__here" aria-current="page">{t.thisLabel}</span>
            <a href={t.otherHref} lang={t.otherLang} hrefLang={t.otherLang}>{t.otherLabel}</a>
            <a href={REPO}>{t.code}</a>
          </nav>
        </header>
        <main>
          <section className="kl-hero">
            <h1 className="kl-hero__title">
              {t.hero.title}
              <span className="kl-hero__dot" aria-hidden="true">.</span>
            </h1>
            <p className="kl-hero__dek">{t.hero.dek}</p>
          </section>
        </main>
      </div>
    </NeoProvider>
  );
}
```

`site/src/theme/klara.css` (vacío de momento, con el bloque que la Tarea 2 rellena):

```css
/* Klara sobre el contrato de neobrutalistcomponents. Valores en la Tarea 2. */
@layer nbc.theme {
  [data-theme="klara"] {
    --nbc-scheme: dark;
  }
}
```

`site/src/page.css` (solo lo que necesita el esqueleto; la Tarea 3 lo completa):

```css
/* La hoja de Klara. Todo sobre los tokens --nbc-* del tema `klara`. */
html { color-scheme: dark; }
body { margin: 0; }
.kl { min-height: 100vh; background: var(--nbc-bg); color: var(--nbc-fg); font-family: var(--nbc-font-sans); }
.kl-mast { display: flex; align-items: baseline; gap: .6rem; padding: 18px 24px 14px; border-bottom: var(--nbc-border-width) var(--nbc-border-style) var(--nbc-border-color); }
.kl-brand { display: inline-flex; align-items: baseline; gap: .5rem; color: inherit; text-decoration: none; }
.kl-k { font: italic 600 30px/1 var(--nbc-font-display); color: var(--nbc-accent); }
.kl-word { font: 500 17px/1 var(--nbc-font-sans); }
.kl-nav { margin-left: auto; display: flex; gap: 1.1rem; font: 500 12px/1 var(--nbc-font-mono); letter-spacing: .04em; }
.kl-nav a { color: var(--nbc-fg-muted); text-decoration: none; }
.kl-nav a:hover { color: var(--nbc-fg); }
.kl-nav__here { color: var(--nbc-fg); }
.kl-hero { padding: 48px 24px 28px; }
.kl-hero__title { margin: 0; font: 600 54px/1.06 var(--nbc-font-display); letter-spacing: -.01em; max-width: 14ch; }
.kl-hero__dot { color: var(--nbc-accent); }
.kl-hero__dek { margin: 14px 0 0; font: 400 19px/1.45 var(--nbc-font-sans); color: var(--nbc-fg-muted); max-width: 44ch; }
```

- [ ] **Step 9: el prerender**

`site/prerender.mjs`:

```js
// Inyecta el HTML renderizado en los cascarones que dejó `vite build` y quita
// todo el JavaScript: la página publicada es HTML + CSS + imágenes.
import { readFile, writeFile, rm, readdir, unlink } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const dist = path.resolve('dist');
const { render } = await import(pathToFileURL(path.resolve('dist-ssr/entry-server.js')).href);

const pages = [
  { file: 'index.html', lang: 'en' },
  { file: 'es/index.html', lang: 'es' },
];

for (const { file, lang } of pages) {
  const p = path.join(dist, file);
  let html = await readFile(p, 'utf8');
  html = html
    .replace(/<script type="module"[^>]*><\/script>\s*/g, '')
    .replace(/<link rel="modulepreload"[^>]*>\s*/g, '')
    .replace('<!--app-->', render(lang));
  if (html.includes('<!--app-->') || /<script/i.test(html)) {
    throw new Error(`prerender: ${file} still has the placeholder or a script`);
  }
  await writeFile(p, html);
  console.log('prerender:', file);
}

// El bundle de cliente existe solo para `vite dev`.
const assets = path.join(dist, 'assets');
for (const f of await readdir(assets)) {
  if (f.endsWith('.js')) await unlink(path.join(assets, f));
}
await rm('dist-ssr', { recursive: true, force: true });
```

- [ ] **Step 10: la comprobación, primera versión**

`site/check.mjs`:

```js
// Comprobación del sitio publicado. Falla con código 1 si algo no cuadra.
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';

const dist = path.resolve('dist');
const errors = [];
const fail = (m) => errors.push(m);

const pages = [
  { file: 'index.html', mustHave: ['Your study library'] },
  { file: 'es/index.html', mustHave: ['Tu biblioteca de estudio'] },
];

for (const { file, mustHave } of pages) {
  let html;
  try {
    html = await readFile(path.join(dist, file), 'utf8');
  } catch {
    fail(`${file}: no existe`);
    continue;
  }
  if (/<script/i.test(html)) fail(`${file}: contiene <script`);
  for (const s of mustHave) if (!html.includes(s)) fail(`${file}: falta el texto «${s}»`);
}

if (errors.length) {
  for (const e of errors) console.error('✗', e);
  process.exit(1);
}
console.log('✓ check: ok');
```

- [ ] **Step 11: instalar y construir**

```bash
cd site && npm install
```
Expected: instala sin errores. Comprobar que existen `node_modules/@fontsource-variable/source-serif-4/wght-italic.css` y `node_modules/neobrutalistcomponents/dist/styles.css` (`ls` de ambos).

```bash
npm run build
```
Expected: tres fases sin error; termina con `prerender: index.html` y `prerender: es/index.html`. Si `vite build --ssr` falla resolviendo `neobrutalistcomponents`, revisar que `ssr.noExternal` está en el config (Step 4).

- [ ] **Step 12: comprobar**

```bash
npm run check
```
Expected: `✓ check: ok`. Verificar a mano una vez: `grep -c "<script" dist/index.html` → `0`; `grep -o "Your study library" dist/index.html` → una coincidencia; `grep -o 'href="[^"]*\.css"' dist/es/index.html` → empieza por `../assets/`.

- [ ] **Step 13: ver la hoja**

```bash
npm run preview
```
Abrir `http://localhost:4173/` y `http://localhost:4173/es/`: cabecera con la K bermellón, titular en Source Serif 4, fondo pizarra. (Las fuentes vienen de `dist/assets`, no de Google: comprobar en la pestaña Network que no hay peticiones a `fonts.googleapis.com`.)

- [ ] **Step 14: Commit**

```bash
cd .. && git add .gitignore site && git commit -m "feat(sitio): esqueleto del sitio en site/, HTML estático sin JavaScript en dos idiomas"
```

---

### Task 2: El tema `klara` y su contraste medido

**Files:**
- Modify: `site/src/theme/klara.css`, `site/check.mjs`

**Interfaces:**
- Produces: el bloque `[data-theme="klara"]` completo (spec § 5). `check.mjs` gana la sección de contraste (`contrastPairs`) y la de Google Fonts.

- [ ] **Step 1: la prueba de contraste, que falla porque el tema está vacío**

Añadir a `site/check.mjs`, antes del bloque final `if (errors.length)`:

```js
// ---- Contraste del tema `klara` (valores de noche) ---------------------------
const themeCss = await readFile(path.resolve('src/theme/klara.css'), 'utf8');
const tokens = {};
for (const m of themeCss.matchAll(/--(nbc-[a-z-]+):\s*([^;]+);/g)) {
  const [, name, raw] = m;
  const ld = raw.match(/light-dark\(\s*(#[0-9a-fA-F]{6})\s*,\s*(#[0-9a-fA-F]{6})\s*\)/);
  const hex = ld ? ld[2] : raw.match(/^#[0-9a-fA-F]{6}$/)?.[0];
  if (hex) tokens[name] = hex.toLowerCase();
}
const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const ratio = (a, b) => {
  const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
};
// Los diecisiete pares de src/lib/themes/contract.ts de neobrutalistcomponents 1.2.0.
const contrastPairs = [
  ['nbc-fg', 'nbc-bg', 4.5], ['nbc-fg', 'nbc-surface', 4.5], ['nbc-fg', 'nbc-surface-alt', 4.5], ['nbc-fg', 'nbc-surface-fill', 4.5],
  ['nbc-fg-muted', 'nbc-surface', 4.5], ['nbc-fg-muted', 'nbc-bg', 4.5],
  ['nbc-primary-fg', 'nbc-primary', 4.5], ['nbc-primary-fg', 'nbc-primary-fill', 4.5],
  ['nbc-accent-fg', 'nbc-accent', 4.5], ['nbc-info-fg', 'nbc-info', 4.5], ['nbc-success-fg', 'nbc-success', 4.5],
  ['nbc-warning-fg', 'nbc-warning', 4.5], ['nbc-danger-fg', 'nbc-danger', 4.5], ['nbc-danger-fg', 'nbc-danger-fill', 4.5],
  ['nbc-danger', 'nbc-surface', 4.5], ['nbc-border-color', 'nbc-bg', 3], ['nbc-focus', 'nbc-bg', 3],
];
// Los fills del tema son alias de un color sólido: se resuelven aquí.
const alias = { 'nbc-primary-fill': 'nbc-primary', 'nbc-danger-fill': 'nbc-danger', 'nbc-surface-fill': 'nbc-surface' };
const color = (name) => tokens[alias[name] ?? name];
for (const [fg, bg, min] of contrastPairs) {
  const a = color(fg), b = color(bg);
  if (!a || !b) { fail(`tema: falta --${!a ? fg : bg}`); continue; }
  const r = ratio(a, b);
  if (r < min) fail(`tema: --${fg} sobre --${bg} = ${r.toFixed(2)}:1, mínimo ${min}:1`);
}

// ---- Ninguna petición a Google Fonts ------------------------------------------
for (const { file } of pages) {
  const html = await readFile(path.join(dist, file), 'utf8').catch(() => '');
  if (/fonts\.g(oogleapis|static)\.com/.test(html)) fail(`${file}: referencia a Google Fonts`);
}
const cssDir = path.join(dist, 'assets');
for (const f of (await import('node:fs')).readdirSync(cssDir)) {
  if (!f.endsWith('.css')) continue;
  const css = await readFile(path.join(cssDir, f), 'utf8');
  if (/fonts\.g(oogleapis|static)\.com/.test(css)) fail(`assets/${f}: referencia a Google Fonts`);
}
```

- [ ] **Step 2: ver la prueba fallar**

```bash
cd site && npm run check
```
Expected: `✗ tema: falta --nbc-fg` y los demás pares, salida con código 1.

- [ ] **Step 3: el tema completo**

Sustituir `site/src/theme/klara.css` por:

```css
/* ============================================================
   KLARA — papel y tinta, de noche.
   Un tema sobre el contrato de neobrutalistcomponents (spec § 5).
   Nativo oscuro; el día queda definido en cada light-dark().
   Las familias «Variable» son las que registran los paquetes
   @fontsource-variable; las otras, el fallback si alguien
   instala las fuentes de sistema.
   ============================================================ */
@layer nbc.theme {
  [data-theme="klara"] {
    --nbc-scheme: dark;

    --nbc-font-sans: 'Inter Tight Variable', 'Inter Tight', system-ui, sans-serif;
    --nbc-font-display: 'Source Serif 4 Variable', 'Source Serif 4', Georgia, serif;
    --nbc-font-mono: 'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, monospace;
    --nbc-weight-body: 400;
    --nbc-weight-label: 500;
    --nbc-weight-display: 600;
    --nbc-label-transform: uppercase;
    --nbc-label-spacing: 0.12em;
    --nbc-display-transform: none;
    --nbc-display-spacing: -0.01em;

    --nbc-bg: light-dark(#F4EFE6, #16181C);
    --nbc-fg: light-dark(#1A1814, #ECE6D6);
    --nbc-fg-muted: light-dark(#6E6859, #B8B2A4);
    --nbc-surface: light-dark(#EFE9DD, #1C1F24);
    --nbc-surface-alt: light-dark(#E7E0D0, #242830);
    --nbc-border-color: light-dark(#6E6859, #807B70);

    --nbc-primary: light-dark(#1A1814, #ECE6D6);
    --nbc-primary-fg: light-dark(#F4EFE6, #16181C);
    --nbc-accent: light-dark(#CB4644, #E06A5E);
    --nbc-accent-fg: light-dark(#F4EFE6, #16181C);
    --nbc-info: light-dark(#CB4644, #E06A5E);
    --nbc-info-fg: light-dark(#F4EFE6, #16181C);
    --nbc-success: light-dark(#2E6B3F, #7FBF8E);
    --nbc-success-fg: light-dark(#F4EFE6, #16181C);
    --nbc-warning: light-dark(#B8862B, #E0B25A);
    --nbc-warning-fg: #1A1814;
    --nbc-danger: light-dark(#CB4644, #E06A5E);
    --nbc-danger-fg: light-dark(#F4EFE6, #16181C);
    --nbc-focus: light-dark(#CB4644, #E06A5E);

    --nbc-primary-fill: var(--nbc-primary);
    --nbc-danger-fill: var(--nbc-danger);
    --nbc-surface-fill: var(--nbc-surface);
    --nbc-texture: none;

    --nbc-border-width: 1px;
    --nbc-border-style: solid;
    --nbc-radius: 8px;
    --nbc-radius-control: 4px;
    --nbc-radius-button: 999px;
    --nbc-radius-small: 4px;

    --nbc-shadow: none;
    --nbc-shadow-lg: none;
    --nbc-shadow-press: none;
    --nbc-press: 0px;
    --nbc-press-active: 0px;
    --nbc-rotate: 0deg;
    --nbc-focus-width: 2px;
    --nbc-focus-offset: 2px;

    --nbc-duration: 140ms;
    --nbc-duration-slow: 260ms;
    --nbc-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
  }
}
```

- [ ] **Step 4: construir y ver la prueba pasar**

```bash
npm run build && npm run check
```
Expected: `✓ check: ok`. Si un par queda por debajo, el mensaje dice cuál; se ajusta solo ese token (más claro el fondo o más oscuro el texto) y se vuelve a correr. Los valores de arriba dan, a mano: `fg/bg` ≈ 13:1, `fg-muted/bg` ≈ 8:1, `accent-fg/accent` ≈ 5,4:1, `danger/surface` ≈ 5:1, `border/bg` ≈ 4,2:1.

- [ ] **Step 5: Commit**

```bash
cd .. && git add site/src/theme/klara.css site/check.mjs && git commit -m "feat(sitio): tema klara sobre el contrato de neobrutalistcomponents, contraste medido"
```

---

### Task 3: La hoja entera, con la ilustración y capturas de relleno

**Files:**
- Create: `site/art/hero.png` (la ilustración elegida, copiada desde `C:\Users\simon\AppData\Local\Temp\claude\C--Users-simon\e074251b-04de-48fc-bade-65ca3ade9101\scratchpad\klara-hero-a.png`), `site/scripts/images.py`, `site/scripts/overflow.mjs`, `site/public/hero.webp`, `site/public/og.jpg`, `site/public/shots/read.webp`, `site/public/shots/speak.webp`, `site/public/shots/review.webp` (de relleno hasta la Tarea 4)
- Modify: `site/src/copy.ts`, `site/src/Page.tsx`, `site/src/page.css`, `site/check.mjs`, `site/package.json`

**Interfaces:**
- Consumes: `Page`, `copy`, `REPO` de la Tarea 1; el tema de la Tarea 2.
- Produces: `PageCopy` completo (campos `why`, `screens`, `made`, `footer`); `python scripts/images.py` (hero + og + capturas); `node scripts/overflow.mjs`.

- [ ] **Step 1: la prueba, antes del contenido**

Añadir a `site/check.mjs`, antes del bloque final:

```js
// ---- Textos, enlaces, alt, hreflang, pesos -----------------------------------
const mustHaveMore = {
  'index.html': ['Why it exists', 'See the code', 'Run it yourself', 'Invitation only', 'mailto:samueldarioballesteros@gmail.com'],
  'es/index.html': ['Por qué existe', 'Ver el código', 'Móntala tú', 'Por invitación', 'mailto:samueldarioballesteros@gmail.com'],
};
const external = new Set();
for (const { file } of pages) {
  const html = await readFile(path.join(dist, file), 'utf8').catch(() => '');
  for (const s of mustHaveMore[file]) if (!html.includes(s)) fail(`${file}: falta «${s}»`);
  for (const l of ['en', 'es', 'x-default']) {
    if (!new RegExp(`hreflang="${l}"`).test(html)) fail(`${file}: falta hreflang ${l}`);
  }
  for (const m of html.matchAll(/<img\b[^>]*>/g)) {
    if (!/\balt=/.test(m[0])) fail(`${file}: <img> sin alt: ${m[0].slice(0, 80)}`);
  }
  for (const m of html.matchAll(/\b(?:href|src)="([^"]+)"/g)) {
    const url = m[1];
    if (/^(https?:|mailto:|#)/.test(url)) { if (/^https?:/.test(url)) external.add(url); continue; }
    const target = path.join(dist, path.dirname(file), url.split('#')[0].split('?')[0]);
    const resolved = url.endsWith('/') ? path.join(target, 'index.html') : target;
    try { await stat(resolved); } catch { fail(`${file}: ${url} no existe en dist`); }
  }
}
const limits = { 'hero.webp': 300 * 1024, 'shots/read.webp': 120 * 1024, 'shots/speak.webp': 120 * 1024, 'shots/review.webp': 120 * 1024, 'og.jpg': 200 * 1024 };
for (const [f, max] of Object.entries(limits)) {
  const s = await stat(path.join(dist, f)).catch(() => null);
  if (!s) fail(`${f}: no existe`);
  else if (s.size > max) fail(`${f}: pesa ${Math.round(s.size / 1024)} KB, máximo ${Math.round(max / 1024)} KB`);
}
for (const url of external) {
  const res = await fetch(url, { method: 'HEAD', redirect: 'follow' }).catch(() => null);
  console.log(`  ${res ? res.status : 'sin respuesta'}  ${url}`);
}
```

```bash
cd site && npm run build && npm run check
```
Expected: fallos `falta «Why it exists»`, `hero.webp: no existe`, etc. Código 1.

- [ ] **Step 2: la ilustración y las imágenes de relleno**

```bash
mkdir -p site/art/shots site/public/shots
cp "C:\Users\simon\AppData\Local\Temp\claude\C--Users-simon\e074251b-04de-48fc-bade-65ca3ade9101\scratchpad\klara-hero-a.png" site/art/hero.png
```

`site/scripts/images.py`:

```python
"""Produce hero.webp, og.jpg y las tres capturas en WebP a partir de site/art/.

  python scripts/images.py            # todo
  python scripts/images.py --shots    # solo las capturas (tras scripts/shots.mjs)

Capturas: si art/shots/<nombre>.png no existe, escribe un relleno del tamaño
final en color pizarra para que el build y la revisión no se bloqueen.
"""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ART, PUB = ROOT / "art", ROOT / "public"
SHOTS = ["read", "speak", "review"]
SHOT_W, SHOT_H = 390, 760          # CSS px; el PNG viene a 2x
FILL = (0x1C, 0x1F, 0x24)          # --nbc-surface de noche


def hero() -> None:
    im = Image.open(ART / "hero.png").convert("RGB")
    w = 2000
    h = round(im.height * w / im.width)
    big = im.resize((w, h), Image.LANCZOS)
    big.save(PUB / "hero.webp", "WEBP", quality=82, method=6)
    # og.jpg: 1200x630, recorte centrado
    ow, oh = 1200, 630
    scale = max(ow / im.width, oh / im.height)
    sw, sh = round(im.width * scale), round(im.height * scale)
    og = im.resize((sw, sh), Image.LANCZOS)
    left, top = (sw - ow) // 2, (sh - oh) // 2
    og.crop((left, top, left + ow, top + oh)).save(PUB / "og.jpg", "JPEG", quality=85, optimize=True, progressive=True)
    print("hero.webp", (PUB / "hero.webp").stat().st_size // 1024, "KB;", "og.jpg", (PUB / "og.jpg").stat().st_size // 1024, "KB")


def shots() -> None:
    (PUB / "shots").mkdir(parents=True, exist_ok=True)
    for name in SHOTS:
        src = ART / "shots" / f"{name}.png"
        out = PUB / "shots" / f"{name}.webp"
        if src.exists():
            im = Image.open(src).convert("RGB")
            # Recorte superior a 390x760 (en px CSS) manteniendo la escala 2x.
            scale = im.width / SHOT_W
            im = im.crop((0, 0, im.width, min(im.height, round(SHOT_H * scale))))
            im = im.resize((SHOT_W * 2, SHOT_H * 2), Image.LANCZOS)
            im.save(out, "WEBP", quality=82, method=6)
            print(name, "real", out.stat().st_size // 1024, "KB")
        else:
            Image.new("RGB", (SHOT_W * 2, SHOT_H * 2), FILL).save(out, "WEBP", quality=60, method=6)
            print(name, "RELLENO", out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    if "--shots" not in sys.argv:
        hero()
    shots()
```

```bash
cd site && python scripts/images.py
```
Expected: `hero.webp` por debajo de 300 KB (si pesa más, bajar `quality` a 76 y repetir), `og.jpg` por debajo de 200 KB, tres `RELLENO`.

- [ ] **Step 3: el copy completo**

Sustituir `site/src/copy.ts` por:

```ts
export type Lang = 'en' | 'es';

export interface Screen {
  key: 'read' | 'speak' | 'review';
  title: string;
  body: string;
  alt: string;
}

export interface PageCopy {
  /** Prefijo relativo a los assets de `public/` desde esta página. */
  assetBase: './' | '../';
  homeHref: string;
  thisLabel: string;
  otherLabel: string;
  otherLang: Lang;
  otherHref: string;
  navLabel: string;
  code: string;
  hero: { title: string; dek: string };
  why: { cap: string; paragraphs: string[] };
  screens: { cap: string; items: Screen[] };
  made: {
    cap: string;
    badges: string[];
    rows: [string, string][];
    alert: string;
    code: string;
    run: string;
  };
  footer: { email: string };
}

export const copy: Record<Lang, PageCopy> = {
  en: {
    assetBase: './',
    homeHref: './',
    thisLabel: 'EN',
    otherLabel: 'ES',
    otherLang: 'es',
    otherHref: './es/',
    navLabel: 'Language and code',
    code: 'Code',
    hero: {
      title: 'Your study library',
      dek: 'Read, speak, review. Every course is shaped to the way you learn.',
    },
    why: {
      cap: 'Why it exists',
      paragraphs: [
        "I'm learning German. The apps I tried asked me back every day so I wouldn't lose a streak. I wanted to have a conversation. So I built the tutor I wanted.",
        "Every day Klara writes me a short story at my level. I read it and tap the words I don't know. I read it out loud and Klara tells me which sound missed, the ö, the ch, and how to make it. Days later the words come back as cards, right before I'd forget them. No streaks, no hearts, no guilt. A magazine that learns with me.",
        "It's my own tool, and the code is open. If you want one, run it with your own keys.",
      ],
    },
    screens: {
      cap: 'What it does',
      items: [
        { key: 'read', title: 'Read', body: "Short stories in the language you're studying. Tap any word to open it: meaning, gender, context.", alt: 'Klara on a phone: a short German story with one word opened, showing its meaning and gender.' },
        { key: 'speak', title: 'Speak', body: 'You talk and Klara corrects the exact sound that missed. What you said yesterday, it remembers today.', alt: 'Klara on a phone: a spoken sentence with the missed sound marked and a hint on how to make it.' },
        { key: 'review', title: 'Review', body: "Flashcards that come back right before you'd forget. No streaks, no hearts, no guilt.", alt: 'Klara on a phone: a review card asking for the gender of a German noun.' },
      ],
    },
    made: {
      cap: "How it's made",
      badges: ['MIT', '6 languages', 'Invitation only'],
      rows: [
        ['Languages', 'six in the interface, any of them as the one you study'],
        ['Tutor', 'whichever model you give a key for: Anthropic, DeepSeek or OpenAI'],
        ['Voice', 'ElevenLabs or Inworld'],
        ['Pronunciation', 'scored sound by sound'],
        ['Runs', 'with Docker Compose and your own keys'],
        ['License', 'MIT'],
      ],
      alert: 'My instance is invitation only. To run yours, start at the README.',
      code: 'See the code',
      run: 'Run it yourself',
    },
    footer: { email: 'Email me' },
  },
  es: {
    assetBase: '../',
    homeHref: './',
    thisLabel: 'ES',
    otherLabel: 'EN',
    otherLang: 'en',
    otherHref: '../',
    navLabel: 'Idioma y código',
    code: 'Código',
    hero: {
      title: 'Tu biblioteca de estudio',
      dek: 'Lees, hablas, repasas. Cada curso se arma a la forma en que aprendes tú.',
    },
    why: {
      cap: 'Por qué existe',
      paragraphs: [
        'Estoy aprendiendo alemán. Las apps que probé me pedían volver cada día para no perder la racha. Yo quería tener una conversación. Así que construí la tutora que quería.',
        'Cada día Klara me escribe una historia corta a mi nivel. La leo y toco las palabras que no sé. La leo en voz alta y Klara me dice qué sonido falló, la ö, la ch, y cómo se hace. Días después las palabras vuelven en fichas, justo antes de que se me olviden. Sin rachas, sin corazones, sin culpa. Una revista que aprende conmigo.',
        'Es mi herramienta, y el código está abierto. Si quieres una, móntala con tus propias llaves.',
      ],
    },
    screens: {
      cap: 'Qué hace',
      items: [
        { key: 'read', title: 'Leer', body: 'Historias cortas en el idioma que estudias. Cada palabra se abre con un toque: significado, género, contexto.', alt: 'Klara en un teléfono: una historia corta en alemán con una palabra abierta, con su significado y su género.' },
        { key: 'speak', title: 'Hablar', body: 'Conversas y Klara te corrige el sonido exacto que falló. Lo que dijiste ayer lo recuerda hoy.', alt: 'Klara en un teléfono: una frase dicha con el sonido que falló marcado y una pista de cómo hacerlo.' },
        { key: 'review', title: 'Repasar', body: 'Fichas que vuelven justo antes del olvido. Sin rachas, sin corazones, sin culpa.', alt: 'Klara en un teléfono: una ficha de repaso que pregunta el género de un sustantivo alemán.' },
      ],
    },
    made: {
      cap: 'Cómo está hecha',
      badges: ['MIT', '6 idiomas', 'Por invitación'],
      rows: [
        ['Idiomas', 'seis en la interfaz, cualquiera como el que estudias'],
        ['Tutora', 'el modelo al que le des una llave: Anthropic, DeepSeek u OpenAI'],
        ['Voz', 'ElevenLabs o Inworld'],
        ['Pronunciación', 'calificada sonido por sonido'],
        ['Corre', 'con Docker Compose y tus llaves'],
        ['Licencia', 'MIT'],
      ],
      alert: 'Mi instancia es por invitación. Para montar la tuya, empieza por el README.',
      code: 'Ver el código',
      run: 'Móntala tú',
    },
    footer: { email: 'Escríbeme' },
  },
};
```

- [ ] **Step 4: la página completa**

Sustituir `site/src/Page.tsx` por:

```tsx
import { NeoProvider, Button, Badge, Card, Table, Alert } from 'neobrutalistcomponents';
import { copy, type Lang } from './copy';

export const REPO = 'https://github.com/sssamuelll/klara';
const README_SETUP = `${REPO}#local-setup`;
const MAIL = 'mailto:samueldarioballesteros@gmail.com';
const SITE = 'https://sdar.dev';

function Brand() {
  return (
    <>
      <span className="kl-k" aria-hidden="true">K</span>
      <span className="kl-word">Klara</span>
    </>
  );
}

export function Page({ lang }: { lang: Lang }) {
  const t = copy[lang];
  const asset = (p: string) => `${t.assetBase}${p}`;
  return (
    <NeoProvider theme="klara" mode="dark">
      <div className="kl">
        <header className="kl-mast">
          <a className="kl-brand" href={t.homeHref}><Brand /></a>
          <nav className="kl-nav" aria-label={t.navLabel}>
            <span className="kl-nav__here" aria-current="page">{t.thisLabel}</span>
            <a href={t.otherHref} lang={t.otherLang} hrefLang={t.otherLang}>{t.otherLabel}</a>
            <a href={REPO}>{t.code}</a>
          </nav>
        </header>

        <main>
          <section className="kl-hero">
            <h1 className="kl-hero__title">
              {t.hero.title}
              <span className="kl-hero__dot" aria-hidden="true">.</span>
            </h1>
            <p className="kl-hero__dek">{t.hero.dek}</p>
          </section>

          <figure className="kl-art">
            <img src={asset('hero.webp')} alt="" width="2000" height="848" decoding="async" fetchPriority="high" />
          </figure>

          <section className="kl-why" aria-labelledby="why">
            <h2 className="kl-cap" id="why">{t.why.cap}</h2>
            {t.why.paragraphs.map((p) => (
              <p className="kl-why__p" key={p.slice(0, 24)}>{p}</p>
            ))}
          </section>

          <section className="kl-screens" aria-labelledby="screens">
            <h2 className="kl-cap" id="screens">{t.screens.cap}</h2>
            <div className="kl-screens__grid">
              {t.screens.items.map((s) => (
                <Card key={s.key} className="kl-screen">
                  <Card.Content>
                    <div className="kl-phone">
                      <img src={asset(`shots/${s.key}.webp`)} alt={s.alt} width="390" height="760" loading="lazy" decoding="async" />
                    </div>
                  </Card.Content>
                  <Card.Header>
                    <Card.Title>{s.title}</Card.Title>
                    <Card.Description>{s.body}</Card.Description>
                  </Card.Header>
                </Card>
              ))}
            </div>
          </section>

          <section className="kl-made" aria-labelledby="made">
            <h2 className="kl-cap" id="made">{t.made.cap}</h2>
            <p className="kl-badges">
              {t.made.badges.map((b) => <Badge key={b} variant="neutral">{b}</Badge>)}
            </p>
            <Table density="compact" className="kl-table">
              <Table.Body>
                {t.made.rows.map(([k, v]) => (
                  <Table.Row key={k}>
                    <Table.HeaderCell scope="row">{k}</Table.HeaderCell>
                    <Table.Cell>{v}</Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table>
            <div className="kl-alert">
              <Alert variant="info">{t.made.alert}</Alert>
            </div>
            <p className="kl-ctas">
              <Button asChild variant="primary" size="lg"><a href={REPO}>{t.made.code}</a></Button>
              <Button asChild variant="secondary" size="lg"><a href={README_SETUP}>{t.made.run}</a></Button>
            </p>
          </section>
        </main>

        <footer className="kl-foot">
          <span className="kl-brand"><Brand /></span>
          <a href={MAIL}>{t.footer.email}</a>
          <a href={SITE}>sdar.dev</a>
        </footer>
      </div>
    </NeoProvider>
  );
}
```

Si TypeScript rechaza `className` en `Card` o `Table`, o `scope` en `Table.HeaderCell`, mirar sus props en `node_modules/neobrutalistcomponents/dist/index.d.ts`: todos extienden las props del elemento HTML que envuelven (`div`, `table`, `th`), así que el error sería de tipos de React, no de la librería.

- [ ] **Step 5: el CSS de la página completo**

Sustituir `site/src/page.css` por:

```css
/* ============================================================
   La hoja de Klara (spec § 4 y § 5). Todo sobre los tokens
   --nbc-* del tema `klara`. Una columna de 1040 px; a partir
   de 720 px las tres pantallas van en fila.
   ============================================================ */
html { color-scheme: dark; }
body { margin: 0; }

.kl {
  min-height: 100vh;
  background: var(--nbc-bg);
  /* grano de papel: dos capas, como en la app */
  background-image:
    radial-gradient(rgba(236, 230, 214, 0.035) 1px, transparent 1px),
    radial-gradient(rgba(236, 230, 214, 0.02) 1px, transparent 1px);
  background-size: 7px 7px, 11px 11px;
  background-position: 0 0, 3px 5px;
  color: var(--nbc-fg);
  font-family: var(--nbc-font-sans);
  font-size: 16px;
  line-height: 1.5;
}
.kl > header, .kl > main, .kl > footer { max-width: 1040px; margin: 0 auto; }

/* cabecera */
.kl-mast { display: flex; align-items: baseline; gap: .6rem; padding: 18px 24px 14px; border-bottom: var(--nbc-border-width) var(--nbc-border-style) var(--nbc-border-color); }
.kl-brand { display: inline-flex; align-items: baseline; gap: .5rem; color: inherit; text-decoration: none; }
.kl-k { font: italic 600 30px/1 var(--nbc-font-display); color: var(--nbc-accent); }
.kl-word { font: 500 17px/1 var(--nbc-font-sans); }
.kl-nav { margin-left: auto; display: flex; gap: 1.1rem; font: 500 12px/1 var(--nbc-font-mono); letter-spacing: .04em; }
.kl-nav a { color: var(--nbc-fg-muted); text-decoration: none; }
.kl-nav a:hover, .kl-nav a:focus-visible { color: var(--nbc-fg); }
.kl-nav__here { color: var(--nbc-fg); }

/* hero */
.kl-hero { padding: 48px 24px 28px; }
.kl-hero__title { margin: 0; font: 600 54px/1.06 var(--nbc-font-display); letter-spacing: -.01em; max-width: 14ch; text-wrap: balance; }
.kl-hero__dot { color: var(--nbc-accent); }
.kl-hero__dek { margin: 14px 0 0; font: 400 19px/1.45 var(--nbc-font-sans); color: var(--nbc-fg-muted); max-width: 44ch; }

/* ilustración sobre panel papel */
.kl-art { margin: 20px 24px 0; padding: 10px; background: #F4EFE6; border-radius: var(--nbc-radius); }
.kl-art img { display: block; width: 100%; height: auto; aspect-ratio: 2000 / 848; border-radius: var(--nbc-radius-control); }

/* rótulos */
.kl-cap { display: flex; align-items: center; gap: .75rem; margin: 0; font: var(--nbc-weight-label) 11px/1 var(--nbc-font-mono); letter-spacing: var(--nbc-label-spacing); text-transform: var(--nbc-label-transform); color: var(--nbc-fg-muted); }
.kl-cap::after { content: ""; flex: 1; height: 1px; background: var(--nbc-border-color); opacity: .5; }

/* por qué existe */
.kl-why { padding: 40px 24px 8px; }
.kl-why__p { margin: 16px 0 0; font: 400 20px/1.5 var(--nbc-font-display); max-width: 58ch; }

/* pantallas */
.kl-screens { padding: 40px 24px 8px; }
.kl-screens__grid { display: grid; grid-template-columns: 1fr; gap: 20px; margin-top: 20px; }
.kl-screen { overflow: hidden; }
.kl-phone { width: 196px; margin: 0 auto; padding: 7px; background: #000; border: var(--nbc-border-width) var(--nbc-border-style) var(--nbc-border-color); border-radius: 26px; }
.kl-phone img { display: block; width: 100%; height: auto; aspect-ratio: 390 / 760; border-radius: 19px; object-fit: cover; }

/* cómo está hecha */
.kl-made { padding: 40px 24px 48px; }
.kl-badges { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 0; }
.kl-table { margin-top: 18px; }
.kl-table th { white-space: nowrap; }
.kl-alert { margin-top: 18px; }
.kl-ctas { display: flex; flex-wrap: wrap; gap: 12px; margin: 22px 0 0; }

/* pie */
.kl-foot { display: flex; align-items: baseline; gap: 1.2rem; padding: 22px 24px 40px; border-top: var(--nbc-border-width) var(--nbc-border-style) var(--nbc-border-color); font-size: 14px; }
.kl-foot a { color: var(--nbc-fg-muted); }
.kl-foot a:hover, .kl-foot a:focus-visible { color: var(--nbc-fg); }

@media (min-width: 720px) {
  .kl-mast, .kl-hero, .kl-why, .kl-screens, .kl-made, .kl-foot { padding-left: 40px; padding-right: 40px; }
  .kl-art { margin-left: 40px; margin-right: 40px; }
  .kl-screens__grid { grid-template-columns: repeat(3, 1fr); gap: 28px; }
}
@media (max-width: 480px) {
  .kl-hero__title { font-size: 36px; }
  .kl-hero__dek { font-size: 17px; }
  .kl-why__p { font-size: 18px; }
}
@media (prefers-reduced-motion: no-preference) {
  .kl-nav a, .kl-foot a { transition: color var(--nbc-duration) var(--nbc-ease); }
}
```

- [ ] **Step 6: la prueba de desbordamiento a 360 px**

Instalar Playwright solo como herramienta local (los navegadores ya están en `D:\caches\ms-playwright`; si el build de Chromium que pide no está, `npx playwright install chromium` lo baja):

```bash
cd site && npm install -D playwright
```

`site/scripts/overflow.mjs`:

```js
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
```

Añadir a `scripts` de `site/package.json`: `"overflow": "node scripts/overflow.mjs"`.

- [ ] **Step 7: construir, comprobar, mirar**

```bash
npm run build && npm run check && npm run overflow
```
Expected: `✓ check: ok` con la lista de enlaces externos y sus códigos (200 para el repo, el README y sdar.dev), y `✓ dist/index.html` + `✓ dist/es/index.html` en overflow. Si `check` marca `hero.webp` por peso, bajar `quality` en `images.py` y repetir.

```bash
npm run preview
```
Revisión visual con Samuel a 1280 y a 390 px (`http://localhost:4173/` y `/es/`): la revista de noche con las tres tarjetas de relleno. Lo que no le cuadre se ajusta en `page.css` y se repite el paso.

- [ ] **Step 8: Commit**

```bash
cd .. && git add site && git commit -m "feat(sitio): la hoja entera: historia, pantallas, ficha, ilustración en el estilo de la app"
```

---

### Task 4: Las capturas reales

**Files:**
- Create: `site/scripts/shots.mjs`
- Modify: `site/public/shots/*.webp` (regenerados), `site/package.json` (script `shots`)

**Interfaces:**
- Consumes: `scripts/images.py --shots` (Tarea 3).
- Produces: `site/art/shots/{read,speak,review}.png` (ignorados por git) → `site/public/shots/*.webp` reales.

- [ ] **Step 1: preparar la cuenta**

Samuel, en su instancia, el mismo día: leer una historia y abrir una palabra; una conversación en Hablar con al menos una corrección; dejar fichas pendientes en Repaso. La app en modo oscuro. Sin eso, las pantallas salen vacías y la captura no sirve.

- [ ] **Step 2: el script**

`site/scripts/shots.mjs`:

```js
// Capturas reales de la instancia de Samuel para la página. Uso:
//   KLARA_EMAIL=… KLARA_PASSWORD=… node scripts/shots.mjs
// Opcional: KLARA_BASE (por defecto https://klara.sdar.dev), KLARA_STORY (id de la historia a capturar).
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
```

Añadir a `scripts` de `site/package.json`: `"shots": "node scripts/shots.mjs && python scripts/images.py --shots"`.

- [ ] **Step 3: capturar**

Lo corre Samuel con sus credenciales, desde `site/`:

```
! KLARA_EMAIL=su-correo KLARA_PASSWORD=su-clave npm run shots
```
Expected: tres `captura:` y tres `real` con sus KB. Mirar los tres PNG en `art/shots/`: si alguna muestra nombre o correo, o una pantalla vacía, repetir con otra vista (`KLARA_STORY=<id>` para Leer; `/pronunciar` en lugar de `/chat` si muestra mejor el sonido marcado, cambiando la ruta en el script).

- [ ] **Step 4: comprobar y mirar**

```bash
npm run build && npm run check && npm run overflow && npm run preview
```
Expected: todo en verde, capturas por debajo de 120 KB (si no, `quality` a 76 en `images.py`). Revisión visual con Samuel de las tres tarjetas con pantallas reales.

- [ ] **Step 5: Commit**

```bash
cd .. && git add site/scripts/shots.mjs site/package.json site/package-lock.json site/public/shots && git commit -m "feat(sitio): capturas reales de Leer, Hablar y Repasar"
```

---

### Task 5: Publicar

**Files:**
- Create: `.github/workflows/pages.yml`
- Modify: `docs/superpowers/specs/2026-10-10-sitio-github-pages-design.md` (nota de la desviación de fuentes), `README.md` (una línea con la URL del sitio)

**Interfaces:**
- Consumes: `npm run build` y `npm run check` de `site/`.
- Produces: `https://sssamuelll.github.io/klara/` y `/es/` en el aire.

- [ ] **Step 1: el workflow**

`.github/workflows/pages.yml`:

```yaml
# Construye site/ y lo publica en GitHub Pages. Es el único workflow encendido
# del repo: CI, CodeQL y Build & Deploy siguen apagados a propósito.
name: Pages

on:
  push:
    branches: [main]
    paths:
      - 'site/**'
      - '.github/workflows/pages.yml'
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: site
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: site/package-lock.json
      - run: npm ci
      - run: npm run build
      - run: npm run check
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

`check.mjs` corre en CI sin Playwright: `overflow` no entra en el workflow a propósito (Playwright no está en `npm ci` como dependencia obligatoria del build). Si `npm ci` instala `playwright` como devDependency, no descarga navegadores sin `npx playwright install`, así que no estorba.

- [ ] **Step 2: anotar la desviación en el spec y la URL en el README**

En el spec, al final de la fila D7 de la tabla de decisiones, añadir: ` Implementado con los paquetes `@fontsource-variable/*` (woff2 en `dist/assets/`), no con `public/fonts/`: mismo resultado.` Y en § 7, sustituir la línea `theme/fonts.css       @font-face locales` por `styles.ts             importa las fuentes (@fontsource-variable), la librería, el tema y page.css` y la línea `fonts/*.woff2 ...` se elimina.

En `README.md`, debajo del primer párrafo:

```markdown
Site: <https://sssamuelll.github.io/klara/> (English) · <https://sssamuelll.github.io/klara/es/> (Spanish). Source in `site/`.
```

- [ ] **Step 3: commit y PR**

```bash
git add .github/workflows/pages.yml docs/superpowers/specs/2026-10-10-sitio-github-pages-design.md README.md
git commit -m "ci(sitio): workflow de Pages para site/, el único encendido"
git push -u origin feat/sitio-pages
gh pr create --title "Sitio de Klara en GitHub Pages: la revista de noche" --body-file - <<'EOF'
La página pública de Klara en `site/`: una hoja en inglés y español, HTML estático sin JavaScript, tema `klara` sobre neobrutalistcomponents, ilustración en el estilo de la app y capturas reales. Spec: `docs/superpowers/specs/2026-10-10-sitio-github-pages-design.md`. Plan: `docs/superpowers/plans/2026-10-10-sitio-github-pages.md`.

Después del merge, Samuel enciende Actions y Pages (pasos 4 y 5 del plan) y lanza el primer despliegue a mano.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

- [ ] **Step 4: encender Actions y Pages (Samuel, después del merge)**

Son cambios de configuración del repo; el clasificador de permisos de Claude Code los bloquea, así que van con `!`:

```
! gh api -X PUT repos/sssamuelll/klara/actions/permissions -F enabled=true -f allowed_actions=all
! gh api -X POST repos/sssamuelll/klara/pages -f build_type=workflow
```
Expected: la primera no devuelve cuerpo (204); la segunda devuelve el JSON del sitio con `"build_type": "workflow"`. Comprobar que los otros tres workflows siguen apagados: `gh workflow list -R sssamuelll/klara --all` → `Pages active`, los demás `disabled_manually`.

- [ ] **Step 5: primer despliegue y comprobación**

```
! gh workflow run pages.yml -R sssamuelll/klara --ref main
```
Luego, cuando termine (`gh run list -R sssamuelll/klara --workflow pages.yml --limit 1`):

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://sssamuelll.github.io/klara/
curl -s -o /dev/null -w "%{http_code}\n" https://sssamuelll.github.io/klara/es/
curl -s https://sssamuelll.github.io/klara/ | grep -c "<script"
curl -s https://sssamuelll.github.io/klara/ | grep -o "Your study library"
```
Expected: `200`, `200`, `0`, `Your study library`. Abrir las dos URL en el teléfono y en el escritorio.

- [ ] **Step 6: anotar**

En `D:\Desktop\plan\PLAN.md`, bajo Klara en la sección 6, añadir la línea `- <fecha>: la página pública está en https://sssamuelll.github.io/klara/ (y /es/).` y una línea en la bitácora. Proponer a Samuel el enlace desde el índice de sdar.dev (otro repo, otro PR).

---

## Self-review

**Cobertura del spec.** § 1 D1–D12: D1 (sin formulario) Tareas 1 y 3; D2 (dos páginas, hreflang) Tareas 1 y 3; D3 (`site/` aparte) Tarea 1; D4 (noche) Tarea 2; D5 (tema sobre el contrato) Tarea 2; D6 (sin JS) Tarea 1 (`prerender.mjs` + `check.mjs`); D7 (fuentes propias) Tareas 1 y 2 con la desviación anotada en la Tarea 5; D8 (ilustración) Tarea 3; D9 (capturas reales) Tarea 4; D10 (Actions + workflow) Tarea 5; D11 (dominio) Tareas 1 y 5; D12 (copy) Tarea 3. § 4 (seis bloques y copy) Tarea 3. § 5 (tokens) Tarea 2. § 6 (capturas) Tarea 4. § 7 (arquitectura) Tareas 1 y 3. § 8 (publicación) Tarea 5. § 9 (pruebas) Tareas 1, 2 y 3 (`check.mjs`, `overflow.mjs`). § 10 (fallos) cubierto por `alt=""`, `aspect-ratio`, el fallo de `check` ante capturas que faltan, y Pages que conserva la versión anterior. § 11 (orden) es el orden de las tareas.

**Marcadores.** Ningún «TBD», «TODO» ni «similar a». El único paso que depende de un dato que no está en el repo es la contraseña de Samuel (Tarea 4, Step 3), que corre él.

**Tipos.** `Lang`, `PageCopy`, `Screen`, `copy`, `Page`, `REPO`, `render` se nombran igual en todas las tareas. `assetBase` es `'./' | '../'` en ambas definiciones de `PageCopy` (Tarea 1 y Tarea 3; la segunda sustituye a la primera entera).

**Review Focus.** Los cinco puntos tienen su prueba: 1 → Tarea 1 Step 10; 2 → Tarea 3 Step 6; 3 → Tarea 3 Step 1 (resolución relativa a la carpeta del HTML); 4 → Tarea 3 Step 1 (`alt`); 5 → Tarea 2 Step 1.
