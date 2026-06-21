# Secuencia de aprendizaje — Rebanada 3 PR-C: pedagogía de género (alemán)

**Fecha:** 2026-06-21
**Estado:** Diseño aprobado (decisiones de alcance cerradas; pendiente de plan de implementación)
**Alcance:** **1 PR, backend-only.** UN idioma: alemán. Cierra la Rebanada 3 (PR-A oráculo+provenance #67, PR-B cloze+evidencia #68 — ambos mergeados). PR-C añade la **pedagogía sobre la evidencia que ya se registra**: feedback de regla de sufijo (determinista, autoritativo) y un predicado de maestría de género de solo-display.

---

## 1. El problema (provenance vs *modalidad*)

PR-A/PR-B dejaron el género corregible: oráculo autoritativo (`gender_lexicon`), provenance (`VocabItem.gender_source ∈ oracle|llm|user`, el oráculo gana), evidencia diádica (`gender_attempts`), y un cloze der/die/das calificado en el servidor. El `GenderAttempt.detail` (JSONB) quedó **reservado** para esta rebanada y hoy está sin usar.

El diagnóstico del roster identificó el invariante que gobierna PR-C, una extensión del de Axiom-0: **el sistema formalizó *quién lo dice* (`gender_source`) pero nunca *qué tipo de afirmación es*** (hecho del oráculo vs tendencia estadística vs inferencia vs *el aprendiz ya lo sabe*). Las tres piezas que el spec de R3 difirió a PR-C son la misma enfermedad — una nueva **modalidad** de afirmación intentando pasar por una aduana que solo inspecciona la **procedencia**, pidiéndole prestada al oráculo una certeza que no posee.

De ahí la regla maestra de PR-C: **una regla de sufijo es una generalización SOBRE el oráculo, y por tanto estrictamente menos autoritativa que el oráculo por-palabra.** El género del oráculo **siempre** es la verdad mostrada; la regla solo aparece como *explicación* cuando coincide con el oráculo (o la palabra está en una lista cerrada y curada de excepciones). El aprendiz nunca ve “los `-er` son *der*” al lado de *die Mutter*.

Evidencia de ciencia del aprendizaje (Köpcke & Zubin; investigación de corrective feedback): el género alemán es ~70-90% predecible por sufijo, pero esa fiabilidad **se reparte de forma muy desigual** entre sufijos. Las reglas duras productivas (`-ung/-heit/-keit…`) son procedimientos inducidos que **generalizan a palabras nuevas y no decaen** como la memoria de ítems arbitrarios; lo que sí decae (excepciones cerradas, trampas de transferencia L1) ya está a la granularidad correcta en `gender_attempts` por-sustantivo.

## 2. Decisiones de marco (cerradas con el dueño + el roster)

| # | Decisión | Elección |
|---|----------|----------|
| C1 | **Detector de sufijo** | Función **pura, síncrona, sin DB** (hermana del resolver de compuestos), `lemma → {suffix, article der/die/das, kind: hard\|tendency} \| None`. El detector es **deliberadamente simple** — match de sufijo-más-largo con un **guard de stem mínimo** (el resto del lema tras quitar el sufijo debe quedar con ≥2 caracteres, para no disparar sobre palabras absurdamente cortas) — porque el **verdadero backstop de falsos positivos es la reconciliación del Caso B contra el oráculo**, no la inteligencia del detector. No intenta análisis morfológico completo. Vive standalone; se invoca **solo** dentro de `record_gender_attempt`, en el camino ya protegido por `gender_source=='oracle'`. **Nunca** se cablea en `resolve_gender` (eso forjaría autoridad de oráculo sobre un guess). |
| C2 | **Reconciliación contra el oráculo** | Por-intento, en tiempo de calificación, con la política de **3 casos** (§4). El género mostrado es **siempre** el del oráculo; la regla se muestra solo en coincidencia o excepción curada. |
| C3 | **Persistencia** | Esquema **fijo** en el `GenderAttempt.detail` JSONB ya reservado: `{suffix, suffix_class, rule_gender, oracle_gender, agreement, exception_listed}`. Escritura aditiva en el insert, sin migración, sin re-lectura. Se persiste **siempre** que se detecte un sufijo — incluida la discrepancia del Caso B (señal de bug para auditoría offline). |
| C4 | **Respuesta al cliente** | Campo **opcional/defaulted** nuevo en `GenderAttemptOut` (`rule: GenderRuleOut \| None`) con el subconjunto **mostrable** (poblado solo en Caso A/C; `null` en B, NULL-grade y sin-sufijo). **NUNCA** en `GenderClozeQuizItem` (filtraría la respuesta antes de contestar; rompería el contrato no-leak endurecido en PR-B). Se añade ahora para que PR-C.1 (el render) sea puro frontend. |
| C5 | **`is_mastered_gender`** | `async def is_mastered_gender(db, *, user_id, vocab_item_id) -> bool` en `competence.py`, hermano del contrato de `is_mastered_lexical` (no del almacenamiento — no hay card por sustantivo). Lee los `GenderAttempt.was_correct` **ya almacenados** (nunca re-califica contra un `VocabItem.gender` posiblemente mutado). Semántica: **“los últimos N intentos por sustantivo, todos correctos”** (no “consecutivos” — el log es append-only, sin unicidad `(user,vocab)` y con orden grueso por `attempted_at`). **N = 3**, vía constante `GENDER_MASTERY_STREAK_N` junto a `MASTERY_INTERVAL_DAYS`. |
| C6 | **Consumidor de maestría** | **Solo display**: `gender_mastered`/`gender_total` en `ModuleCurrentOut` (vía `GET /modules/current`, que el Home ya consume). **NO** entra a `advance_module_if_mastered` (la compuerta queda léxica y de un solo escritor). |
| C7 | **Alcance UI** | **Backend-only en PR-C.** El render de la nota de sufijo + las 6 claves de locale (es/en/de/fr/pt/ja) van en un **follow-up PR-C.1** (tarea de microcopy / solace-wren), para mantener PR-C atómico y revisar los contratos no-leak/paridad aislados. |
| C8 | **Incongruencia ES→DE** | **Diferida, fuera de PR-C.** No existe fuente autoritativa del género español (`translations` es un string del LLM sin artículo); inferirlo o preguntarle al LLM reinstala el “eco del modelo”, y en el eje español el aprendiz venezolano **le gana en autoridad** a cualquier fuente que el sistema produzca (Axiom-0 prohíbe que el sistema sea la autoridad del lado ES). Si algún día se hace: **solo contenido curado a mano** (~50-150 pares de conflicto, `provenance='curated'`, scope ES), **nunca un auto-diff**. Queda en backlog. |
| C9 | **Scheduling de género** | **Diferido.** Indecidible con N=0 evidencia en prod; la investigación respalda que las reglas duras no decaen (SM-2 sobre “`-ung` es femenino” es error de categoría). Instrumentar el `detail` (C3) primero; decidir empíricamente después. |
| C10 | **Lockstep de selección** | El detector es feedback **aditivo**; **no** cambia qué palabras son elegibles. El contrato de selección (de + oráculo + der/die/das) sigue idéntico en `build_gender_cloze` y en el endpoint. Una palabra que se sirve como cloze debe seguir siendo calificable. |

## 3. Tabla autoritativa de sufijos (de la lente de ciencia del aprendizaje)

**Sufijos DUROS** — enseñables como regla (`kind: "hard"`, ~100%, excepciones nulas o de clase cerrada):

| Sufijo | Género | Notas |
|--------|--------|-------|
| `-chen` | das | Diminutivo; sin excepciones productivas (*das Mädchen* pese al referente — el sufijo porta el género, no la raíz). |
| `-lein` | das | Diminutivo; sin excepciones. |
| `-ung` | die | ~100% en vocabulario normal. *der Schwung/Sprung* terminan en “ung” pero no son `-ung` derivados; como el detector hace match simple, estos disparan un falso positivo que la **reconciliación del Caso B** (regla `die` contra oráculo `der`) suprime y registra. No se intenta distinguirlos en el detector. |
| `-heit` | die | Exceptionless. |
| `-keit` | die | Exceptionless. |
| `-schaft` | die | Exceptionless. |
| `-tät` (`-ität`) | die | Latino; ~100% (*die Qualität, die Universität*). |
| `-ion` (`-tion/-sion`) | die | ~100% en vocabulario normal. |
| `-ling` | der | Sin excepciones productivas (*der Lehrling, der Schmetterling*). |
| `-ismus` | der | ~100% (*der Kapitalismus*). |
| `-ment` | das | ~100% en vocabulario normal (*das Dokument, das Instrument*). *der Moment* es un lexema/sentido distinto; lo maneja la reconciliación con el oráculo. |
| `-tum` | das | Enseñable **porque la excepción es cerrada y enumerable**: das salvo **der Reichtum** y **der Irrtum** (el Caso C canónico). No confundir con el latino `-um` (*das Datum, das Museum*), que es separado. |

**Sufijos de TENDENCIA** — `kind: "tendency"`, suavizados (“suelen ser…”), **jamás absolutos**:

| Sufijo | Tendencia | Notas |
|--------|-----------|-------|
| `-e` (polisilábico) | die (~90%) | *die Blume/Lampe/Katze*, pero *der Name/Junge/Käse, das Auge/Ende*. |
| `-er` | der (~70-80%) | Agentivos fiables (*der Lehrer*), pero *die Mutter/Butter, das Messer/Fenster/Wasser/Zimmer*. La trampa clásica — nunca como regla. |
| `-el` | der (~60-70%) | Genuinamente partido: *der Löffel/Mantel* vs *die Gabel/Insel, das Mittel/Segel*. |
| `-en` | der (~70%) | Subregularidades en competencia; los infinitivos nominalizados son das (*das Schwimmen*). |
| `-ie/-ik/-ur` | die | Tendencia alta con excepciones de préstamo (*das Genie/Mosaik, der Atlantik, das Abitur/Futur*). |
| `-nis` | die/das | Genuinamente partido (*die Erlaubnis/Kenntnis* vs *das Ergebnis/Verständnis/Zeugnis*). Dos géneros — nunca regla; si se muestra, solo “die o das”. |

El detector devuelve el sufijo **más largo que matchee** (p.ej. `-ität` antes que `-tät` antes que un hipotético `-ät`), evaluando primero las reglas duras. Si nada matchea: sin regla (Caso sin-sufijo).

## 4. Política de excepciones — 3 casos (+ NULL)

Decidida por-intento, en tiempo de calificación, dentro del guard `gender_source=='oracle'` del endpoint, usando el sufijo detectado + `vocab.gender` (el artículo del oráculo):

- **Caso A — la regla coincide con el oráculo** (lo común): se muestra la regla, atribuida.
  - Sufijo **duro** → como regla: *“Wohnung es die — todo `-ung` es femenino.”*
  - Sufijo **tendencia** → suavizado: *“los `-e` suelen ser die”*, nunca “siempre”.
  - `detail.agreement = true`, `exception_listed = false`; respuesta `rule` poblada.
- **Caso B — la regla contradice un sufijo duro** (debe ser casi vacío): es casi siempre un **falso positivo del detector** (el problema “Schwung”), no una excepción real. Se **suprime la regla**, se muestra solo la verdad binaria (*“das, no der”*), y se **persiste la discrepancia** en `detail` como señal de bug. `detail.agreement = false`, `exception_listed = false`; respuesta `rule = null`.
- **Caso C — contradice en una excepción de clase cerrada y curada** (*der Reichtum, der Irrtum* para `-tum`): el ÚNICO lugar donde se enseña una excepción, de alto valor por memorable: *“los `-tum` son das — pero Reichtum e Irrtum van der.”* Permitido **solo** si la palabra está en una lista enumerada a mano (no derivada al vuelo). `detail.agreement = false`, `exception_listed = true`; respuesta `rule` poblada con `is_exception = true`.
- **NULL — sin género verificado** (fallo de red/calificación, `correct_gender` nulo): ni regla ni nota. No se puede anclar una explicación a un género no verificado.

**Garantía:** el género mostrado es siempre el del oráculo; la regla aparece solo cuando coincide con el oráculo o la palabra está curada. El feedback metalingüístico **nunca puede ser menos autoritativo que la fuente de verdad**, y el sistema nunca afirma una regla que la palabra concreta frente al aprendiz viola.

## 5. Arquitectura y unidades

```
DETECTOR (puro, sin DB)            RECONCILIACIÓN (oráculo manda)
 detect_gender_rule(lemma)         record_gender_attempt (stories.py)
   -> {article, kind} | None  ──►   - guard: gender_source=='oracle' (ya existe)
                                     - regla = detect_gender_rule(vocab.lemma)
                                     - 3-casos vs vocab.gender + lista curada
                                     - detail = {suffix, suffix_class, rule_gender,
EVIDENCIA (ya existe)                          oracle_gender, agreement, exception_listed}
 gender_attempts(was_correct,        - GenderAttempt(detail=...)  [insert aditivo]
                 detail JSONB)        - GenderAttemptOut(rule= mostrable | None)
   │
   ▼
 is_mastered_gender(user, vocab)    DISPLAY (consumidor vivo, no dead code)
  = últimos N was_correct = True  ──► ModuleCurrentOut.gender_mastered/gender_total
  (async, lee filas; N=3)             vía GET /modules/current (Home ya lo llama)
```

- **`curriculum/gender_rules.py`** (nuevo) — `detect_gender_rule(lemma) -> GenderRule | None` (puro, frontera morfológica, sufijo-más-largo, duro-primero) + la **lista cerrada curada** de excepciones (`_CURATED_EXCEPTIONS: dict[str, str]`, p.ej. `{"Reichtum": "der", "Irrtum": "der"}`) + la función de reconciliación pura `reconcile_rule(rule, oracle_gender, lemma) -> ReconciledRule` que implementa los 3 casos y produce el objeto `detail` + el flag de mostrabilidad. Todo testeable sin DB.
- **`schemas/finish.py`** — `GenderRuleOut` (subconjunto mostrable: `suffix`, `suffix_class`, `rule_gender`, `is_exception`) + campo opcional `rule: GenderRuleOut | None = None` en `GenderAttemptOut`.
- **`routers/stories.py`** — `record_gender_attempt`: tras calcular `was_correct`, computa la regla, reconcilia, escribe `detail` en el `GenderAttempt`, y puebla `rule` en la respuesta cuando sea mostrable. **Una sola** computación in-scope; persiste y devuelve el mismo objeto (sin `db.refresh`).
- **`curriculum/competence.py`** — `is_mastered_gender(...)` (async, “últimos N todos correctos”, constante `GENDER_MASTERY_STREAK_N=3`) + `module_gender_progress(db, *, user_id, module_id) -> tuple[int,int]` (gender_mastered, gender_total) en dos queries: (a) el set elegible del módulo (module_vocab ⋈ vocab_items donde de + oráculo + género in der/die/das), (b) los `GenderAttempt` del usuario para esos `vocab_item_id`, agrupados en Python por sustantivo (orden por `attempted_at` desc, tomar últimos N, todos correctos). Sin N+1.
- **`schemas/module.py`** — `ModuleCurrentOut`: `gender_mastered: int`, `gender_total: int`.
- **`routers/modules.py`** — `get_current_module`: llama `module_gender_progress` y puebla los dos campos.

## 6. Manejo de errores / casos borde

- **Sufijo no detectado** → sin regla, sin `detail` de regla (o `detail=null`); la respuesta `rule=null`. Comportamiento idéntico al de hoy salvo el campo opcional.
- **Caso B (falso positivo)** → regla suprimida, verdad binaria, discrepancia persistida. No se rompe el grading.
- **NULL grade** → ni regla ni nota.
- **Homógrafos** (*der/die See*) → el PK por lema colapsa a un género (last-write-wins, limitación pre-existente de PR-A). La maestría y las notas descansan sobre el `was_correct` almacenado contra el único género del oráculo; **no se afirman excepciones de sufijo para homógrafos**. Documentado como límite v1.
- **`detail` drift** → se computa una vez in-scope, se persiste ese objeto exacto y se devuelve ese objeto exacto; sin re-lectura.
- **Universalidad** → el detector es alemán por contrato; se invoca solo dentro del guard de + oráculo. El colapso de universalidad es esperado y acotado, no una regresión.

## 7. Pruebas

- **Detector** (puro): tabla duro-vs-tendencia (cada sufijo de §3 → género + kind correctos); frontera morfológica (*Schwung* NO matchea `-ung`; *Datum* NO matchea `-tum`); sufijo-más-largo (*Universität* → `-ität`, no `-tät`).
- **Reconciliación** (pura): Caso A duro (regla mostrable, `agreement=true`); Caso A tendencia (suavizado); Caso B (regla suprimida, `rule=null`, `detail.agreement=false` persistido); Caso C curado (*Reichtum* → `is_exception=true`, mostrable); NULL → nada.
- **Endpoint**: `detail` persistido con el esquema fijo; `GenderAttemptOut.rule` poblado/nulo según caso; backward-compat (clientes viejos ignoran el campo opcional); **el contrato no-leak del `gender_cloze` sigue intacto** (el `GenderClozeQuizItem` no gana ningún campo).
- **`is_mastered_gender`**: bordes de racha (3 correctos seguidos = true; 2 correctos + 1 fallo reciente = false; orden por `attempted_at`; menos de N intentos = false).
- **`module_gender_progress`**: gender_total = nouns elegibles del módulo; gender_mastered cuenta solo los maestreados; módulo sin nouns-oráculo → (0, 0).
- **Suite completa** sin regresión; ruff (E,F,I,B,UP,RUF) limpio; roundtrip de migración N/A (sin migración — `detail` ya existe).

## 8. Fronteras — diferido explícito

- **PR-C.1 (follow-up):** render de la nota de sufijo en el verdict de `StoryFinish` + 6 claves de locale (tarea de microcopy). Puro frontend gracias al campo `rule` que PR-C ya devuelve.
- **Incongruencia ES→DE:** backlog, solo contenido curado, nunca auto-diff (C8).
- **Scheduling de género:** diferido hasta tener datos; instrumentar primero (C9).
- **Gender en la compuerta de avance:** no — la compuerta queda léxica y de un solo escritor (C6/D4).
- **Soporte de homógrafos:** límite v1 documentado.
- **El eje léxico de R1** (TSV de frecuencia) sigue siendo deuda separada, no bloquea esto.
