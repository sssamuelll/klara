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

if (errors.length) {
  for (const e of errors) console.error('✗', e);
  process.exit(1);
}
console.log('✓ check: ok');
