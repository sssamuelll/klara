# design-sync — notas de Klara

## Lo que hace raro a este repo

- **Klara no es una librería de componentes, es una app Vite privada.**
  `frontend/package.json` es `"private": true` y no tiene `main`/`module`/
  `exports`, así que no hay entrada de `dist/` de librería. No busques una.
- **Los 17 componentes son `export default`, cero exports nombrados.** El modo
  synth del convertidor hace `export * from` de cada `.tsx`, y eso **no**
  reexporta defaults: sin barrel el bundle sale vacío. Por eso existe
  `frontend/.ds-entry.tsx`, que los reexporta nombrados. Es la entrada real
  (`cfg.entry`), no una reimplementación.
- **Los estilos los importa el barrel, no `cfg.cssEntry`.** Se intentó primero
  con `cssEntry` apuntando a una hoja de `@import`s: el convertidor la **anexa
  literal** al final de `_ds_bundle.css`, y esas rutas relativas no resuelven
  desde la raíz del bundle (`_ds_bundle.css` acabó con 12 KB en vez de 146 KB).
  La vía buena es que `.ds-entry.tsx` importe las hojas en el mismo orden que
  `main.tsx`, y que esbuild las empaquete igual que la app.
- **`cfg.tokensGlob` es inerte aquí.** `copyTokens()` sale temprano si no hay
  `tokensPkg`, y los tokens de Klara no son un paquete npm: viven en
  `src/styles/tokens.css` y viajan inlineados vía el `@import` de `global.css`.
  `tokens/` queda vacío a propósito; validate igual reporta 75 tokens definidos.

## ⚠️ Riesgos de re-sync

- **El arreglo de charset del servidor del arnés hay que reponerlo.** Los
  scripts montados en `.ds-sync/` se recopian en cada re-sync y el parche se
  pierde. Sin él, `package-validate.mjs` falla con
  `[BUNDLE_EXPORT] 15/15 not a component on window.Klara`, que es un **falso
  negativo**: el bundle está bien.

  Causa: el bundle contiene caracteres no-ASCII (13 líneas — comentarios en
  español y, la que mata, un rango de diacríticos combinantes en el regex de
  `matchesLoose` de `StoryFinish.tsx`). El fuente lo tiene escapado
  (`\u0300-\u036f`) pero **esbuild lo emite como carácter literal**. El servidor
  local mandaba `text/javascript` sin `charset`, el navegador lo leía como
  Latin-1, y el regex reventaba con `Range out of order in character class`,
  matando la evaluación del bundle entero. Poner `<meta charset>` en la página
  NO basta: para un `<script src>` externo manda la cabecera HTTP.

  Reponer en `.ds-sync/storybook/http-serve.mjs`: añadir `; charset=utf-8` a los
  tipos de texto del mapa `MIME` **y** al `Content-Type` de la ruta raíz `/`.

  Las previews sí declaran `<meta charset="utf-8">`, por eso el render check
  pasa 15/15 aunque el smoke de exports falle. Si algún día un diseño hecho con
  este sistema aparece roto, esto es lo primero que hay que mirar.

- **Chromium no está en la ruta por defecto.** Hay un `PLAYWRIGHT_BROWSERS_PATH`
  apuntando a `D:\caches\ms-playwright`. Ya hay varias versiones descargadas;
  `npx playwright install chromium` desde `.ds-sync/` funciona.

- **Windows + finales de línea.** El repo va con `core.autocrlf=true`. Si
  editas un fuente con un script, escribe con `newline="\r\n"` o dejarás el
  archivo entero en LF y ensuciarás el árbol (`scripts/deploy-prod.sh` se niega
  a desplegar con el árbol sucio).

## Componentes excluidos, y por qué

`componentSrcMap` los pone en `null`:

- `NativeChrome` — hace `return null`. Solo efectos de Capacitor (splash, botón
  atrás). No hay nada que renderizar.
- `ProtectedRoute` — devuelve `<Navigate>`. Es un guardián de rutas.

Los otros 15 sí tienen UI.

## Contexto que necesitan las previews

Casi todo componente de Klara lee **router** (`useNavigate`, `useLocation`,
`useParams`) e **i18n** (`useTranslation`). El i18n se resuelve solo: el barrel
hace `import "./src/i18n"` y ese módulo llama a `i18n.init()` como efecto, así
que queda vivo sin proveedor. El router sí hace falta envolverlo.

## Dónde está el brief

`cfg.guidelinesGlob` apunta a `../docs/design/klara-sistema/*.md`, que sube
`BRIEF.md` (el encargo del rediseño) y `auditoria-css.md` (las cifras que lo
sustentan) a `guidelines/`. Si el brief se mueve, actualiza ese glob.
