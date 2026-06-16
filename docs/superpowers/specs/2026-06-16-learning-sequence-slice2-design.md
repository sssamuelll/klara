# Secuencia de aprendizaje — Rebanada 2: eje de género (exposición, alemán)

> **⚠️ SUPERADO (2026-06-16).** Esta dirección (género en modo *exposición*) fue descartada tras revisión adversarial del roster: la exposición sin corrección es un placebo honesto (no enseña género, que es un binding diádico que requiere corrección), el hint suave probablemente no muerde, y solo mordería mientras R1 esté inerte. La feature de género se reorientó a **corrección con oráculo autoritativo** (Wiktionary), y el roster, tras investigación de ciencia del aprendizaje, impuso un orden: **primero la fundación de currículo** (módulo-como-predicado + competencia-por-estado), porque construir UI/gamificación sobre competencia-como-presencia cementa la confusión evento/estado. Ver el spec activo **`2026-06-16-learning-sequence-slice2-modules-foundation-design.md`**. La feature de género-con-corrección pasa a ser **Rebanada 3**, sobre esa fundación. Este documento se conserva como registro del razonamiento.

**Fecha:** 2026-06-16
**Estado:** SUPERADO — ver banner arriba.
**Alcance:** un PR. Backend (lectura de exposición de género + hint de prompt + medición + surfacing) + toque mínimo de frontend (nota de género). UN idioma: alemán (es→de). Eje: género gramatical (der/die/das), **modo EXPOSICIÓN** — no maestría.

---

## 1. El problema (diagnóstico del roster)

La Rebanada 1 cerró el eje **léxico**: `competence.known_set` lee los lemas que el usuario tiene en SRS, y `selection.next_target_words` resta `(corpus por frecuencia) − known_set` para dirigir la historia. El eje de **género** está declarado en `axes.py` (`de: [lexical, gender, case, word_order]`) pero sin implementar. El movimiento ingenuo — clonar `known_set` para género — es un **error de categoría**, y el roster lo desmontó.

Sentencia de Axiom-0 (el invariante):

> Una intervención de currículo es legítima exactamente mientras su **fuente de verdad sea más autoritativa que el aprendiz al que mide**. La Rebanada 1 lo cumplió: `known_set` lee un binding que el propio usuario creó (tienes `UserCard` porque tú decidiste aprender eso). El género lo viola en dos frentes: (a) **aridad** — saber una palabra es un predicado monádico `conoce(x)`, monótono y booleano; saber el género es diádico `asigna_correctamente(x, art)`, ternario y por-ítem (puedes tener `Tisch` en SRS y no saber que es `der`); (b) **autoría** — el binding sustantivo→artículo lo escribió el LLM (`_upsert_vocab_items`, `story_gen.py:116`), no el usuario ni una fuente curada, y `on_conflict_do_update` lo **sobrescribe en silencio por historia** (`set_={"gender": stmt.excluded.gender}`). La "verdad" de género es el último eco del modelo.

**Consecuencia forzada por el código:** hoy **ninguna forma puede afirmar maestría de género**. Un drill der/die/das mediría al aprendiz contra una inferencia del LLM menos confiable que el propio aprendiz — certificaría el eco del modelo como currículo. La única intervención honesta es **seleccionar sesgando exposición, sin nombrar competencia**.

## 2. Decisiones marco (cerradas con el dueño)

| # | Decisión | Elección |
|---|---|---|
| G1 | **Modo** | **Exposición, no maestría.** R2 balancea a qué géneros se EXPONE al usuario; nunca afirma que los domine. No hay oráculo de género confiable hoy (G6), así que afirmar maestría mentiría. |
| G2 | **Contrato** | El género **abre su propio contrato** (distribución por género), NO extiende `competence.known_set` ni su firma `set[str]`. Un set monádico no puede representar un binding diádico sin mentir sobre la aridad. |
| G3 | **Mecanismo** | **Hint en el prompt** (vivo, sin depender del TSV), no re-rank de `next_target_words` (que comparte la inercia de R1). El re-rank queda como refinamiento secundario que se activa solo cuando exista inventario de frecuencia. |
| G4 | **Fuente de exposición** | Distribución de der/die/das entre los `VocabItem` de los `target_vocab_item_ids` de las últimas ~N historias del usuario. **Data viva en prod** (el LLM ya puebla `gender` en cada historia). |
| G5 | **Honestidad** | En NINGUNA frontera (UI, i18n, API, logs) se escribe "dominas/sabes/competencia" sobre lo que es conteo de exposición. El microcopy dice *"has visto sobre todo der"*, jamás *"sabes der"*. |
| G6 | **Drill** | **Deuda visible POST-SHIP**, con dos precondiciones nombradas antes de construirlo (§9). El género no es ítem léxico (consistente con D4 de R1). |

## 3. Qué muerde vivo vs qué espera al TSV (el crux)

La Rebanada 1 está mergeada pero **inerte en prod**: `next_target_words` lee `frequency_rank`, que solo lo puebla el loader del TSV de frecuencia (licencia pendiente). Hay dos caminos para sesgar género, y solo uno muerde hoy:

| Camino | Mecanismo | ¿Muerde hoy? |
|---|---|---|
| **Hint en el prompt** | bloque nuevo en `STORY_USER_PROMPT`, hermano de `target_block`, independiente de `target_lemmas` | **Sí** — moldea los sustantivos que el LLM elige aunque `next_target_words` devuelva `[]` |
| Re-rank de target words | preferir sustantivos de género sub-expuesto dentro de `next_target_words` | No — comparte la inercia de R1 (lee `frequency_rank`, vacío sin TSV) |

R2 se construye sobre el **hint de prompt**. Esto convierte a R2 en **la primera vez que el lazo `estado→prompt→medición` opera contra data real en prod** — la prueba barata del lazo que Lyra exigía, pagada con la única data de currículo que ya está viva (el género), no con la que está bloqueada por licencia (la frecuencia).

---

## 4. Arquitectura — contrato propio del eje de género

El género **no** reusa la interfaz de competencia léxica. Abre un contrato propio, deliberadamente angosto:

```python
# klara/curriculum/gender.py  (nuevo módulo)
# GenderExposure: el estado de género legible HOY, como distribución, no como set.
#   .counts: dict[str, int]        # {"der": n, "die": m, "das": k}
#   .total: int
#   .underexposed: list[str]       # géneros por debajo de la cuota pareja, asc
#
# async def gender_exposure(db, *, user_id, language) -> GenderExposure
#   Cuenta der/die/das entre los VocabItem referenciados por los
#   target_vocab_item_ids de las últimas ~10 historias del usuario en `language`
#   (ventana tuneable; acota la lectura y refleja exposición reciente, no histórica).
```

- Es estado **legible y vivo** (los `target_vocab_item_ids` y `VocabItem.gender` existen en prod). **Cero tabla nueva, cero migración.**
- `underexposed` se computa contra una cuota pareja (1/3 cada género para alemán): los géneros con conteo bajo la media. Si la exposición es pareja o nula (usuario nuevo), `underexposed` cae a un default sensato (favorecer die/das, los menos frecuentes en texto y los que más cuestan a hispanohablantes).
- **No toca `competence.py`.** Si una rebanada futura necesitara un known-set de género (maestría), abriría su propia estructura de binding, no el `set[str]` monádico (G2).
- **Limitación honesta documentada:** la "exposición" se mide sobre los *target words* (subconjunto curado), no sobre todos los sustantivos del cuento. El desglose de oraciones (`breakdown`) no lleva género hoy, así que medir la exposición total exigiría un join lema→`VocabItem` por token. Se difiere; los target words son el binding más limpio con género adjunto.

---

## 5. La intervención (cierre del lazo, vivo)

```
1. exposure = gender_exposure(user, "de")
2. hint = "El estudiante ha visto sobre todo {dominante}; favorece sustantivos
           {underexposed} donde sea natural, sin forzar la historia."   # o None
3. build_story_user_prompt(..., gender_hint=hint)   # bloque nuevo, independiente de target_lemmas
4. generate_story corre igual que hoy; el LLM redacta favoreciendo esos géneros
5. medición post-hoc: distribución de género de los target_words generados → log
```

- **Punto de inyección:** `build_story_user_prompt` (`prompts.py:109`) gana un parámetro `gender_hint: str | None`; se añade un placeholder hermano de `{target_block}` en `STORY_USER_PROMPT` (`prompts.py:101`). El hint es **independiente de `target_lemmas`**, por eso muerde aunque no haya selección léxica (sin TSV).
- **Solo alemán:** el hint se construye solo para `target_language == "de"`; para los demás idiomas `gender_hint=None` y el bloque queda vacío (igual que `target_block`).
- **No fuerza:** el hint es una preferencia ("favorece … donde sea natural"), no una orden rígida — el LLM no debe deformar la historia para cumplir una cuota. La medición (§8) dice si cumplió, no lo bloquea.
- Es **un cambio de prompt + una query de lectura**, no un refactor del motor de generación. Simétrico a R1.

---

## 6. Surfacing (el porqué, lenguaje de exposición)

- El `gender` **ya viaja** en `StoryWordOut` (`schemas/story.py`, serializado en `stories.py:67`) y **ya se pinta** como artículo coloreado en `WordPopover.tsx` (der azul / die rojo / das verde). **Cero UI nueva** para mostrar el género en sí.
- Se añade una **nota de género** a nivel historia, por la misma vía que `curriculum_note` (`stories.py:78`), en **lenguaje de exposición**: p.ej. *"Esta historia trae más die/das — has venido viendo sobre todo der."* Nunca afirma maestría.
- La nota se emite solo cuando hay señal de exposición real (no para el usuario nuevo sin historial).

## 7. Contrato de honestidad + i18n

- **Honestidad (G5), innegociable:** toda cadena cara al usuario en lenguaje de exposición. Prohibido "dominas / sabes / competencia / maestría" sobre conteos de exposición. La frontera donde el significado colapsa (de conteo a dominio) es exactamente la UI/i18n; ahí se vigila.
- **i18n:** keys nuevas en los 6 locales (`es/en/de/fr/ja/pt`), `i18n:check` enforced, `es` como fuente. El pase fino de microcopy se difiere a **solace-wren** (como en R1).
- **Cabo de R1 a resolver en el plan:** el `curriculum_note` actual quedó hardcodeado en español y sin consumir en frontend. Para la nota de género se decide en el plan: localizarla bien desde el inicio (threading de `locale` en `_serialize_story`) **o** seguir el patrón diferido de R1. Recomendación: localizarla bien, ya que aquí sí se consume; el costo de threading `locale` es menor que la incoherencia.

## 8. Medición / validación del lazo (telemetría)

Sin esto R2 sería otra rebanada que no sabemos si funciona. Tras generar:

- Computar la distribución de género de los `target_words` realmente generados (tienen `gender` vía `_parse_gender`).
- `log.info("story.gender.balance", requested_underexposed=…, produced_counts=…, target_language="de")` — análogo a `story.curriculum.missed`/`dropped` de R1.
- Esta es **la señal que dice si el LLM obedece el hint** — la validación viva del lazo `estado→prompt→medición`. No bloquea la generación; es telemetría de calidad.

---

## 9. Fronteras — diferido explícito (deuda visible aceptada)

- **Drill der/die/das = POST-SHIP**, con **dos precondiciones** antes de construirlo:
  1. **Congelar la autoría del género.** Hoy `_upsert_vocab_items` sobrescribe `gender` por historia (`set_={"gender": …}`). Antes de medir acierto hay que defender un binding establecido (no sobrescribir un género ya fijado, o mover la verdad a una fuente con provenance).
  2. **Crear el referente.** `QuizAttempt` (`stories.py:359`) ya tiene `was_correct` + `detail` JSONB, pero se ancla a `story_id` + `question_index`, **nunca a `vocab_item_id`**. Falta esa arista para que un fallo de pregunta se conecte con el fallo de género de un sustantivo concreto. El mecanismo de evidencia ya existe; falta la arista.
- **El eje no extiende `known_set`.** Si una rebanada futura modela maestría de género, abre su propio contrato de binding (G2).
- **Re-rank de selección por género** (camino inerte de §3): refinamiento secundario, se activa cuando exista el TSV de frecuencia. No en esta rebanada.
- **Exposición total (no solo target words):** medir el género de TODOS los sustantivos del cuento exige género en el `breakdown` o un join lema→`VocabItem`. Diferido (§4).
- **Otros idiomas con género** (fr/pt): el contrato de género es genérico, pero v1 solo lo activa para alemán. Deuda visible.

### Frente paralelo (no bloquea R2): adquisición del TSV de frecuencia

Documento aparte con las fuentes candidatas de lista de frecuencia alemana (Kelly-DE, SUBTLEX-DE, DeReWo) y su situación de licencia, para que el dueño decida la adquisición. R2 no lo necesita para morder; pero cargarlo es lo que desentumece el eje léxico de R1 **y** activa el re-rank de género (§3). Es la apuesta asimétrica que valida ambas rebanadas.
