# Cerrar el ciclo SRS en Practice — canal de mantenimiento por pronunciación

**Fecha:** 2026-06-15
**Estado:** Diseño aprobado (pendiente de plan de implementación)
**Alcance:** un PR. Frontend (`Practice.tsx`, `useSentencePractice.ts`, cliente API + tipos) +
backend (cola de práctica, schemas, endpoint batch nuevo, scheduler de mantenimiento nuevo).

---

## 1. Problema

La pantalla `/review` (hoy `Practice.tsx`, "Pronunciar") evolucionó hacia drills de
pronunciación. El backend SRS estilo Anki ya existe (`srs_engine.py`, `routers/srs.py`,
modelos `UserCard`/`Review`), pero **no tiene un consumidor que cierre el ciclo**. Dos
síntomas verificados en código:

1. **Carta inmortal.** La cola (`services/practice_queue.py`) consume el signal "due" de
   una `UserCard` para surfacearla como línea de pronunciación, pero **nadie reprograma la
   carta** — `next_review_at` no se mueve. La carta queda due para siempre.
2. **El summary miente.** `Practice.tsx:286-298` pinta "mañana / en dos días / esta semana"
   **hardcodeado por posición** (`i===0 → tomorrow`), no calculado por ningún SRS.

Este diseño cierra el ciclo: practicar una carta due la reprograma de verdad, y el summary
muestra el intervalo **real**.

---

## 2. Decisión de framing (la que reordena todo)

Axiom-0, sintetizando al consejo, nombró el invariante:

> El intervalo SRS es una afirmación causal. Una afirmación honesta no es la que dice el
> dato verdadero, sino la que **nombra correctamente de qué es verdad**.

Voronov verificó (contra `pronunciation/azure_client.py`) que Azure mide **articulación**
(accuracy de fonemas), no **recall**, y que el modo *read-along* (el target está en pantalla)
hace el recuerdo **estructuralmente inobservable**. Un scheduler de memoria alimentado por una
señal de pronunciación afirma "memoria" cuando mide "boca".

**Decisión: modelo híbrido de dos canales, ambos honestos.**

- **Canal de pronunciación (este PR):** *mantiene* cartas vivas. Las mantiene en circulación
  en una cadencia corta; **nunca las gradúa** a intervalos largos. El copy del summary habla
  de "cuándo lo repites en voz", **no** de memoria.
- **Canal de recall (futuro, fuera de alcance):** *promueve* cartas a intervalos largos vía
  el motor SM-2 completo (revelar + Again/Hard/Good/Easy). No se construye aquí.

Consecuencia directa: el "GOOD-techo" (que GOOD nunca produce intervalos largos vía
pronunciación) **deja de ser un bug** — es el diseño. Y la contradicción "stats por fracción
de frase vs rating por palabra-foco" se disuelve porque **las stats del summary pasan a
basarse en la palabra-foco** (mismo sujeto que el rating).

---

## 3. Decisiones de producto (cerradas)

| # | Decisión | Detalle |
|---|---|---|
| D1 | **Mapeo conservador** | `bad → Again`, `ok → Hard`, `good → Good`. **Nunca** `Easy` (promoción = canal recall). |
| D2 | **Alcance** | Cualquier item respaldado por una `UserCard` **due** se reprograma (venga como `struggled` o `review`). Cartas no-due no se tocan. |
| D3 | **Fuente del rating** | La banda de la **palabra-foco**. Fallback cuando no hay banda para esa palabra: **peor banda de la frase** (lo más conservador → intervalo más corto). |
| D4 | **Escritura** | Auto al llegar al summary, exactamente una vez. El summary muestra intervalos **reales** devueltos por el backend. |
| D5 | **Identidad de carta** | Se **porta `cardId` desde la cola** (no se resuelve por texto aguas abajo). Ver §4.1. |
| D6 | **Forma del endpoint** | **Endpoint batch nuevo**, mapeo banda→rating en Python, una transacción atómica. Ver §4.3. |
| D7 | **Mecanismo de mantenimiento** | **Scheduler nuevo** `schedule_pronunciation_maintenance` (escalera corta fija, no toca `ease`/`repetitions`/`state`). **No modifica** `schedule_next_review`. Ver §4.2. |

---

## 4. Arquitectura

### 4.1 Portar `cardId` desde la cola (mata la resolución frágil por texto)

**Hallazgo del board (BLOCKER):** `focus_text` es la forma **flexionada de superficie** (el
peor token, `practice_queue.py:124`), no un lemma. `gegangen`/`Häuser`/`läuft` no casefoldean
a `gehen`/`Haus`/`laufen`. Resolver `focus_text.casefold() == VocabItem.lemma` aguas abajo
vaciaría el scope B justo para el vocabulario flexivo (alemán), dejando la carta inmortal donde
más duele.

**Solución:** la cola **ya conoce** la `UserCard` (`build_review_items` la resuelve en
`practice_queue.py:334` — `for _card, vocab in rows` — y la **descarta**). Dejamos de
descartarla.

- `PracticeItemOut` (`schemas/practice.py`) gana un campo opcional **`card_id: UUID | None`**
  (serialization_alias `cardId`).
- **Items `review`:** llevan el `card_id` de la `UserCard` due que los originó.
- **Items `struggled`:** el dedup struggled∩review ya matchea por `focus_text.casefold() ==
  lemma` (`build_practice_queue`, `practice_queue.py:436-454`). Cuando un item struggled
  corresponde a una carta due, **se le adjunta ese `card_id`** en ese punto. Un struggled cuyo
  peor token no es vocab tracked queda con `card_id = None`.
- **Items sin carta** (`card_id = None`): no se reprograma nada (no hay carta que tocar). El
  attempt de pronunciación se sigue persistiendo como hoy (`recordPronunciationAttempt`).

Esto elimina de raíz: la resolución por texto, el "lemma ambiguo" autoinfligido, y el problema
de flexión para todo item que lleve carta.

> **Nota de tokenización (precondición, §6):** el rating se deriva de la banda de la
> palabra-foco. La banda vive en `scoresBySentence[i]` keyed por índice de token. El backend
> re-tokeniza `sentence_target` con el tokenizador **canónico** (Python) para hallar el índice
> de la palabra-foco y leer su banda. Esto exige paridad **exacta** de tokenizadores — hoy
> rota (§6).

### 4.2 Scheduler de mantenimiento (nuevo, no toca el motor)

`schedule_next_review` no se modifica. En estado `REVIEWING` **multiplica** el intervalo por el
ease (promueve) — exactamente lo que el canal de pronunciación NO debe hacer.

**Nuevo:** una función hermana (en `srs_engine.py` junto a `schedule_next_review`, o en un
módulo nuevo — el plan decide *dónde*, no *si*) expone:

```python
def schedule_pronunciation_maintenance(card: UserCard, band: Literal["bad","ok","good"])
        -> tuple[float, datetime]:
    """Canal de mantenimiento por pronunciación: mueve next_review_at en una
    escalera corta y FIJA. NO toca ease, repetitions ni state — esos son estado
    de promoción, propiedad del canal de recall (futuro)."""
```

Escalera (espeja los pasos cortos del motor para coherencia, sin la rama exponencial):

| Banda | Rating (D1) | Intervalo | Nota |
|---|---|---|---|
| `bad` | Again | ~10 min (`0.0069` d) | re-drill pronto |
| `ok` | Hard | ~1 h (`0.04` d) | |
| `good` | Good | +1 día (`1.0` d) | mantiene, no gradúa |

El servicio asigna **explícitamente** `card.interval_days`, `card.next_review_at`,
`card.last_reviewed_at` (replicando el contrato implícito de `submit_review`, ya que
`schedule_*` solo retorna y no persiste — hallazgo de Amina). `ease`/`repetitions`/`state` se
dejan intactos.

> **Interacción documentada:** solo se tocan cartas **due** (su `next_review_at` ya está en el
> pasado). Reprogramar una carta promovida-por-recall que esté due a una cadencia de
> mantenimiento es correcto bajo el modelo híbrido: si nunca la recordás (recall), no crece. No
> hay de-promoción de cartas no-due porque no se tocan.

### 4.3 Endpoint batch (nuevo)

`POST /api/v1/srs/cards/review-batch` (en `routers/srs.py` o `routers/practice.py` — decisión
del plan). Auth-gated.

**Entrada** (`schemas/srs.py` o `practice.py`) — **requiere `validation_alias` camelCase +
`populate_by_name`** (hallazgo de Gap/Amina: `serialization_alias` NO aplica a deserialización;
sin esto el POST devuelve 422 o procesa vacío):

```python
class PronunciationReviewIn(BaseModel):
    card_id: UUID                      # validation_alias "cardId"
    focus_text: str                    # "focusText" — la palabra-foco (= lemma del item)
    sentence_target: str               # "sentenceTarget" — para re-tokenizar
    word_bands: dict[int, Literal["bad","ok","good"]]   # "wordBands" {tokenIdx: band}

class PronunciationBatchIn(BaseModel):
    reviews: list[PronunciationReviewIn]
    # target_language NO se acepta del cliente — se lee de user.target_language (Vex)
```

> **El backend deriva la banda** (mantiene D6 "mapeo en backend" y deja al frontend sin
> dependencia del tokenizador en submit): re-tokeniza `sentence_target` con el tokenizador
> **canónico** (Python, §6), halla el token `== focus_text`, lee `word_bands[idx]`. Fallback
> (D3): si la palabra-foco no tiene banda, **peor banda de la frase**. El cliente nunca calcula
> índices de token.

**Algoritmo del servicio** (`services/practice_session.py`, una transacción):

1. **Dedup `card_id`** en el batch (idempotencia intra-request — un cardId aparece una vez).
2. Por cada review: `card = db.get(UserCard, card_id)`; **invariante de seguridad
   obligatorio y testeado:** `card.user_id == user.id` o se ignora (404/skip). Resolver desde
   un id arbitrario del cliente hace de este filtro la **única** barrera (Gap).
3. Si la carta **no está due** (`next_review_at` futuro): skip (D2).
4. `rating = _BAND_TO_RATING[band]` (constante **nueva**, distinta de `_BAND_RANK`).
5. `interval, next_at = schedule_pronunciation_maintenance(card, band)`; asignar los 4 campos
   (§4.2); `db.add(Review(...))` para auditoría.
6. Acumular `RescheduledCardOut`.
7. **Commit único** al final → atomicidad de sesión (todo-o-nada).

**Salida:**

```python
class RescheduledCardOut(BaseModel):
    focus_text: str        # serialization_alias "focusText"
    interval_days: float   # "intervalDays"
    next_review_at: datetime  # "nextReviewAt"
    # rating y translation CORTADOS (Vex): el cliente ya tiene focusTx vía match por cardId

class PronunciationBatchOut(BaseModel):
    rescheduled: list[RescheduledCardOut]
```

El router declara `response_model_by_alias=True` (igual que `GET /practice/queue`,
`practice.py:24`).

**Concurrencia (default, §3 tabla):** producto monousuario → **sin `SELECT FOR UPDATE`** en
v1. El dedup de `cardId` cubre el intra-request; el commit único da atomicidad de batch. Riesgo
documentado (TODO): el `POST /srs/cards/{id}/review` manual no se coordina con esta vía — bajo
para un solo usuario secuencial.

### 4.4 Frontend (`Practice.tsx`, fase summary)

- **Disparo + confirmación.** `sessionSubmittedRef` dispara el POST al entrar a `summary`. Se
  marca **al confirmar éxito**, no al disparar (Richter: marcar al disparar convierte un fallo
  en pérdida invisible). En fallo: reintentable; `reset()` ("otra ronda") lo limpia.
- **Payload.** Por cada índice `i` con score **y `items[i].cardId != null`**:
  `{ cardId, focusText: items[i].focusText, sentenceTarget: sentences[i].target,
  wordBands: scoresBySentence[i] }` (§4.3 — el backend deriva la banda). Líneas sin score,
  simuladas (§6), o sin `cardId` → excluidas.
- **Máquina de estados de envío:** `idle → sending → ok | failed`.
  - `sending`: skeleton/placeholder en el bloque de próximos repasos.
  - `ok` con `rescheduled` no vacío: render de la lista con intervalos **reales** humanizados.
  - `ok` con `rescheduled = []` (legítimo: nada due, o solo struggled sin carta): **ocultar la
    sección entera** — no "VUELVEN PRONTO — 0" sobre un `<ul>` vacío (Iris). El `<hr>`
    (`Practice.tsx:278`) se ata a la **misma** condición para no dejar un separador colgando.
  - `failed`: ocultar la sección (nunca fabricar intervalos) + ofrecer reintento.
- **Stats por palabra-foco** (consecuencia del framing §2): `tallySummary` pasa a contar la
  banda de la palabra-foco por línea, no la fracción de la frase, para que stats y rating
  hablen del mismo sujeto.
- **i18n.** Reusar `_bucket_for` + las claves `story.finish.summary.schedule.*` (ya espejadas
  en 6 locales). **Borrar** las 3 claves posicionales obsoletas `practice.summary.returns.
  {tomorrow,inTwoDays,thisWeek}` en los 6 locales (`check-i18n.mjs` falla si una sobra/falta).

---

## 5. Flujo (diagrama de Kenji)

```mermaid
sequenceDiagram
    actor User as Usuario
    participant UI as Practice.tsx (summary)
    participant Hook as useSentencePractice.ts
    participant API as POST /srs/cards/review-batch
    participant Svc as services/practice_session.py
    participant Sched as schedule_pronunciation_maintenance
    participant DB as UserCard / Review

    User->>UI: Termina sesión (entra a summary)
    Note over UI: sessionSubmittedRef dispara 1 vez<br/>se marca al CONFIRMAR éxito
    UI->>Hook: lee scoresBySentence + flag simulado + items[].cardId
    Note over Hook: excluye: sin score / simuladas / cardId null
    UI->>API: PronunciationBatchIn { reviews:[{cardId, focusText, sentenceTarget, wordBands}] }
    API->>Svc: dedup cardId
    loop por review (transacción única)
        Svc->>DB: get(UserCard); assert user_id == user.id
        Note over Svc: re-tokeniza (canónico) → banda foco<br/>?? peor banda de frase → rating (D1)
        alt no due
            Note over Svc,DB: skip (D2)
        else due
            Svc->>Sched: maintenance(card, band)
            Sched-->>Svc: (interval, next_at)  [no toca ease/reps/state]
            Svc->>DB: asigna interval_days/next_review_at/last_reviewed_at + Review
        end
    end
    Svc->>DB: COMMIT (atómico)
    Svc-->>API: rescheduled[]
    API-->>UI: PronunciationBatchOut
    alt rescheduled no vacío
        UI-->>User: intervalos reales humanizados
    else vacío / fallo
        UI-->>User: oculta la sección (hr incluido), reintento si fallo
    end
```

---

## 6. Precondiciones (realidad del código — sin decisión, deben resolverse)

1. **Flag "simulado" (BLOCKER).** `useSentencePractice.ts:325` mete `simulatedBands()`
   (`Math.random`) en el **mismo** `scoresBySentence` que las bandas reales (línea 295), sin
   marca. Sin un mecanismo, un 503 de Azure haría que `Math.random` reprograme cartas reales.
   - Añadir `simulatedIndices: Set<number>` al hook; poblarlo en el catch `service_unavailable`
     (líneas 322-327); exponerlo en la interfaz `UseSentencePractice`; excluir esos índices del
     payload.
   - **`clearFeedback` (líneas 230-243) debe limpiar también el Set** o quedarán índices mal
     marcados tras un retry (Null Vale).
2. **Tokenizador canónico (BLOCKER).** Backend `_TOKEN_RE` (`practice_queue.py:82`) usa comillas
   tipográficas `„""`; frontend (`pronunciation.ts:28`, `useSentencePractice.ts:61`) usa rectas
   ASCII. Los índices de token se desalinean para frases con `"…"` → banda equivocada.
   - Definir el tokenizador **Python como canónico**; corregir las copias del frontend para que
     espejen byte a byte; añadir un test/guard de paridad. El regex vive en 3 lugares: no se
     puede "no duplicar" cruzando la frontera de lenguaje — solo disciplina + test.
3. **Persistencia explícita.** `schedule_*` (incl. el nuevo) solo retorna; el servicio asigna
   los campos a la carta (§4.2).
4. **`validation_alias` camelCase** en los schemas de entrada (§4.3).

---

## 7. Deferrals explícitos (nombrados, no arreglados aquí)

- **struggled-signal sigue abierto.** `_build_struggled_items` selecciona attempts con
  `overall_score < 70` en ventana de 14 días. Re-practicar una palabra y decirla "ok" deja un
  attempt aún `<70` → la frase struggled reaparece eternamente: **el mismo bug de
  inmortalidad, en el otro signal**. Este PR cierra el ciclo SRS, **no** el struggled. Definir
  un umbral de "graduación" del struggled es trabajo futuro.
- **Canal de recall** (revelar + 4 botones, promoción vía SM-2 completo): futuro.
- **Fix de data `VocabItem.language="de"`**: ticket de higiene aparte.
- **Índice `(user_card_id, reviewed_at)`** para la query de dedup: no se añade en v1 (volumen
  bajo); si duele, POST-SHIP.

---

## 8. Bordes

- **Reintentos:** `clearFeedback` borra el score previo → solo el último intento cuenta (modelo
  "una calificación" de Anki). Naturalmente correcto.
- **Salida temprana (`onExit`, `Practice.tsx:328`):** hace `setPhase('setup')` sin POST. Definir
  en el plan si "back" descarta los scores (modelo actual) o persiste lo puntuado. Default:
  descartar (consistente con hoy); el cierre solo ocurre al llegar a `summary`.
- **Delta visible stats vs returns:** el usuario puede ver "8 frases, 3 a revisar" arriba y la
  lista de reprogramadas más corta abajo (una "a revisar" no tenía carta due). El dek debe
  aclarar que la lista cubre solo vocabulario en SRS.
- **Truncado de la lista:** hoy `slice(0,3)` (`Practice.tsx:245`) porque struggled rara vez >3;
  SRS-due puede ser mayor. Mostrar todas, o reflejar el total en el contador + "+N".
- **Timezone:** asegurar comparaciones aware (`reviewed_at` es `timezone=True`, `now(UTC)`);
  `stories.py:267` ya evidencia datetimes naive desde Postgres en este repo — guardar contra
  `TypeError`.
- **Docstrings obsoletos a actualizar:** `practiceQueue.ts:13` ("STRUGGLED-ONLY", ya falso);
  `practice_queue.py:31-34` ("Pending PR #3b" — este diseño ES ese cierre).

---

## 9. Testing

**Backend (pytest):**
- Mapeo D1: `bad→Again`, `ok→Hard`, `good→Good`; **nunca `Easy`**.
- `schedule_pronunciation_maintenance`: escalera correcta; **no muta** `ease`/`repetitions`/
  `state`; asigna los 4 campos.
- Resolución por `card_id`: due reprograma; no-due se ignora; carta inexistente se ignora.
- **Aislamiento entre usuarios:** carta de otro usuario nunca se toca (invariante de seguridad).
- Dedup de `card_id` en el batch (idempotencia intra-request); atomicidad (un fallo no deja
  commits parciales).
- Deserialización camelCase del body (ligado a `validation_alias`).
- Banda de palabra-foco vs fallback (peor banda de frase) cuando el foco no tiene banda.
- No re-testear tokenizador/`_BAND_RANK` (ya cubiertos por `test_practice_queue.py`, 20 tests).

**Frontend:**
- `typecheck` + `i18n:check` (claves obsoletas borradas en los 6 locales; sin claves nuevas si
  se reusa `schedule.*`).
- Exclusión de líneas simuladas (**bloqueado** hasta que exista el flag, §6.1).
- Exclusión de líneas sin `cardId` / sin score.
- Disparo-único + marca al confirmar + reintento en fallo.
- `rescheduled = []` oculta sección + `<hr>`.

---

## Apéndice — procedencia

Diseño endurecido tras un red-team adversarial de 12 lentes del consejo (Serrano, Halberg,
Voronov, Richter, Null Vale, Iris, Lyra, Cassian, Vex, Amina, Plumb, crítico de completitud) +
síntesis + Axiom-0 (convocado por conflicto genuino entre 9 lentes). 116 findings crudos
consolidados. El framing de §2 es la sentencia de Axiom-0; el BLOCKER de flexión (§4.1) y las
precondiciones (§6) son hallazgos verificados contra el código que invalidaban el diseño
original (resolución por texto + "el flag simulado existe" + "el tokenizador es idéntico").
