# El taller — F0 (diseño)

Spec de la única fase autorizada por `docs/design/klara-desktop/KICKOFF.md` (v3).
Ámbito: una superficie de escritorio donde el usuario **escribe o pega texto, lo
convierte en tarjetas con etiquetas libres, y las repasa ahí mismo** con el FSRS
que ya corre en producción — sin `Course`, sin tocar el dominio de alemán.

**Estado: v2, tras el gate de Serrano** (4 BLOCKER, 6 HIGH, 5 MEDIUM; las cuatro
citas de código que sostenían los BLOCKER están verificadas a mano). El gate de
Iris sobre el mockup va después y puede mover la composición, no el contrato.

## Goal

Falsar en 48 horas de uso real la tesis "Klara sirve para aprender cualquier cosa",
con el criterio comprometido en el kickoff: **≥20 tarjetas creadas en un fin de
semana sobre un tema que no sea alemán → continúa; <20 → congela.** La §11 define
cómo se cuenta ese número, que hasta ahora no tenía regla.

## 0. Nombres (pase solace-wren, 2026-08-11)

El producto ya habla en objetos físicos: `/review` se titula **"La caja de fichas"**.
La superficie nueva hereda esa casa.

| | Decisión | Por qué |
|---|---|---|
| Ruta | **`/taller`** | Es el único candidato que nombra la divergencia: un sitio donde se *fabrica*, que es la tesis del escritorio. `/mesa` no dice qué pasa ahí; `/tarjetas` nombra una lista. |
| Namespace i18n | `taller` | Al nivel de `curso`, `mapa`, `perfil`, `estudiar`. |

**Los tres sustantivos: tarjeta · etiqueta · repaso.**

- **tarjeta**, no *ficha*: `ficha` es la caja de alemán. Dos sistemas conviven cuatro
  semanas (deuda declarada, dueña Lyra); que se llamen distinto mantiene legible la
  convivencia.
- **etiqueta**, no *carpeta* ni *curso*: la generalidad viene de no cablear la taxonomía.
- **repaso**, no *cola*: en venezolano "cola" es una fila, una cola de animal, un
  refresco y un aventón. "Repaso" ya está en la boca del producto.

Código en inglés como el resto del repo: `study_cards`, `tags`, `due`.

## 1. Modelo de datos — migración `20260811_0021_study_cards.py`

Aditiva. `down_revision = "20260810_0020"`. Cero cambios sobre tablas existentes.

### `study_cards`

| Columna | Tipo | Null | Default | Nota |
|---|---|---|---|---|
| `id` | `uuid_pk` | no | `uuid4` | |
| `user_id` | UUID | no | — | FK `users.id` CASCADE |
| `front` | Text | no | — | 1..500, sin TAB/CR/LF (§4) |
| `back` | Text | no | — | 1..2000, sin TAB/CR/LF (§4) |
| `tags` | `ARRAY(Text)` | no | `'{}'` | ≤10, normalizadas |
| `batch_id` | UUID | no | — | lote de autoría (§3, §11) |
| `archived_at` | timestamptz | sí | — | borrado blando (§6) |
| `state` | enum `card_state` | no | `NEW` | **reusa el tipo**, `create_type=False` |
| `stability` / `difficulty` | Float | sí | — | FSRS |
| `fsrs_step` | Integer | sí | — | FSRS |
| `fsrs_last_review` | timestamptz | sí | — | FSRS |
| `interval_days` | Float | no | `0.0` | |
| `next_review_at` | timestamptz | **no** | `now()` | ver nota |
| `last_reviewed_at` | timestamptz | sí | — | |
| `repetitions` | Integer | no | `0` | |
| `created_at` / `updated_at` | `created_ts` / `updated_ts` | no | `now()` | |

- Índices: `ix_study_card_due (user_id, next_review_at)`, `ix_study_card_batch (user_id, batch_id)`.
- **`next_review_at` es NOT NULL**, a diferencia de `user_cards`. Allá es nullable y
  la consulta de vencidas trata NULL como vencido (`routers/srs.py:95`); acá una
  tarjeta nace vencida con `next_review_at = created_at`, lo que da orden determinista
  (la más vieja primero) sin la rama `is_(None)`.
- **Sin unique sobre el contenido.** Los duplicados que escribe el usuario son suyos.
  Los duplicados que genera un reintento **no** — de eso se ocupa `batch_id` (§3).
- **`ease` no se copia**: legacy congelada, `schedule_next_review` no la toca
  (`srs_engine.py:106`).
- **`source` se elimina** (estaba en la v1). Con dos valores derivados del endpoint
  invocado medía qué ruta se llamó, no cómo se autoró: escribir cinco tarjetas a mano
  en el textarea habría quedado como `paste`. `batch_id` mide lo que interesa de verdad
  — cuántas tarjetas por sesión de autoría, y cuántas sesiones hubo.
- Sin índice GIN sobre `tags`: se agrega cuando el filtro se mida lento.

### `study_card_reviews`

| Columna | Tipo | Null | Nota |
|---|---|---|---|
| `id` | `uuid_pk` | no | |
| `user_id` | UUID | no | FK `users.id` CASCADE |
| `study_card_id` | UUID | no | FK `study_cards.id` CASCADE |
| `rating` | enum `review_rating` | no | **reusa el tipo**, `create_type=False` |
| `elapsed_seconds` | Integer | sí | |
| `prev_interval_days` / `new_interval_days` | Float | no | |
| `device` | String(16) | no | `CHECK IN ('desktop','mobile')` |
| `reviewed_at` | `created_ts` | no | |

- Índice `ix_study_review_user_time (user_id, reviewed_at)`.
- `device` es obligatorio en el cuerpo del request; el servidor no lo adivina del
  User-Agent y no tiene default. **No es criterio de éxito** — con `NOT NULL` + CHECK
  es verdadero por construcción y no puede falsarse. Es un invariante de esquema. Lo
  falsable está en §11.
- El archivado no borra reviews. Por eso `archived_at` en vez de `DELETE` (§6).

## 2. `srs_engine` — un solo scheduler, cálculo **y** escritura

El kickoff: *"Dos implementaciones de FSRS que derivan es el peor resultado posible."*
El motor no toca la clase `UserCard`, solo ocho atributos — pero **tampoco persiste**:
`srs_engine.py:101-108` muta cinco campos y devuelve un trío que
`routers/srs.py:116-121` asigna. Unificar solo el cálculo dejaría la escritura
duplicada, que es la misma deriva por la puerta de atrás.

Se añade a `services/srs_engine.py`:

```python
class FsrsCard(Protocol):
    state: CardState
    stability: float | None
    difficulty: float | None
    fsrs_step: int | None
    fsrs_last_review: datetime | None
    interval_days: float
    next_review_at: datetime | None
    last_reviewed_at: datetime | None
    repetitions: int


def apply_review(card: FsrsCard, rating: ReviewRating) -> float:
    """Programa y persiste en el objeto. Devuelve prev_interval_days."""
```

`apply_review` contiene exactamente lo que hoy hace `routers/srs.py:116-121`. Los dos
routers la llaman. `_to_fsrs_card`, `schedule_next_review` y `project_intervals` cambian
`UserCard` → `FsrsCard`, solo anotaciones. `schedule_pronunciation_maintenance` no se toca.

El repo no corre `mypy` (solo `ruff`), así que el `Protocol` es contrato de revisión,
no gate de CI.

**Tests que sostienen el invariante:**
1. Paridad: la misma secuencia de ratings sobre un `UserCard` y un `StudyCard` con
   estado inicial idéntico produce **los nueve atributos** idénticos — no solo el trío
   devuelto. Un test que solo comparara el retorno pasaría en verde aunque un router
   olvidara asignar `state` o `last_reviewed_at`.
2. Regresión del alemán: la suite backend existente cubre `POST /srs/cards/{id}/review`
   y debe pasar sin tocar sus asserts.

## 3. Endpoints — `APIRouter(prefix="/taller", tags=["taller"])`

Deps: `DBSession`, `CurrentUser`, `LocaleDep`. Schemas en `schemas/taller.py`. **Toda
consulta lleva `user_id == user.id`**; tarjeta ajena o inexistente ⇒ **404**.

| # | Método y ruta | Cuerpo / query | Devuelve |
|---|---|---|---|
| 1 | `GET /taller/overview` | — | `{total, due, tags: [{tag, count}]}` |
| 2 | `POST /taller/cards` | `{front, back, tags[], batch_id}` | 201 `StudyCardOut` |
| 3 | `POST /taller/cards/bulk` | `{cards: [{front, back}], tags[], batch_id}` | 201 `{created, cards[]}` |
| 4 | `GET /taller/cards` | `?tag=&limit=&offset=` | `{total, items: StudyCardOut[]}` |
| 5 | `GET /taller/cards/due` | `?limit=` (def. 20, máx. 50) | `StudyCardOut[]` con `next_intervals` |
| 6 | `POST /taller/cards/{id}/review` | `{rating, elapsed_seconds, device}` | `StudyCardOut` actualizada |
| 7 | `POST /taller/cards/{id}/archive` | — | 204 |
| 8 | `GET /taller/export` | — | TSV |

`overview` existe porque el mockup pide un total, un conteo de vencidas y conteos por
etiqueta que `limit/offset` no permite derivar en cliente. Una llamada al montar.

### `bulk`: todo-o-nada e idempotente

- **Una transacción.** Si una tarjeta del lote falla la validación, se rechaza el lote
  entero con 422 y la lista de índices ofensores. Cero filas escritas. `created`
  siempre es igual al largo del lote.
- **`batch_id` lo genera el cliente**, uno por intento de guardado. Antes de insertar:
  si ya existe una fila con `(user_id, batch_id)`, se devuelven las de ese lote sin
  insertar nada. Un doble clic, un reintento o una respuesta perdida no duplican.
- Tope de 200 tarjetas por lote.

### Regla de parseo (única, en el cliente)

El kickoff pedía el parseo TSV en el endpoint. **Se desvía, con razón declarada:** la
pantalla exige previsualizar antes de guardar, así que el cliente parsea igual; un
parser a cada lado es el modo de fallo que el propio kickoff prohíbe para FSRS. Queda
**una** función pura en `frontend/src/lib/tallerParse.ts` con sus tests, y el endpoint
recibe tarjetas ya estructuradas.

- Una tarjeta por línea no vacía; `front` y `back` separados por TAB.
- **Línea con cero TABs o con más de uno ⇒ rechazada y visible** con su número de línea.
  Rechazar el caso de dos TABs no es purismo: un export de Anki de tres columnas metería
  la tercera dentro de `back` en silencio, y "nada se descarta en silencio" es regla.
- Como `front` y `back` nunca contienen TAB, CR ni LF, el TSV de `export` no necesita
  escapado ni quoting. La restricción en la entrada es lo que hace segura la salida.
- Tope de 200 por guardado, dicho antes de guardar.
- Duplicados escritos por el usuario: se permiten y no se avisa.

### `export`

TSV `front \t back \t tags(coma) \t created_at \t archived`. Existe para que congelar
el experimento no le cueste sus tarjetas a nadie y para reimportar en Anki.

## 4. Validación en frontera

| Campo | Regla | Fallo |
|---|---|---|
| `front` | `strip`, 1..500, sin TAB/CR/LF | 422 |
| `back` | `strip`, 1..2000, sin TAB/CR/LF | 422 |
| `tags` | ≤10; cada una `strip` + minúsculas + dedupe, 1..32 | 422 |
| `cards` (bulk) | 1..200 | 422 |
| `batch_id` | UUID válido, obligatorio | 422 |
| `rating` | enum `ReviewRating` | 422 |
| `elapsed_seconds` | 0..3600, **se recorta** al tope | — |
| `device` | `desktop` \| `mobile`, obligatorio | 422 |
| pegado (cliente) | ≤100 000 caracteres | se corta **en el último salto de línea completo**, con aviso del número de líneas descartadas |

`elapsed_seconds` se recorta en vez de rechazar: una tarjeta abierta toda la noche no
puede costar la pérdida del review.

**Los 422 del servidor son un bug, no un camino de usuario:** la previsualización valida
las mismas reglas antes de habilitar guardar. Para el caso residual, el cliente del taller
mapea cualquier 422 a una sola cadena traducida (`taller.errors.invalid`) y manda el detalle
a consola. Limitación declarada: `main.py` no tiene handler de `RequestValidationError` y
`client.ts:118` serializa el array de Pydantic crudo; arreglar eso es global y queda fuera.

## 5. Ciclo de vida del texto (el estado que la v1 no tenía)

| Momento | Qué pasa con el textarea |
|---|---|
| Al escribir | se guarda en `localStorage` (`taller.draft`), con rebote; se restaura al montar |
| Guardado con éxito | **quedan solo las líneas que no se guardaron**: las rechazadas y el sobrante por encima de 200. Las guardadas se van |
| Pegado > 100 000 caracteres | se corta en el último salto de línea completo; nunca a mitad de línea |
| 401 durante el guardado | `client.ts:106` desmonta la pantalla; el borrador sobrevive en `localStorage` y vuelve al reingresar |
| Redimensionar bajo 1024px | igual: el borrador está en `localStorage`, no se pierde nada |

Ocho líneas de código que cubren 401, recarga, cierre accidental y caída. El experimento
entero es 48 horas de una persona escribiendo: perder el pegado una vez lo invalida.

## 6. Archivar en vez de borrar

`POST /taller/cards/{id}/archive` pone `archived_at = now()`. Las consultas filtran
`archived_at IS NULL`; los reviews sobreviven; `export` las incluye marcadas. Un `DELETE`
en cascada destruiría el ledger, que el kickoff declara no opcional.

**Editar una tarjeta queda cortado.** Se agrega si el fin de semana lo pide.

## 7. Frontend

- Ruta `/taller` en `App.tsx`, **suelta dentro de `<ProtectedRoute>`**, fuera de `V4Shell`
  (precedente: `/estudiar/:id`, `App.tsx:231-239`). Import estático: el repo no usa `lazy`.
- **Puerta de escritorio: `@media (min-width: 1024px)`, sin `pointer: fine`.** La v1 lo
  pedía y estaba mal: `pointer` reporta el señalador primario, así que un portátil táctil
  a 1920px reporta `coarse` y quedaría fuera — posiblemente la propia máquina del dogfood.
  Por debajo de 1024px, un mensaje traducido, no un layout roto.
- **Punto de entrada:** un enlace que solo se renderiza sobre 1024px, así el diff-cero
  sobre la pantalla móvil se cumple por construcción. **Dónde se coloca lo decide Iris.**
- **Modos que nunca coexisten:** *componer* y *repasar* son estados excluyentes de la ruta.
  De ahí sale el modelo de foco (§8) sin necesidad de Petra.

### Repaso: qué se comparte y qué no

El kickoff pedía "parametrizar `RecallReviewSession`, no forkearlo". La v1 dijo que
`lib/recallSession.ts` se reusaba **verbatim** y eso era falso: `recallSession.ts:12`
declara `cards: CardOut[]`, y `CardOut` (`api/types.ts:86-99`) exige `vocab_item_id`,
`lemma`, `pos` y `ease`. Reusarla verbatim obligaría a fabricar lexemas falsos.

- **La máquina se hace genérica con parámetro por defecto:** `RecallState<T = CardOut>`.
  Los sitios de llamada del alemán no cambian; el runtime es idéntico. Es **excepción
  nombrada** al diff-cero (§10), declarada antes de construir, no después.
- **La vista del taller es propia y corta**: `RecallReviewSession` renderiza lema, género
  e IPA, que el taller no tiene. Ese componente no cambia ni una línea.
- **El repaso del taller NO es fire-and-forget.** `RecallReviewSession.tsx:50` lanza
  `void api.reviewCard(...).catch(() => dispatch({type:"rateFailed"}))` y avanza igual: un
  POST fallido no escribe fila en el ledger, no reprograma FSRS, y solo deja un contador al
  final. El taller **no avanza hasta que el POST resuelve**; si falla, la tarjeta se queda
  en pantalla con un reintento. El kickoff dice que el ledger no es opcional; esta es la
  única forma de que eso sea cierto.

## 8. Teclado

`RecallReviewSession.tsx:56-67` registra `keydown` en `window` sin comprobar el foco. En
alemán es inocuo porque no hay campos de texto; en el taller, que es sobre todo un
textarea, escribir "1" calificaría una tarjeta.

- **Componer:** solo `Ctrl/Cmd+Enter` (guardar), enlazado **al textarea**, no a `window`.
- **Repasar:** `Space` revela, `1-4` califican, `Esc` sale — en `window`, y en ese estado
  no existe ningún campo de texto en pantalla.
- Los atajos viven **en un array** (la concesión de costo cero del kickoff).
- La gramática fina de interacción sigue **diferida a Petra Haft en F2**. El modelo de
  propiedad del foco no es gramática fina: es la condición para que la pantalla funcione,
  y se resuelve arriba con modos excluyentes.

## 9. i18n

Namespace `taller` en los **6** locales (`es` fuente de verdad; `npm run i18n:check` falla
con `missing` o `extra`). Cero strings duros: puerta de escritorio, estados vacíos, errores
de parseo, reintento de review.

## 10. Alcance del despliegue y qué significa "alemán intacto"

**F0 sale detrás de allowlist.** Un ajuste `TALLER_USER_IDS` (lista separada por comas);
los endpoints devuelven 403 a quien no esté y el enlace no se renderiza. Sin esto, F0
despliega escritura sin cuota a cualquier cuenta autenticada, contamina el conteo de §11
con datos de terceros, y deja tarjetas ajenas varadas si la regla dicta congelar.

**"Alemán intacto" se define como artefacto verificable**, no como afirmación:

1. `git diff --stat origin/main` no toca ningún archivo bajo `frontend/src/routes/`,
   `frontend/src/components/` ni `frontend/src/styles/` — **con dos excepciones nombradas**:
   `frontend/src/lib/recallSession.ts` (parámetro de tipo con default, §7) y
   `backend/src/klara/services/srs_engine.py` + `backend/src/klara/routers/srs.py`
   (extracción de `apply_review`, §2).
2. `uv run pytest tests/` verde sin editar ningún assert existente.
3. `npm run typecheck` verde.
4. Smoke iPhone verde.

## 11. Cómo se cuenta el número que decide la fase

El kickoff comprometió "≥20 tarjetas" sin decir qué es una tarjeta creada. Definición
operativa, fijada **antes** del fin de semana:

- **Sujeto:** un `user_id` único, anotado antes de empezar.
- **Ventana:** desde el deploy hasta el lunes 00:00 de Caracas (UTC−4), en `created_at` UTC.
- **Unidad:** filas en `study_cards` de ese `user_id` dentro de la ventana **y no
  archivadas al cierre**. Archivar resta: una tarjeta que Samuel borró por mala no es
  evidencia de que el taller sirvió.
- **Consulta**, corrida una vez el lunes:

```sql
SELECT count(*)                       AS tarjetas,
       count(DISTINCT batch_id)       AS lotes,
       count(DISTINCT date(created_at AT TIME ZONE 'America/Caracas')) AS dias
FROM study_cards
WHERE user_id = :uid AND archived_at IS NULL
  AND created_at >= :t0 AND created_at < :t_fin;
```

**Los tres números se reportan juntos, y solo el primero es el gate.** `lotes` y `dias`
existen porque 20 tarjetas de un solo pegado en una sola sesión miden "puedo pegar una
lista", no "vuelvo al taller". No cambio el umbral que Samuel comprometió; dejo el dato
a la vista para que la decisión del lunes se tome con él (§Preguntas abiertas 1).

**El criterio falsable que reemplaza a "`device` al 100%":** cero reviews perdidos — el
contador de la sesión en el cliente debe coincidir con `count(*)` de `study_card_reviews`
en la ventana. Con §7 (no avanzar hasta que el POST resuelva) puede fallar de verdad, y
por eso mide algo.

## 12. Estados de fallo

| Situación | Comportamiento |
|---|---|
| Pegado sin ningún TAB | 0 tarjetas; la previsualización lo dice; guardar deshabilitado |
| Línea con 2+ TABs (export de Anki de 3 columnas) | rechazada y visible, con su número de línea |
| Pegado de 5 000 líneas | se guardan las primeras 200; el resto **queda en el textarea** |
| Reenvío del mismo lote | `batch_id` lo absorbe: devuelve el lote existente, no duplica |
| Una tarjeta del lote inválida | 422 con los índices; **cero filas escritas** |
| 401 a mitad del guardado | la pantalla se desmonta; el borrador sobrevive en `localStorage` |
| POST de review falla | la tarjeta no avanza; reintento visible; no hay hueco en el ledger |
| Tarjeta de otro usuario | 404 |
| Usuario fuera de la allowlist | 403 y sin enlace |
| Repaso de tarjeta archivada | se acepta y se registra |
| Dos pestañas califican la misma tarjeta | gana la última escritura; el ledger guarda ambas filas |
| Repaso vacío | estado vacío que enseña qué iría ahí |
| Primera sesión con 200 vencidas | `due` sirve 20 por defecto, máx. 50 — no hay muro |
| `device` ausente | 422, nunca un default |
| Reloj | todo UTC; el vencimiento se compara en el servidor |

## 13. Fuera de scope (explícito)

Editor de bloques · notas como entidad · mapa mental · dashboard de widgets · plugins ·
paquetes `.mnemo` · import de Anki · command palette · entidad `Course` · consumo móvil
de la cola nueva (es F1) · edición de tarjetas · handler global de `RequestValidationError` ·
paleta y tipografía de mnemo (cambio de identidad, no estética) · cualquier contador de
racha, XP o minutos (prohibición constitucional).

## 14. Gates

1. ~~Serrano sobre esta spec~~ — hecho; esta es la v2.
2. **Iris** sobre el mockup — *antes* del plan.
3. Plan de ejecución, y recién ahí código.
4. Por PR: `npm run i18n:check` · `uv run pytest tests/` · `uv run ruff check src tests` ·
   `npm run typecheck` · el diff-cero de §10 · auditoría dark · a11y de foco y teclado ·
   smoke 1024/1280/1440/1920/720 + 1180 legacy.

## Preguntas abiertas

1. **`lotes` y `dias` son dato o son gate.** El umbral de 20 está comprometido y no lo
   toco. Pero si el lunes el número es "23 tarjetas, 1 lote, 1 día", eso satisface la
   regla midiendo otra cosa. Recomendación: decidir **ahora**, no el lunes, si un solo
   lote cuenta como continuar. Decidirlo después de ver el dato es elegir la conclusión.
2. **Traducción de los 5 locales no-`es`.** ~25 claves. `check-i18n` compara sets de
   claves, no contenido, así que copiar el `es` pasa el gate y deja deuda silenciosa.
   Recomendación: traducir ahora.
3. **`apply_review` toca el router de alemán.** Es refactor puro con la suite backend
   de guardia, y la alternativa es dejar duplicado el contrato de persistencia FSRS —
   la deriva que el kickoff llama el peor resultado posible. Declarado como excepción
   nombrada en §10, pero es una decisión de Samuel, no mía.

## Self-review

- Cuatro desviaciones del kickoff, todas declaradas: parser solo en cliente (§3), vista
  de repaso propia con máquina genérica (§7), `archive` añadido (§6), y allowlist en el
  deploy (§10).
- Dos criterios de éxito del kickoff se retiran por infalsables y se reemplazan:
  "`device` al 100%" pasa a invariante de esquema, y "diff-cero" pasa de afirmación a
  artefacto con lista de archivos y dos excepciones nombradas (§10, §11).
- Lo que esta spec **no** resuelve y no debe: dónde va el punto de entrada (Iris), la
  gramática de interacción fina (Petra, F2), y la convergencia de los dos sistemas de
  tarjetas (4 semanas, Lyra).
