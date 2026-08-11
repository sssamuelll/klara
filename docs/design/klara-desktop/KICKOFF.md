# Kickoff v3 — El escritorio de Klara: el taller

**Fecha:** 2026-08-11 · **Estado de partida:** `main` en `f190a11`
**Sustituye íntegramente a la v2.** Endurecido por la sesión adversarial de la ronda 3 (Lyra · Voronov · Richter · Serrano · Cassian) + ingeniería inversa de mnemo + inventario real del código. Documentos vinculantes: `ACTA-2026-08-11-ronda3-mnemo-multitema.md` y `research/anexo-1..8`.

---

## 0. El encargo y su traducción

Samuel (2026-08-11): escritorio *entre lo que tenemos y mnemo*, más cerca de mnemo en limpieza; **funcionalidad distinta del móvil — otra aplicación complementaria, usadas en conjunto**; y **Klara aprende cualquier cosa, no solo idiomas**.

Traducción tras el fuego adversarial:

> **El escritorio es el taller: donde el material entra al sistema. El móvil es la práctica: donde el material se ejercita.** El escritorio hace algo que el móvil no hace — *autoría* — y por eso el multi-tema nace ahí: escribir tarjetas de cualquier tema no necesita el motor de alemán.

Y la limpieza pedida se consigue sin tocar la identidad, porque —

> **La limpieza de mnemo no es su paleta: es su conteo de sustantivos.** Papel/tinta cálido, serif editorial y un bermellón se sienten tan limpios como mnemo si la pantalla tiene tres cosas. El taller tiene tres: **tarjeta, etiqueta, cola.**

## 1. Lo que la sesión adversarial cerró (no se re-litiga)

- **Multi-tema SIN entidad `Course`.** Lección de mnemo: la generalidad viene de *no cablear la taxonomía* — carpetas y tags, cero `Subject`. En Klara: **etiquetas libres**, sin jerarquía, sin campo `tipo`. (Voronov: `tipo` no es un atributo, es el nombre del motor que sabe leer ese contenido; "curso" sin institución certificadora es teatro curricular.)
- **Aislamiento total del alemán.** Tablas nuevas. Nada entra a `vocab_items`, que es un catálogo **global entre usuarios** y contaminaría a terceros.
- **La identidad se conserva.** Papel/tinta, serif, un bermellón, hairlines. No hay conflicto real entre el encargo y la constitución: el conflicto era de scope.
- **Anti-gamification sigue siendo constitucional.** Mnemo trae `streak.svg`, `xp.svg`, "Day Streak", "Minutes studied 0/30". Nada de eso cruza; el dashboard de widgets es su vehículo y se descarta.
- **F3 (dominio `Course`) queda diferida como proyecto aparte**, no como precondición. Su decisión es de Lyra, con datos.
- **La calma de mnemo está pagada por la ausencia del LLM** (Richter): sin latencia, sin costo por acción, sin fallo del modelo. El taller v1 no genera nada — es texto que escribe el usuario. Por eso puede ser igual de calmo.

## 2. Constitución vigente (heredada de la v2)

Identidad de `DESIGN.md` (serif `Source Serif 4` lectura / `Inter Tight` UI / mono metadata; papel-tinta nunca puros; un acento; hairlines; sin mascota, sin gradientes ni glow). Anti-Duolingo. i18n total (6 locales, `check-i18n` gate). **Precedencia: evidencia de aprendizaje > identidad visual > preferencia estética.** Jurisprudencia de Iris intacta (micro-mono 10/12, gutters, nada se recorta en silencio, una portada por página, lo interactivo no viste de metadata). Progreso honesto = open learner model + calibración; **jamás** streaks ni tiempo-en-app (Goodhart, anexo 5).

## 3. Estado del terreno, corregido

Lo que la v2 decía sigue vigente (todo lo v4 es una columna de 430px a 1440px; gramática de teclado oculta en touch; tokens de escala sin estrenar). **Correcciones de la ronda 3:**

- **El motor de repaso genérico YA EXISTE en prod**: FSRS desde la migración `0018`; `srs_engine.schedule_next_review()` y `project_intervals()` son funciones puras que solo leen atributos. Los robos #4 y #5 de mnemo (scheduler puro, preview de intervalo en el botón) están hechos. `RecallReviewSession.tsx` ya es Espacio-para-voltear + `1-4` con intervalos pintados.
- **Lo que NO existe es autoría**: `POST /srs/cards` exige un `vocab_item_id` preexistente, y `user_cards.vocab_item_id` es **FK NOT NULL** a la tabla del léxico alemán. *Klara no puede agendar nada que no sea un lexema.*
- **`study_sessions` tiene un solo escritor**: `speak_finish.py:80`. El criterio conductual de la v2 medía la superficie excluida.
- **El perfil está construido, sin consumo y con la aridad equivocada** (`user_id` PK ⇒ f(perfil), no f(tema × perfil)).
- **Cero offline**: el service worker solo cachea Google Fonts.

## 4. Fase F0 — El taller (la única fase autorizada hoy)

**Core:** una ruta standalone a ≥1024px `pointer:fine` donde el usuario **pega o escribe texto plano, se vuelve tarjetas con etiquetas libres, y las repasa ahí mismo con el FSRS que ya corre en prod** — sin `Course`, sin editor de bloques, sin command palette, sin import de Anki, sin dashboard, y sin tocar una línea del alemán.

*(El nombre real de la ruta lo decide `solace-wren`; "el taller" es etiqueta de trabajo.)*

### Modelo de datos (migración `0021`, aditiva)

- **`study_cards`** — `id, user_id, front, back, tags text[], source, created_at, updated_at` + las columnas de agenda que ya tiene `user_cards` (`state, stability, difficulty, fsrs_step, fsrs_last_review, interval_days, next_review_at, last_reviewed_at, repetitions`). Índice `(user_id, next_review_at)`. **Sin unique sobre el contenido** — los duplicados son asunto del usuario.
- **`study_card_reviews`** — `id, user_id, study_card_id, rating, elapsed_seconds, prev/new_interval_days, **device**, reviewed_at`. El ledger no es opcional: reviews que no se registran son datos de entrenamiento que no existen nunca más.
- **Un solo scheduler**: `srs_engine` se parametriza con un `Protocol` de ~6 líneas con los atributos FSRS. **Dos implementaciones de FSRS que derivan es el peor resultado posible de esta fase.**

### Bloqueos duros de F0

1. Anti-gamification (constitucional).
2. Aislamiento del alemán: tabla nueva, jamás `vocab_items`.
3. Validación en frontera: largo de front/back, tope de etiquetas, tope del pegado, scoping por `user_id`.
4. Columna `device` en el ledger — es el criterio falsable y **no se puede backfillear**.
5. Funcionalidad divergente (autoría): sin esto el escritorio es un teléfono ancho y el encargo no se cumplió.

### Cortado explícitamente

Editor de bloques · notas como entidad · mapa mental · dashboard de widgets · `IModule`/plugins · paquetes `.mnemo` · import de Anki · command palette · consumo móvil de la cola nueva (fase siguiente) · paleta y tipografía de mnemo (no es estética: es cambio de identidad). **Concesión de costo cero:** los atajos de la pantalla nueva viven en **un array**, para que la palette futura sea leer ese array.

### Calendario y regla de decisión

| # | Trabajo | h |
|---|---|---|
| 1 | Migración `0021` + modelos + `Protocol` en `srs_engine` + tests del scheduler sobre la tabla nueva | 3 |
| 2 | 5 endpoints (crear single + bulk desde pegado TSV, listar por etiqueta, cola due, review, export) + validación + tests | 4 |
| 3 | Mockup de una pantalla, dos temas → **gate visual de Iris** | 4 |
| 4 | Pantalla: pegar/escribir → previsualizar → guardar; lista con filtro por etiqueta | 6 |
| 5 | Repaso: **parametrizar** `RecallReviewSession` (no forkearlo) | 3 |
| 6 | CSS ≥1024px `pointer:fine`, densidad de tres sustantivos, auditoría dark | 4 |
| 7 | i18n 6 locales + `check-i18n` | 2 |
| **—** | **Build de dogfood en la máquina de Samuel** | **26h** |
| 8 | **Samuel usa el taller un fin de semana con un tema real que no sea alemán. Cero código.** | 0 |
| 9 | Arreglar solo lo que el uso rompió + gates + smoke matrix (1024/1280/1440/1920/720 + 1180 legacy) + diff-cero móvil + PR | 5 |
| 10 | Deploy a prod | 1 |

> **Regla de decisión, comprometida por adelantado:** **≥20 tarjetas creadas en el fin de semana → continúa** (fase siguiente: el móvil consume la cola nueva, que es el pago real de "se usan en conjunto"). **<20 → el taller se congela donde esté y la pregunta multi-tema vuelve a Lyra con datos**, no con otra ronda de council.

### Permission slip

> Se autoriza shippear un escritorio cuya única superficie propia es un taller de tarjetas de texto plano con etiquetas libres — sin `Course`, sin editor de bloques, sin palette, sin import, sin dashboard — conviviendo con el dominio de alemán en tablas separadas y con la identidad papel/tinta intacta, mientras el resto de la app sigue siendo una columna de 430px. **Rechazarlo tiene que ser explícito; el default no puede ser "primero resolvemos el multi-tema".**

## 5. Carril paralelo — el perfil consumido (decisión de Samuel, 2026-08-11)

Los tres agentes de juicio coinciden en que **este es el foso**: la tesis "herramientas = f(tema × perfil)" está construida al 90% y rinde 0. Corre en paralelo al taller porque no comparten archivos (el taller: tablas, rutas y CSS nuevos; el perfil: `llm/prompts.py`, `story_gen.py`, `learner_synthesis.py`).

**El test de Richter, que nadie ha corrido:** *una materia, dos aprendices.* Alemán para alguien que respondió "el audio me dispersa" contra alguien que respondió "me fija las cosas" — ambos valores ya existen en `schemas/learner_catalog.py`. Un prompt lee `synthesis`. La sesión generada difiere de forma visible. **Si f(perfil) no produce diferencia dentro de una sola materia, f(tema × perfil) entre materias es fantasía con más superficie.**

Deuda conocida a declarar en su spec: la aridad. `learner_profile.user_id` es PK ⇒ hoy es f(perfil) global; el `course_learner_overlay` prometido nunca se construyó.

## 6. Fases siguientes (no autorizadas todavía)

- **F1** (si ≥20 tarjetas): el móvil consume la cola nueva — el objeto compartido que hace real la palabra "complementarias" (Voronov: sin sustantivo que cruce, no hay complementariedad, hay dos apps).
- **F2**: `/estudiar` a ≥1024px (la D1 del kickoff v2) — aquí **Petra Haft vuelve a ser obligatoria** (paneles simultáneos ⇒ modelo de propiedad de foco).
- **F3+**: dominio genérico real, convergencia de los dos sistemas de tarjetas. **Revisión a 4 semanas, dueño: Lyra.**

## 7. Gates

Serrano sobre la spec del taller (tiene estados de fallo reales: parseo del pegado, duplicados, vacío, tarjetas huérfanas) · **Iris antes del plan** (gate visual, lección del v4) · Petra Haft **diferida con rastro** hasta F2 · gates mecánicos por PR: diff-cero sobre la lista móvil (se cumple por construcción), `check-i18n` 6 locales, a11y de foco y teclado, auditoría dark, smoke matrix.

## 8. Criterios de éxito (falsables)

1. **≥20 tarjetas creadas en el fin de semana de dogfood** sobre un tema que no sea alemán. Es la tesis entera, falsable en 48 horas y por $0.
2. **Sesión de taller completa sin tocar el mouse** (pegar → guardar → repasar → salir), verificada por checklist.
3. **Alemán intacto**: diff-cero sobre la lista móvil + smoke iPhone verde + suite backend en verde.
4. **`device` poblado en el 100% de los reviews del taller** desde el primer día (no backfilleable).
5. i18n 6 locales, cero strings duros; auditoría dark en cada pantalla nueva.

*(La calidad estética no es criterio: es el gate de Iris. Un criterio que un gate cumple por construcción no mide nada.)*
