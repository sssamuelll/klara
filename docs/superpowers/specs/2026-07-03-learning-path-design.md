# Ruta de aprendizaje + librería de historias por módulo — diseño

**Fecha:** 2026-07-03
**Estado:** aprobado (brainstorm con el owner, 4 decisiones de producto cerradas)
**Continúa:** `2026-06-16-learning-sequence-slice2-modules-foundation-design.md` (la "gamificación / mapa de maestría" que ese spec difirió explícitamente en §11)

## 1. Problema

Klara genera historias adaptadas al módulo activo (eso ya funciona server-side), pero:

1. **No hay ruta visible.** El usuario no ve la secuencia de módulos, su posición, ni qué sigue — solo un widget "current module" sin CSS en Home. La guía tipo Duolingo no existe como concepto de navegación.
2. **Toda historia cuesta una espera de LLM.** POST /stories es síncrono: una completion de 4000 tokens (timeout 60s × reintentos litellm × 2 reintentos de parseo), ~2-3% de fallo residual → 502. El usuario se queda pegado mirando "Klara está escribiendo…".
3. **Toda historia cuesta plata.** Cada usuario paga su generación aunque el contenido de un módulo A1 sea perfectamente compartible.

## 2. Decisiones de producto (cerradas con el owner)

| Decisión | Elección |
|---|---|
| Origen del fallback | **Híbrido**: seed curado por el owner + pool que crece reciclando generaciones de usuarios |
| Progresión | **Gated suave**: la ruta marca módulo actual y muestra los siguientes bloqueados, pero se puede saltar ("empezar aquí igual") |
| Gate de módulo | **Dos señales**: *completar* (3 historias del módulo terminadas → desbloquea el siguiente) y *dominar* (el gate SRS existente 85%/21d, mostrado como anillo lento) |
| Alcance del seed | **Solo es→de**: 8 módulos A1 alemán × 5 historias con traducciones al español. Otros nativos los llena el pool orgánicamente |

## 3. Invariantes que se preservan

- **Módulo = predicado, nunca contenedor de historias** (spec de junio, `models/module.py:31-33`). `Module` sigue sin referenciar `Story`. La librería es una entidad de *serving* aparte; la provenance nueva es Story→Module, dirección opuesta a la prohibida.
- **Nada de rachas/vidas/ligas/XP por volumen** (spec de junio §11/M8). La ruta visualiza estado de competencia, no gamification loops.
- **Señal visible = monotónica** ("encontradas" nunca baja); la señal lenta (dominadas) llena el anillo pero no protagoniza.
- **Historias del usuario = del usuario.** La librería se sirve por **copy-on-claim**: clonar a `stories` con `user_id`. Todo lo downstream (finish, quiz, attempts, SRS, klara_note) funciona sin tocarse.

## 4. Modelo de datos

### Tabla nueva `story_library`

| Columna | Tipo | Nota |
|---|---|---|
| id | UUID PK | |
| module_id | FK modules ON DELETE CASCADE | keyed por módulo |
| language | str(8) | target (redundante con module, pero barato y consulta directa) |
| native_language | str(8) | las historias llevan traducciones — la librería es por par |
| level | CEFRLevel | |
| title, content, target_words, comprehension_questions, quiz_items, insight | mismos tipos que `stories` | clone-ready: el claim es un INSERT..SELECT conceptual |
| topic | str nullable | |
| source | enum `seed` \| `pool` | |
| source_story_id | UUID nullable | provenance si vino del pool |
| content_hash | str(64) UNIQUE | sha256 de los textos target de las frases, unidos por `\n` — dedup del pool |
| times_served | int default 0 | |
| is_active | bool default true | kill-switch de curaduría |
| generated_by_provider, generated_by_model, generation_cost_usd | como en `stories` | economía medible |
| created_at | | |

Índice: `(module_id, native_language, is_active)`.

### Columnas nuevas en `stories` (nullable, cero impacto en filas existentes)

- `module_id` FK modules ON DELETE SET NULL — qué módulo condicionó la generación/claim. Es la base para contar "N historias de este módulo".
- `library_source_id` FK story_library ON DELETE SET NULL — de qué entrada se clonó. Doble uso: filtro "no re-servir esta entrada a este usuario" y contador de circulación.

### `StoryView` se activa

La tabla existe dormida (`models/story.py:55-68`, nunca escrita). Nuevo write path: al llegar al summary del finish se upserta la fila con `finished_at = now()`. Ese es el evento **historia completada** que alimenta el gate.

Una sola migración alembic: `story_library` + las dos columnas.

## 5. Mecánica de la ruta

- **Puntero** = `users.current_module_id` (existente). Semántica: "dónde estás trabajando".
- **Empezar una historia en el módulo M mueve el puntero a M** — tanto el claim como la generación con `module_id`. Esto implementa el gated suave sin endpoint `activate`: saltar adelante y volver a repasar son el mismo gesto. Los gates empujan el puntero hacia adelante desde donde esté.
- **Completar**: `STORIES_TO_COMPLETE = 3` (constante en `curriculum/`, no columna — YAGNI). Un módulo está completado cuando el usuario tiene ≥3 stories con `module_id = M` y `StoryView.finished_at` no nulo. Derivado en lectura; sin tabla de historial de completitud (misma deuda aceptada que el spec de junio §11).
- **Avance por completar**: al escribir un finish, si la historia pertenece al módulo activo y con ella llega a 3, el puntero avanza al siguiente `sequence_order` (forward-only, mismo idioma). Completar un módulo no-activo (repaso) no mueve el puntero.
- **Avance SRS existente** (`advance_module_if_mastered`) se queda intacto — el que dispare primero gana; ambos son forward-only e idempotentes.
- **Dominar**: sin cambios de mecánica; `module_progress` ya devuelve mastered/total. La UI lo muestra como anillo que se llena con semanas.
- **Locked (visual)**: módulo desbloqueado si `sequence_order == 1`, o su anterior está completado, o `sequence_order <=` el del módulo activo. Los bloqueados se muestran con candado pero siguen siendo tappeables ("empezar aquí igual").

## 6. API

1. **`GET /modules`** (nuevo) — todos los módulos del `target_language` del usuario, ordenados por `sequence_order`. Por módulo: id, sequence_order, title, cefr_level, can_dos, grammatical_focus, encountered/mastered/total, tripleta gender, `stories_finished`, `stories_to_complete` (3), `completed`, `is_current`, `unlocked`, `library_available` (entradas activas del par no reclamadas por este usuario).
2. **`POST /modules/{id}/story`** (nuevo) — el claim: elige la entrada activa no-vista con menor `times_served` (empate → más antigua), la clona a `stories` (con `module_id`, `library_source_id`), ejecuta `enroll_cards` del vocab del módulo (mismo efecto que create_story), incrementa `times_served`, mueve el puntero a M, devuelve el story id. Milisegundos; el audio ya está caliente (precache al construir la librería). Librería vacía → **404 `library.empty`** y el frontend ofrece generar.
3. **`POST /stories`** gana dos campos opcionales: `module_id` (condiciona ese módulo en vez del activo, y mueve el puntero) y `topic_origin` (`chip` | `free` | `none`, default `none`) — el backend no distingue chip de texto libre sin esto.
4. **`POST /stories/{id}/finish`** (nuevo) — upserta `StoryView.finished_at`; dispara el chequeo de avance por completar. Owner-checked como el resto de endpoints de story.

`GET /modules/current` se queda (compat).

## 7. Pool: reglas de reciclaje

En el camino de éxito de `create_story`, la historia se copia a `story_library` **solo si**:

- `topic_origin != free` — topics personales escritos por el usuario nunca se sirven a otros;
- la verificación de cobertura pasó completa (cero target lemmas descartados) — el gate de calidad ya existente;
- tiene `module_id`;
- `content_hash` no existe ya;
- el par (module_id, native_language) tiene < **50** entradas activas (cap; al llegar, se deja de insertar — sin evicción).

El fallo del insert al pool nunca rompe la creación de la historia (best-effort, log y sigue).

## 8. Seed pipeline

**Script `klara.scripts.build_story_library`** (mismo patrón idempotente que `load_de_modules`):

- Datos inline: por cada uno de los 8 módulos, 5 topics curados que varían el subconjunto de lemmas objetivo (el sustituto a nivel módulo del dedup per-user de vocab reciente, que no aplica a contenido compartido).
- Por entrada: genera con el pipeline real, verifica cobertura; si descarta lemmas, regenera (máx. 3 intentos) o la salta con log.
- Inserta la fila (source `seed`) y corre `precache_texts` para dejar TTS caliente en el `audio_cache` global.
- Idempotente por `content_hash`; re-correrlo solo agrega lo que falta.
- Costo por fila queda registrado en las columnas de provenance.

**Único refactor del diseño:** extraer de `story_gen.py` el core de generación+verificación (recibe params explícitos: módulo, lemmas, idiomas, avoid-list, LLM) separado de la persistencia per-user (fila stories, vocab upsert per-user, recent-vocab query). `create_story` y el build script consumen el mismo core.

Seed inicial: 8 × 5 = **40 historias es→de**.

## 9. Frontend

- **Home = la ruta.** El widget module actual (sin CSS hoy) se reemplaza por la lista vertical de nodos: número + título, check completado, anillo dual (encontradas = progreso visible rápido; dominadas = relleno lento), mini-indicador der/die/das, candado suave con "empezar aquí igual", nodo actual resaltado con CTA "continuar aquí". Datos: `GET /modules`.
- **`/module/:id`** (pantalla nueva): header con can-dos + foco gramatical + progreso (el API ya manda esos campos; el FE hoy los bota), CTA primario **"Leer una historia"** (claim → `/story/:id`), secundario **"Crear mi propia historia"** (→ `/story/new?module=id`), y la lista de historias ya leídas del módulo (re-leibles). Estado librería-vacía: el CTA primario se convierte en generar.
- **`StoryFinish`**: NextSteps gana "Siguiente historia del módulo" (claim directo si hay `module_id`) y "Volver a la ruta"; al montar el summary dispara `POST /stories/{id}/finish`.
- **`NewStory`**: escape hatch intacto; manda `module_id` (si vino con query param) y `topic_origin`.
- **klara_note**: el prompt pierde la aseveración "no hay ninguna [historia] en cola" (`finish_lessons.py:90`) — ya no será verdad.
- Nav se queda en 4 items (la ruta vive en el tab Home). Rutas nuevas en `App.tsx`: `/module/:id`.
- i18n: grupos nuevos `path` y `module` en los **6** locales en el mismo commit (`check-i18n` obliga).
- CSS: `path.css` nuevo siguiendo las primitivas `k-*`; los ancestros visuales son `home__feature` y `home__sec-item`.
- Empty state por idioma sin módulos (fr, ja…): la ruta lo dice honesto y todo cae al flujo actual por frecuencia.

## 10. Errores

- **Fallback bidireccional, nunca callejón sin salida**: claim sin librería → ofrecer generar; generación 502 → ofrecer historia lista si `library_available > 0`.
- Doble claim concurrente del mismo usuario: benigno (dos historias o la misma dos veces). Riesgo aceptado; sin locking.
- El insert al pool es best-effort; jamás convierte un éxito de generación en error.
- Cambio de target_language: la ruta es por idioma; el guard existente de puntero stale (`ensure_active_module`) ya cubre el cambio.

## 11. Testing

pytest (backend):
- claim: clon fiel de todos los campos, enroll de vocab, filtro no-visto, menor-times_served primero, 404 en vacío, puntero movido;
- `GET /modules`: derivación de completed/unlocked/is_current/library_available;
- finish: upsert idempotente, avance por completar (solo módulo activo, forward-only);
- pool: excluye `topic_origin=free`, excluye cobertura incompleta, dedup por hash, respeta cap, best-effort;
- build script contra LLM fake: idempotencia, gate de cobertura, salto tras 3 intentos.

Frontend: vitest para lógica pura nueva (si la hay); sin harness de componentes (estado actual del repo). Verificación e2e manual del flujo completo antes del merge.

## 12. Fuera de alcance / deuda aceptada

- Módulos A2+ y otros idiomas target (el modelo lo soporta; es autoría de contenido).
- Placement test (la posición inicial sigue siendo el módulo 1).
- Filtro por módulo en practice queue (module_vocab_ids lo haría barato; después).
- `stories_to_complete` por módulo como columna (constante por ahora).
- Evicción/curación del pool más allá de `is_active` manual.
- Streaming/render progresivo de generación en vivo (la librería es el camino barato a instantáneo).
- Tabla de historial de completitud (derivado en lectura, como en junio).
- Speak con foco derivado del módulo (anotado en el spec de junio como futuro).
