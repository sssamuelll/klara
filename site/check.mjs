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
