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
