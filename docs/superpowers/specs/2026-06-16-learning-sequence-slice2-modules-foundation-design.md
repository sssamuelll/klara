# Secuencia de aprendizaje — Rebanada 2: fundación de currículo (módulos, alemán)

**Fecha:** 2026-06-16
**Estado:** Diseño aprobado (rev. 2, tras revisión adversarial del roster). Pendiente de plan.
**Alcance:** **dos PRs.** **PR-A** (esta rebanada, envía): entidad `Module` + generación dirigida por el módulo activo + **auto-inscripción** del vocab del módulo en el SRS + progreso de lectura visible + 1 módulo semilla. **PR-B** (siguiente): compuerta rigurosa de avance + autoría de la secuencia A1 completa. UN idioma: alemán (es→de). Eje: el contrato de currículo en sí — base para género (Rebanada 3) y demás ejes.

---

## 1. El problema (y por qué ESTA rebanada primero)

El dueño arrancó con: *"las historias por sí solas pierden secuencia"*. La Rebanada 1 (eje léxico) está mergeada pero **inerte** en prod (sin lista de frecuencia; `next_target_words` devuelve `[]`). Falta el **objeto de estado del aprendiz hecho explícito como currículo secuenciado**.

Diagnóstico de Voronov, confirmado por la investigación de ciencia del aprendizaje:

> El **contenido** es un FLUJO (generado al vuelo, infinito). El **currículo** debe ser un GRAFO DE ESTADOS de competencia (finito, secuenciado, con compuertas que leen evidencia de dominio). El error de categoría es tratar el "módulo" como CONTENEDOR de contenido — un flujo no se contiene, se *condiciona* y se *verifica*. `verify_coverage` (que R1 ya tiene) es el embrión: el módulo es el predicado, la generación es libre, el verificador es la compuerta entre las dos ontologías de tiempo.

Invariante que gobierna la secuencia: *una intervención de currículo es legítima exactamente mientras su fuente de verdad sea más autoritativa que el aprendiz al que mide.*

### La fuente de calor (corrección de la rev. 1, BLOCKER del roster)

La rev. 1 hizo que la **compuerta LEYERA** maestría SRS — pero **nada PRODUCE** ese estado en el loop real del usuario: (a) las `UserCard` solo nacían por click manual (`POST /srs/cards`), así que el vocab del módulo nunca entraba al SRS; (b) la maestría solo sube por `submit_review` (recall), un canal minoritario frente a leer historias. Resultado: la fundación habría quedado inerte por una razón **distinta** a R1, y peor, visible como un "0/12" eterno. *Se construyó el termómetro y se olvidó la fuente de calor.*

**La arista que faltaba:** cuando una historia dirigida por el módulo se genera, **auto-inscribir** en el SRS las palabras del módulo que aparecen en ella. Así el loop dominante (leer) **produce** las tarjetas → entran a la cola de review → el review las madura → la compuerta avanza. La lectura alimenta el estado; la compuerta lo lee.

### Historia de diseño

Género-exposición (placebo, descartado) → género-con-corrección (alto valor, exige oráculo: build grande) → investigación + roster → **fundación de módulos primero** → revisión adversarial encontró el BLOCKER de la fuente de calor → **rev. 2: auto-inscripción + dos señales + partir en dos PRs**. Registro previo en `2026-06-16-learning-sequence-slice2-design.md` (SUPERADO).

## 2. Decisiones marco (cerradas con el dueño)

| # | Decisión | Elección |
|---|---|---|
| M1 | **Qué es un módulo** | Predicado por intensión: can-dos CEFR + microlista de vocab + foco(s) gramatical(es) + umbral de maestría. **Nunca** un contenedor de historias (cero `module_id` en `Story`). |
| M2 | **Vínculo módulo↔contenido** | Condicionar + verificar (`verify_coverage`), no contener. |
| M3 | **Fuente de calor** | `create_story` **auto-inscribe** en el SRS el vocab del módulo que aparece en la historia generada. El SRS pasa de opt-in a **dirigido por currículo**. La lectura produce el estado. |
| M4 | **Dos señales (honestas)** | **"Encontrada"** = la tarjeta existe (se mueve con la lectura; monótona) → alimenta el panel visible. **"Dominada"** = `REVIEWING + interval ≥ 21d` (SRS riguroso, lento) → alimenta la compuerta de avance. |
| M5 | **El módulo trae su vocab** | La microlista curada alimenta `target_lemmas` → la generación muerde **sin** el TSV de frecuencia (§3). |
| M6 | **Seed + migración** | Esquema en migración (con `downgrade` ordenado); data de módulos por script (`load_de_modules.py`), nunca en la migración. |
| M7 | **Partición** | **PR-A** (envía): esquema + generación por módulo + auto-inscripción + progreso + 1 módulo semilla. **PR-B**: compuerta de avance + autoría de los 8 módulos (trabajo de contenido, no cabe con el código). |
| M8 | **UI** | Mínima (módulo activo + "encontradas X/N", monótono). **Sin** gamificación/mapa de maestría (proyección de la compuerta; va después; la de género es POST-oráculo). |

## 3. El unlock (el módulo trae su vocab + la lectura lo inscribe)

`generate_story` **acepta `target_lemmas` arbitrarios** — el requisito `frequency_rank IS NOT NULL` vive solo en `next_target_words`, no en la generación. Entonces:

1. La microlista curada del módulo (sembrada, `frequency_rank` NULL — válido) alimenta `target_lemmas`.
2. `verify_coverage` confirma qué lemas del módulo aparecieron (ya existe).
3. **Auto-inscripción (M3):** esos lemas presentes se inscriben como `UserCard` (estado NEW) si no existen ya → entran a la cola de review.
4. El lazo **leer → tarjeta creada → cola de review → maestría → avance** queda cerrado, **sin TSV ni licencia de nadie**. Esto es lo que hace a la fundación enviable y con mordida real.

---

## 4. Arquitectura — la entidad `Module`

```python
# models/module.py (nuevo)
class Module(Base):                      # tabla "modules"
    id: uuid_pk
    language: str                        # "de"
    cefr_level: CEFRLevel                # reusa el enum existente (create_type=False)
    sequence_order: int                  # orden dentro de (language) — la secuencia
    title: str                           # "En el café"
    can_dos: list[str]   (JSONB)         # 1-3 descriptores can-do CEFR
    grammatical_focus: list[str] (JSONB) # 1-2 focos; gancho para género (R3)
    mastery_threshold: float = 0.85      # fracción dominada para superar (compuerta — PR-B)
    # UniqueConstraint(language, sequence_order)

# tabla module_vocab (module_id FK, vocab_item_id FK) — la microlista curada
```

- **Posición del usuario:** `User.current_module_id` (FK nullable a `modules`). **Inicialización perezosa con un único punto de escritura:** ocurre **solo en `create_story`** (write path) — si es NULL y existen módulos para el `target_language`, se fija al de menor `sequence_order` y se persiste. `GET /modules/current` **solo LEE** (devuelve null → el panel muestra estado vacío). Esto resuelve la contradicción lectura/escritura que marcó el roster.
- **Sin tabla de progreso histórico en v1** (YAGNI). Deuda visible declarada (§11): no queda registro de *cuándo* se superó un módulo; si R3 lo necesita, será migración retroactiva sin datos históricos.

## 5. Competencia: dos señales, interfaz por-eje

```python
# curriculum/competence.py
MASTERY_INTERVAL_DAYS = 21.0
def is_mastered_lexical(card) -> bool:           # predicado de maestría del eje LÉXICO
    return card.state == CardState.REVIEWING and card.interval_days >= MASTERY_INTERVAL_DAYS

# module_progress(db, user_id, module) -> (encountered: int, mastered: int, total: int)
#   ONE query: module_vocab ⟕ user_cards (del usuario), con COUNT FILTER:
#     encountered = COUNT(card.id)
#     mastered    = COUNT(*) FILTER (WHERE state='reviewing' AND interval_days>=21)
#   total = COUNT(module_vocab). Sin N+1, sin cargar a Python.
```

- **`known_set` (presencia) NO cambia** — la usa `next_target_words` (ruta de frecuencia, secundaria e inerte sin TSV). Cambiarla re-targetearía palabras a medio aprender sin beneficio aquí.
- **Maestría como interfaz por-EJE (no hardcode):** `is_mastered_lexical` es el predicado del eje léxico (intervalo). La Rebanada 3 (género) traerá su **propio** predicado (verificado contra oráculo, no intervalo). El contrato de competencia admite un predicado por eje; no se cementa "maestría = intervalo≥21d" como universal. Esto evita la deuda que el roster señaló para R3.

## 6. Auto-inscripción (la fuente de calor)

En `create_story`, tras computar la cobertura (los `kept_words` = lemas del módulo que el LLM realmente incluyó):

- Para cada `vocab_item` del módulo activo presente en la historia que **no** tenga `UserCard` del usuario → crear `UserCard(state=NEW)`. El `UniqueConstraint(user_id, vocab_item_id)` previene duplicados (insert idempotente vía `on_conflict_do_nothing`).
- Las tarjetas NEW quedan `due` (next_review_at NULL) → aparecen en la cola de Practice/review existente. El usuario las repasa; `submit_review` las madura.
- **Solo en el camino con módulo activo.** Sin módulo (fallback), comportamiento de hoy (cero auto-inscripción). No toca el flujo opt-in de `+ Review` (sigue existiendo para palabras fuera del módulo).

## 7. Rewire de la generación (cierre del lazo por módulo)

`create_story` (`routers/stories.py:108`):

1. Inicializa `current_module_id` si hace falta (§4). Si hay módulo activo → el vocab del módulo alimenta los `target_lemmas` que `generate_story` ya recibe (viajan por el `target_block` de R1). **Adicionalmente** se inyecta un **bloque de objetivo de módulo nuevo** (can-do + foco gramatical) como contexto duro; el LLM escribe **libre**.
2. `verify_coverage` valida contra el vocab del módulo (ya existe; log `story.curriculum.missed`).
3. Auto-inscripción de los lemas cubiertos (§6).
4. **Fallback:** sin módulo activo (DB sin seed, p.ej. CI) → `next_target_words` como hoy. Sin regresión.

## 8. Progreso visible (mínimo, monótono)

- **Endpoint** `GET /modules/current` → módulo activo (título, can-dos) + `(encountered, mastered, total)`. Solo lee.
- **`Home.tsx`** — panel compacto: título del módulo + can-do + **"has encontrado X de N palabras"** (señal *encontrada*, **monótona** — nunca baja, evita el "sabes menos" que marcó el roster con la señal *dominada*). **Sin** mapa de maestría ni gamificación.
- **Estado vacío obligatorio:** sin módulo activo (prod fresco / CI / antes de la primera historia) el panel renderiza *"aún sin módulo — genera tu primera historia"*. No es opcional (la tabla arranca vacía).
- Keys i18n en los 6 locales (`i18n:check`), `es` fuente, incluida la cadena de estado vacío.

## 9. Contenido sembrado

`scripts/load_de_modules.py` (calca `load_de_lexical.py`, idempotente, **post-deploy, no en migración**). Siembra módulos A1 y su vocab (como `VocabItem`, `frequency_rank` NULL).

- **PR-A:** **1 módulo semilla** ("En el café") para probar el lazo end-to-end (generación → cobertura → auto-inscripción → progreso). El código no espera a la autoría completa.
- **PR-B:** la secuencia A1 completa (~6-8 módulos: saludos, números, café, compras, familia, rutina, casa, ciudad), cada uno con can-dos + ~10-15 lemas + foco gramatical. Es trabajo de contenido (redacción + revisión pedagógica del dueño), su propio PR de datos. Criterio de aceptación de la data: los lemas deben ser palabras que el LLM incluya con naturalidad y que `verify_coverage` detecte tras lematización (si no, `story.curriculum.missed` se dispara).

## 10. Disciplina de migración

- **Migración solo-esquema:** `modules`, `module_vocab`, `User.current_module_id`. `cefr_level` **referencia el enum existente** (`create_type=False`), no lo recrea.
- **`downgrade` en orden inverso de dependencias** (el CI de roundtrip hace upgrade→downgrade base→upgrade): drop de la columna/FK `User.current_module_id` → drop `module_vocab` (FKs a `modules` y `vocab_items`) → drop `modules`. Verificable localmente con upgrade/downgrade/upgrade antes del PR.
- **Data por script**, nunca en la migración → downgrade limpio. En DB fresca (CI) la tabla queda vacía y la generación usa el fallback (§7).

## 11. Fronteras — diferido explícito (deuda visible aceptada)

- **PR-B = compuerta de avance:** chequeo en `submit_review` (forward-only, único punto donde la maestría cambia), `module_mastery ≥ threshold` → avanza `current_module_id`. Guard de no-op si la tarjeta revisada no pertenece al módulo activo. Más la autoría de los 8 módulos. **No en PR-A** (con 1 módulo no hay a dónde avanzar).
- **Sin historial de avance** (no hay tabla de progreso): deuda visible; si R3/analytics lo necesitan → migración retroactiva sin datos previos.
- **Rebanada 3 = género-con-corrección** sobre esta base: oráculo Wiktionary + provenance + binding diádico + arista `QuizAttempt → vocab_item_id` + cloze de género contra el oráculo. El `grammatical_focus` del módulo es el gancho; el predicado de maestría de género es propio (§5).
- **Verificador de cobertura GRAMATICAL:** no es simétrico al léxico (presencia vs buena-formación); diferido hasta resolver el verificador autoritativo. El módulo v1 verifica solo léxico.
- **Gamificación / mapa de maestría:** proyección de la compuerta; después de PR-B. Nunca rachas/vidas/ligas/leaderboards/XP por volumen.
- **SM-2 → FSRS:** diferido hasta tener volumen de reviews.
- **TSV de frecuencia (frente paralelo del dueño):** enciende `next_target_words` y el re-rank de género diferido. La fundación no lo necesita para morder.
