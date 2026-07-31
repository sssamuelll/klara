# Klara — Dirección de Diseño

> **Estado (2026-07-31):** superseded en layout por el mockup v4 (`Klara App v4.html` + mobile3/4).
> De este documento sigue vigente SOLO la identidad: tipografía, paleta papel/tinta, un acento,
> anti-referencias. Las decisiones por pantalla de abajo describen una iteración anterior.

## Tesis en una línea

**Klara es una revista que aprende contigo, no un juego que te castiga.**

Editorial-print con alma analógica. Anti-Duolingo militante: sin streaks, sin corazones, sin gamification con guilt. La tipografía hace el trabajo pesado; el color es accent, no espectáculo.

---

## Identidad visual

### Klara como personaje

**Marca tipográfica.** Klara se manifiesta como una **`K` cursiva en serif** (`Source Serif 4`, italic). Aparece:

- En el masthead, junto al wordmark — siempre presente, nunca al frente.
- En la firma de cada historia (`Escrita por Klara · 4 de mayo`), tipo columnista.
- En el footer del Home como sello editorial.
- **Cuando "habla"** (audio TTS sonando), pulsa con un halo bermellón (`klara-breath`, ciclo de 1.6s, escala 0.85→1.05, opacidad 0→0.22). Es la única señal visual de presencia activa. Respeta `prefers-reduced-motion`.

Sin avatar, sin forma abstracta, sin pulpo, sin búho. Klara es una firma, no un personaje.

### Tipografía

| Rol | Familia | Variable |
|---|---|---|
| Lectura (alemán protagonista) | **Source Serif 4** (var.) | `--font-serif` |
| UI, botones, copy secundario | **Inter Tight** | `--font-sans` |
| Metadata, marginalia, badges | **JetBrains Mono** | `--font-mono` |

Source Serif 4 fue elegida porque tiene presencia editorial sin ser cliché, soporta los caracteres alemanes con personalidad (las `ä`, `ö`, `ü`, `ß` se ven hechas para alemán), y su versión variable permite finos ajustes de peso sin múltiples archivos.

### Paleta

**Light — papel:**
- `--paper` `#F4EFE6` — fondo (hueso cálido, no blanco puro)
- `--ink` `#1A1814` — texto (tinta cálida, no negro puro)
- `--rule` `#D9D2C0` — hairlines y bordes
- `--accent` `oklch(0.58 0.17 25)` — bermellón (Klara, focus, audio fill)

**Dark — U-Bahn nocturno:**
- `--paper` `#16181C` — slate-ink, jamás `#000`
- `--ink` `#ECE6D6` — off-white cálido
- `--accent` `oklch(0.72 0.15 28)` — bermellón aclarado

Un único acento. Sin gradientes. Sin glow. Sin glassmorphism. El "color" del producto es el papel y la tinta.

**Grano de papel:** dos capas de `radial-gradient` semi-transparentes en `body` para textura sutil. Imperceptible salvo por la sensación.

---

## Decisiones por pantalla

### Home — repensado

**No son 3 cards.** Es una **portada editorial**:

1. **Fecha grande** en mono, tipo encabezado de diario (`LUN 04 MAY 2026 · NÜRNBERG`).
2. **Saludo grande** en serif (56px), con el nombre del usuario en *italic* — Samuel está en cursiva, es el sujeto.
3. Una línea sobria: *"Tres minutos. Sin apuro."* — la voz de Klara.
4. **Historia de hoy** como **feature article**: badge de nivel, título grande, dek (subtítulo) en italic, footer con minutos/palabras/nuevas + link "Leer →".
5. Tres acciones secundarias como **lista numerada** (`01`, `02`, `03`), cada una con título en serif y dek en sans. Hover desplaza 6px hacia la derecha — gesto editorial.
6. Al pie, la firma `Klara — Edición Nürnberg`.

**Por qué:** 3 cards obliga a una decisión paralela. La portada editorial **propone** una historia (la de hoy) y deja las otras opciones al alcance pero subordinadas. Eso baja la carga cognitiva (TDAH-friendly) sin forzar nada.

### `/story/:id` — pantalla estrella

La decisión editorial fuerte: **el alemán manda, el español es marginalia.**

**Tres modos** (toggle visible, persiste por usuario):

- **Inmersivo** — solo alemán. Para releer.
- **Marginalia** — alemán protagonista, español en mono pequeño al margen derecho en desktop / como glosa con regla izquierda en mobile. *Default.* Mezcla la lectura corrida con la consulta sin distraer.
- **Paralelo** — español en italic debajo de cada oración. Para A0/A1 o sesiones difíciles.

**Cada palabra es tappeable.** Hover muestra wash bermellón (`--accent-wash`); tap abre **WordPopover** con:
- Artículo coloreado (der/die/das — azul / rojo / verde, sutil) + lemma en serif grande.
- Botón circular de audio (negro tinta).
- Traducción.
- Ejemplo en contexto (DE en serif + ES en mono).
- Botón `+ Repaso` para mandar la palabra a SRS.
- POS (sustantivo, verbo, etc.) en italic al pie.

**Audio bar full-width** entre header y body, con play/pause pill, track de progreso (fill bermellón), y tiempo en tabular-nums.

**Lista de palabras nuevas** al final, cada una con toggle `+ Repaso` / `✓ En repaso`.

**Nada de streaks.** Nada de "completaste tu objetivo del día". Solo la historia, las palabras, y dos botones al pie: *Otra historia* y *Volver al inicio*.

### `/story/new`

Input grande tipo manuscrito (serif 26px, sin border, solo regla inferior que se oscurece al focus). Placeholder en italic: *"Una panadería un sábado a las 8…"*.

**Chips hiperlocales de Nürnberg** debajo: *Panadería un sábado, Cita en el Bürgeramt, U-Bahn averiada, Comprando un Deutschlandticket, Vecino que toca timbre, Médico de cabecera*. Abrazan el nicho — no son genéricos.

Dos botones: **Generar historia** (primary, ink) + **Sorprendeme** (ghost). Al pie, una línea con `KlaraMark` y *"Nivel detectado: A2 → B1"* — Klara está observando pero sin presión.

---

## Sistema

### Espaciado

Escala de 4px: `4, 8, 12, 16, 24, 32, 48, 64, 96`. Suelo de 22px en mobile y 80px en desktop para los gutters de página. Columnas de lectura tope `--maxw-read: 640px`.

### Geometría

- Esquinas: 2 / 4 / 8 / 14 px y `pill`. Casi nada redondeado — `2px` y `4px` dominan. Botones cuadrados editoriales, no pill-shaped salvo el `play` y los chips.
- Hairlines de 1px en `--rule`, no shadows. Las dos sombras (`--shadow-rest`, `--shadow-pop`) están reservadas para popovers.

### Motion

- Easings con peso: `--ease-page` (cubic-bezier 0.2, 0.7, 0.2, 1) para transiciones de página tipo paso de página.
- Duraciones: `140ms` (microacciones), `260ms` (defaults), `480ms` (page-in).
- `klara-breath` 1600ms — el latido de Klara cuando habla.
- **`prefers-reduced-motion: reduce`** corta todas las duraciones a 0ms.

### Accesibilidad

- Focus ring de 2px en `--accent` con offset de 3px, visible en cualquier fondo.
- Contraste: ink/paper en light = ~14:1 (AAA). En dark = ~12:1.
- Todo el flujo es navegable por teclado (botones reales, no `<div onClick>`).
- Selection invertida con accent + paper.

---

## Tweaks

Tres controles, sin sobre-ingeniería:

- **Modo:** light / dark.
- **Tamaño:** slider 0.85–1.30, escala el cuerpo de lectura sin tocar UI.
- **Layout:** immersive / marginalia / parallel.

Persiste vía el contrato de la host. Listo en `tweaks-panel.jsx`.

---

## Anti-referencias respetadas

- ❌ Sin streaks, vidas, corazones, "perdiste la racha".
- ❌ Sin mascota cartoon. Sin búho, sin pulpo, sin emoji-gore.
- ❌ Sin gradiente purple-pink, sin glassmorphism cliché, sin glow neón.
- ❌ Sin banderas alemanas, lederhosen, pretzels decorativos.
- ❌ Sin shadcn-genérico. Cero `<Card><CardContent>...</CardContent></Card>`.
- ✅ Tipografía hace el trabajo. El nicho (Nürnberg, Bürgeramt) está abrazado, no escondido.

---

## Stack y portado

Mockup en HTML + React (Babel inline) para iterar rápido. Listo para portar a TSX:

| Mockup | TSX destino sugerido |
|---|---|
| `tokens.css` | `frontend/src/styles/tokens.css` (reemplaza el actual) |
| `global.css` | `frontend/src/styles/global.css` (reemplaza el actual) |
| `pages.css` | `frontend/src/styles/pages.css` (nuevo) |
| `components.jsx` → `KlaraMark` | `frontend/src/components/KlaraMark.tsx` |
| `components.jsx` → `Masthead` | `frontend/src/components/Masthead.tsx` |
| `components.jsx` → `WordPopover` | `frontend/src/components/WordPopover.tsx` (reemplaza) |
| `components.jsx` → `SentenceView` | `frontend/src/components/SentenceView.tsx` (reemplaza) |
| `components.jsx` → `Home` | `frontend/src/routes/Home.tsx` |
| `components.jsx` → `StoryNew` | `frontend/src/routes/StoryNew.tsx` |
| `components.jsx` → `Story` | `frontend/src/routes/Story.tsx` |

**Dependencias a agregar** (`package.json`):

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }
}
```

Las fuentes vienen por `@import` de Google Fonts en `global.css`. Si preferís self-hosted (recomendado para producción), descargá Source Serif 4 + Inter Tight + JetBrains Mono variables y reemplazá el `@import` por `@font-face`.

**Tipos sugeridos (TypeScript):**

```ts
type Level = "A0" | "A1" | "A2" | "B1";
type Article = "der" | "die" | "das" | null;
type ReadMode = "immersive" | "marginalia" | "parallel";

interface Word {
  lemma: string;
  article: Article;
  pos: string;
  translation: string;
  example?: { de: string; es: string };
}

interface Token {
  type: "word" | "punct" | "space";
  text: string;
  word?: Word;
}

interface Sentence {
  es: string;
  tokens: Token[];
}

interface Story {
  id: string;
  level: Level | string;
  title: string;
  dek: string;
  dateLabel: string;
  minutes: number;
  wordCount: number;
  sentences: Sentence[];
  newWords: Pick<Word, "lemma" | "article" | "translation">[];
}
```

---

## Próximos pasos

1. **Tokens** y **global** se pueden pegar directamente al repo sin cambios.
2. **Componentes JSX → TSX**: añadir tipos, cambiar `(e)` por `(e: React.MouseEvent<…>)`, listo.
3. **Audio real**: reemplazar el `setInterval` simulado en `Story` por hooks contra ElevenLabs (ya tenés la integración). Mantener el bermellón en el progress fill.
4. **Hover en mobile**: el wash en `:hover` no aplica bien en touch. Considerar `:active` + un haptic suave (`navigator.vibrate?.(10)`).
5. **`/review` y `/chat`**: están como placeholder editorial. Cuando llegue el momento, repaso podría ser flashcards en formato "tarjeta postal" (papel, tinta, una palabra grande, dorso con traducción). Chat podría ser una **columna de conversación tipo carta** — cada turno como párrafo en serif, con la `K` cursiva al inicio de los turnos de Klara.
6. **Edición Nürnberg → otras ciudades**: el subtítulo `Edición Nürnberg` está pensado para escalar (`Edición Berlín`, `Edición Buenos Aires` cuando el español sea L2). Es identidad fuerte sin ser inflexible.
