# Klara — brief del sistema de diseño

**Para:** el rediseño en Claude Design.
**Fecha:** 2026-08-30.
**Estado del repo al escribir esto:** rama `main`, producción en `sha-19ad35c`.

---

## 0. La tesis, antes que nada

**Klara no necesita un estilo nuevo. Ya tiene uno, está declarado, y es bueno.**
Lo que no tiene es **un** vocabulario: tiene diez, apilados en tres generaciones.

`frontend/src/styles/tokens.css` abre así, desde mayo:

> `KLARA — DESIGN TOKENS. Editorial-print, warm analog, anti-Duolingo.`

Ese archivo ya define papel cálido, tinta casi negra, un solo acento bermellón en
oklch, una escala tipográfica editorial y una escala de movimiento con un
`--dur-breath` de 1600 ms llamado «el pulso de Klara». La disciplina es real:
**cero colores hex fuera de `tokens.css`** en 5.314 líneas de CSS.

Así que el trabajo **no es inventar una dirección**. Es cobrar la que ya está
pagada. El rediseño es **consolidación**, no invención — y ese es el encargo.

---

## 1. Qué es Klara

Una aplicación para aprender —empezó por alemán, ahora es multi-tema— construida
alrededor de tres actos que se repiten a diario:

1. **Leer** un pasaje que la app narra en voz alta, palabra por palabra.
2. **Hablar** esas frases y recibir corrección de pronunciación, por palabra.
3. **Repasar** con repetición espaciada lo que ya se vio.

Todo lo demás —el taller donde el usuario convierte sus propios textos en
material, el mapa del curso, el perfil— existe para alimentar esos tres actos.

Es mobile-first de verdad: hay una app Android nativa (Capacitor) corriendo en un
teléfono, y la web es el mismo bundle. **El teléfono es el caso principal, no una
adaptación.**

---

## 2. La evidencia: qué está roto

Auditoría del 2026-08-30 sobre `frontend/src/`:

| | |
|---|---|
| Líneas de CSS | **5.314** en 17 hojas |
| Clases declaradas | **756** |
| Clases muertas (declaradas, nunca usadas en `.tsx`) | **111** (15%) |
| Hojas que se cargan en **todas** las rutas | **14 de 17** |
| Vocabularios privados por función | **10** |
| Componentes React | 17 |
| Rutas | 22 |

### 2.1 Todo se carga siempre

`main.tsx` importa 12 hojas de golpe, y `global.css` hace `@import` de otras dos.
Resultado: **la pantalla de login descarga `finish.css` (1.021 líneas) y
`onboarding.css` (718)**. Nada está dividido por ruta.

### 2.2 Tres generaciones vivas a la vez

- **Editorial de escritorio** — `global.css` (`kapp`, `kframe`, `k-masthead`,
  `k-page`) + `pages.css`. En `pages.css` hay **45 clases muertas de 122**: el
  bloque `home*` entero (23 clases) quedó huérfano cuando la home real se mudó a
  `m3-`/`m4-`.
- **Móvil v3/v4** — `mobile3.css` («radicalmente simple: cero scroll») y
  `mobile4.css` («se apoya en mobile3.css»). Es el sistema que la gente usa hoy.
- **Por función** — diez hojas, cada una con su dialecto propio:
  `fin-*`, `kc-*`/`kac-*`, `rr-*`, `ob-*`, `ob5-*`, `gr-*`, `auth-*`,
  `landing__*`, `path__*`/`mod__*`, y `taller.css` con nombres planos.

### 2.3 El mismo átomo, diez veces

No hay un botón: hay diez maneras de hacer un botón.

| Átomo | Reimplementaciones encontradas |
|---|---|
| Botón | `k-btn`, `m3-hero`, `m3-srs button`, `kac-feedback__btn`, `rr-rate__*`, `m4-add`, `m4-upload`, botones de `fin-*` y `ob-*` |
| Botón redondo | `m3-rbtn` (`.play`, `.mic`, `.step`, `.micgrande`) |
| Ficha / tarjeta | `m3-ficha`, `rr-ficha`, `qcard`, `m4-tema` |
| Fila de lista | `m3-rowbtn`, `m3-plan li`, `m3-rows li`, `m4-tema`, `ob5-fila` |
| Barra de progreso | `m3-prog .seg`, `m3-repbar`, `m3-cefr`, `m4-bar`, `rr-prog__*`, `path__bar` |
| Encabezado de sección | `m4-sec`, `m3-top` |

**Ese cuadro es el encargo entero, resumido.**

---

## 3. Lo que NO se toca

Esto no está a discusión, y respetarlo es parte del entregable:

1. **Los valores de `tokens.css`.** La paleta, la escala tipográfica, los radios,
   las duraciones. Son la identidad y ya son correctos. El sistema nuevo se
   escribe **encima** de esos tokens, consumiéndolos con `var(--…)`.
2. **Cero hex sueltos.** La disciplina actual es casi perfecta; no se degrada.
3. **El tema oscuro.** Todo componente existe en claro y oscuro vía
   `:root[data-theme="dark"]`.
4. **La marca respirando.** `.klara-mark[data-speaking="true"]` late a
   `--dur-breath` cuando Klara habla. Es el único gesto vivo de la interfaz.
5. **El grano del papel.** `body` lleva dos `radial-gradient` de 3px y 7px. Es
   sutil a propósito y es lo que hace que no parezca una web más.

---

## 4. Los tokens, tal como son hoy

Copiados literales de `frontend/src/styles/tokens.css`. **Úsense estos valores.**

### Color — claro (papel)

```
--paper    #F4EFE6      --ink     #1A1814
--paper-2  #EFE9DD      --ink-2   #423E36
--paper-3  #E7E0D0      --ink-3   #6E6859
--rule     #D9D2C0      --ink-4   #9A9382

--accent       oklch(0.58 0.17 25)    /* bermellón, acento único */
--accent-ink   oklch(0.36 0.13 25)
--accent-wash  oklch(0.94 0.04 25)
```

### Color — oscuro (U-Bahn de noche)

```
--paper    #16181C      --ink     #ECE6D6
--paper-2  #1C1F24      --ink-2   #B8B2A4
--paper-3  #242830      --ink-3   #807B70
--rule     #2A2E36      --ink-4   #5A564E

--accent       oklch(0.72 0.15 28)
--accent-ink   oklch(0.85 0.10 30)
--accent-wash  oklch(0.28 0.07 25)
```

Ni el negro ni el blanco son puros, a propósito. El oscuro es tinta de pizarra,
no negro; el claro es papel, no blanco.

### Tipografía

```
--font-serif  "Source Serif 4", "GT Sectra", "Newsreader", Georgia, serif
--font-sans   "Inter Tight", "Söhne", -apple-system, …
--font-mono   "JetBrains Mono", "IBM Plex Mono", ui-monospace, …
```

Reparto de papeles, y es estricto:

- **Serif** = el contenido. Alemán, titulares, palabras de ficha. Cursiva para la
  voz de Klara.
- **Sans** = los controles. Botones, campos.
- **Mono** = la marginalia. Metadatos, estados, contadores. Siempre en versalitas
  con `letter-spacing: 0.08em`.

Escala: `--t-mark 14` · `--t-meta 13` · `--t-body 17` · `--t-read 22` ·
`--t-read-lg 26` · `--t-h3 28` · `--t-h2 40` · `--t-h1 56` · `--t-display 88`.

### Geometría y movimiento

```
radios   --r-xs 2px · --r-sm 4px · --r-md 8px · --r-lg 14px · --r-pill 999px
espacio  4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96
columna  --maxw-read 640px
tiempos  --dur-fast 140ms · --dur-med 260ms · --dur-slow 480ms · --dur-breath 1600ms
curvas   --ease-page cubic-bezier(0.2, 0.7, 0.2, 1)   /* pasar página */
```

Sombras: casi ninguna, y entintadas —nunca negras—. `--shadow-rest` es
prácticamente un borde de 1px.

**Radios pequeños.** El máximo normal es 8px. Nada de píldoras salvo el chip. Es
prensa, no iOS.

---

## 5. El vocabulario que hay que producir

Un componente por fila. Cada uno con **todos sus estados**, en **los dos temas**.
Los nombres actuales están para que se sepa qué se está reemplazando.

| # | Componente | Reemplaza | Estados obligatorios |
|---|---|---|---|
| 1 | **Botón** | `k-btn`, `m3-hero`, `kac-feedback__btn`, `m4-add`, `m4-upload`, botones de `fin-*` y `ob-*` | sólido · fantasma · acento · deshabilitado · cargando · con flecha |
| 2 | **Botón redondo** | `m3-rbtn` | reposo · activo · grabando (anillo que late) · deshabilitado · tres tamaños (44 / 54 / 66–74) |
| 3 | **Ficha** | `m3-ficha`, `rr-ficha`, `qcard`, `m4-tema` | frente · reverso · con ejemplo · vacía |
| 4 | **Fila** | `m3-rowbtn`, `m3-plan li`, `m3-rows li`, `ob5-fila` | pendiente · ahora · hecha · bloqueada · dominada |
| 5 | **Barra de progreso** | `m3-prog .seg`, `m3-repbar`, `m3-cefr`, `m4-bar`, `rr-prog__*` | segmentos · relleno continuo · con hitos (CEFR) |
| 6 | **Cinta de sección** | `m4-sec` | sola · con contador |
| 7 | **Marca de nivel** | `k-level` | A0–C2 |
| 8 | **Chip** | `k-chip` | reposo · seleccionado · deshabilitado |
| 9 | **Hoja inferior** | `m3-sheet` + `m3-scrim` | entrando · en reposo |
| 10 | **Barra de pestañas** | `m3-tabbar` | 2, 3 y 4 destinos · activo · con menú desplegable |
| 11 | **Línea superior** | `m3-top`, `m3-sess-top` | marca · sesión con progreso |
| 12 | **Bloque héroe** | `m3-hero` | activo · deshabilitado |
| 13 | **Nota al margen** | `m3-gloss`, `m3-corr` | glosa · corrección (tachado + acierto) |
| 14 | **Palabra puntuada** | `[data-score]` dentro de `.m3-oracion` | bien · regular · mal · activa (sonando) |
| 15 | **Error** | `k-error` | en línea |
| 16 | **La marca** | `klara-mark` | quieta · hablando |

**Regla de oro:** después de esto, ninguna pantalla define un botón, una tarjeta,
una fila ni una barra propios. Si una pantalla necesita algo que no está en la
lista, se añade **a la lista**, no a su hoja.

---

## 6. Las pantallas, y qué debe pasar con cada una

Las cinco primeras son el día del usuario. Las últimas existen y no se pueden
ignorar, pero no compiten por atención.

### 6.1 Biblioteca — `routes/Inicio.tsx`, `Portada.tsx`

El estante de temas que el usuario estudia. Ya está construido (`m4-tema`,
`m4-lib`).

**Directiva:** que se lea como estante, no como panel de control. Sin cifras que
no accionen nada. Cada tema: título en serif, estado en mono, una barra de 2px.

### 6.2 Lectura — `routes/Story.tsx`, `components/EstudiarView.tsx`

Teleprompter: una oración a la vez, centrada, sin scroll (`m3-lect`,
`m3-oracion`, 25–30px serif).

**Directiva, la más importante del brief: el pasaje ES la pantalla.** Nada
compite con él. Ni título, ni migas, ni tarjeta que lo contenga. El dock de
transporte abajo y la glosa como marginalia; nada más.

### 6.3 Hablar — `routes/Speak.tsx`, y el dock de lectura

El usuario dice la frase y cada palabra recibe color. Ya existe:
`[data-score="good|ok|bad"]` pinta un subrayado de 3px por palabra.

**Directiva: el puntaje va junto a las palabras, no en un panel aparte.** Se lee
la frase y la nota en una sola mirada. Prohibido: tabla de resultados, tarjeta de
«tu puntaje», gráfico de barras. Debe sentirse como aliento, nunca como examen.

### 6.4 Repaso — `components/RecallReviewSession.tsx`

Una ficha centrada, gigante, y las salidas debajo.

**Directiva: una carta, todo el aire, el contador como consuelo.** El «faltan N»
va pequeño y debajo, nunca como barra de presión arriba.

**Pregunta abierta para el rediseño:** hoy hay **tres** salidas (`m3-srs` es un
grid de 3). El estudio visual que originó este brief propuso **dos**. Decidir con
argumento, no por estética: cuántas salidas tiene una ficha es un juicio de SRS,
no de diseño.

### 6.5 Taller — `routes/Taller.tsx`

Donde el usuario convierte sus propios textos en material.

**Directiva:** es el único que es **herramienta de verdad**, no superficie de
lectura, y es el más difícil de mantener en calma. Merece la atención que
normalmente se va a las pantallas bonitas. Banco de trabajo, no asistente por
pasos.

### 6.6 Las otras — onboarding, auth, perfil, mapa

`onboarding.css` (718 líneas, cero clases muertas) y `finish.css` (1.021, cero
muertas) están **sanos**: se usan enteros. Su problema es solo que hablan dialecto
propio. Se traducen al vocabulario nuevo; no se rediseñan de cero.

---

## 7. Restricciones que el rediseño debe respetar

No son preferencias. Rompen la app si se ignoran.

1. **Cascarón nativo Android (Capacitor).** `targetSdk 36` fuerza edge-to-edge.
   Toda ruta de alto completo necesita `env(safe-area-inset-*)`. Ya hubo un bug
   por esto: la landing se metía bajo la barra de gestos.
2. **Objetivos táctiles ≥ 44px.** Sin excepciones, ni en la marginalia en mono.
3. **Cero scroll en sesión.** `.m3-app` es `height:100dvh; overflow:hidden`. Las
   pantallas de sesión se comprimen, no scrollean — hay un bloque
   `@media (max-height:720px)` que ya lo hace. Mantenerlo.
4. **Ancho máximo 430px** en móvil (`.m3-app`); 1180px en escritorio.
5. **Dos idiomas a la vez, siempre.** Contenido en alemán, interfaz en el idioma
   del usuario (español, inglés, alemán…). Toda maqueta debe mostrar los dos y
   sobrevivir a que el alemán sea largo: `Bundesausbildungsförderungsgesetz` no
   puede romper una fila.
6. **`prefers-reduced-motion`** pone las duraciones en 0. Ninguna información
   puede depender solo de una animación.
7. **Sin emoji.** Iconos SVG de trazo. Los tokens son editoriales; un emoji los
   contradice.
8. **Sin cromo falso.** Nunca dibujar la barra de estado de iOS («9:41 · batería
   · wifi») ni un teclado pintado. En el teléfono real se dibujan encima.

---

## 8. Qué se espera de vuelta

En este orden:

1. **La hoja de componentes** — los 16 de §5, cada uno con todos sus estados, en
   los dos temas. Esta es la entrega principal: es la fuente de verdad que hoy no
   existe.
2. **Las cinco pantallas del día** (§6.1–6.5), reconstruidas **usando solo esos
   componentes**. Si una pantalla necesita algo fuera de la hoja, es que la hoja
   está incompleta.
3. **Una nota de lo que sobra** — qué de las 111 clases muertas y de los diez
   dialectos se puede borrar, y en qué orden es seguro hacerlo.

Lo que **no** hace falta: una paleta nueva, una tipografía nueva, un logo nuevo,
ni una propuesta de marca. Eso ya está resuelto y está bien.

---

## 9. Dónde mirar en el repo

| Qué | Ruta |
|---|---|
| Tokens (la fuente de la identidad) | `frontend/src/styles/tokens.css` |
| Primitivas compartidas actuales | `frontend/src/styles/global.css` |
| Sistema móvil real | `frontend/src/styles/mobile3.css`, `mobile4.css` |
| Todas las hojas | `frontend/src/styles/` (17 archivos) |
| Componentes | `frontend/src/components/` (17) |
| Rutas | `frontend/src/routes/` (22) |
| Maqueta v4 previa | `docs/design/klara-v4/` |
| Auditoría completa que sustenta §2 | `docs/design/klara-sistema/auditoria-css.md` |
