# Secuencia de aprendizaje — Rebanada 3: género con corrección (alemán)

**Fecha:** 2026-06-16
**Estado:** Diseño aprobado (pendiente de planes de implementación)
**Alcance:** **3 PRs** (estilo R2). UN idioma: alemán. Eje: género gramatical (der/die/das) en **modo CORRECCIÓN** — el segundo eje del contrato de currículo, ahora con una fuente de verdad autoritativa.

---

## 1. El problema (y por qué AHORA es legítimo)

La Rebanada 2 dejó el contrato de currículo vivo (módulos por intensión, generación dirigida, auto-inscripción al SRS, compuerta de avance léxica). El campo `grammatical_focus` de cada módulo (p.ej. *"género de sustantivos de comida"*) es el gancho declarado para esta rebanada. Pero el género **no podía enseñarse antes**: el invariante del currículo —*una intervención es legítima mientras su fuente de verdad sea más autoritativa que el aprendiz al que mide*— se violaba, porque la única "verdad" de género era el LLM escribiéndola y **sobrescribiéndola por historia** (`_upsert_vocab_items`, `story_gen.py:136`). Corregir contra eso sería certificar el eco del modelo como currículo.

**Lo que destraba la Rebanada 3:** un **oráculo de género autoritativo** de dato abierto — [gambolputty/german-nouns](https://github.com/gambolputty/german-nouns), ~100k sustantivos, CSV (`lemma` + `genus` m/f/n → der/die/das), **CC-BY-SA 4.0**, con resolución de compuestos. Con una verdad estable y externa, el género pasa de *exposición* (placebo, descartado en R2) a **corrección**: un cloze de artículo que prueba y corrige contra el oráculo, no contra el LLM.

Evidencia de ciencia del aprendizaje (investigación previa) que sostiene la forma: la corrección explícita metalingüística reduce errores de género ~50% y dura más que la sola exposición; el género alemán es ~70-90% predecible por sufijo (Köpcke); el adulto lo aprende por ruta léxica (palabra+artículo). *(El feedback por sufijo y las incongruencias ES→DE son potentes, pero v1 los difiere — §2 G5.)*

Las **3 precondiciones** que el roster impuso, ahora satisfechas por el diseño: **(1) provenance** (el oráculo gana sobre el LLM), **(2) aridad** (el género es diádico `asigna(sustantivo, artículo)`, necesita su propio binding, no el `UserCard` monádico), **(3) evidencia** (registrar acierto de género por-sustantivo).

## 2. Decisiones marco (cerradas con el dueño + el roster)

| # | Decisión | Elección |
|---|---|---|
| G1 | **Almacén del oráculo** | Tabla nueva `gender_lexicon(lemma, pos, gender)`, sembrada **offline** del CSV de gambolputty por un script idempotente `load_de_gender` (clona `inventory.load_frequency`). **No** el paquete pip en runtime (RAM/latencia por worker, cero ganancia sobre una tabla indexada). |
| G2 | **Compuestos** | Función **pura** `resolve_gender(lemma)` por **sufijo-más-largo** contra el léxico (*Hausaufgabe → Aufgabe → die*), determinista, testeable sin DB, con fallback explícito a `None` ("desconocido") — **nunca** cae a la conjetura del LLM. |
| G3 | **Provenance** | Campo nuevo `VocabItem.gender_source` (`oracle\|llm\|user`, default `llm`). En `_upsert_vocab_items` se consulta el oráculo **antes** del insert; si resuelve, `gender=oráculo` + `source=oracle`, y el `on_conflict` se vuelve **condicional**: el LLM nunca pisa un género `oracle`. La compuerta vive **en el `set_`**, no en código de app (dos historias concurrentes no se pisan). |
| G4 | **Binding diádico** | Tabla nueva `gender_attempt(user_id, vocab_item_id, picked_article, was_correct, attempted_at, detail JSONB)` — **registro de evidencia**, NO extensión de `QuizAttempt` (eso colapsaría dos aridades). Maestría = **predicado derivado** `is_mastered_gender` (hermano de `is_mastered_lexical`, p.ej. N aciertos consecutivos por sustantivo). **Sin scheduler SM-2** — el género por sufijo se internaliza, no decae. |
| G5 | **Feedback v1** | **Binario** contra el oráculo (acierto/fallo + mostrar el artículo correcto). El feedback estratificado por sufijo + incongruencias ES→DE se **difiere a PR-C**. v1 persiste el sufijo detectado en `gender_attempt.detail` para no perder la señal, sin renderizarlo. |
| G6 | **Superficie del cloze** | Nuevo tipo `gender_cloze`, generado **determinista en backend** desde sustantivos del cuento con `gender_source='oracle'`, picker de **3 botones der/die/das (tap, no voz)**, match exacto contra el oráculo, en el flujo Finish existente. **No** reusar el `ClozeQuizItem` de pronunciación (su grading es Azure≥60 en frontend — modelos de corrección incompatibles). |
| G7 | **Licencia** | CC-BY-SA 4.0 → añadir atribución (NOTICE / about). Usamos el dataset como oráculo de referencia cargado en nuestra DB, no lo redistribuimos. |

## 3. Arquitectura

```
ORÁCULO (verdad del mundo)        PROVENANCE (verdad gana al aprendiz)
 gender_lexicon(lemma,pos,gender) → resolve_gender(lemma)  ──┐
                                                              ▼
                            _upsert_vocab_items: si oráculo resuelve →
                            VocabItem.gender = oráculo, gender_source='oracle'
                            (on_conflict condicional: LLM no pisa 'oracle')
                                                              │
EVIDENCIA (aprendiz vs mundo)                                 ▼
 gender_attempt(user,vocab_item,picked,was_correct)  ◄── gender_cloze (Finish)
 is_mastered_gender(user, vocab_item) = predicado derivado    determinista, tap,
                                                              match exacto vs oráculo
```

- **`models/gender_lexicon.py`** (nuevo) — modelo `GenderLexicon(lemma PK, pos, gender)`. **`curriculum/gender_lex.py`** (nuevo) — `resolve_gender(lemma) -> str|None` (sufijo-más-largo + fallback), y `load_gender_lexicon(db, rows)` (upsert idempotente). **`scripts/load_de_gender.py`** — CLI que parsea el CSV y carga.
- **`models/vocab.py`** — `gender_source` (migración aditiva). **`services/story_gen.py`** — consulta el oráculo en `_upsert_vocab_items`; `on_conflict` condicional.
- **`models/gender.py`** (nuevo) — `GenderAttempt`. **`curriculum/competence.py`** — `is_mastered_gender` (hermano de `is_mastered_lexical`).
- **`services/finish_lessons.py`** / **`routers/stories.py`** — generación determinista del `gender_cloze` desde target nouns con `gender_source='oracle'`; endpoint nuevo `POST /stories/{id}/gender/attempts` → escribe `gender_attempt`. **`schemas/`** — `GenderClozeItem`, `GenderAttemptIn/Out`.
- **Frontend** — renderer del picker tap der/die/das en `StoryFinish`, grading por respuesta del backend, POST de la evidencia; i18n en 6 locales.

## 4. Descomposición (3 PRs — orden innegociable: oráculo → provenance → binding → superficie → pedagogía)

- **PR-A — Oráculo + provenance (las precondiciones de verdad).**
  `gender_lexicon` (modelo + migración) + `load_de_gender` (script, CSV) + `resolve_gender` (compuestos, función pura testeable sin DB) + `VocabItem.gender_source` (migración aditiva, default `llm`) + compuerta condicional en `_upsert_vocab_items` (el oráculo gana, fin de la corrupción por historia). **No** toca el quiz ni el frontend. Deja el oráculo cargado y consultable y el género de prod dejando de corromperse.
- **PR-B — Binding + corrección (lo visible al usuario).**
  `gender_attempt` (modelo + migración) + `is_mastered_gender` (`competence.py`) + generación determinista del `gender_cloze` en Finish + picker tap der/die/das (frontend) + grading exacto contra el oráculo + endpoint que escribe la evidencia + i18n. Entrega la corrección de género de cara al usuario.
- **PR-C — Pedagogía (post-ship).**
  Feedback estratificado por sufijo (regla dura `-ung/-heit/-keit/-chen/-lein` vs tendencia `-en/-el/-er`) + marcado de incongruencias ES→DE (*der Mond ≠ la luna*). Posible scheduling de género **solo si** los datos lo justifican.

## 5. Trampas a evitar (del roster)

1. **Resolver la 3ª precondición literal** = añadir `vocab_item_id` a `QuizAttempt`. Colapsa dos aridades (`question_index` queda sin sentido para género; `vocab_item_id` casi siempre nulo para mc/shadow) y tienta a darle un scheduler de olvido SM-2 — modelando la deducción de reglas como decaimiento de memoria. El género por sufijo **no se olvida**.
2. **Cargar german-nouns por pip en runtime** — RAM por worker + latencia de import, cero ganancia sobre tabla indexada.
3. **Reusar el `ClozeQuizItem`** y su grading de pronunciación Azure≥60 "para no duplicar" — funde dos modelos de corrección incompatibles y pierde la arista por-sustantivo.
4. **Construir PR-C dentro de PR-B** — con la ciencia de Köpcke fresca da la tentación de enviar el feedback de sufijo "ya que estamos", convirtiendo ~5 días en ~3 semanas y atrasando la medición del núcleo.
5. **Inventar un `gender_card` con SM-2** antes de tener un solo attempt registrado — diseñar el 2º piso antes de fundir el 1º.

## 6. Fronteras — diferido explícito

- **PR-C (pedagogía):** feedback por sufijo + incongruencias ES→DE + scheduling de género condicional. Diferido.
- **Separación física `gender`/`gender_guess`** (Voronov): endurecimiento opcional; v1 usa una columna `gender` + `gender_source`, suficiente porque la compuerta condicional ya impide la colisión.
- **Parser completo de compuestos:** v1 hace sufijo-más-largo; descomposición morfológica completa diferida.
- **Práctica/SRS de género** (cloze de género en la cola de `/review`): v1 vive solo en Finish; Practice diferido.
- **Otros idiomas con género** (fr/pt): el contrato es genérico; v1 solo alemán.
- **El eje léxico de R1** sigue esperando su TSV de frecuencia — deuda separada, no bloquea esto.
