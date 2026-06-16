# Secuencia de aprendizaje — Rebanada 2: fundación de currículo (módulos + competencia-por-estado, alemán)

**Fecha:** 2026-06-16
**Estado:** Diseño aprobado (pendiente de plan de implementación)
**Alcance:** un PR. Backend (entidad `Module` por intensión + seed script de A1 + competencia-por-estado para la compuerta + rewire de generación al módulo activo + compuerta de avance) + **UI mínima** (módulo activo + progreso). UN idioma: alemán (es→de). Eje: el contrato de currículo en sí — la base sobre la que se montan género (Rebanada 3) y los demás ejes.

---

## 1. El problema (y por qué ESTA rebanada primero)

El dueño arrancó con: *"las historias por sí solas pierden secuencia"*. La Rebanada 1 (eje léxico) está mergeada pero **inerte** en prod (sin lista de frecuencia cargada, `next_target_words` devuelve `[]`). Lo que falta no es más contenido: es el **objeto de estado del aprendiz hecho explícito como currículo secuenciado**.

Diagnóstico de Voronov (ontología), confirmado por investigación de ciencia del aprendizaje:

> El **contenido** es un FLUJO (generado al vuelo, infinito, sin estado). El **currículo** debe ser un GRAFO DE ESTADOS de competencia (finito, secuenciado, con compuertas que leen evidencia de dominio). El error de categoría es tratar el "módulo" como un CONTENEDOR de contenido — un flujo no se contiene, se *condiciona* y se *verifica*. `verify_coverage` (que R1 ya tiene) es el embrión exacto: el módulo es el predicado, la generación es libre, el verificador es la compuerta entre las dos ontologías de tiempo.

Invariante que gobierna toda la secuencia (heredado del spec R2): *una intervención de currículo es legítima exactamente mientras su fuente de verdad sea más autoritativa que el aprendiz al que mide.*

**Por qué la fundación antes que la feature de género** (orden no-negociable del roster): si se construye gamificación o historias-por-módulo **antes** de reparar la definición de competencia (hoy `known_set` = "existe `UserCard`", binario, confunde *tener tarjeta* con *dominar*), se cementa la confusión evento/estado en la capa más visible y más cara de revertir. Se repara la ontología primero; la UI hereda la verdad. El género-con-corrección (Rebanada 3) aterriza sobre esta base, no sobre arena.

### Historia de diseño (cómo llegamos aquí)

Género-exposición (placebo honesto, descartado) → género-con-corrección (alto valor pedagógico, pero exige oráculo de Wiktionary + binding diádico + arista de evidencia: build grande) → investigación de aprendizaje + roster → **fundación de módulos primero** (esta rebanada), género-con-corrección como Rebanada 3. Registro completo del razonamiento en `2026-06-16-learning-sequence-slice2-design.md` (SUPERADO).

## 2. Decisiones marco (cerradas con el dueño)

| # | Decisión | Elección |
|---|---|---|
| M1 | **Qué es un módulo** | Un **predicado por intensión**: can-dos CEFR + microlista de vocab objetivo + foco(s) gramatical(es) + umbral de maestría. **Nunca** un contenedor de historias. |
| M2 | **Vínculo módulo↔contenido** | El contenido IA se **condiciona** por el módulo y se **verifica** contra él (generalizar `verify_coverage`). **Cero** `module_id` en `Story`, **cero** tabla `module_stories`. |
| M3 | **Competencia** | La **compuerta** de avance lee **maestría por ESTADO** del SRS (no presencia de tarjeta). |
| M4 | **Fuente de vocab** | El módulo trae su **propia microlista curada** → la generación muerde **sin** el TSV de frecuencia (§3). |
| M5 | **Seed + migración** | Esquema en migración (con `downgrade`, lo exige el CI de roundtrip); **data de módulos por script** (`load_de_modules.py`), nunca embebida en la migración. |
| M6 | **UI** | UI **mínima** (módulo activo + progreso). **Sin gamificación/mapa de maestría** todavía (es proyección de la compuerta, va después; la de género es POST-oráculo). |

## 3. El unlock (el módulo trae su propio vocab)

`generate_story` **acepta `target_lemmas` arbitrarios** — el requisito de `frequency_rank IS NOT NULL` vive solo en `next_target_words` (`selection.py:54`), no en la generación. Por tanto:

- La microlista curada del módulo (sembrada por nosotros, con `frequency_rank` NULL — válido, la columna es nullable) alimenta `target_lemmas` directamente.
- `verify_coverage` (`coverage.py`) confirma post-hoc que esos lemas aparecen.
- **El lazo `objetivo → prompt → generación → verificación` muerde en prod por primera vez, SIN esperar licencia de frecuencia.** El módulo trae su data. Esto es lo que hace a la fundación enviable y con mordida real hoy.

---

## 4. Arquitectura — la entidad `Module`

```python
# models/module.py (nuevo)
class Module(Base):                      # tabla "modules"
    id: uuid_pk
    language: str                        # "de"
    cefr_level: CEFRLevel                # A1, ...
    sequence_order: int                  # orden dentro de (language) — la secuencia
    title: str                           # "En el café"
    can_dos: list[str]   (JSONB)         # 1-3 descriptores can-do CEFR
    grammatical_focus: list[str] (JSONB) # 1-2 focos; gancho para género (R3): "género de sustantivos de comida"
    mastery_threshold: float = 0.85      # fracción del vocab dominado para superar
    # UniqueConstraint(language, sequence_order)

# tabla puente module_vocab (module_id, vocab_item_id) — la microlista curada
```

- **Posición del usuario:** `User.current_module_id` (FK nullable a `modules`). **Inicialización perezosa:** si es NULL y existen módulos para el `target_language`, se fija al de menor `sequence_order` en el primer uso. **Sin tabla de progreso histórico en v1** (YAGNI); la maestría se computa en vivo desde las `UserCard`.
- **Cero `module_id` en `Story`** (M2). La historia se archiva como hoy; el vínculo es por objetivo.

## 5. Competencia por estado (la compuerta)

```python
# curriculum/competence.py — añadir (NO romper known_set)
MASTERY_INTERVAL_DAYS = 21.0
def is_mastered(card) -> bool:
    return card.state == CardState.REVIEWING and card.interval_days >= MASTERY_INTERVAL_DAYS

async def module_mastery(db, *, user_id, module) -> float:
    # |vocab del módulo con UserCard dominada| / |vocab del módulo|
```

- **`known_set` (presencia) NO cambia** — la usa `next_target_words` (la ruta de frecuencia, secundaria e inerte sin TSV). Cambiarla re-targetearía palabras a medio aprender y rompería sus tests sin beneficio en esta rebanada. La reparación que importa (Voronov) es que **la COMPUERTA lea estado**, y eso se cumple con `is_mastered`/`module_mastery`, no tocando `known_set`.
- **Avance (forward-only, un solo punto de wiring):** se chequea en `submit_review` (`routers/srs.py`) — el único lugar donde el estado de una tarjeta cambia y por tanto la maestría puede cruzar el umbral. Si `module_mastery(user, módulo_activo) ≥ module.mastery_threshold`, `current_module_id` avanza al siguiente `sequence_order`. **Solo hacia adelante:** un lapso posterior (una tarjeta que cae bajo el umbral tras un AGAIN) NO retrocede al usuario de módulo — derivar el módulo activo en vivo desde la maestría causaría regresión de módulo, mala UX; por eso se almacena el puntero y se avanza monotónicamente. `GET /modules/current` solo LEE, no muta.

## 6. Rewire de la generación (cierre del lazo por módulo)

`create_story` (`routers/stories.py:108`):

1. Si `user.current_module_id` está fijado → el vocab del módulo activo alimenta los `target_lemmas` que `generate_story` ya recibe (viajan por el `target_block` existente, `prompts.py:101`). Adicionalmente se inyecta un **bloque de objetivo de módulo nuevo** (can-do + foco gramatical) como contexto duro; el LLM escribe **libre** (preserva naturalidad).
2. `verify_coverage` valida contra el vocab del módulo (ya existe; log `story.curriculum.missed` ya instrumentado).
3. **Fallback:** si no hay módulo activo (DB sin seed, p.ej. CI), cae a `next_target_words` como hoy. Sin romper nada.

Dos entradas distintas al prompt: el **vocab** del módulo reusa el `target_block` de R1 (lemas objetivo); el **objetivo** del módulo (can-do + foco gramatical) es un bloque nuevo, hermano de aquel.

## 7. Secuencia A1 sembrada (contenido curado)

`scripts/load_de_modules.py` (calca `load_de_lexical.py`, idempotente, **post-deploy, no en migración**). Siembra ~6-8 módulos A1 y su vocab (como `VocabItem`, `frequency_rank` NULL):

1. Saludos y presentarse · 2. Números y la hora · 3. En el café (comida/bebida) · 4. De compras · 5. La familia · 6. La rutina diaria · 7. En casa · 8. Moverse por la ciudad.

Cada módulo: 1-3 can-dos + ~10-15 lemas de vocab + 1-2 focos gramaticales. El campo `grammatical_focus` es **descriptivo** en v1 (entra al prompt como contexto); el **drill** de ese foco (p.ej. género) llega en R3. El dueño revisa/edita el set antes de sembrar.

## 8. Surfacing (mínimo)

- **Endpoint** `GET /modules/current` → módulo activo (título, can-dos) + progreso (`X/N` dominadas, `module_mastery`).
- **`Home.tsx`** — panel compacto del módulo activo: título + can-do + "4/12 dominadas". **Sin** mapa de maestría ni gamificación. Keys i18n en los 6 locales (`i18n:check`), `es` fuente.

## 9. Disciplina de migración

- **Migración solo-esquema:** `modules`, `module_vocab`, `User.current_module_id` (FK nullable). `downgrade` funcional (el CI de roundtrip hace upgrade→downgrade base→upgrade).
- **Data por script** (`load_de_modules.py`), nunca en la migración → downgrade limpio, sin data que revertir. En DB fresca (CI) la tabla queda vacía y la generación usa el fallback (§6).

---

## 10. Fronteras — diferido explícito (deuda visible aceptada)

- **Rebanada 3 = género-con-corrección**, sobre ESTA fundación: oráculo de Wiktionary + provenance (`oracle|llm|user`, el oráculo gana sobre el LLM) + binding diádico propio + arista `QuizAttempt → vocab_item_id` + cloze de género calificado contra el oráculo, con feedback estratificado (reglas duras de sufijo vs tendencias) e incongruencias ES→DE. El campo `grammatical_focus` del módulo es el gancho.
- **Verificador de cobertura GRAMATICAL:** NO es simétrico al léxico (presencia booleana vs buena-formación de una estructura; un LLM-as-checker hereda el problema de provenance). Diferido hasta resolver quién es el verificador autoritativo. El módulo v1 verifica solo léxico.
- **Gamificación / mapa de maestría:** es la proyección visible de la compuerta; se construye DESPUÉS de que la compuerta lea estado (esta rebanada lo habilita). Mapa de maestría léxico = siguiente; gamificación de género = POST-oráculo. **Nunca:** rachas, vidas, ligas, leaderboards, XP por volumen (la evidencia los marca como daño y chocan con el tono "sin apuro/sin culpa").
- **Migración SM-2 → FSRS:** diferida hasta tener volumen de reviews que optimizar.
- **`known_set` → estado en la ruta de selección:** diferido; la ruta de frecuencia está inerte sin TSV, así que no urge.
- **Frente paralelo (no bloquea):** adquisición del TSV de frecuencia (Kelly-DE/SUBTLEX-DE/DeReWo) — enciende la ruta de `next_target_words` y el re-rank de género diferido. La fundación no lo necesita para morder.
