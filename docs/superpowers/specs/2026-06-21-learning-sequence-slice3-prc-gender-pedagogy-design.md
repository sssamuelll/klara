# Secuencia de aprendizaje — Rebanada 3 PR-C: pedagogía de género (alemán)

**Fecha:** 2026-06-21
**Estado:** Diseño aprobado (decisiones de alcance cerradas; revisado adversarialmente por el roster; pendiente de plan)
**Alcance:** **1 PR, backend-only.** UN idioma: alemán. Cierra la Rebanada 3 (PR-A oráculo+provenance #67, PR-B cloze+evidencia #68 — ambos mergeados). PR-C añade la **pedagogía sobre la evidencia que ya se registra**: feedback de regla de sufijo (determinista, autoritativo) y un predicado de maestría de género de solo-display.

---

## 1. El problema (provenance vs *modalidad*)

PR-A/PR-B dejaron el género corregible: oráculo autoritativo (`gender_lexicon`), provenance (`VocabItem.gender_source ∈ oracle|llm|user`, el oráculo gana), evidencia diádica (`gender_attempts`), y un cloze der/die/das calificado en el servidor. El `GenderAttempt.detail` (JSONB nullable) quedó **reservado** para esta rebanada y hoy está sin usar.

El diagnóstico del roster identificó el invariante que gobierna PR-C, una extensión del de Axiom-0: **el sistema formalizó *quién lo dice* (`gender_source`) pero nunca *qué tipo de afirmación es*** (hecho del oráculo vs tendencia estadística vs inferencia vs *el aprendiz ya lo sabe*). Las tres piezas que el spec de R3 difirió a PR-C son la misma enfermedad — una nueva **modalidad** de afirmación intentando pasar por una aduana que solo inspecciona la **procedencia**, pidiéndole prestada al oráculo una certeza que no posee.

De ahí la regla maestra de PR-C: **una regla de sufijo es una generalización SOBRE el oráculo, y por tanto estrictamente menos autoritativa que el oráculo por-palabra.** El género del oráculo **siempre** es la verdad mostrada; la regla solo aparece como *explicación* cuando coincide con el oráculo (o la palabra está en una lista cerrada y curada de excepciones). El aprendiz nunca ve "los `-er` son *der*" al lado de *die Mutter*.

Evidencia de ciencia del aprendizaje (Köpcke & Zubin; corrective feedback): el género alemán es ~70-90% predecible por sufijo, pero esa fiabilidad se reparte de forma muy desigual. Las reglas duras productivas (`-ung/-heit/-keit…`) son procedimientos inducidos que **generalizan a palabras nuevas y no decaen** como la memoria de ítems arbitrarios; lo que sí decae (excepciones cerradas, trampas de transferencia L1) ya está a la granularidad correcta en `gender_attempts` por-sustantivo.

## 2. Decisiones de marco (cerradas con el dueño + el roster)

| # | Decisión | Elección |
|---|----------|----------|
| C1 | **Detector de sufijo** | Función **pura, síncrona, sin DB** (hermana del resolver de compuestos), `detect_gender_rule(lemma) -> GenderRule \| None`. El detector es **deliberadamente simple** — match de **sufijo-más-largo** con un **guard de stem mínimo** (el resto del lema tras quitar el sufijo debe quedar con **≥2 codepoints**, para no disparar sobre palabras absurdamente cortas) — porque el **verdadero backstop de falsos positivos es la reconciliación contra el oráculo (Caso B)**, no la inteligencia del detector. **Orden determinista único:** match **más largo primero**; ante empate de longitud, **duro antes que tendencia** (con la tabla §3 actual no hay colisión cross-class real — es robustez, no bug activo). No intenta análisis morfológico completo. Vive standalone; se invoca **solo** dentro de `record_gender_attempt`, en el camino ya protegido por `gender_source=='oracle'` (donde `vocab.gender` es siempre no-nulo). **Nunca** se cablea en `resolve_gender` (eso forjaría autoridad de oráculo sobre un guess). |
| C2 | **Reconciliación contra el oráculo** | Pura: `reconcile_rule(rule, oracle_gender, lemma) -> GenderRuleDetail`. **Solo se invoca con un `rule` no-nulo**; el guard sin-sufijo→`detail=null` vive en el call site (`record_gender_attempt`), no dentro de `reconcile_rule` (por eso su retorno nunca es `None`). **`agreement` (rule_gender == oracle_gender) es la ÚNICA compuerta para mostrar**; `suffix_class` (hard\|tendency) solo le da sabor a la copy del Caso A, no controla el flujo. La proyección `GenderRuleDetail` (6 llaves) → `GenderRuleOut` (4 llaves) se construye también en el call site. Política de casos en §4. |
| C3 | **Persistencia** | Esquema **fijo** en el `GenderAttempt.detail` JSONB ya reservado: el objeto `GenderRuleDetail` de 6 llaves (§5). Escritura aditiva en el insert, sin migración, sin re-lectura. Se persiste **siempre que se detecte un sufijo** — con **las 6 llaves pobladas**, incluida la discrepancia del Caso B (señal de bug para auditoría offline). Si no se detecta sufijo: `detail = null`. |
| C4 | **Respuesta al cliente** | Campo **opcional/defaulted** nuevo en `GenderAttemptOut` (`rule: GenderRuleOut \| None = None`) — proyección estricta del `detail` (§5). Poblado **solo cuando es mostrable** (Caso A o C); `null` en Caso B y en sin-sufijo. **NUNCA** en `GenderClozeQuizItem` (filtraría la respuesta antes de contestar; rompería el contrato no-leak endurecido en PR-B). Se añade ahora para que PR-C.1 (el render) sea puro frontend. |
| C5 | **`is_mastered_gender`** | `async def is_mastered_gender(db, *, user_id, vocab_item_id) -> bool` en `competence.py`, la **implementación de género del contrato de competencia** que el docstring del módulo ya anuncia — hermano de `is_mastered_lexical` (que hoy **tampoco tiene caller directo**: tanto la compuerta como `module_progress` inlinean/comparten su lógica; es un predicado-contrato nombrado). No es dead code: es el predicado per-noun del contrato, disponible para callers futuros (una compuerta de género o Practice). Lee los `GenderAttempt.was_correct` **ya almacenados** (nunca re-califica contra un `VocabItem.gender` posiblemente mutado). Semántica: **maestría sii hay al menos N intentos para el sustantivo Y los últimos N son todos correctos** (el piso `<N ⇒ false` es normativo, no solo de test). Orden determinista **`ORDER BY attempted_at DESC, id DESC`** (`attempted_at` es grueso y sin índice propio; `id` es uuid4 — desempata determinísticamente aunque no cronológicamente, aceptable). **N = 3**, vía constante `GENDER_MASTERY_STREAK_N`. El cómputo de racha vive en **un helper puro compartido** `_streak_mastered(attempts_desc, n) -> bool`; `module_gender_progress` lo usa **directamente** sobre su lectura bulk (igual que `module_progress` inlinea el filtro léxico en vez de llamar a `is_mastered_lexical`), e `is_mastered_gender` lo usa sobre la lectura per-noun — un solo origen de verdad, no pueden divergir. |
| C6 | **Consumidor de maestría** | **Solo display**, en **tri-estado paralelo al léxico**: `gender_encountered`/`gender_mastered`/`gender_total` en `ModuleCurrentOut` (vía `GET /modules/current`, que el Home ya consume), espejo exacto de `(encountered, mastered, total)`. **NO** entra a `advance_module_if_mastered` (la compuerta queda léxica y de un solo escritor). |
| C7 | **Alcance UI** | **Backend-only en PR-C.** El render de la nota de sufijo + las 6 claves de locale (es/en/de/fr/pt/ja) van en un **follow-up PR-C.1** (tarea de microcopy / solace-wren). |
| C8 | **Incongruencia ES→DE** | **Diferida, fuera de PR-C.** No existe fuente autoritativa del género español (`translations` es un string del LLM sin artículo); inferirlo reinstala el "eco del modelo", y en el eje español el aprendiz venezolano **le gana en autoridad** a cualquier fuente del sistema (Axiom-0 prohíbe que el sistema sea la autoridad del lado ES). Si algún día: **solo contenido curado a mano**, **nunca un auto-diff**. Backlog. |
| C9 | **Scheduling de género** | **Diferido.** Indecidible con N=0 evidencia; las reglas duras no decaen. Instrumentar el `detail` (C3) primero. |
| C10 | **Lockstep de selección + semántica del denominador** | El detector es feedback **aditivo**; **no** cambia qué palabras son elegibles. El **predicado** de elegibilidad (de + oráculo + `pos==NOUN` + género ∈ der/die/das) es idéntico en `build_gender_cloze` y en `module_gender_progress` ("lockstep" = mismo predicado, no misma cardinalidad). **El denominador es exposición, no algo que el aprendiz lleve solo a 1.0.** `build_gender_cloze` sirve **solo el primer noun elegible por historia**, y ese orden lo gobierna la composición de la historia (no el aprendiz), así que un noun nunca-primero-elegible podría no servirse nunca. **Por eso `gender_total` se trata exactamente como el `total` léxico: el tamaño del currículo de género del módulo, NO una barra completable por mérito del aprendiz.** El tri-estado lo hace honesto — `gender_encountered` (nouns con ≥1 intento) es la exposición real, `gender_mastered` la competencia, `gender_total` el currículo — espejo de `(encountered, mastered, total)`, que ya vive con la misma estructura sin que nadie lo llame defecto. **Contrato para PR-C.1:** la copy del Home presenta esto como *progreso* ("dominas 3 de 8"), nunca como un porcentaje que el aprendiz controla hasta 100%. |

## 3. Tabla autoritativa de sufijos (de la lente de ciencia del aprendizaje)

**Sufijos DUROS** — `suffix_class="hard"`, enseñables como regla (~100%, excepciones nulas o de clase cerrada):

| Sufijo | Género | Notas |
|--------|--------|-------|
| `-chen` | das | Diminutivo; sin excepciones productivas (*das Mädchen* pese al referente). |
| `-lein` | das | Diminutivo; sin excepciones. |
| `-ung` | die | ~100%. *der Schwung/Sprung* terminan en "ung" pero no son `-ung` derivados; como el detector hace match simple, disparan un falso positivo que la **reconciliación del Caso B** (regla `die` vs oráculo `der`) suprime y registra. No se intenta distinguirlos en el detector. |
| `-heit` | die | Exceptionless. |
| `-keit` | die | Exceptionless. |
| `-schaft` | die | Exceptionless. |
| `-tät` (`-ität`) | die | Latino; ~100% (*die Qualität, die Universität*). El sufijo-más-largo prefiere `-ität` sobre `-tät`. |
| `-ion` (`-tion/-sion`) | die | ~100% en vocabulario normal. |
| `-ling` | der | Sin excepciones productivas (*der Lehrling, der Schmetterling*). |
| `-ismus` | der | ~100% (*der Kapitalismus*). |
| `-ment` | das | ~100% (*das Dokument, das Instrument*). *der Moment* es otro lexema; lo maneja el Caso B. |
| `-tum` | das | Enseñable **porque la excepción es cerrada y enumerable**: das salvo **der Reichtum** y **der Irrtum** (el Caso C canónico, vía lista curada). No confundir con el latino `-um` (*das Datum*), que es separado y NO está en la tabla. |

**Sufijos de TENDENCIA** — `suffix_class="tendency"`, copy suavizada (“suelen ser…”) **solo cuando coinciden con el oráculo**; si discrepan, se suprimen (Caso B, igual que un duro):

| Sufijo | Tendencia | Notas |
|--------|-----------|-------|
| `-e` | die (~90%) | *die Blume/Lampe/Katze*, pero *der Name/Junge/Käse, das Auge/Ende*. El gate es **solo** el guard de stem ≥2 codepoints (no hay conteo de sílabas); los falsos positivos como *Käse/Name/Auge* (oráculo der/das) caen en Caso B y se suprimen. |
| `-er` | der (~70-80%) | Agentivos fiables (*der Lehrer*), pero *die Mutter/Butter, das Messer/Fenster/Wasser/Zimmer*. La trampa clásica — solo se muestra si coincide con el oráculo. |
| `-el` | der (~60-70%) | Partido: *der Löffel/Mantel* vs *die Gabel/Insel, das Mittel/Segel*. |
| `-en` | der (~70%) | Subregularidades en competencia; infinitivos nominalizados son das (*das Schwimmen*). |
| `-ie/-ik/-ur` | die | Tendencia alta con excepciones de préstamo (*das Genie/Mosaik, der Atlantik, das Abitur*). |

> **`-nis` excluido del detector.** Es genuinamente de dos géneros (die/das) y el modelo de `rule_gender` escalar no puede representar "die o das". Como además "nunca es regla", se omite por completo de la tabla del detector — un noun en `-nis` simplemente no detecta sufijo (sin regla, `detail=null`), que es el comportamiento correcto.

## 4. Política de casos — el álgebra (servidor)

En el servidor, dentro del guard `gender_source=='oracle'`, `oracle_gender = vocab.gender` es **siempre no-nulo**. Dado el resultado de `detect_gender_rule(vocab.lemma)`:

- **Sin sufijo detectado** → sin regla. `detail = null`. Respuesta `rule = null`.
- **Sufijo detectado** → `agreement = (rule.rule_gender == oracle_gender)`:
  - **Caso A — `agreement == true`** (lo común): regla **mostrable**. `is_exception=false`. La copy depende de `suffix_class`: duro → como regla (*“Wohnung es die — todo `-ung` es femenino”*); tendencia → suavizado (*“los `-e` suelen ser die”*). Respuesta `rule` poblada.
  - **Caso B — `agreement == false` y el lema NO está en `_CURATED_EXCEPTIONS`** (cualquier `suffix_class`): es una discrepancia regla↔oráculo — casi siempre un falso positivo del detector (*Schwung*) o un noun donde la tendencia no aplica (*die Mutter*). **Se suprime la regla**: respuesta `rule = null`, se muestra solo la verdad binaria del oráculo. `is_exception=false`. Se **persisten las 6 llaves** del `detail` (señal de bug/auditoría).
  - **Caso C — `agreement == false` pero el lema está en `_CURATED_EXCEPTIONS` con valor == `oracle_gender`** (*der Reichtum, der Irrtum* para `-tum`): la ÚNICA excepción enseñable, de alto valor por memorable (*“los `-tum` son das — pero Reichtum e Irrtum van der”*). `is_exception=true`. Respuesta `rule` poblada.

**Garantía:** el género mostrado es **siempre** el del oráculo; la regla aparece **solo** cuando coincide (A) o la palabra está curada (C). `agreement` es la única compuerta de mostrabilidad; ninguna combinación queda indefinida; el feedback nunca puede ser menos autoritativo que la fuente de verdad.

> **NULL (frontend, PR-C.1):** si el POST de calificación falla en el cliente (sin `correct_gender` verificado), el render no muestra ni regla ni nota — no se ancla una explicación a un género no verificado. Es una preocupación del render diferido, no del servidor (que siempre tiene `oracle_gender` aquí).

## 5. Arquitectura, tipos y unidades

**Tipos concretos (sin drift — renombres de identidad a través de las capas):**

```python
# detector (puro) — curriculum/gender_rules.py
@dataclass(frozen=True)
class GenderRule:
    suffix: str
    rule_gender: Literal["der", "die", "das"]
    suffix_class: Literal["hard", "tendency"]

# reconciliador / objeto persistido en GenderAttempt.detail (6 llaves)
class GenderRuleDetail(TypedDict):
    suffix: str
    suffix_class: Literal["hard", "tendency"]
    rule_gender: Literal["der", "die", "das"]
    oracle_gender: Literal["der", "die", "das"]
    agreement: bool
    is_exception: bool

# wire — schemas/finish.py — proyección estricta de GenderRuleDetail (quita oracle_gender + agreement)
class GenderRuleOut(BaseModel):
    suffix: str
    suffix_class: Literal["hard", "tendency"]
    rule_gender: Literal["der", "die", "das"]
    is_exception: bool
```

Los nombres `suffix`, `suffix_class`, `rule_gender`, `is_exception` son **idénticos** a través de detector→detail→wire (sin renombres ocultos). `detail` añade `oracle_gender` + `agreement` (auditoría); `GenderRuleOut` es la proyección mostrable.

```
DETECTOR (puro, sin DB)            RECONCILIACIÓN (oráculo manda)
 detect_gender_rule(lemma)         record_gender_attempt (stories.py)
   -> GenderRule | None        ──►  - guard: gender_source=='oracle' (ya existe)
                                    - rule = detect_gender_rule(vocab.lemma)
                                    - detail = reconcile_rule(rule, vocab.gender, vocab.lemma)
                                    - GenderAttempt(detail=detail | None)  [insert aditivo]
EVIDENCIA (ya existe)               - GenderAttemptOut(rule = proyección si mostrable else None)
 gender_attempts(was_correct,
                 detail JSONB)     DISPLAY (tri-estado, espejo del léxico)
   │                                module_gender_progress(user, module)
   ▼                                  -> (gender_encountered, gender_mastered, gender_total)
 is_mastered_gender(user, vocab)    ──► ModuleCurrentOut.gender_{encountered,mastered,total}
  = _streak_mastered(últimos, N=3)      vía GET /modules/current (Home ya lo llama)
```

- **`curriculum/gender_rules.py`** (nuevo) — `detect_gender_rule` (puro; sufijo-más-largo, duros-primero, guard ≥2 codepoints), la lista cerrada `_CURATED_EXCEPTIONS: dict[str, str]` (p.ej. `{"Reichtum": "der", "Irrtum": "der"}`), y `reconcile_rule(rule, oracle_gender, lemma) -> GenderRuleDetail` con los 3 casos. **Semántica de la lista curada:** lookup **exacto sobre `vocab.lemma`** (sin matching de compuestos — *Privatreichtum* NO está y por tanto cae a Caso B por diseño); membresía es el **único** disparador de Caso C; el valor curado se **cruza** contra `oracle_gender` (si difiere, no es Caso C → Caso B). Todo testeable sin DB.
- **`schemas/finish.py`** — `GenderRuleOut` + campo opcional `rule: GenderRuleOut | None = None` en `GenderAttemptOut`.
- **`routers/stories.py`** — `record_gender_attempt`: tras `was_correct`, computa `rule`/`detail` una sola vez in-scope, escribe `detail` en el `GenderAttempt`, y puebla `rule` en la respuesta cuando es mostrable (Caso A/C). Sin `db.refresh`; persiste y devuelve el mismo objeto.
- **`curriculum/competence.py`** — `_streak_mastered(attempts_desc, n) -> bool` (puro: `len(attempts_desc) >= n and all(a.was_correct for a in attempts_desc[:n])`); `is_mastered_gender(db, *, user_id, vocab_item_id)` (async: una query `WHERE user_id AND vocab_item_id ORDER BY attempted_at DESC, id DESC`, usa `ix_gender_attempt_user_vocab`, pasa al helper); `module_gender_progress(db, *, user_id, module_id) -> tuple[int,int,int]` (espejo del `(encountered, mastered, total)` léxico) en **dos queries, sin N+1**: (a) el set elegible del módulo (`module_vocab ⋈ vocab_items` donde `language=='de'` + `gender_source=='oracle'` + `pos==NOUN` + `gender ∈ {der,die,das}`); **si el set elegible está vacío, retorna `(0, 0, 0)` sin emitir la query (b)** (evita el `IN ()` degenerado); (b) **una** query de todos los `GenderAttempt` del usuario `WHERE vocab_item_id IN (set elegible) ORDER BY attempted_at DESC, id DESC`; bucketea en Python por `vocab_item_id` y aplica el **mismo** `_streak_mastered`. `gender_total = |set elegible|`, `gender_encountered = #{nouns elegibles con ≥1 intento}`, `gender_mastered = #{maestreados}`.
- **`schemas/module.py`** — `ModuleCurrentOut`: `gender_encountered: int`, `gender_mastered: int`, `gender_total: int`.
- **`routers/modules.py`** — `get_current_module`: llama `module_gender_progress` y puebla los tres campos (sin conflación con el `(encountered, mastered, total)` léxico existente — son ejes paralelos, denominadores distintos).

## 6. Manejo de errores / casos borde

- **Sufijo no detectado / `-nis`** → sin regla, `detail=null`, respuesta `rule=null`. Idéntico a hoy salvo el campo opcional.
- **Caso B (discrepancia, cualquier kind)** → regla suprimida en el wire (`rule=null`), verdad binaria mostrada, **las 6 llaves del `detail` pobladas** (la supresión afecta solo la respuesta, no el registro persistido). No rompe el grading.
- **Caso C** → solo si el lema está en `_CURATED_EXCEPTIONS` y su valor == `oracle_gender`.
- **Homógrafos** (*der/die See*): el colapso a un género **ocurre en `GenderLexicon`** (cuyo PK es `lemma`, last-write-wins) y se superficie en `VocabItem` bajo su constraint único `(lemma, language, pos)`. `VocabItem` mismo tiene PK UUID surrogate. La maestría y las notas descansan sobre el `was_correct` almacenado contra ese único género; **no se afirman excepciones de sufijo para homógrafos**. Límite v1 documentado.
- **`detail` drift** → se computa una vez in-scope, se persiste ese objeto exacto y se devuelve su proyección; sin re-lectura.
- **Mutación del oráculo tras maestría** (límite v1 aceptado): la maestría se computa sobre **evidencia histórica** (`was_correct` congelado al calificar), nunca re-calificando. Eso protege contra el churn de re-grading, pero significa que si un noun se calificó como `die`, el aprendiz acumula N aciertos, y luego el léxico se re-siembra corrigiendo el lema a `der`, `is_mastered_gender` seguirá `true` para una competencia ahora-falsa y no la re-evaluará. **No se reconcilia en PR-C** (una re-siembra del léxico que invalide filas de evidencia afectadas es backlog). Es latente, dispara solo en una corrección del oráculo, y a la escala de la Rebanada 3 una frase documentada basta — no requiere cambio de diseño.
- **Orden no determinista** → el desempate `id DESC` hace la racha determinista bajo empates de `attempted_at`.
- **Universalidad** → el detector es alemán por contrato; se invoca solo dentro del guard de + oráculo (que `story_gen` ya garantiza para nouns alemanes). Colapso de universalidad esperado y acotado, no regresión.

## 7. Pruebas

- **Detector** (puro): tabla duro-vs-tendencia (cada sufijo de §3 → género + `suffix_class` correctos); sufijo-más-largo (*Universität* → `-ität`); guard de stem (palabra demasiado corta → `None`); `-nis` → `None` (excluido); *Schwung* SÍ detecta `-ung` (el detector es simple — la supresión es del reconciliador, no del detector).
- **Reconciliación** (pura): Caso A duro (mostrable, `agreement=true`, `is_exception=false`); Caso A tendencia (mostrable, suavizado); **Caso B duro** (*Schwung* → `rule=null`, `detail.agreement=false`, 6 llaves pobladas); **Caso B tendencia** (*die Mutter* con `-er→der` → `rule=null`, suprimido — el test del invariante); Caso C curado (*Reichtum* → `is_exception=true`, mostrable); curado con valor != oráculo → Caso B (no se confía a ciegas); compuesto no-listado (*Privatreichtum*) → Caso B.
- **Endpoint**: `detail` persistido con las 6 llaves; `GenderAttemptOut.rule` poblado/nulo según caso; backward-compat (clientes viejos ignoran el opcional); **el `GenderClozeQuizItem` no gana ningún campo** (no-leak estructural).
- **`_streak_mastered` / `is_mastered_gender`**: 3 correctos = true; 2 correctos = false (piso `<N`); 3 correctos + 1 fallo más reciente = false; orden `attempted_at DESC, id DESC` bajo empate; <3 intentos = false.
- **`module_gender_progress`** (tri-estado): `gender_total` = nouns elegibles (de+oráculo+NOUN+der/die/das) del módulo; `gender_encountered` = elegibles con ≥1 intento; `gender_mastered` cuenta solo los maestreados (`encountered ≥ mastered`); módulo sin nouns elegibles → `(0, 0, 0)` **sin emitir la segunda query** (sin `IN ()`); una sola query de attempts cuando hay elegibles (no N+1).
- **Suite completa** sin regresión; ruff (E,F,I,B,UP,RUF) limpio; sin migración (la columna `detail` ya existe).

## 8. Fronteras — diferido explícito

- **PR-C.1 (follow-up):** render de la nota de sufijo en el verdict de `StoryFinish` + 6 claves de locale (tarea de microcopy). Puro frontend gracias al campo `rule`.
- **Read-path de la señal de auditoría del Caso B:** PR-C **solo escribe** el `detail` de discrepancias; ninguna métrica/dashboard/alerta lo consume todavía. Diferido **explícitamente** a un paso posterior de observabilidad (no es una omisión — es el "instrumentar primero, medir después" de C9).
- **Incongruencia ES→DE:** backlog, solo contenido curado, nunca auto-diff (C8).
- **Scheduling de género:** diferido hasta tener datos (C9).
- **Gender en la compuerta de avance:** no — la compuerta queda léxica y de un solo escritor (C6).
- **Soporte de homógrafos:** límite v1 documentado.
- **El eje léxico de R1** (TSV de frecuencia) sigue siendo deuda separada, no bloquea esto.
