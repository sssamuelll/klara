# Kickoff — Rediseño de escritorio de Klara (app + landing)

**Fecha:** 2026-08-10 · **Para:** el agente de diseño que escribirá la spec del escritorio
**Estado de partida:** main `c5a0faf` (fase "Puerta de entrada v4" desplegada en prod)

---

## 0. Misión

Diseñar el escritorio de Klara — la app completa y la landing — y llevar el diseño al siguiente nivel. No "hacer responsive lo que hay": hoy no existe un diseño de escritorio que mejorar. A 1440px, toda la app v4 es una columna de 430px flotando en el centro con un borde fino (`mobile3.css:10-11`) y ~1000px de vacío a los lados. Partes de cero, con una identidad fuerte ya ganada y un producto que funciona.

La vara: que alguien que evalúa Klara en un monitor grande piense "esto es un producto serio hecho por gente con criterio", y que quien estudia una hora en escritorio termine convencido de que estudiar aquí es **mejor** que en el teléfono, no igual de bueno más grande.

## 1. Las dos decisiones ya tomadas (Samuel, 2026-08-10 — no se re-litigan)

1. **El escritorio es el modo de estudio profundo, no la app móvil ensanchada.** Es donde se estudia largo: superficies simultáneas (p. ej. texto + gloss/ficha a la vez, donde el móvil obliga a alternar), teclado como interfaz primaria, lectura extendida. La tesis a defender: *el escritorio del estudiante*.
2. **La identidad se profundiza, no se reemplaza.** Papel/tinta, serif editorial, UN bermellón, hairlines: constitucional. El "siguiente nivel" es de oficio — escala tipográfica editorial real, jerarquía de papel, detalle fino — no de marca nueva.

## 2. La constitución (lo que ata, con fuente)

- **Identidad** (`docs/design/klara-v4/DESIGN.md`, vigente SOLO en identidad — L3-5): serif de lectura `Source Serif 4`, sans UI `Inter Tight`, mono metadata `JetBrains Mono` (L30-34); papel/tinta nunca blanco/negro puro, dark "jamás #000" (L41-47); "Un único acento. Sin gradientes. Sin glow. Sin glassmorphism." (L51); hairlines 1px en `--rule`, no shadows (L115); "Klara es una firma, no un personaje" — sin mascota (L26). Anti-referencias explícitas en L147-151.
- **Anti-Duolingo constitucional** (plan maestro v4, L19-20): sin streaks, sin corazones, sin guilt, sin suscripción visible. El escritorio no es excusa para dashboards de vanidad.
- **i18n total** (plan maestro L24): ni un string duro; 6 locales (es master) en el mismo PR; `check-i18n.mjs` gate.
- **La tesis del producto** (plan maestro L7): las herramientas de un curso son función de (tema × perfil), no del tema solo. El escritorio debe dejar sitio a esa personalización, no cablear un layout único para siempre.
- **El móvil no regresa:** el frame 430/100dvh de móvil queda intacto píxel por píxel. Todo lo nuevo vive detrás de breakpoints o composición nueva; ninguna regla existente de móvil se toca sin justificación explícita.

## 3. Jurisprudencia de Iris Tane (fallos ya emitidos — se heredan, no se reabren)

- Micro-mono con pisos: 10px etiquetas de vistazo, 12px mono-como-contenido ("la L1 es lectura funcional, no nota al pie" — spec F2 L106).
- Gutters unificados: 22px; 28px solo como sangrado de lectura declarado (`m3-lect`). DESIGN.md L110 ya anticipa "80px en desktop" como suelo de gutter de página — retómalo.
- `--art-die` separado del acento (no dos rojos compitiendo).
- Nada se recorta en silencio (techos de línea explícitos); alturas reservadas para feedback (la oración no salta).
- Una portada por página (el hero no se duplica).
- Su doctrina de la última fase: **lo interactivo no viste uniforme de metadata** — las acciones se distinguen de las etiquetas (subrayados 1px, tinta plena). En escritorio, con hover y foco, esto se vuelve más importante, no menos.
- Iris es gate de merge por pantalla. Diseña esperando su auditoría: jerarquía, densidad, tipografía, color, alineación.

## 4. Estado medido del terreno (inventario 2026-08-10, post-`c5a0faf`)

**Anchos reales a 1440px:**

| Superficie | Hoy | Fuente |
|---|---|---|
| Todo lo v4 (Inicio, Portada, Mapa, Perfil, auth, `/estudiar`) | 430px fijos + borde | `mobile3.css:10-11` |
| Landing pública | 430px fijos + borde | `landing.css:5,16` |
| LegacyShell (Module, NewStory, Settings, Practice, Speak) | crece a 1180px (`--maxw-page`) | `global.css:108-114` |
| Onboarding | **el único layout desktop real**: grid `200px / 1fr / 280px`, max 1200px, colapsa a 1080/860 | `onboarding.css:48-67` |

**Shells** (`App.tsx`): `RootGate` (`/` → Landing o Inicio), `V4Frame/V4Shell` (+TabBar), `AuthShell`, `LegacyShell` (kapp/kframe+Masthead), y `/estudiar/:id` standalone. Las pantallas legacy con piel vieja: Module (148 líneas), NewStory (147), Settings (274), Practice (507, híbrido — monta las sesiones v4), Speak (844, híbrido `kc-*`).

**Activos dormidos que el diseño debe explotar:**

- **Ya existe una gramática de teclado completa, escondida:** `useSentencePractice.ts:544-577` (`→`/`Enter` avanza, `←` retrocede, `Espacio` audio, `M` mic, `Esc` sale), `RecallReviewSession.tsx:57-66` (`1-4` califican), Escape cierra popovers/menús. El hint visual (`.k-hint`) se oculta en touch a propósito (`sentence-view.css:569-576`). En escritorio esto asciende de huevo de pascua a interfaz de primera clase.
- **Tokens de escala sin estrenar:** `--t-display` 88px (3 usos), `--maxw-read` 640px (1 uso), `--maxw-page` 1180px (2 usos), `--shadow-*` casi vírgenes. La escala grande de la identidad existe en `tokens.css` y nunca se ha usado — el escritorio es su estreno. `tokens.css` no tiene ni una media query de tamaño: el sistema de tokens está listo para crecer sin romper nada.
- **Pieles de sesión compartidas:** `sentence-view.css`, `finish.css`, `recall-review.css`, `gender-review.css` sirven tanto al flujo v4 (`/estudiar`) como al legacy (Practice). Son la piel del estudio — el corazón del "modo profundo".
- **Peso muerto real:** `pages.css` + `path.css` (~180 selectores) solo sostienen Module/NewStory/Settings. Si el rediseño absorbe esas pantallas, ese CSS muere con ellas.
- **PWA sin nada de escritorio** (`vite.config.ts:8-33`): sin `screenshots`, sin `shortcuts`, sin `display_override`. Instalada en desktop muestra el teléfono centrado en una ventana.

**El mockup v4 nunca diseñó escritorio:** su `@media (min-width:900px)` era un simulador de kiosco (el móvil con borde y gutters), no una composición (`docs/design/klara-v4/global.css:78-105`). No hay ningún documento previo de desktop en `docs/` — este kickoff es el primero.

## 5. Alcance

**Dentro:**
1. **Landing pública** en escritorio — es lo que ve un evaluador nuevo; hoy es la columna móvil.
2. **El corazón del estudio en profundo:** `/estudiar` (teleprompter + gloss + sheet), Repaso (fichas), Speak/chat. Aquí vive la tesis de las superficies simultáneas y el teclado.
3. **El shell:** biblioteca (Inicio), Portada, Mapa, Perfil, auth — la navegación de escritorio (la TabBar móvil no es una respuesta de desktop).
4. **Las pantallas legacy** (Module, NewStory, Settings, Practice como orquestador, Speak): decide si el rediseño las absorbe al sistema nuevo o las deja explícitamente fuera con justificación. No pueden quedar en el limbo sin veredicto.
5. **Manifest/PWA desktop** si el diseño lo amerita (shortcuts, screenshots).

**Fuera:**
- El dominio Course/F3 y todo backend (el rediseño es del eje UI; los datos que hay son los que hay).
- El móvil: cero regresiones, cero re-aperturas de sus fallos ya cerrados.
- Suscripción, racha, gamification (constitucional).
- SEO/prerender de la landing y página legal (deuda heredada de la fase anterior, explícitamente aparte).

## 6. Preguntas que la spec debe responder (el agente decide — con dirección, no con menú)

1. **La composición del estudio profundo:** ¿cómo se reparten texto, gloss, ficha y audio en 1440px? ¿Dos paneles fijos, panel contextual, margen anotado tipo libro? ¿Qué pasa en 1024px y en 768px, y dónde muere el layout de escritorio y nace el móvil?
2. **La gramática de interacción completa:** teclado como primera clase (¿palette? ¿atajos globales? ¿navegación por foco?), hover con propósito, selección de texto en el teleprompter. La gramática existente (`→`, `Espacio`, `M`, `1-4`) es el punto de partida, no el techo.
3. **La navegación de escritorio:** qué reemplaza a la TabBar. ¿Rail lateral, cabecera, nada-porque-el-contenido-navega?
4. **La escala editorial:** cómo se usa `--t-display`/88px y el vacío. El lujo del papel es el margen — que el aire sea composición, no sobra.
5. **La landing de escritorio:** el hero editorial en grande, sin volverse un template de SaaS. Qué enseña (¿el producto de verdad? ¿tipografía sola?).
6. **Dark mode en escritorio:** los tokens dark existen (`tokens.css:89-108`); ¿el escritorio lo estrena o lo difiere?
7. **Las pantallas legacy:** absorber vs. declarar fuera (con plan de muerte de `pages.css`/`path.css` si se absorben).
8. **Sesiones largas y atención:** el research de UDL/TDAH/autismo (`docs/research/`, carpetas "Adaptación para TDAH…", "Diseño accesible para autismo…", "Universal Design for Learning…") habla de carga cognitiva y foco — úsalo para decidir densidad, no como cita decorativa.

## 7. Proceso y gates

- **Flujo:** brainstorming dirigido → spec en `docs/superpowers/specs/` → review de roster → plan (`writing-plans`) → ejecución subagent-driven. Igual que las fases v4.
- **Roster de review de la spec:** Serrano (gaps y estados de fallo), **Petra Haft** (la gramática de interacción teclado/mouse es su territorio — invocarla ANTES de cerrar la spec, es propositiva), Iris (gate visual por pantalla en ejecución), Voronov solo si aparece una tensión ontológica real.
- **Gates de ejecución:** los de siempre — `gates-locales` (Actions OFF), `check-i18n` 6 locales, a11y de entrada (foco visible, navegación por teclado real, `prefers-reduced-motion` ya respetado en tokens), smoke en monitor real + el iPhone para confirmar cero regresión móvil.
- **Anti-regresión móvil verificable:** el diff de CSS móvil existente debe ser ~cero; lo nuevo entra por breakpoints/archivos nuevos. Cualquier excepción, justificada línea por línea.

## 8. Criterios de éxito

1. A 1440px ninguna pantalla es una columna móvil con borde: toda superficie tiene composición pensada para su ancho.
2. Una sesión de estudio en escritorio usa capacidades que el móvil no tiene (simultaneidad, teclado, lectura extendida) — la tesis hecha píxeles.
3. La identidad es más ella misma que antes: alguien que ame el móvil reconoce el escritorio como la versión adulta del mismo objeto.
4. Iris no encuentra un fallo estructural nuevo (los de su doctrina, resueltos de nacimiento).
5. El móvil, byte-idéntico donde no se declaró lo contrario.
6. Todo lo visible, en 6 locales, sin un string duro.
