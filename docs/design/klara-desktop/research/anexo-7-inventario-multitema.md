# Anexo 7 — Inventario real de multi-tema en Klara (docs vs código)

*Destilado por reasonix flash 2026-08-11 (1.1M tokens de entrada, $0.0212). Corrección de Richter incorporada al pie.*


## 1. Backend — modelos y migraciones (qué existe REALMENTE)

`backend/src/klara/models/` (24 archivos). **No existe ninguna entidad `Course`, `Topic`, `Subject` ni tabla de cursos en ninguna migración** (el único hit `course|topic|subject|materia|biblioteca|tema` en `backend/alembic/versions/` es la columna `topic` nullable de `story_library`, `20260703_0014_story_library.py:49`).

Clasificación:
- **Específicos de idiomas:** `user.py:31-38` (`level=CEFR`, `native_language="es"`, `target_language="de"`, `learning_context`), `story.py:24-32` (`level CEFR`, `target_language`, `native_language`), `vocab.py:12,21,39-41` (`lemma`, `gender`, `ipa`, `cefr_level`, uq `uq_vocab_lemma_lang_pos`), `module.py:40` (`cefr_level`, `language`), `gender.py`, `gender_lexicon.py`, `gender_l1_note.py`, `pronunciation_diagnosis.py:30-34` (`native/target_language`, `weakest_phoneme`), `library.py:28-30,41` (StoryLibrary: `language`, `native_language`, `level CEFR`, `topic`), `speak_turn.py`, `attempts.py`.
- **Genéricos (maquinaria de estudio):** `srs.py`, `session.py` (`study_sessions`), `audio.py`, `audio_quality_measurement.py`, `base.py`, `enums.py` (`CardState`, `ReviewRating`, `SessionType`).
- **Auth:** `user.py` (User), `oauth.py`, `invitation.py`, `waitlist.py`.

**Todo cuelga de `User` con un único `target_language`/`native_language`** (`user.py:36-37`). `library.py` NO es una "biblioteca de temas": es una caché global de historias pre-generadas keyed por `(module_id, language, native_language)` (`curriculum/library.py:41-53`), con índice `ix_library_module_native` (`models/library.py:21`). Migraciones multi-tema: **cero**. La más reciente (`20260809_0019_learner_profile.py`) crea solo `learner_profile`.

## 2. Frontend — rutas y componentes

Router real (`frontend/src/App.tsx`): shell v4 `V4Shell` (línea 119) con `/curso/:id`→`Portada` (121-127), `/curso/:id/mapa`→`MapaCurso` (128-135), `/perfil` (136-143), `/perfil/aprendizaje`→`PerfilAprendizaje` (144-151), `/nuevo`→`NuevoPlaceholder` (152-159); sesión `/estudiar/:id`→`StoryView` (231-238); legacy `/story/new`, `/module/:id`, `/review`, `/gender`, `/chat`, `/settings` (170-227).

- **Cableado real:** Inicio-biblioteca con tarjeta de curso + botón "+ Nuevo tema" (`routes/Inicio.tsx:62-83`), Portada con plan de 4 pasos (`routes/Portada.tsx:23-41`), MapaCurso (`routes/MapaCurso.tsx`), TabBar (`components/TabBar.tsx`), Perfil con fila "Cómo aprendes" (`routes/Perfil.tsx:38-58`).
- **Placeholder explícito:** `routes/NuevoPlaceholder.tsx` — solo `prontoTitulo`/`prontoDek` ("próximamente"), sin formulario. `NuevoTema`, `PlanPropuesto` **solo existen en el mockup** (`docs/design/klara-v4/mobile4-nuevo.jsx:34`, `mobile4-app.jsx:31`), no en `src/`.
- **Hardcode alemán:** el curso es literalmente `id: "aleman"` en `lib/courseView.ts:13,40`; navegaciones duras `navigate("/curso/aleman")` en `Inicio.tsx:64`, `MapaCurso.tsx:20`, `Portada.tsx:44`; escala CEFR fija `["A0","A1","A2","B1"]` con comentario "por-curso llega con F3" (`MapaCurso.tsx:10-11`); pasos fijos 01-04 (leer/pronunciar/hablar/repasar) en `courseView.ts:33-38` con nota "la máquina real llega con plan_steps en F3".

## 3. Acoplamiento a idiomas (cuantificado)

Conteo directo (grep, backend `src/`+`alembic` vs `frontend/src`):
- `target_language|native_language`: **backend ~35 archivos / >200 líneas** (200+ hits truncados; p.ej. `routers/stories.py:166-191,249-256`, `curriculum/modules.py:26-43`, `services/practice_queue.py:180-185`, `routers/speak.py:276`), **frontend ~15 archivos / ~70 líneas** (`api/types.ts:65-66,110-111`, `routes/Inicio.tsx:47`, `Speak.tsx:171`, `Story.tsx:60`, `StoryFinish.tsx:366,1238`). Coincide con la auditoría Plumb citada en el plan: "196 callsites en 33 archivos backend + 72 en 19 frontend; 371 de lemma/CEFR" (`docs/superpowers/plans/2026-07-31-rediseno-v4-biblioteca.md:34`).
- `lemma|cefr|phoneme|ipa|pronunciation`: backend ~45 archivos (`curriculum/inventory.py`, `coverage.py`, `selection.py:31-37` CEFR_ORDER, `gender_lex.py`, `lemmatize.py`, `vocab.py`, `enums.py:4`), frontend ~30 (`lib/speakFocus.ts`, `lib/pronunciation.ts`, `GenderPicker.tsx`, `EstudiarView.tsx:110-116`, `StoryFinish.tsx:940-1317`).
- `tts|stt|azure`: backend ~25 archivos (`tts/`, `pronunciation/azure_client.py`, `stt_client.py`, `routers/tts.py`, `speak.py`), frontend ~12 (`api/client.ts:332-382`, `lib/streamClient.ts:41`, `useMicScorer.ts`).
- `FOCUS_PHONEME_SETS`: `{"de": ["y","ʏ"]}` — **única entrada** (`services/speak_analysis.py:23-25`), usada como gate en `routers/speak.py:104`; espejo en `lib/speakFocus.ts:34` ("each additional language must arrive WITH its Azure IPA phoneme validation").

**Cuellos de botella reales para un tema no-idioma:** (a) `User` con UN target_language y filtros en cada query (`stories.py:256`, `modules.py:43`); (b) el schema de "ficha" = palabra (`lemma+gender+ipa+cefr`, `vocab.py`); (c) eje de voz asumido en toda sesión (práctica = pronunciación, `services/practice_queue.py`); (d) CEFR como escala universal (`selection.py`); (e) `translations` keyed por native_language (`srs.py:38`).

## 4. Docs vs realidad

| Promesa (docs) | ¿Existe en código? |
|---|---|
| Entidad `Course` como wrapper del dominio, tipos `tecnico`/`oral`, backfill curso "Alemán" (plan:7,109; D-C) | **NO** — ni modelo ni migración ni columna `tipo` |
| Migraciones `0015_courses…0021_session_types` (plan:194) | **NO** — la última es `0020_waitlist_signups` |
| Rutas `/curso/:id`, `/nuevo`, `/estudiar/:id` (plan:23) | **SÍ** (App.tsx:119-160,231-238) pero curso hardcodeado "aleman" |
| `NuevoTema` con meta/fecha/contexto (plan:77,206) | **NO** — placeholder (`NuevoPlaceholder.tsx`) |
| `PlanPropuesto` + `COURSE_PLAN_PROMPT` (plan:205; spec:242) | **NO** — 0 hits en código; solo docs y mockup |
| Job async de generación con estados (D-I, plan:115) | **NO** — generación síncrona en `routers/stories.py` |
| SRS scoped por curso (`concept_id`+`course_id`), `vocab_items`→`concepts` (plan:194,227) | **NO** — `vocab_items` global con upsert `uq_vocab_lemma_lang_pos` (`inventory.py:68`) |
| Shell v4, TabBar, biblioteca, Portada, MapaCurso (F1) | **SÍ** completo |
| `learner_profile` + `GET/PUT /me/learning-profile` + síntesis (F1.5) | **SÍ** (ver §5) |
| StoryLibrary con `topic` chip/free + provenance (spec §7) | **SÍ** — `models/library.py:41`, `schemas/story.py:71-77`, `curriculum/library.py:192-206` (fail-closed: topic libre rechazado) |
| i18n 6 locales, claves `biblioteca.*`/`curso.*`/`perfil.aprendizaje.*` | **SÍ** (`locales/{es,en,de,fr,ja,pt}/common.json`) |

**Lectura:** el "trabajo adelantado" es real pero es **F1 (shell v4) + F1.5 (perfil)**. F3 (dominio Course) y F4 (NuevoTema→PlanPropuesto) están 0% implementadas; los docs las marcan como el spec-gate.

## 5. Perfil de aprendizaje — existe y está completo… pero sin consumo

- **Sí existe:** modelo `LearnerProfile` (`models/learner_profile.py:25-43`: `user_id`, `answers JSONB`, `timings JSONB`, `facts JSONB`, `synthesis TEXT`, `derived_for_version`, `version`, `updated_at`); migración `20260809_0019_learner_profile.py`; endpoints `GET/PUT /me/learning-profile` (`routers/users.py:114-165`, con validación de allow-list contra `schemas/learner_catalog.py`); síntesis LLM best-effort (`services/learner_synthesis.py:90-141`, `FACT_KEYS` allow-list líneas 30-46). Frontend completo: catálogo de 23 preguntas (`perfil/catalog.ts:41-67`, `OB_CONSUMO` línea 67), vistas del cuestionario y pantalla de síntesis (`perfil/views.tsx`), ruta `/perfil/aprendizaje`, fila en Perfil (`routes/Perfil.tsx:38-44`), medición de `timings` (`perfil/timings.ts`).
- **¿Se usa en generación? NO.** El perfil solo se escribe (PUT) y lee (GET/fila de Perfil). **Ningún prompt de generación lo lee**: `learner_synthesis` no es importado por `story_gen.py` ni `llm/prompts.py` (grep: sus únicos consumidores son `routers/users.py:15` y sí mismo). La tesis "herramientas = f(tema × perfil)" es **0% real** en el pipeline de generación hoy; el consumo está prometido para F4 (spec:242).

## 6. Generación de contenido hoy

Pipeline único: `routers/stories.py` → `services/story_gen.py` → `llm/prompts.py`. **Atado a idiomas de arriba a abajo:**
- `STORY_SYSTEM_PROMPT` (`llm/prompts.py:1-99`): "profesora de {target_label}", nivel CEFR, reglas de lemas, `gender_rule` (línea 6), quiz con shadow/cloze de habla. `is_german` hardcode en `prompts.py:222`.
- `STORY_USER_PROMPT` recibe `Tema: {topic}` (`prompts.py:101-103`) — pero `topic` es el **tema narrativo de la historia** (ambientación), no una materia de estudio; `stories.py:193-215` lo valida con `topic_origin: chip|free|none`.
- `story_gen.py` tiene lógica de género por idioma (`:61-62,92-103` `_LEADING_ARTICLES`), cobertura de lemas vía `canonical_lemma`/simplemma (`curriculum/lemmatize.py`), y el oráculo de género alemán (`:159`).
- Otros prompts también idioma-atados: `_QUIZ_PROMPT`/`_NOTE_PROMPT`/`_INSIGHT_PROMPT` (`services/finish_lessons.py:26,83,106`), `CHAT/SPEAK_SYSTEM_PROMPT` (`prompts.py:135,145`), `phonetic_hints` (`services/phonetic_hints.py:41`).

**Para un tema arbitrario haría falta:** contenedor de contenido distinto a "historia en prosa + palabras" (el schema `story.py` y el prompt serializan todo a prosa lineal con átomos tappeables — la "proyección filológica" de Voronov, plan:37), un `COURSE_PLAN_PROMPT` nuevo (no existe), job async (no existe), y desconectar CEFR/género/pronunciación del camino de generación.

## 7. Los 5 bloqueos reales para estudiar "cualquier cosa" (por dificultad, de mayor a menor)

1. **Dominio: no existe `Course` y el idioma vive en `User`** (difícil, arquitectónico). Un solo `target_language` filtra stories (`stories.py:256`), modules (`modules.py:43`), speak (`speak.py:276`), library (`curriculum/library.py:164`); el nivel es CEFR (`selection.py:31-37`); el SRS y `vocab_items` son globales sin scoping (`inventory.py:68`). Migrar `native/target/level` de `User` a `Course` + backfill + `concept_id`/`course_id` es la F3 entera (plan:109,194) — nada de esto está hecho.
2. **Contenedor de contenido único = historia de idioma** (difícil). El schema `Story` (`story.py:20-70`) y `STORY_SYSTEM_PROMPT` obligan a prosa + lemas + breakdown + quiz de habla; no hay campos neutrales `front/back`/`term`/`gloss` (D-H prometido, plan:114) ni tipos de contenido (código, diagramas, flashcards de concepto). No existe `COURSE_PLAN_PROMPT` ni job async de generación (D-I, plan:115).
3. **Eje de voz/pronunciación asumido** (medio). `FOCUS_PHONEME_SETS={"de"}` (`speak_analysis.py:23-25`), Speak gated a `target_language` (`speak.py:276`), práctica = pronunciación (`practice_queue.py`), TTS con voz por idioma (`config.py:66-71`) y caché que se envenena con texto no-hablable (riesgo #2, plan:226). Falta el eje `speakable:false` por chunk (plan:208).
4. **Perfil sin consumo** (bajo-medio). Todo el F1.5 está hecho pero nada lee `synthesis`/`facts`/`answers`; sin eso la "biblioteca" es una colección de temas iguales, no herramientas = f(tema × perfil) (spec:242).
5. **Frontend hardcodeado a "aleman"** (bajo, mecánico). `courseView.ts:13,40`, `navigate("/curso/aleman")` en 3 rutas, escala CEFR fija (`MapaCurso.tsx:10`), pasos fijos (`courseView.ts:33-38`), `NuevoPlaceholder` vacío. Es lo más barato: adaptadores client-side (F1 del plan) sin tocar backend.

**Veredicto:** la afirmación del usuario se confirma a medias — el shell v4 y el Perfil de Aprendizaje son trabajo real y shippeado; pero la **entidad `Course`, los tipos `tecnico/oral`, `NuevoTema`/`PlanPropuesto` y el consumo del perfil en generación existen solo en docs y mockup**. Hoy klara es una app de alemán con ropa de biblioteca: 1 curso hardcodeado, 1 idioma, 1 formato de contenido, 1 eje de voz.
---

## Corrección de Richter (ronda 3)

Este inventario clasifica `srs.py` y `session.py` como *genéricos (maquinaria de estudio)*. **Es falso a nivel de esquema:**

```python
# backend/src/klara/models/srs.py
vocab_item_id: Mapped[UUID] = mapped_column(
    ForeignKey("vocab_items.id", ondelete="CASCADE"), nullable=False
)
```

El motor de repaso no está atado al idioma *por uso* sino **por clave foránea**, a una tabla cuya identidad es `uq_vocab_lemma_lang_pos`. **Klara no puede agendar nada que no sea un lexema.** El bloqueo #1 no es "el dominio": es una línea de DDL.

Segunda corrección: `vocab_items` es un **catálogo global compartido entre usuarios** (unique sobre `(lemma, language, pos)`, sin `user_id`). Correcto para idiomas (*die Katze* es el mismo objeto para todos); error de categoría para material autoral. Multi-tema no requiere agregar `Course`: requiere **invertir la propiedad del contenido**.
