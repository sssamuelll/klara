# Secuencia de aprendizaje — Rebanada 1: eje léxico dirigido (alemán)

**Fecha:** 2026-06-15
**Estado:** Diseño aprobado (pendiente de plan de implementación)
**Alcance:** un PR. Backend (saneamiento + lematizador + inventario de frecuencia + regla de selección + cobertura) + un toque de frontend (el "por qué"). UN idioma: alemán (es→de). Eje: léxico.

---

## 1. El problema (diagnóstico del consejo)

Klara confunde una **etiqueta** (`user.level`: un escalar CEFR estático, autodeclarado, que nada actualiza — `user.py`) con un **modelo de competencia** (qué dominas, qué te falta, en qué orden). El lazo **evidencia → competencia → generación está abierto**: el sistema mide (SRS `UserCard`, `PronunciationAttempt`, `QuizAttempt`) y descarta la señal. `generate_story` (`services/story_gen.py`) recibe solo `level` + los lemas de las últimas 5 historias (anti-repetición, no secuencia) y el LLM **improvisa** `target_words` a ese escalar congelado, con `frequency_rank` (`models/vocab.py:38`, indexado en `ix_vocab_cefr_freq`) **dormido**.

Sentencia de Axiom-0:

> No falta currículo. Falta **el objeto del que el currículo es solo una sombra**: el estado del aprendiz aún no existe como cosa explícita. La secuencia, el SRS, la frecuencia — todos son funciones que toman ese estado como argumento. Y lo que el dueño nombró (símbolos del japonés, das/der/die del alemán) **no son complejidades distintas: son ejes distintos del mismo objeto de estado**. "Un sistema de historias para todos los idiomas" se rompe donde el estado es un escalar, porque un escalar no puede tener ejes ortogonales por idioma.

## 2. Decisiones marco (cerradas con el dueño)

| # | Decisión | Elección |
|---|---|---|
| D1 | **Resolución de arranque** | Híbrido: **declarar los ejes** del estado del aprendiz ahora, **poblar solo el léxico** en v1. La rebanada barata es el primer eje del modelo real, no un desechable. |
| D2 | **Idioma** | Alemán (es→de) — par del propio dueño, único con hook language-aware (extracción de género), y su eje gramatical declarado prepara la Rebanada 2. |
| D3 | **Fuente de verdad** | Híbrido: esqueleto **curado/externo** (lista de frecuencia con bandas CEFR, licencia abierta — Kelly o SUBTLEX-DE+CEFR) ancla el orden; el LLM solo rellena (historias, glosas). **Nunca** rank derivado por LLM. |
| D4 | **Filtro léxico** | El eje léxico selecciona **palabras de contenido** (sust./verbo/adj.). Las function words (der/die/das, und, ist) NO son ítems léxicos: der/die/das pertenece al eje de género (Rebanada 2). |
| D5 | **Unidad** | Lema canónico con **flexiones agrupadas** (no familias de derivados). Requiere lematización real, no strip de artículos. |
| D6 | **Cobertura** | El LLM redacta alrededor de lemas objetivo elegidos externamente; se **valida** que la historia los contenga; los no cubiertos se descartan (no se afirma enseñar lo ausente). |

## 3. La descomposición completa (contexto — esto es grande)

El problema completo son 9 subsistemas; esta rebanada ataca los de build 1-4 en su mínima expresión léxica. El resto queda **explícitamente diferido** (§9).

| Subsistema | Build | En Rebanada 1 |
|---|---|---|
| Saneamiento de datos + lematización | 1 | **Sí** (paso 0) |
| Inventario de referencia por idioma (frecuencia) | 2 | **Sí** (alemán, léxico) |
| Modelo de estado de competencia | 2 | **Sí** (interfaz + impl. léxica sobre `UserCard`) |
| Cierre del lazo evidencia→competencia→generación | 3 | **Sí** (regla de selección → prompt) |
| Validación de cobertura del output | 4 | **Sí** |
| Visibilidad para el usuario | 4 | **Sí** (mínima, vía `insight`) |
| Modelo de ejes gramaticales por idioma | 5 | No — Rebanada 2 (género) |
| Placement / recalibración | 5 | No — diferido |
| Pipeline japonés | 6 | No — proyecto aparte |

---

## 4. Arquitectura — la columna vertebral (estado + ejes)

El compromiso del híbrido (D1) se materializa SIN sobre-construir:

**(a) Registro de ejes por idioma** — config, no tabla:
```python
# klara/curriculum/axes.py  (nuevo módulo)
LANGUAGE_AXES: dict[str, list[str]] = {
    "de": ["lexical", "gender", "case", "word_order"],   # solo "lexical" activo en v1
    "ja": ["lexical", "orthography", "particles", "pitch"],
    "en": ["lexical"], "fr": ["lexical"], "pt": ["lexical"], "es": ["lexical"],
}
```
"Declarar los ejes" = nombrar el espacio de competencia de cada idioma. Solo `lexical` se puebla; los demás existen como compromiso de forma, no código muerto.

**(b) Interfaz uniforme de competencia** — el "objeto de estado" como contrato, no tabla nueva:
```python
# competence_state(user_id, language, axis) -> CompetenceState
#   .known: set[str]      # lemas dominados/en-aprendizaje (tienen UserCard)
#   .unseen_top(n, band)  # próximos n del inventario, banda <= user.level, no en known
```
Para `lexical` se implementa **sobre lo que ya existe**: el known-set son los lemas con `UserCard` (estado/ease distinguen learning vs mastered); `unseen` = inventario de frecuencia − known. **Cero tabla nueva en v1.** La Rebanada 2 (género) añade otra implementación de la MISMA interfaz; el contrato no cambia. `user.level` queda como **compuerta de banda** (aún no derivado del estado; la interfaz deja el lugar para que lo sea después).

---

## 5. Inventario de referencia (eje léxico de alemán)

El "minuendo": el conjunto de lo enseñable, ordenado. Artefacto **curado one-time** (D3), no algo que el LLM invente.

- **Fuente:** lista de frecuencia alemana con bandas CEFR, licencia abierta. Candidato primario: **Kelly** (CEFR + frecuencia, multi-idioma, abierta); alternativa SUBTLEX-DE + mapeo CEFR. ~2.500 lemas A1–B1 (cobertura ~90-95% del texto corriente según la matemática del corpus lens; suficiente para v1).
- **Carga (script idempotente, no runtime):**
  - Backfill de `frequency_rank` + `cefr_level` sobre `VocabItem` de alemán, casando por lema canónico (post-lematización) + `pos`. **El `cefr_level` de la lista SOBRESCRIBE** el inferido por LLM (que es ruido, no verdad de terreno).
  - Lemas de la lista no presentes → se siembran como `VocabItem` nuevos (rank + banda CEFR; traducción/ejemplo nulos, el LLM los rellena perezosamente al aparecer en una historia).
  - Solo palabras de contenido entran al eje léxico (D4); las function words de la lista se ignoran para selección (pero pueden existir como `VocabItem` para otros usos).
- **Presupone el paso 0** (§7): backfillear sobre filas con `language="de"` mal etiquetado o sin lema canónico ensucia el inventario.

---

## 6. La regla de selección (cierre del lazo)

```
next_target_words(user, "de", n) =
    SELECT vocab WHERE language="de"
      AND pos IN (NOUN, VERB, ADJECTIVE, ADVERB)        -- palabras de contenido (D4)
      AND cefr_level <= user.level                       -- compuerta de banda
      AND frequency_rank IS NOT NULL
      AND canonical_lemma NOT IN known_set(user, "de")   -- la resta
    ORDER BY frequency_rank ASC
    LIMIT n                                              -- n ≈ 3-5
```
- `known_set(user, "de")` = lemas canónicos con `UserCard` del usuario (vía la interfaz §4b).
- **Inyección:** se pasan estos lemas a `generate_story` en el mismo punto donde hoy se pasa `recent_vocab` (`story_gen.py:179,187`). El system/user prompt instruye al LLM a **construir la historia alrededor de estos lemas** (writer, no curador). Es **una query + un cambio de prompt**, no un refactor del motor.
- `user.level` sigue como compuerta (no derivado en v1).

---

## 7. Paso 0 — Saneamiento + lematización (prerrequisito)

Migración/script idempotente, ANTES de poblar el inventario:

1. **`VocabItem.language` mal etiquetado:** corregir las filas alemanas heredadas con `language="de"` por defecto que no son alemán real (fragilidad documentada en `practice_queue.py:36-42`), al menos para el alcance del backfill.
2. **`cefr_level` heredado de la historia:** el actual lo asigna el LLM por inferencia (`story_gen.py:128`). Se reconcilia/sobrescribe contra la lista de referencia para el alemán; lo no presente en la lista queda sin nivel confiable (NULL) en vez de mentir.
3. **Lematización real de alemán** (`simplemma` — ligero, MIT, soporta alemán; **dependencia nueva del backend, decisión consciente**): mapear flexiones (läuft/lief/gelaufen → laufen) a un lema canónico, para que `frequency_rank`, known-set y cobertura cuenten **familias, no flexiones**. Se usa en dos puntos: al normalizar `VocabItem` en la carga, y al chequear cobertura (§8) sobre los tokens de la historia.
   - *Alternativa si se rechaza la dependencia:* lematización por reglas básicas + la lista de Kelly como diccionario de formas. Más frágil; el corpus lens advierte que sin lematización correcta la cobertura es ficción.

---

## 8. Validación de cobertura (honestidad del "aprende esto")

Tras generar la historia:
- Lematizar los tokens del `breakdown`/oraciones y verificar que **cada lema objetivo pedido aparece**.
- **En miss:** quitar los lemas no cubiertos de `Story.target_vocab_item_ids` (no afirmamos enseñar lo ausente) + `log`. **La regeneración automática queda diferida** (costo/latencia) — se documenta como deferral.
- Sin esto, el currículo alucina niveles en silencio.

---

## 9. El "por qué" (cara al usuario, mínimo)

- Por cada palabra objetivo, una línea callada: *"está entre las ~N más comunes que aún no dominas."* Sin rachas ni culpa (coherente con el tono "sin apuro y sin racha").
- Toque de frontend mínimo donde ya se muestran las palabras objetivo (popover de palabra / finish). El pase fino de microcopy se difiere a `solace-wren`.

> **Desviación en implementación:** el plan originalmente proponía reusar `Story.insight`, pero ese campo tiene otra estructura (`insight_title`/`insight_body`, glosa lingüística generada por el LLM). En su lugar la implementación introduce un campo computado `curriculum_note` en `StoryOut`, y el "por qué" por-palabra se expone vía `frequency_rank` en el popover. Cabo suelto conocido: `curriculum_note` aún no se consume en frontend y se emite hardcodeado en español; se localiza o se quita cuando se decida conectarlo (no bloquea v1).

---

## 10. Fronteras — diferido explícito (deuda visible aceptada)

- **Eje gramatical de género (der/die/das) = Rebanada 2.** Es lo que el dueño nombró; queda barato porque su eje ya está declarado (§4a). No en v1.
- **Los otros 5 idiomas siguen improvisando** (en/fr/es/pt/ja): el sistema genérico actual los sirve sin cambios. Deuda visible.
- **Japonés:** proyecto aparte (cambia la unidad de aprendizaje en todo el pipeline).
- **Árbitro SRS-vs-currículo** en la cola diaria: la Rebanada 1 solo dirige la **selección de palabras objetivo de una historia**; no toca la cola diaria de Practice/SRS. El árbitro se decide cuando ambos lazos compitan por la cola.
- **Placement / derivar `user.level`:** diferido; v1 usa `user.level` como compuerta estática.
- **Regeneración por cobertura fallida:** diferida (§8).
- **Objetivo/dominio del usuario** (viaje/negocios) condicionando la selección: diferido (hoy `learning_context` es texto libre).

---

## 11. Testing

**Backend (pytest):**
- `next_target_words`: ordena por `frequency_rank`; respeta la compuerta de banda (`cefr_level <= user.level`); **excluye el known-set**; **filtra a palabras de contenido** (una function word de alto rank NO se selecciona); respeta `limit n`.
- Interfaz de competencia: `known_set` deriva correctamente de `UserCard` (visto/aprendiendo/dominado); un lema sin carta cae en `unseen`.
- Lematizador: flexiones de alemán mapean al lema canónico esperado; la carga agrupa flexiones bajo un lema.
- Cobertura: una historia que contiene los lemas objetivo pasa; una que omite uno → ese lema se quita de `target_vocab_item_ids` y se loguea.
- Script de carga: idempotente (re-correrlo no duplica ni reescribe espurio); sobrescribe `cefr_level` inferido con el de la lista; siembra lemas faltantes.
- Saneamiento: filas `language="de"` mal etiquetadas corregidas en el alcance.

**Frontend:** `typecheck` + `i18n:check` + `build`; el "por qué" se renderiza cuando hay palabras objetivo, y no rompe cuando `insight` está vacío.

---

## Apéndice — procedencia

Diseño derivado de un diagnóstico del consejo (14 agentes, 11 lentes: 5 de dominio — SLA/currículo, CEFR/evaluación, japonés, alemán, lingüística de corpus — + 6 del consejo — Voronov, Serrano, Richter, Lyra, Cassian, Halberg — + crítico de completitud) + síntesis + Axiom-0. El framing de §1 es la sentencia de Axiom-0. El filtro de palabras de contenido (D4) y la lematización-como-prerrequisito (§7) son refinamientos verificados de la lente de lingüística de corpus.
