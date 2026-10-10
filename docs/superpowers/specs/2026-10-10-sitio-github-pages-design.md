# El sitio de Klara en GitHub Pages: la revista de noche

> **Estado:** diseño aprobado en conversación el 2026-10-10, parte por parte (propósito, idiomas, enfoque, look, librería, historia, publicación). Siguiente paso: un plan de implementación (`writing-plans`).
> **Rama:** `feat/sitio-pages` (worktree `.claude/worktrees/sitio`), cortada de `main` en `2eb1ace`.
> Lo marcado [VERIFICAR] no se comprobó todavía; se comprueba en el plan, no se asume.

## 0. El pedido

> **Samuel, 2026-10-10:** «vamos a hacerle una página web a klara y la hospedamos directamente en github pages» · «una mezcla entre la A y la C» · «revista de noche y que aproveche lo evolucionado que está neobrutalistcomponents para apoyarse de él, y que por favor cuente la historia bien, porque le hace falta marketing (sin IA slop) al grano».

El mismo día Klara pasó a ser un repo público. La página es la cara pública de ese repo: cuenta qué es, por qué existe, cómo se ve y manda al código. Klara sigue siendo personal y por invitación; la página no vende, no registra, no promete un lanzamiento.

## 1. Decisiones

| # | Pregunta | Decisión | Rechazado, y por qué |
|---|---|---|---|
| D1 | Para qué | **Entender y seguir al repo.** Sin formulario, sin lista de espera. | guía de instalación completa en la página (vive en el README); lista de espera hacia la instancia de Samuel (sin tope de gasto por usuario, cada invitado gasta sus llaves) |
| D2 | Idiomas | **Inglés y español.** `/` en inglés, `/es/` en español, `hreflang` cruzado, cambio por enlace. | solo inglés; alemán (por la regla de Vina, un nativo del sector lo revisa antes de publicarse) |
| D3 | Enfoque | **La hoja:** un sitio estático propio en `site/`, aparte del frontend de la app. | una ruta del frontend React de Klara (acopla el sitio al build, al service worker y a la base de la API); solo el README |
| D4 | Look | **La revista de noche:** la estructura editorial de la dirección A en la paleta oscura de Klara (dirección C). Siempre oscura. | día y noche por ajuste del sistema; banda nocturna con cuerpo claro |
| D5 | Librería | **neobrutalistcomponents 1.2.0** con un tema propio `klara` sobre su contrato de tokens, por la vía oficial *bring your own theme*. | copiar CSS de la librería; usar un tema existente (Swiss es el más cercano pero no es papel y tinta) |
| D6 | Runtime en el navegador | **Ninguno.** React se usa en el build para producir HTML estático; la página se sirve sin JavaScript. | SPA renderizada en el cliente (un `curl` o un rastreador no ve nada; un runtime para una página sin interacción) |
| D7 | Fuentes | **Autoalojadas** en `site/public/fonts/` (Source Serif 4, Inter Tight, JetBrains Mono; las tres OFL). | Google Fonts (una petición a Google por visita desde un sitio administrado desde Alemania; la sentencia del LG München de 2022 lo hace evitable) |
| D8 | Ilustración | **Una, generada con el mismo `STYLE_PROMPT` de la app** (`backend/src/klara/services/illustration.py`): la sala de lectura con el tranvía, elegida el 2026-10-10. Optimizada a WebP. | capturar Hoy como hero (trae datos de Samuel); ilustración de otro estilo |
| D9 | Pantallas | **Capturas reales** de la instancia de Samuel: Leer, Hablar, Repasar. Ajustes nunca. | maquetas hechas con tokens (fueron solo para elegir el look) |
| D10 | Publicación | **GitHub Actions**: un workflow que construye `site/` y despliega a Pages en cada push a `main` que toque `site/**`. Actions se enciende en el repo; CI y CodeQL siguen apagados. | rama `gh-pages` empujada a mano (válida si Samuel la prefiere; cambia solo § 8) |
| D11 | Dominio | **`https://sssamuelll.github.io/klara/`.** `klara.sdar.dev` sigue siendo la app. | mover la app a otro subdominio (rompe la URL de la API que lleva la app nativa y los redirects de OAuth) |
| D12 | Copy | **Lo que Samuel ya escribió en la app se reutiliza sin cambios**; lo nuevo son dos bloques (por qué existe, ficha técnica) escritos con `solace-wren` contra la banlist. | reescribir el tagline; la promesa de lanzamiento de la portada de la app («Avísame cuando abra») |

## 2. Punto de partida (medido 2026-10-10)

- **`main` de Klara** está en `2eb1ace` (2026-10-01, «Hoy y Biblioteca»). Rutas que existen y se pueden enseñar: `Hoy`, `Biblioteca`, `Story` (leer con palabra abrible), `Speak`, `Pronunciar`, `Repaso`, `MapaCurso`, `GenderReview`, `Practice`, `Settings`. Lo de tres idiomas (`feat/tres-idiomas-nucleo`) no está en `main` y no entra en la página.
- **La portada dentro de la app** (`frontend/src/routes/Landing.tsx`) tiene copy en seis idiomas bajo `landing.*` y `waitlist.*` en `frontend/src/locales/<lang>/common.json`: tagline, apoyo, tres bloques (leer, hablar, repasar), pie. Habla de un lanzamiento que no va a ocurrir; el copy se reutiliza, la promesa no.
- **Identidad visual** (`docs/design/klara-v4/DESIGN.md`, vigente solo en identidad): papel `#F4EFE6`, tinta `#1A1814`, filete `#D9D2C0`, acento bermellón `oklch(0.58 0.17 25)`; oscuro: pizarra `#16181C`, tinta hueso `#ECE6D6`, acento `oklch(0.72 0.15 28)`. Source Serif 4 para lectura, Inter Tight para UI, JetBrains Mono para metadatos. La K cursiva en serif es la firma de Klara; no hay avatar ni logo. Tokens reales en `frontend/src/styles/*.css` (`--paper`, `--paper-2`, `--paper-3`, `--ink`, `--ink-2`, `--ink-3`, `--ink-4`, `--rule`, `--accent`, `--accent-wash`, `--accent-ink`).
- **Ilustraciones de la app**: `STYLE_PROMPT` fijo en `backend/src/klara/services/illustration.py` (grabado y riso sobre papel crema, tinta negra cálida y bermellón, luz ámbar, sin texto). Costo medido: USD 0,069 por imagen con `gemini-3.1-flash-image-preview`.
- **neobrutalistcomponents 1.2.0** (`D:\Desktop\projects\neobrutalistcomponents`, publicada en npm, React 19 como peer): dieciséis componentes sobre un contrato cerrado de tokens `--nbc-*` (`src/lib/themes/contract.ts`); cada tema es un bloque `[data-theme="x"]` con `light-dark()` en la capa `nbc.theme`; `NeoProvider` acepta cualquier nombre de tema (`theme="my-brand"` está en sus tests) y `mode` `light | dark | system`. Los temas BYO pueden omitir tokens: `tokens.css` trae valores neutros. El tema `swiss` ya usa Inter Tight y JetBrains Mono. Su propio sitio se publica a Pages con `.github/workflows/deploy-pages.yml` (`npm run build:site` → `site-dist` → `upload-pages-artifact` → `deploy-pages`) y `base: './'`.
- **Actions en Klara**: apagado a nivel de repo (`enabled: false`) desde el 2026-08-07 porque en privado se cobraba; `Build & Deploy`, `CI` y `CodeQL` están `disabled_manually`. El repo es público desde el 2026-10-10, así que los minutos vuelven a ser gratis. Pages no está configurado (la API devuelve 404).
- **React**: el frontend de la app usa React 18.3; la librería pide React 19. Por eso `site/` tiene su propio `package.json`.
- **No hay capturas** de la app en el repo. Hay una ilustración de referencia (`docs/design/klara-hoy/ilustracion-flash.jpg`) y los íconos en `frontend/public/` (`favicon.svg`, `icon-192.png`, `icon-512.png`).
- **Node local**: v24.19.0, npm 11.11.0. `.gitignore` ya ignora `.superpowers/`, `backend/dist/` y `frontend/dist/`; falta `site/dist/` y `site/node_modules/`.

## 3. Alcance

**Entra:**

- `site/`: una app mínima Vite + React 19 que produce HTML estático en dos idiomas, con el tema `klara` sobre neobrutalistcomponents.
- El copy final en inglés y español (§ 4), la ilustración (§ 5), tres capturas reales (§ 6).
- El workflow de Pages, el encendido de Actions y la configuración de Pages (§ 8).
- Una comprobación ejecutable (§ 9).
- `.gitignore` para `site/dist/` y `site/node_modules/`.

**Fuera:**

- Tocar el frontend o el backend de la app. La portada interna con su lista de espera se queda como está (otra decisión, otro día).
- Encender `CI`, `CodeQL` o `Build & Deploy`.
- Alemán u otros idiomas.
- Contribuir el tema `klara` a la librería (idea para después).
- El enlace desde el índice de sdar.dev a este sitio: es otro repo y otro PR; se propone cuando el sitio esté en el aire.
- Un dominio propio.

## 4. La página: estructura y copy

Una sola hoja larga, seis bloques. Inglés es la versión raíz; el español es traducción de Samuel donde ya existía y de `solace-wren` donde es nuevo. Lo marcado **(app)** viene tal cual de `frontend/src/locales/{en,es}/common.json`.

### 4.1 Cabecera

La K cursiva en Source Serif 4, color acento, y la palabra «Klara» en Inter Tight. A la derecha, en mono y versalitas: el idioma activo en tinta, el otro como enlace, y «Code» / «Código» al repo. Sin menú.

### 4.2 Hero **(app)**

- EN: **Your study library.** / Read, speak, review. Every course is shaped to the way you learn.
- ES: **Tu biblioteca de estudio.** / Lees, hablas, repasas. Cada curso se arma a la forma en que aprendes tú.

El punto final del tagline va en color acento. Debajo, la ilustración (§ 5) a todo el ancho de la columna, dentro de un panel color papel sobre la pizarra, como hace el héroe de la app en modo oscuro.

### 4.3 Por qué existe (nuevo)

Rótulo mono: «Why it exists» / «Por qué existe». Texto en Source Serif 4, 20px, máximo 58 caracteres por línea.

EN:

> I'm learning German. The apps I tried asked me back every day so I wouldn't lose a streak. I wanted to have a conversation. So I built the tutor I wanted.
>
> Every day Klara writes me a short story at my level. I read it and tap the words I don't know. I read it out loud and Klara tells me which sound missed, the ö, the ch, and how to make it. Days later the words come back as cards, right before I'd forget them. No streaks, no hearts, no guilt. A magazine that learns with me.
>
> It's my own tool, and the code is open. If you want one, run it with your own keys.

ES:

> Estoy aprendiendo alemán. Las apps que probé me pedían volver cada día para no perder la racha. Yo quería tener una conversación. Así que construí la tutora que quería.
>
> Cada día Klara me escribe una historia corta a mi nivel. La leo y toco las palabras que no sé. La leo en voz alta y Klara me dice qué sonido falló, la ö, la ch, y cómo se hace. Días después las palabras vuelven en fichas, justo antes de que se me olviden. Sin rachas, sin corazones, sin culpa. Una revista que aprende conmigo.
>
> Es mi herramienta, y el código está abierto. Si quieres una, móntala con tus propias llaves.

Cada afirmación tiene su función detrás: historia a nivel (`NewStory`, nivel CEFR del perfil), palabra abrible (`WordPopover`), sonido que falló y cómo hacerlo (`pronunciation` + `phonetic_hints`), fichas antes del olvido (`srs_engine`).

### 4.4 Tres pantallas **(app)**

Tres `Card` en fila (una columna en teléfono). Cada una: rótulo mono, la captura dentro de un marco de teléfono dibujado en CSS, título en serif, texto.

- EN: **Read** · Short stories in the language you're studying. Tap any word to open it: meaning, gender, context. / **Speak** · You talk and Klara corrects the exact sound that missed. What you said yesterday, it remembers today. / **Review** · Flashcards that come back right before you'd forget. No streaks, no hearts, no guilt.
- ES: **Leer** · Historias cortas en el idioma que estudias. Cada palabra se abre con un toque: significado, género, contexto. / **Hablar** · Conversas y Klara te corrige el sonido exacto que falló. Lo que dijiste ayer lo recuerda hoy. / **Repasar** · Fichas que vuelven justo antes del olvido. Sin rachas, sin corazones, sin culpa.

### 4.5 Cómo está hecha (nuevo)

Rótulo mono: «How it's made» / «Cómo está hecha». Una `Table` de dos columnas, densidad compacta, sin rayas:

| EN | | ES | |
|---|---|---|---|
| Languages | six in the interface, any of them as the one you study | Idiomas | seis en la interfaz, cualquiera como el que estudias |
| Tutor | whichever model you give a key for: Anthropic, DeepSeek or OpenAI | Tutora | el modelo al que le des una llave: Anthropic, DeepSeek u OpenAI |
| Voice | ElevenLabs or Inworld | Voz | ElevenLabs o Inworld |
| Pronunciation | scored sound by sound | Pronunciación | calificada sonido por sonido |
| Runs | with Docker Compose and your own keys | Corre | con Docker Compose y tus llaves |
| License | MIT | Licencia | MIT |

Debajo, un `Alert` variante info, sin botón de cierre:

- EN: My instance is invitation only. To run yours, start at the README.
- ES: Mi instancia es por invitación. Para montar la tuya, empieza por el README.

Y dos `Button`: primario «See the code» / «Ver el código» → `https://github.com/sssamuelll/klara`; secundario «Run it yourself» / «Móntala tú» → `https://github.com/sssamuelll/klara#local-setup` (el ancla de «## Local setup», comprobada en el README de `main`).

Tres `Badge` junto al rótulo: «MIT», «6 languages» / «6 idiomas», «Invitation only» / «Por invitación».

### 4.6 Pie **(app)**

Una línea: la K cursiva, «Klara», y el enlace «Email me» / «Escríbeme» a `mailto:samueldarioballesteros@gmail.com` (el mismo correo que ya muestra la portada de la app). Un segundo enlace discreto a `https://sdar.dev`. Sin año, sin copyright.

### 4.7 Metadatos

`<title>`: «Klara · Your study library» / «Klara · Tu biblioteca de estudio». `description`: la línea de apoyo del hero. `og:image`: la ilustración en 1200×630 recortada del mismo archivo. `lang` correcto en cada página, `hreflang` `en`, `es` y `x-default` (→ `/`). `theme-color` `#16181C`. Favicon: `frontend/public/favicon.svg` copiado a `site/public/`.

## 5. El tema `klara`

Un solo archivo `site/src/theme/klara.css` con un bloque `[data-theme="klara"]` en la capa `nbc.theme`, más `site/src/theme/fonts.css` con los `@font-face` locales. Nativo oscuro. Los valores de día se declaran igual para que `light-dark()` sea completo, aunque la página fije `mode="dark"`.

| Token | Valor (`light-dark(día, noche)`) | De dónde sale |
|---|---|---|
| `--nbc-scheme` | `dark` | D4 |
| `--nbc-font-display` | `'Source Serif 4', Georgia, serif` | DESIGN.md |
| `--nbc-font-sans` | `'Inter Tight', system-ui, sans-serif` | DESIGN.md |
| `--nbc-font-mono` | `'JetBrains Mono', ui-monospace, monospace` | DESIGN.md |
| `--nbc-weight-body` / `-label` / `-display` | `400` / `500` / `600` | la app |
| `--nbc-label-transform` / `-spacing` | `uppercase` / `0.12em` | el `k-cap` de la app |
| `--nbc-display-transform` / `-spacing` | `none` / `-0.01em` | el `k-hero__title` |
| `--nbc-bg` | `light-dark(#F4EFE6, #16181C)` | `--paper` |
| `--nbc-fg` | `light-dark(#1A1814, #ECE6D6)` | `--ink` |
| `--nbc-fg-muted` | `light-dark(#6E6859, #B8B2A4)` | `--ink-3` día, `--ink-2` noche |
| `--nbc-surface` | `light-dark(#EFE9DD, #1C1F24)` | `--paper-2` |
| `--nbc-surface-alt` | `light-dark(#E7E0D0, #242830)` | `--paper-3` |
| `--nbc-border-color` | `light-dark(#6E6859, #807B70)` | `--ink-3` (no el filete: los bordes de control necesitan 3:1) |
| `--nbc-primary` / `--nbc-primary-fg` | `light-dark(#1A1814, #ECE6D6)` / `light-dark(#F4EFE6, #16181C)` | tinta sobre papel |
| `--nbc-accent` / `--nbc-accent-fg` | `light-dark(#CB4644, #E06A5E)` / `light-dark(#F4EFE6, #16181C)` | bermellón |
| `--nbc-info` / `--nbc-info-fg` | igual que el acento | un solo acento (DESIGN.md) |
| `--nbc-success` / `-fg` | `light-dark(#2E6B3F, #7FBF8E)` / `light-dark(#F4EFE6, #16181C)` | [VERIFICAR contraste] |
| `--nbc-warning` / `-fg` | `light-dark(#B8862B, #E0B25A)` / `#1A1814` | [VERIFICAR contraste] |
| `--nbc-danger` / `-fg` | igual que el acento | |
| `--nbc-focus` | igual que el acento | |
| `--nbc-texture` | `none` | el grano de papel va en la página, no en los componentes |
| `--nbc-border-width` / `-style` | `1px` / `solid` | hairlines |
| `--nbc-radius` / `-control` / `-button` / `-small` | `8px` / `4px` / `999px` / `4px` | `--r-md`, `--r-sm`, `--r-pill` |
| `--nbc-shadow*`, `--nbc-press*`, `--nbc-rotate` | `none` / `0px` / `0deg` | sin sombras (DESIGN.md) |
| `--nbc-duration` / `-slow` / `--nbc-ease` | `140ms` / `260ms` / `cubic-bezier(0.2, 0.8, 0.2, 1)` | `--dur-fast`, `--dur-med`, `--ease-out` |

Pares de contraste que la comprobación (§ 9) calcula con la fórmula WCAG 2.2 sobre los valores de noche: los diecisiete de `CONTRAST_PAIRS` del contrato. Los que no lleguen se ajustan en el plan, no en la página.

Lo que es de la página y no del tema (`site/src/page.css`): la cabecera, el hero (54px en escritorio, 36px en teléfono), el panel papel de la ilustración, el grano de papel en `body` (dos `radial-gradient`, como la app), el marco de teléfono, la rejilla de tres columnas que pasa a una por debajo de 720px, el pie. Todo con los mismos tokens `--nbc-*`.

## 6. Capturas

Tres, de la instancia de Samuel en `klara.sdar.dev`, tomadas con Chrome y su sesión, con la app en modo oscuro para que casen con la noche:

| Pantalla | Ruta | Qué se ve | Archivo |
|---|---|---|---|
| Leer | `/story/<id>` | una historia en alemán con una palabra abierta (el popover) | `site/public/shots/read.webp` |
| Hablar | `/chat` (la ruta de `Speak.tsx` en `main`; `/pronunciar` como alternativa si muestra mejor el sonido marcado) | una frase dicha, con el sonido marcado y la pista fonética | `site/public/shots/speak.webp` |
| Repasar | `/repaso` | una ficha de género en pantalla | `site/public/shots/review.webp` |

Viewport 390×844 a 2×, recortadas a 390×760 (sin la barra de estado del teléfono, que no existe en el navegador), WebP calidad 82, menos de 120 KB cada una [VERIFICAR peso]. Ajustes no se captura. Si una pantalla muestra el nombre o el correo de Samuel, se toma otra vista; nada se retoca.

Mientras no existan, el build usa tres imágenes de relleno del mismo tamaño en color `--nbc-surface` para que la página se pueda construir y revisar.

## 7. Arquitectura de `site/`

```
site/
  package.json            react 19, react-dom 19, neobrutalistcomponents ^1.2.0, vite, @vitejs/plugin-react, typescript
  vite.config.ts          base './', build de cliente (solo CSS y assets) y build SSR (prerender)
  index.html              cascarón EN: <html lang="en">, metadatos, <div id="root"><!--app--></div>
  es/index.html           cascarón ES
  prerender.mjs           importa el build SSR, renderToStaticMarkup(<Page lang/>) y lo inyecta en los dos cascarones
  src/
    Page.tsx              la hoja entera, un componente puro que recibe lang
    copy.ts               todo el texto en en/es, tipado, una sola fuente
    entry-server.tsx      export { render(lang) }
    page.css              estilos de la página sobre los tokens --nbc-*
    theme/klara.css       el tema (§ 5)
    theme/fonts.css       @font-face locales
  public/
    fonts/*.woff2         Source Serif 4 (var, roman + italic), Inter Tight (var), JetBrains Mono (400, 500)
    hero.webp             la ilustración (≈ 2000 px de ancho, menos de 300 KB) [VERIFICAR peso]
    og.jpg                1200×630
    shots/*.webp          § 6
    favicon.svg
  check.mjs               § 9
  dist/                   salida (ignorada por git)
```

- **Build:** `npm run build` = `vite build` (cliente: procesa `page.css`, `klara.css`, `styles.css` de la librería y los assets con hash, y deja en `dist/` los dos cascarones con su `<link>` al CSS y un `<script type="module">`) + `vite build --ssr src/entry-server.tsx --outDir dist-ssr` + `node prerender.mjs` (lee cada cascarón de `dist/`, le quita el `<script type="module">` y el `modulepreload`, inyecta el HTML de `renderToStaticMarkup(<Page lang/>)` en lugar de `<!--app-->`, y lo reescribe en su sitio; al final borra `dist-ssr/`). Resultado: HTML + CSS + imágenes, cero JavaScript servido.
- **Dev:** `vite` sirve la página con React en el cliente solo para iterar el diseño en caliente; el entregable es el prerender. [VERIFICAR que `renderToStaticMarkup` de los componentes usados no emite nada que dependa del navegador; `Dialog` y `Tooltip` no se usan.]
- El `NeoProvider` envuelve toda la hoja con `theme="klara"` y `mode="dark"`; `<html>` lleva `color-scheme: dark` para que barras y controles nativos casen.
- `copy.ts` es la única fuente del texto; `Page.tsx` no lleva literales.
- Sin dependencias fuera de las listadas. Sin enrutador, sin estado, sin analítica.

## 8. Publicación

1. `.github/workflows/pages.yml`, calcado del `deploy-pages.yml` de la librería: en `push` a `main` con `paths: ['site/**', '.github/workflows/pages.yml']` y en `workflow_dispatch`; `node 22`; `npm ci` y `npm run build` dentro de `site/`; `upload-pages-artifact` con `site/dist`; job `deploy` con `deploy-pages@v4`, `concurrency: pages`, `cancel-in-progress: false`.
2. Encender Actions en el repo: Settings → Actions → General → «Allow all actions», o `gh api -X PUT repos/sssamuelll/klara/actions/permissions -F enabled=true -f allowed_actions=all` (lo corre Samuel: el clasificador de permisos de Claude Code bloquea los cambios de configuración del repo, como pasó con la visibilidad). Los tres workflows viejos siguen `disabled_manually`; solo `pages.yml` corre.
3. Pages: Settings → Pages → Source «GitHub Actions», o `gh api -X POST repos/sssamuelll/klara/pages -f build_type=workflow`.
4. El primer despliegue se lanza a mano con `workflow_dispatch` desde `main` después del merge, y se comprueba `https://sssamuelll.github.io/klara/` y `/es/`.

Si Samuel prefiere la rama a mano: `npm run build` local y `git subtree push --prefix site/dist origin gh-pages`, Pages con Source «Deploy from a branch» → `gh-pages` `/`. Nada más cambia.

## 9. Pruebas

Una sola comprobación ejecutable, `node site/check.mjs`, que corre después del build y falla si:

- falta `dist/index.html` o `dist/es/index.html`, o alguno contiene `<script`;
- el HTML en inglés no contiene «Your study library» o el español no contiene «Tu biblioteca de estudio»;
- algún `href` o `src` relativo apunta a un archivo que no existe en `dist/`;
- `hreflang` no trae `en`, `es` y `x-default`;
- alguno de los diecisiete pares de contraste del contrato, calculado sobre los valores de noche de `klara.css`, queda por debajo de su mínimo;
- `hero.webp` pesa más de 300 KB o alguna captura más de 120 KB.

Los enlaces externos (repo, README, sdar.dev, mailto) se listan en la salida con su código HTTP, sin fallar el build por ellos.

Revisión visual: capturas de `dist/` a 390 y 1280 px de ancho con el navegador, antes de pedir el merge, para que Samuel vea la hoja real y no la maqueta.

## 10. Cuando algo falla

| Situación | Qué pasa |
|---|---|
| Una fuente no carga | el `font-family` cae a Georgia / system-ui / ui-monospace; la hoja sigue legible |
| La ilustración no carga | el panel papel conserva su `aspect-ratio` 21:9 y queda vacío; `alt=""` porque el titular está encima |
| Una captura no existe en el build | el build falla por § 9, no se publica una hoja con huecos |
| El workflow falla | Pages conserva la versión anterior; el error se ve en Actions |
| El visitante entra a `/klara/es` sin barra final | Pages sirve `es/index.html` igual |

## 11. Orden de construcción

1. **El tema y la hoja con relleno.** `site/` con `package.json`, Vite, `klara.css`, `fonts.css`, `copy.ts`, `Page.tsx`, `page.css`, la ilustración optimizada, tres capturas de relleno, el prerender y `check.mjs` en verde. Revisión visual con Samuel.
2. **Las capturas reales** (§ 6), y la revisión visual otra vez.
3. **La publicación** (§ 8): workflow, Actions, Pages, primer despliegue, comprobación de las dos URL.
4. **Después, aparte:** el enlace desde el índice de sdar.dev.

## 12. Riesgos y perillas

- **El contraste del tema.** Los valores de noche de `--ink-3` y del acento sobre pizarra pasan de 4,4:1 y 6:1 a ojo; la comprobación lo mide. Si algún par de estado (éxito, aviso) no llega, se ajusta ese token y nada más.
- **`light-dark()` y `color-scheme`.** `light-dark()` resuelve según `color-scheme`; la librería lo fija por `data-mode`. Con `mode="dark"` en el provider y `color-scheme: dark` en `<html>`, no hay versión clara que se cuele.
- **Las capturas traen datos.** Son de la cuenta de Samuel; se eligen vistas sin nombre ni correo y no se retocan. Si no hay una vista limpia de Hablar, se graba una frase nueva neutral antes de capturar.
- **Peso.** La ilustración original pesa 3,8 MB en PNG; en WebP a 2000 px queda en el orden de 200 a 300 KB [VERIFICAR]. La comprobación pone el techo.
- **Actions encendido.** Solo corre `pages.yml`; los otros tres siguen apagados por nombre. Si Samuel no quiere Actions, la rama a mano del § 8 cuesta lo mismo.
- **La librería evoluciona.** `^1.2.0` fija la mayor; un cambio de contrato en 2.x no entra solo.
