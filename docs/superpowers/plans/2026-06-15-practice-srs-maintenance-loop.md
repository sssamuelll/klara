# SRS Maintenance Loop in Practice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar el ciclo SRS en Practice: practicar una carta due la reprograma de verdad (canal de *mantenimiento*, nunca promueve), y el summary muestra el intervalo real en vez de texto hardcodeado.

**Architecture:** El backend dueña la lógica. La cola porta `cardId` (deja de descartar la `UserCard` que ya resuelve). Un endpoint batch nuevo (`POST /srs/cards/review-batch`) deriva la banda de la palabra-foco server-side, la mapea a un rating con un scheduler de *mantenimiento* nuevo (escalera corta fija que NO toca `ease`/`repetitions`/`state`), reprograma en una transacción atómica y devuelve intervalos reales. El frontend manda el resultado de la sesión una vez al llegar al summary y renderiza lo devuelto.

**Tech Stack:** Backend: FastAPI + SQLAlchemy async + Pydantic v2 + pytest (`uv run pytest`). Frontend: React + Vite + TypeScript + react-i18next. **No hay runner de unit tests en el frontend** (solo `npm run typecheck`, `npm run build`, `npm run i18n:check`) — los pasos del frontend se verifican con esos comandos + un chequeo manual descrito. Esto es una desviación consciente de la palabra "unit test" del spec §9: el repo no tiene framework de tests FE y este plan no introduce uno.

**Spec:** `docs/superpowers/specs/2026-06-15-practice-srs-maintenance-loop-design.md`

**Decisiones de plan fijadas** (del spec): endpoint en `routers/srs.py`; salida temprana (`onExit`/"back") descarta scores como hoy (el cierre solo ocurre al llegar a `summary`). El scheduler de mantenimiento vive en `srs_engine.py` junto a `schedule_next_review` (sin modificarla). `target_language` NO se acepta del cliente (la carta se resuelve por `cardId` + ownership; el idioma es irrelevante).

**Comandos de verificación:**
- Backend: `cd backend && uv run pytest tests/ -v` · `uv run ruff check src tests` · `uv run ruff format --check src tests` (requiere `TEST_DATABASE_URL` a un Postgres real).
- Frontend: `cd frontend && npm run typecheck && npm run i18n:check && npm run build`.

---

## File Structure

**Backend (crear):**
- `src/klara/services/tokens.py` — tokenizador canónico + `BAND_RANK` + `worst_band`, compartidos por `practice_queue` y `practice_session` (mata la 2ª/3ª copia del regex en backend).
- `src/klara/services/practice_session.py` — `apply_pronunciation_reviews(...)`, la lógica del cierre.
- `tests/test_tokens.py`, `tests/test_srs_maintenance.py`, `tests/test_practice_session.py`.

**Backend (modificar):**
- `src/klara/services/practice_queue.py` — importar el tokenizador de `tokens.py`; portar `card_id`.
- `src/klara/services/srs_engine.py` — añadir `schedule_pronunciation_maintenance`.
- `src/klara/schemas/practice.py` — `card_id` en `PracticeItemOut`.
- `src/klara/schemas/srs.py` — schemas del batch (con `validation_alias`).
- `src/klara/routers/srs.py` — endpoint `POST /cards/review-batch`.

**Frontend (crear):**
- `src/lib/srsTime.ts` — `humanizeNextReview(nextReviewAt)`.

**Frontend (modificar):**
- `src/lib/pronunciation.ts` — regex canónico unificado + `wordTokensByIndex` + `worstBand` + `focusBand`.
- `src/lib/useSentencePractice.ts` — regex desde `pronunciation.ts`; `simulatedIndices` Set expuesto.
- `src/lib/practiceQueue.ts` — `cardId?` en `PracticeItem`.
- `src/api/types.ts` — tipos del batch.
- `src/api/client.ts` — `submitPronunciationReviews`.
- `src/routes/Practice.tsx` — wiring del summary (máquina de estados, payload, render real, stats por palabra-foco).
- `src/locales/{es,en,de,fr,ja,pt}/common.json` — borrar 3 claves posicionales obsoletas.

---

## PARTE A — Backend

### Task 1: Tokenizador canónico compartido (`services/tokens.py`)

**Files:**
- Create: `backend/src/klara/services/tokens.py`
- Modify: `backend/src/klara/services/practice_queue.py`
- Test: `backend/tests/test_tokens.py`

- [ ] **Step 1: Verificar el patrón canónico actual antes de extraer**

El tokenizador del backend es la fuente canónica. Captura su patrón EXACTO (incluye comillas
tipográficas que el frontend hoy NO espeja — ese es el bug del spec §6.2):

Run: `cd backend && uv run python -c "from klara.services.practice_queue import _TOKEN_RE; print(repr(_TOKEN_RE.pattern))"`
Expected: imprime el patrón con la clase de puntuación (anótalo verbatim; lo reproduces tal cual en `tokens.py`).

- [ ] **Step 2: Escribir el test que falla**

```python
# backend/tests/test_tokens.py
"""El tokenizador canónico debe tratar comillas tipográficas y guillemets como
puntuación (NO como parte de la palabra), igual en todo el repo. Este test ancla
ese comportamiento para que el frontend pueda espejarlo byte a byte (spec §6.2)."""

from klara.services.tokens import BAND_RANK, word_tokens_by_index, worst_band


def test_curly_quotes_are_punctuation_not_word_chars():
    # „Tür" con comillas tipográficas: la palabra es "Tür", sin las comillas.
    text = '„Tür" sagt sie.'
    tokens = word_tokens_by_index(text)
    assert "Tür" in tokens.values()
    assert not any('„' in w or '"' in w or '"' in w for w in tokens.values())


def test_word_indices_are_global_token_positions():
    # "Die Nummer" -> word tokens en índices globales 0 y 2 (1 es el espacio).
    tokens = word_tokens_by_index("Die Nummer")
    assert tokens == {0: "Die", 2: "Nummer"}


def test_worst_band_picks_lowest_rank():
    assert worst_band({0: "good", 2: "bad", 4: "ok"}) == "bad"
    assert worst_band({0: "good", 2: "ok"}) == "ok"
    assert worst_band({}) is None
    assert BAND_RANK["bad"] < BAND_RANK["ok"] < BAND_RANK["good"]
```

- [ ] **Step 3: Correr el test para verque falla**

Run: `cd backend && uv run pytest tests/test_tokens.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'klara.services.tokens'`.

- [ ] **Step 4: Crear `tokens.py`**

```python
# backend/src/klara/services/tokens.py
"""Tokenizador canónico del repo + ranking de bandas.

Fuente única de verdad para la tokenización palabra/espacio/puntuación. El
frontend (`frontend/src/lib/pronunciation.ts`) DEBE espejar `_PUNCT` byte a byte
— los índices de `word_bands` se alinean entre cliente y servidor solo si ambos
tokenizan idéntico (spec §6.2). Si cambias `_PUNCT`, cambia las copias del
frontend y corre el smoke de pronunciación con una frase con comillas curvas.
"""

from __future__ import annotations

import re

# Clase de puntuación canónica. Reproduce EXACTAMENTE lo capturado en Task 1
# Step 1. Codepoints: ASCII . , ! ? ; : ( ) - · ¡(U+00A1) ¿(U+00BF) · —(U+2014)
# –(U+2013) · »(U+00BB) «(U+00AB) · „(U+201E) "(U+201C) "(U+201D).
_PUNCT = r".,!?;:„“”»«()¡¿—–\-"
_TOKEN_RE = re.compile(rf"(\s+)|([{_PUNCT}]+)|([^\s{_PUNCT}]+)")

# Ranking de bandas, peor -> mejor. Banda desconocida ordena al final (segura).
BAND_RANK: dict[str, int] = {"bad": 0, "ok": 1, "good": 2}


def word_tokens_by_index(text: str) -> dict[int, str]:
    """{índice_global_de_token: texto_de_palabra} solo para tokens de palabra.

    El índice cuenta TODOS los tokens (espacio, puntuación, palabra) para que
    coincida con las llaves de `word_bands` producidas por el frontend.
    """
    out: dict[int, str] = {}
    i = 0
    for m in _TOKEN_RE.finditer(text):
        if m.group(3):  # token de palabra
            out[i] = m.group(3)
        i += 1
    return out


def worst_band(word_bands: dict[int, str]) -> str | None:
    """La peor banda presente (por BAND_RANK), o None si no hay ninguna."""
    if not word_bands:
        return None
    return min(word_bands.values(), key=lambda b: BAND_RANK.get(b, 99))
```

- [ ] **Step 5: Refactorizar `practice_queue.py` para importar de `tokens.py`**

En `backend/src/klara/services/practice_queue.py`: borra la definición local de `_TOKEN_RE`
(línea ~82), de `_word_tokens_by_index` (líneas ~85-98) y de `_BAND_RANK` (línea ~76). **Borra
también `import re` (línea ~47)** — su único uso en el archivo es el `_TOKEN_RE` que se va a
`tokens.py`; dejarlo dispara F401 (unused-import) y hace fallar `ruff check` en el Step 7. Añade
arriba (en el bloque de imports `from klara...`):

```python
from klara.services.tokens import BAND_RANK as _BAND_RANK
from klara.services.tokens import word_tokens_by_index as _word_tokens_by_index
```

Deja intactos `_worst_token`, `_focus_translation` y el resto: ya llaman a `_word_tokens_by_index`
y `_BAND_RANK` por esos nombres, así que los alias mantienen el código existente sin más cambios.

- [ ] **Step 6: Correr tests para verificar verde (nuevo + regresión)**

Run: `cd backend && uv run pytest tests/test_tokens.py tests/test_practice_queue.py -v`
Expected: PASS (los 3 nuevos + los 20 de `test_practice_queue` siguen pasando).

- [ ] **Step 7: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/services/tokens.py backend/src/klara/services/practice_queue.py backend/tests/test_tokens.py
git commit -m "refactor(srs): extract canonical tokenizer to services/tokens.py"
```

---

### Task 2: Scheduler de mantenimiento (`schedule_pronunciation_maintenance`)

**Files:**
- Modify: `backend/src/klara/services/srs_engine.py`
- Test: `backend/tests/test_srs_maintenance.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/tests/test_srs_maintenance.py
"""El canal de pronunciación MANTIENE: escalera corta fija, sin tocar el estado
de promoción (ease/repetitions/state). schedule_next_review no se toca."""

from datetime import UTC, datetime

import pytest

from klara.models.enums import CardState
from klara.models.srs import UserCard
from klara.services.srs_engine import schedule_pronunciation_maintenance


def _card() -> UserCard:
    return UserCard(
        user_id=None,
        vocab_item_id=None,
        ease=2.5,
        interval_days=30.0,
        repetitions=5,
        state=CardState.REVIEWING,
    )


@pytest.mark.parametrize(
    "band,expected_days",
    [("bad", 0.0069), ("ok", 0.04), ("good", 1.0)],
)
def test_maintenance_ladder_intervals(band, expected_days):
    card = _card()
    interval, next_at = schedule_pronunciation_maintenance(card, band)
    assert interval == expected_days
    assert next_at > datetime.now(UTC)


def test_maintenance_never_touches_promotion_state():
    # Una carta promovida (REVIEWING, interval 30) dicha "good": el mantenimiento
    # NO multiplica por ease ni cambia ease/repetitions/state.
    card = _card()
    schedule_pronunciation_maintenance(card, "good")
    assert card.ease == 2.5
    assert card.repetitions == 5
    assert card.state == CardState.REVIEWING
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `cd backend && uv run pytest tests/test_srs_maintenance.py -v`
Expected: FAIL con `ImportError: cannot import name 'schedule_pronunciation_maintenance'`.

- [ ] **Step 3: Implementar (añadir al final de `srs_engine.py`)**

```python
# Maintenance ladder for the pronunciation channel. Short, FIXED steps — this
# channel keeps due cards in circulation; it NEVER promotes to long intervals
# (that's the recall channel's job, future). Mirrors the LEARNING-path steps of
# schedule_next_review WITHOUT its REVIEWING exponential growth, and crucially
# does NOT touch ease/repetitions/state (promotion state owned by recall).
_MAINTENANCE_INTERVAL_DAYS: dict[str, float] = {
    "bad": 0.0069,  # ~10 min — re-drill soon (rating Again)
    "ok": 0.04,     # ~1 hour (rating Hard)
    "good": 1.0,    # +1 day — maintained, not graduated (rating Good)
}


def schedule_pronunciation_maintenance(
    card: UserCard, band: str
) -> tuple[float, datetime]:
    """Pronunciation maintenance channel. Returns (interval_days, next_review_at).

    The caller persists card.interval_days / next_review_at / last_reviewed_at
    (this function deliberately does NOT mutate the card — schedule_next_review
    mutates ease/repetitions, this one keeps the card's promotion state frozen).
    `band` is one of "bad" | "ok" | "good".
    """
    interval = _MAINTENANCE_INTERVAL_DAYS[band]
    next_review = datetime.now(UTC) + timedelta(days=interval)
    return interval, next_review
```

`datetime`, `UTC`, `timedelta` y `UserCard` ya están importados arriba en `srs_engine.py`.

- [ ] **Step 4: Correr el test para verificar verde**

Run: `cd backend && uv run pytest tests/test_srs_maintenance.py -v`
Expected: PASS (5 casos: 3 parametrizados + 2).

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/services/srs_engine.py backend/tests/test_srs_maintenance.py
git commit -m "feat(srs): add pronunciation maintenance scheduler (no promotion)"
```

---

### Task 3: Portar `card_id` (schema + cola)

**Files:**
- Modify: `backend/src/klara/schemas/practice.py`, `backend/src/klara/services/practice_queue.py`
- Test: `backend/tests/test_practice_queue.py`

- [ ] **Step 1: Escribir los tests que fallan (añadir al final de `test_practice_queue.py`)**

```python
@pytest.mark.asyncio
async def test_review_item_carries_card_id(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")
    vid = await _seed_due_card(
        db_session, user_id=uid, lemma="Brot", translation="pan",
        example_target="Ich esse Brot.",
    )
    card_id = (
        await db_session.execute(select(UserCard).where(UserCard.vocab_item_id == vid))
    ).scalar_one().id
    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    review = [i for i in items if i["reason"] == "review"]
    assert review and review[0]["cardId"] == str(card_id)


@pytest.mark.asyncio
async def test_struggled_without_card_has_null_card_id(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    uid = await _user_id_by_email(db_session, "practice@example.com")
    ref = "Die Nummer wechselt."
    sid = await _seed_story(
        db_session, user_id=uid,
        sentences=[{"target": ref, "native": "El número cambia.", "new_words": [], "breakdown": []}],
    )
    await _seed_attempt(
        db_session, user_id=uid, story_id=sid, sentence_index=0,
        reference_text=ref, overall_score=50.0, word_bands={"0": "bad", "2": "ok"},
    )
    r = await client.get("/api/v1/practice/queue", headers={"Cookie": cookie})
    items = r.json()["items"]
    struggled = [i for i in items if i["reason"] == "struggled"]
    assert struggled and struggled[0]["cardId"] is None
```

- [ ] **Step 2: Correr para verificar que fallan**

Run: `cd backend && uv run pytest tests/test_practice_queue.py -k "card_id" -v`
Expected: FAIL — `KeyError: 'cardId'` (el campo no existe aún).

- [ ] **Step 3: Añadir `card_id` a `PracticeItemOut`** (`schemas/practice.py`, tras `sentence_index`):

```python
    # Identidad de la UserCard SRS que respalda este item, cuando la hay. La cola
    # YA resuelve la carta (build_review_items) y el dedup struggled∩review matchea
    # el lemma — portarla aquí deja que el cierre del ciclo reprograme POR ID, sin
    # re-resolver por texto aguas abajo (que colapsa para formas flexionadas).
    card_id: UUID | None = Field(default=None, serialization_alias="cardId")
```

Añade el import si falta: `from uuid import UUID` (arriba del archivo).

- [ ] **Step 4: Portar `card_id` en `build_review_items`** (`practice_queue.py`)

En el bucle `for _card, vocab in rows:` (línea ~334) renombra `_card` a `card` y, en el
`PracticeItemOut(...)` que construye (línea ~393), añade:

```python
                card_id=card.id,
```

- [ ] **Step 5: Portar `card_id` a items struggled que son due, en `build_practice_queue`**

En `build_practice_queue` (`practice_queue.py:416`). **Importante:** hoy `review_items` SOLO se
define dentro del bloque `if remaining > 0:` (líneas ~438-454). Dos cambios:

**(a)** Inicializa `review_items` ANTES de ese `if`, para que exista siempre:

```python
    review_items: list[PracticeItemOut] = []
    remaining = limit - len(items)
    if remaining > 0:
        review_items = await build_review_items(  # quita el `review_items =` de la línea actual
            ...
        )
        for it in review_items:
            ...  # (bucle de dedup-append existente, sin cambios)
```

(es decir: declara `review_items = []` arriba y dentro del `if` ASIGNA a esa misma variable en vez
de crear una local nueva.)

**(b)** A NIVEL de `build_practice_queue` (FUERA del `if`, después de que cierra y ANTES del
cálculo de `source_title` en ~línea 461), mapea lemma->card_id y adjúntalo a los struggled due:

```python
    # Un struggled cuyo focus es una carta due debe reprogramarse igual que un
    # review (scope B). El dedup ya lo dejó como struggled; aquí le adjuntamos la
    # identidad de su carta para que el cierre del ciclo la alcance.
    card_by_lemma = {
        it.focus_text.casefold(): it.card_id
        for it in review_items
        if it.card_id is not None
    }
    for it in items:
        if it.card_id is None and it.focus_text.casefold() in card_by_lemma:
            it.card_id = card_by_lemma[it.focus_text.casefold()]
```

- [ ] **Step 6: Correr tests (nuevos + regresión)**

Run: `cd backend && uv run pytest tests/test_practice_queue.py -v`
Expected: PASS (los 2 nuevos + los 20 existentes).

- [ ] **Step 7: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/schemas/practice.py backend/src/klara/services/practice_queue.py backend/tests/test_practice_queue.py
git commit -m "feat(practice): carry cardId from queue for due-card items"
```

---

### Task 4: Schemas del batch (`schemas/srs.py`)

**Files:**
- Modify: `backend/src/klara/schemas/srs.py`
- Test: `backend/tests/test_practice_session.py` (se crea aquí; se amplía en Task 5)

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/tests/test_practice_session.py
"""Cierre del ciclo SRS por pronunciación (canal de mantenimiento)."""

from __future__ import annotations

import uuid

from klara.schemas.srs import PronunciationBatchIn, RescheduledCardOut


def test_batch_in_deserializes_camelcase():
    # El frontend envía camelCase; validation_alias debe aceptarlo (si no, 422).
    payload = PronunciationBatchIn.model_validate(
        {
            "reviews": [
                {
                    "cardId": str(uuid.uuid4()),
                    "focusText": "Brot",
                    "sentenceTarget": "Ich esse Brot.",
                    "wordBands": {"0": "good", "2": "good", "4": "bad"},
                }
            ]
        }
    )
    assert payload.reviews[0].focus_text == "Brot"
    assert payload.reviews[0].word_bands[4] == "bad"  # llaves coercionadas a int


def test_rescheduled_out_serializes_camelcase():
    from datetime import UTC, datetime

    out = RescheduledCardOut(focus_text="Brot", interval_days=1.0, next_review_at=datetime.now(UTC))
    dumped = out.model_dump(by_alias=True)
    assert "focusText" in dumped and "intervalDays" in dumped and "nextReviewAt" in dumped
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_practice_session.py -v`
Expected: FAIL — `ImportError: cannot import name 'PronunciationBatchIn'`.

- [ ] **Step 3: Añadir los schemas a `schemas/srs.py`**

**Primero, los imports — al TOPE del archivo, no al final** (colocarlos abajo dispara E402 +
I001 y hace fallar `ruff check`). El archivo hoy tiene `from pydantic import BaseModel` (línea 4)
y NO importa `typing`. Cámbialo a:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
```

(es decir: fusiona `ConfigDict, Field` en la línea de pydantic existente, y añade la línea de
`typing` en el bloque de stdlib, manteniendo el orden de imports que ruff espera).

**Luego, las CLASES — al final del archivo:**

```python
class PronunciationReviewIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    card_id: UUID = Field(validation_alias="cardId")
    focus_text: str = Field(validation_alias="focusText")
    sentence_target: str = Field(validation_alias="sentenceTarget")
    word_bands: dict[int, Literal["bad", "ok", "good"]] = Field(validation_alias="wordBands")


class PronunciationBatchIn(BaseModel):
    reviews: list[PronunciationReviewIn]


class RescheduledCardOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    focus_text: str = Field(serialization_alias="focusText")
    interval_days: float = Field(serialization_alias="intervalDays")
    next_review_at: datetime = Field(serialization_alias="nextReviewAt")


class PronunciationBatchOut(BaseModel):
    rescheduled: list[RescheduledCardOut]
```

`UUID` y `datetime` ya se importan al inicio de `srs.py`.

- [ ] **Step 4: Correr para verificar verde**

Run: `cd backend && uv run pytest tests/test_practice_session.py -v`
Expected: PASS (2 casos).

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/schemas/srs.py backend/tests/test_practice_session.py
git commit -m "feat(srs): add pronunciation review-batch schemas (camelCase aliases)"
```

---

### Task 5: Servicio del cierre (`practice_session.py`)

**Files:**
- Create: `backend/src/klara/services/practice_session.py`
- Test: `backend/tests/test_practice_session.py` (ampliar)

- [ ] **Step 1: Escribir los tests que fallan (añadir a `test_practice_session.py`)**

```python
import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy import select

from klara.models import Review, User, UserCard, VocabItem
from klara.models.enums import CardState, PartOfSpeech, ReviewRating
from klara.schemas.srs import PronunciationReviewIn
from klara.services.practice_session import apply_pronunciation_reviews


async def _seed_user(db_session) -> uuid.UUID:
    from klara.models.enums import CEFRLevel
    u = User(
        id=uuid.uuid4(), email=f"u-{uuid.uuid4().hex[:6]}@k.app", hashed_password="x",
        is_active=True, is_verified=True, is_superuser=False, display_name="U",
        level=CEFRLevel.A0, native_language="es", target_language="de",
    )
    db_session.add(u)
    await db_session.flush()
    return u.id


async def _seed_card(db_session, *, user_id, lemma, next_review_at, language="de"):
    # vocab_items NO se trunca entre tests (conftest.py) y hay unique
    # (lemma, language, pos) — sufija el lemma para no chocar entre casos.
    # Ningún assert compara el lemma exacto, así que el sufijo es inocuo.
    vocab = VocabItem(
        id=uuid.uuid4(), language=language, lemma=f"{lemma}-{uuid.uuid4().hex[:8]}",
        pos=PartOfSpeech.NOUN,
    )
    db_session.add(vocab)
    await db_session.flush()
    card = UserCard(
        id=uuid.uuid4(), user_id=user_id, vocab_item_id=vocab.id,
        ease=2.5, interval_days=30.0, repetitions=5, state=CardState.REVIEWING,
        next_review_at=next_review_at,
    )
    db_session.add(card)
    await db_session.commit()
    return card.id


def _review(card_id, focus, target, bands):
    return PronunciationReviewIn(
        card_id=card_id, focus_text=focus, sentence_target=target, word_bands=bands
    )


@pytest.mark.asyncio
async def test_due_card_reschedules_without_promotion(db_session):
    uid = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=uid, lemma="Brot", next_review_at=None)
    # "Ich esse Brot." -> tokens 0 Ich, 2 esse, 4 Brot. Foco "Brot" en idx 4 = bad.
    out = await apply_pronunciation_reviews(
        db_session, user_id=uid,
        reviews=[_review(cid, "Brot", "Ich esse Brot.", {0: "good", 2: "good", 4: "bad"})],
    )
    assert len(out) == 1 and out[0].focus_text == "Brot"
    assert out[0].interval_days == 0.0069  # bad -> Again ladder
    card = await db_session.get(UserCard, cid)
    assert card.ease == 2.5 and card.repetitions == 5 and card.state == CardState.REVIEWING
    assert card.next_review_at > datetime.now(UTC)
    review = (await db_session.execute(select(Review).where(Review.user_card_id == cid))).scalar_one()
    assert review.rating == ReviewRating.AGAIN


@pytest.mark.asyncio
async def test_non_due_card_is_skipped(db_session):
    uid = await _seed_user(db_session)
    future = datetime.now(UTC) + timedelta(days=10)
    cid = await _seed_card(db_session, user_id=uid, lemma="Haus", next_review_at=future)
    out = await apply_pronunciation_reviews(
        db_session, user_id=uid,
        reviews=[_review(cid, "Haus", "Das Haus.", {2: "good"})],
    )
    assert out == []
    card = await db_session.get(UserCard, cid)
    assert card.next_review_at == future  # intacta


@pytest.mark.asyncio
async def test_other_users_card_is_ignored(db_session):
    owner = await _seed_user(db_session)
    attacker = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=owner, lemma="Tür", next_review_at=None)
    out = await apply_pronunciation_reviews(
        db_session, user_id=attacker,
        reviews=[_review(cid, "Tür", "Die Tür.", {2: "bad"})],
    )
    assert out == []


@pytest.mark.asyncio
async def test_focus_band_fallback_to_worst_when_focus_absent(db_session):
    uid = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=uid, lemma="Zug", next_review_at=None)
    # Foco "Zug" no aparece en la frase -> fallback peor banda (bad) -> Again.
    out = await apply_pronunciation_reviews(
        db_session, user_id=uid,
        reviews=[_review(cid, "Zug", "Das Auto faehrt.", {0: "good", 2: "bad", 4: "ok"})],
    )
    assert out[0].interval_days == 0.0069


@pytest.mark.asyncio
async def test_duplicate_card_ids_applied_once(db_session):
    uid = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=uid, lemma="Wort", next_review_at=None)
    out = await apply_pronunciation_reviews(
        db_session, user_id=uid,
        reviews=[
            _review(cid, "Wort", "Ein Wort.", {2: "good"}),
            _review(cid, "Wort", "Ein Wort.", {2: "bad"}),
        ],
    )
    assert len(out) == 1  # dedup intra-batch
    reviews = (await db_session.execute(select(Review).where(Review.user_card_id == cid))).scalars().all()
    assert len(reviews) == 1


@pytest.mark.asyncio
async def test_band_to_rating_never_easy(db_session):
    uid = await _seed_user(db_session)
    cid = await _seed_card(db_session, user_id=uid, lemma="gut", next_review_at=None)
    out = await apply_pronunciation_reviews(
        db_session, user_id=uid,
        reviews=[_review(cid, "gut", "Sehr gut.", {2: "good"})],
    )
    assert out[0].interval_days == 1.0  # good -> Good (+1 day), nunca Easy
    review = (await db_session.execute(select(Review).where(Review.user_card_id == cid))).scalar_one()
    assert review.rating == ReviewRating.GOOD
```

- [ ] **Step 2: Correr para verificar que fallan**

Run: `cd backend && uv run pytest tests/test_practice_session.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.services.practice_session'`.

- [ ] **Step 3: Implementar `practice_session.py`**

```python
# backend/src/klara/services/practice_session.py
"""Cierre del ciclo SRS por pronunciación — canal de MANTENIMIENTO.

Recibe el resultado de una sesión de Practice (por línea: la UserCard que la
respalda, la palabra-foco, la frase dicha y las bandas por token). Por cada
carta DUE del usuario, deriva la banda de la palabra-foco, la mapea a un rating
(conservador, nunca Easy) y la reprograma con el scheduler de mantenimiento
(escalera corta, sin promover). Una transacción atómica. Dedup por card_id.

NO modifica srs_engine.schedule_next_review (canal de recall, futuro). NO acepta
target_language del cliente: la carta se resuelve por id + ownership.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from klara.models import Review, UserCard
from klara.models.enums import ReviewRating
from klara.schemas.srs import PronunciationReviewIn, RescheduledCardOut
from klara.services.srs_engine import schedule_pronunciation_maintenance
from klara.services.tokens import word_tokens_by_index, worst_band

# Mapeo conservador banda->rating. NUNCA Easy: la promoción es del canal de
# recall, no de la articulación. Distinto de BAND_RANK (eso ordena bandas).
_BAND_TO_RATING: dict[str, ReviewRating] = {
    "bad": ReviewRating.AGAIN,
    "ok": ReviewRating.HARD,
    "good": ReviewRating.GOOD,
}


def _focus_band(sentence_target: str, focus_text: str, word_bands: dict[int, str]) -> str | None:
    """Banda de la palabra-foco; fallback a la peor banda de la frase (spec D3).

    Re-tokeniza con el tokenizador canónico (mismos índices que el frontend) y
    busca el token == focus_text. Si esa palabra no tiene banda (Azure la omitió,
    o el foco no está en la frase), cae a la peor banda — lo más conservador.
    """
    target = focus_text.casefold()
    for idx, word in word_tokens_by_index(sentence_target).items():
        if word.casefold() == target:
            band = word_bands.get(idx)
            if band is not None:
                return band
            break
    return worst_band(word_bands)


def _is_due(next_review_at: datetime | None, now: datetime) -> bool:
    """Mismo predicado que routers/srs.due_cards: NULL o <= now."""
    if next_review_at is None:
        return True
    if next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=UTC)
    return next_review_at <= now


async def apply_pronunciation_reviews(
    db: AsyncSession,
    *,
    user_id: UUID,
    reviews: list[PronunciationReviewIn],
) -> list[RescheduledCardOut]:
    now = datetime.now(UTC)
    seen: set[UUID] = set()
    out: list[RescheduledCardOut] = []

    for r in reviews:
        if r.card_id in seen:  # dedup intra-request (idempotencia sin lock)
            continue
        seen.add(r.card_id)

        card = await db.get(UserCard, r.card_id)
        # Invariante de seguridad: la carta resuelta por un id del cliente DEBE
        # pertenecer al usuario. Es la única barrera de aislamiento (spec §4.3).
        if card is None or card.user_id != user_id:
            continue
        if not _is_due(card.next_review_at, now):
            continue

        band = _focus_band(r.sentence_target, r.focus_text, r.word_bands)
        if band is None:
            continue

        prev_interval = card.interval_days
        interval, next_at = schedule_pronunciation_maintenance(card, band)
        card.interval_days = interval
        card.next_review_at = next_at
        card.last_reviewed_at = now
        db.add(
            Review(
                user_card_id=card.id,
                user_id=user_id,
                rating=_BAND_TO_RATING[band],
                prev_interval_days=prev_interval,
                new_interval_days=interval,
            )
        )
        out.append(
            RescheduledCardOut(
                focus_text=r.focus_text, interval_days=interval, next_review_at=next_at
            )
        )

    await db.commit()
    return out
```

- [ ] **Step 4: Correr para verificar verde**

Run: `cd backend && uv run pytest tests/test_practice_session.py -v`
Expected: PASS (8 casos: 2 de Task 4 + 6 nuevos).

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/services/practice_session.py backend/tests/test_practice_session.py
git commit -m "feat(srs): pronunciation maintenance close-the-loop service"
```

---

### Task 6: Endpoint `POST /srs/cards/review-batch`

**Files:**
- Modify: `backend/src/klara/routers/srs.py`
- Test: `backend/tests/test_practice_session.py` (ampliar con un test de integración)

- [ ] **Step 1: Escribir el test de integración que falla (añadir a `test_practice_session.py`)**

```python
async def _register_and_login(client, seed_invite) -> str:
    token = await seed_invite(email=None)
    await client.post(
        "/api/v1/auth/register",
        json={"email": "loop@example.com", "password": "hunter2hunter2", "invite_token": token},
    )
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "loop@example.com", "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return r.headers["set-cookie"].split(";")[0]


@pytest.mark.asyncio
async def test_review_batch_endpoint_reschedules(client, seed_invite, db_session):
    cookie = await _register_and_login(client, seed_invite)
    uid = (await db_session.execute(select(User).where(User.email == "loop@example.com"))).scalar_one().id
    cid = await _seed_card(db_session, user_id=uid, lemma="Brot", next_review_at=None)
    r = await client.post(
        "/api/v1/srs/cards/review-batch",
        headers={"Cookie": cookie},
        json={"reviews": [{
            "cardId": str(cid), "focusText": "Brot",
            "sentenceTarget": "Ich esse Brot.", "wordBands": {"4": "good"},
        }]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rescheduled"]) == 1
    assert body["rescheduled"][0]["focusText"] == "Brot"
    assert body["rescheduled"][0]["intervalDays"] == 1.0
    assert "nextReviewAt" in body["rescheduled"][0]


@pytest.mark.asyncio
async def test_review_batch_requires_auth(client):
    r = await client.post("/api/v1/srs/cards/review-batch", json={"reviews": []})
    assert r.status_code == 401
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_practice_session.py -k review_batch -v`
Expected: FAIL — 404 (ruta inexistente) en el primer test.

- [ ] **Step 3: Implementar el endpoint** (en `routers/srs.py`)

Añade los imports al bloque existente:

```python
from klara.schemas.srs import (
    CardCreateRequest,
    CardOut,
    PronunciationBatchIn,
    PronunciationBatchOut,
    ReviewOut,
    ReviewSubmitRequest,
)
from klara.services.practice_session import apply_pronunciation_reviews
```

Añade el endpoint (al final del router, tras `submit_review`):

```python
@router.post(
    "/cards/review-batch",
    response_model=PronunciationBatchOut,
    response_model_by_alias=True,
)
async def review_batch(
    payload: PronunciationBatchIn,
    db: DBSession,
    user: CurrentUser,
) -> PronunciationBatchOut:
    """Cierra el ciclo SRS desde una sesión de Practice: reprograma (mantenimiento)
    cada carta DUE del usuario respaldando una línea pronunciada. Atómico, idempotente
    por card_id. Las cartas no-due y las que no son del usuario se ignoran en silencio."""
    rescheduled = await apply_pronunciation_reviews(
        db, user_id=user.id, reviews=payload.reviews
    )
    return PronunciationBatchOut(rescheduled=rescheduled)
```

- [ ] **Step 4: Correr para verificar verde (todo el archivo)**

Run: `cd backend && uv run pytest tests/test_practice_session.py -v`
Expected: PASS (10 casos).

- [ ] **Step 5: Suite completa + lint + commit**

```bash
cd backend && uv run pytest tests/ -v && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/routers/srs.py backend/tests/test_practice_session.py
git commit -m "feat(srs): POST /srs/cards/review-batch close-the-loop endpoint"
```

---

## PARTE B — Frontend

> Sin runner de unit tests (ver Tech Stack). Cada task verifica con `npm run typecheck`
> (+ `i18n:check`/`build` donde aplique) y un chequeo manual descrito.

### Task 7: Unificar el tokenizador del frontend con el backend

**Files:**
- Modify: `frontend/src/lib/pronunciation.ts`, `frontend/src/lib/useSentencePractice.ts`

- [ ] **Step 1: Centralizar el regex canónico en `pronunciation.ts`**

Reemplaza el cuerpo de `wordTokenIndices` (líneas ~27-37) y añade helpers, dejando UNA fuente
del patrón. La clase de puntuación debe ser **byte-idéntica** a `backend/src/klara/services/tokens.py`
`_PUNCT` (incluye las comillas tipográficas `„""` U+201E/U+201C/U+201D, hoy ausentes — spec §6.2):

> NOTA: `ScoreBand` YA está declarado/exportado en `pronunciation.ts` (línea 4). NO añadas un
> import de `ScoreBand` — úsalo como tipo local. Los helpers nuevos van en el mismo archivo.

```ts
// Clase de puntuación canónica del repo. DEBE coincidir byte a byte con
// backend services/tokens.py `_PUNCT`, o los índices de word_bands se desalinean
// entre cliente y servidor. Codepoints: . , ! ? ; : „(U+201E) "(U+201C) "(U+201D)
// »(U+00BB) «(U+00AB) ( ) ¡(U+00A1) ¿(U+00BF) —(U+2014) –(U+2013) -.
const WORD_PUNCT = ".,!?;:„“”»«()¡¿—–\\-";
const WORD_RE_SRC = `(\\s+)|([${WORD_PUNCT}]+)|([^\\s${WORD_PUNCT}]+)`;

export function wordTokenIndices(text: string): number[] {
  const re = new RegExp(WORD_RE_SRC, "g");
  const out: number[] = [];
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[3]) out.push(i);
    i++;
  }
  return out;
}

/** {índice_global_de_token: palabra} — espeja backend word_tokens_by_index. */
export function wordTokensByIndex(text: string): Record<number, string> {
  const re = new RegExp(WORD_RE_SRC, "g");
  const out: Record<number, string> = {};
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[3]) out[i] = m[3];
    i++;
  }
  return out;
}

const BAND_RANK: Record<ScoreBand, number> = { bad: 0, ok: 1, good: 2 };

/** La peor banda presente, o null. Espeja backend worst_band. */
export function worstBand(bands: Record<number, ScoreBand>): ScoreBand | null {
  const vals = Object.values(bands);
  if (vals.length === 0) return null;
  return vals.reduce((w, b) => (BAND_RANK[b] < BAND_RANK[w] ? b : w));
}

/** Banda de la palabra-foco con fallback a la peor banda de la frase (spec D3). */
export function focusBand(
  text: string,
  focusText: string,
  bands: Record<number, ScoreBand>,
): ScoreBand | null {
  const target = focusText.toLowerCase();
  const tokens = wordTokensByIndex(text);
  for (const [idx, word] of Object.entries(tokens)) {
    if (word.toLowerCase() === target) {
      const b = bands[Number(idx)];
      if (b) return b;
      break;
    }
  }
  return worstBand(bands);
}
```

(Si `ScoreBand` ya está declarado arriba en el mismo archivo, no lo re-importes — usa el tipo local.)

- [ ] **Step 2: Unificar el regex de `useSentencePractice.ts`**

En `useSentencePractice.ts`, el `WORD_RE` local (línea ~61) tiene la MISMA divergencia. NO lo
importes de `pronunciation.ts` (el `WORD_RE_SRC` de allá es privado, y este `WORD_RE` se usa como
regex con estado — `lastIndex` en las líneas 67 y 82). En su lugar, **edita en sitio** la clase de
puntuación de la línea 61 a las comillas canónicas `„“”»«` (byte-idéntica a `WORD_PUNCT` de
`pronunciation.ts`), conservando `const WORD_RE = /.../g`. `badWordsFromBands` y `simulatedBands`
siguen igual.

- [ ] **Step 3: Verificar (typecheck + manual)**

Run: `cd frontend && npm run typecheck`
Expected: 0 errores.
Manual: en una frase con comillas tipográficas (p.ej. `„Tür" sagt sie.`), `wordTokensByIndex`
devuelve `Tür` sin las comillas y el mismo índice que el backend (comparar contra
`tests/test_tokens.py::test_word_indices_are_global_token_positions`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/pronunciation.ts frontend/src/lib/useSentencePractice.ts
git commit -m "fix(pron): unify frontend tokenizer with backend (curly quotes)"
```

---

### Task 8: Flag de bandas simuladas en el hook

**Files:**
- Modify: `frontend/src/lib/useSentencePractice.ts`

- [ ] **Step 1: Añadir estado `simulatedIndices`**

Junto a los `useState` del hook (tras `scoresBySentence`, ~línea 179):

```tsx
  // Índices (queue position) cuyas bandas son SIMULADAS (Math.random, fallback de
  // 503 de Azure). Se EXCLUYEN del cierre de ciclo SRS — jamás reprograman cartas
  // reales con ruido (spec §6.1).
  const [simulatedIndices, setSimulatedIndices] = useState<Set<number>>(new Set());
```

- [ ] **Step 2: Poblarlo en el catch de `service_unavailable`**

En `stopRecording`, dentro del `catch` donde hoy mete `simulatedBands` (~líneas 322-327):

```tsx
      if (perr.kind === "service_unavailable") {
        const sentence = sentences[idxAtStart];
        if (sentence) {
          setScoresBySentence((s) => ({ ...s, [idxAtStart]: simulatedBands(sentence.target) }));
          setSimulatedIndices((s) => new Set(s).add(idxAtStart));
        }
        setPronError(null);
      } else {
```

- [ ] **Step 3: Limpiarlo en `clearFeedback` y `reset`**

En `clearFeedback` (~líneas 230-243), añade tras limpiar los otros mapas:

```tsx
    setSimulatedIndices((s) => {
      if (!s.has(currentIndex)) return s;
      const next = new Set(s);
      next.delete(currentIndex);
      return next;
    });
```

En `reset` (~líneas 382-390), añade:

```tsx
    setSimulatedIndices(new Set());
```

- [ ] **Step 4: Exponerlo en la interfaz y el return**

En `interface UseSentencePractice` (tras `scoresBySentence`, ~línea 164):

```tsx
  /** Índices cuyas bandas son simuladas (503) — excluir del cierre SRS. */
  simulatedIndices: Set<number>;
```

En el `return {...}` final, añade `simulatedIndices,`.

- [ ] **Step 5: Verificar (typecheck + manual)**

Run: `cd frontend && npm run typecheck`
Expected: 0 errores.
Manual: con el backend de pronunciación devolviendo 503 (sin clave Azure), grabar una línea →
sus bandas se pintan (simuladas) pero el índice queda en `simulatedIndices`; tras "reintentar"
(`clearFeedback`) el índice sale del Set.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/useSentencePractice.ts
git commit -m "feat(practice): track simulated-band indices to exclude from SRS"
```

---

### Task 9: `cardId` en el tipo `PracticeItem`

**Files:**
- Modify: `frontend/src/lib/practiceQueue.ts`

- [ ] **Step 1: Añadir el campo y corregir el docstring obsoleto**

En `interface PracticeItem` (tras `sentenceIndex?`, ~línea 63):

```ts
  /**
   * Id de la UserCard SRS que respalda este item, cuando la hay (review items, y
   * struggled cuyo focus es una carta due). Ausente para struggled sin vocab en
   * SRS. El cierre del ciclo reprograma POR este id (no por texto).
   */
  cardId?: string;
```

Y corrige el docstring de cabecera (líneas ~13-17): borra "Scope today: the endpoint is
STRUGGLED-ONLY..." (falso desde PR #56) — reemplázalo por: "El endpoint sirve struggled + review;
los items respaldados por una carta SRS due portan `cardId`."

- [ ] **Step 2: Verificar + commit**

Run: `cd frontend && npm run typecheck`
Expected: 0 errores.

```bash
git add frontend/src/lib/practiceQueue.ts
git commit -m "feat(practice): add cardId to PracticeItem type"
```

---

### Task 10: Tipos + método de cliente API

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`

- [ ] **Step 1: Añadir los tipos** (en `api/types.ts`, junto a los demás)

```ts
export interface PronunciationReviewIn {
  cardId: string;
  focusText: string;
  sentenceTarget: string;
  wordBands: Record<number, "bad" | "ok" | "good">;
}

export interface RescheduledCard {
  focusText: string;
  intervalDays: number;
  nextReviewAt: string; // ISO 8601
}

export interface PronunciationBatchOut {
  rescheduled: RescheduledCard[];
}
```

- [ ] **Step 2: Añadir el método de cliente** (en `api/client.ts`)

En el bloque de imports de `./types`, añade `PronunciationBatchOut, PronunciationReviewIn`. Tras
`reviewCard` (~línea 195) añade:

```ts
  submitPronunciationReviews: (reviews: PronunciationReviewIn[]) =>
    request<PronunciationBatchOut>("/srs/cards/review-batch", {
      method: "POST",
      body: JSON.stringify({ reviews }),
    }),
```

- [ ] **Step 3: Verificar + commit**

Run: `cd frontend && npm run typecheck`
Expected: 0 errores.

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat(api): add submitPronunciationReviews client method"
```

---

### Task 11: Humanizador de tiempo (`srsTime.ts`)

**Files:**
- Create: `frontend/src/lib/srsTime.ts`

- [ ] **Step 1: Crear el humanizador (reusa las claves SRS existentes)**

```ts
// frontend/src/lib/srsTime.ts
import i18n from "../i18n";

/**
 * Etiqueta localizada de "cuándo vuelve esta palabra". Reusa las MISMAS claves y
 * umbrales de la sección Schedule del Finish de historias (story.finish.summary
 * .schedule.*), que ya están espejadas en los 6 locales — sin claves nuevas. Los
 * umbrales (en días) replican backend routers/stories.py `_bucket_for`.
 */
export function humanizeNextReview(nextReviewAt: string): string {
  const delta = (new Date(nextReviewAt).getTime() - Date.now()) / 86_400_000; // días
  const k = (s: string): string => i18n.t(`story.finish.summary.schedule.${s}`);
  if (delta <= 1) return k("dueNow");
  if (delta <= 3) return k("soon");
  if (delta <= 7) return k("thisWeek");
  if (delta <= 14) return k("nextWeek");
  return k("later");
}
```

- [ ] **Step 2: Verificar + commit**

Run: `cd frontend && npm run typecheck`
Expected: 0 errores.
Manual: `humanizeNextReview(new Date(Date.now()+2*86400000).toISOString())` → "En unos días"
(es). (Las claves `dueNow/soon/thisWeek/nextWeek/later` ya existen — confirmado en
`es/common.json:242-246`.)

```bash
git add frontend/src/lib/srsTime.ts
git commit -m "feat(practice): humanize next-review using shared SRS schedule keys"
```

---

### Task 12: Wiring del summary en `Practice.tsx`

**Files:**
- Modify: `frontend/src/routes/Practice.tsx`

- [ ] **Step 1: Imports y estado nuevo**

Añade a los imports:

```tsx
import { api } from "../api/client";
import type { PronunciationReviewIn, RescheduledCard } from "../api/types";
import { focusBand } from "../lib/pronunciation";
import { humanizeNextReview } from "../lib/srsTime";
import { useRef } from "react";
```

Dentro del componente, junto a los `useState`:

```tsx
  type SendState = "idle" | "sending" | "ok" | "failed";
  const [sendState, setSendState] = useState<SendState>("idle");
  const [rescheduled, setRescheduled] = useState<RescheduledCard[]>([]);
  // Se marca al CONFIRMAR éxito (no al disparar): un fallo deja reintentar en vez
  // de perder la reprogramación en silencio (spec §4.4).
  const sessionSubmittedRef = useRef(false);
```

- [ ] **Step 2: Reescribir `tallySummary` para contar por palabra-foco**

Reemplaza la función `tallySummary` (líneas ~52-73) por (stats por la banda de la palabra-foco,
mismo sujeto que el rating SRS — spec §2/§4.4):

```tsx
function tallySummary(
  items: PracticeItem[],
  sentences: StorySentence[],
  scoresBySentence: Record<number, PronScores>,
): { clear: number; mid: number; revisit: number; answered: number } {
  let clear = 0;
  let mid = 0;
  let revisit = 0;
  let answered = 0;
  for (let i = 0; i < items.length; i++) {
    const scores = scoresBySentence[i];
    if (!scores || Object.keys(scores).length === 0) continue;
    const band = focusBand(sentences[i].target, items[i].focusText, scores);
    if (!band) continue;
    answered++;
    if (band === "good") clear++;
    else if (band === "ok") mid++;
    else revisit++;
  }
  return { clear, mid, revisit, answered };
}
```

- [ ] **Step 3: Función de envío + efecto de disparo único**

Añade dentro del componente (tras la definición de `practice`):

```tsx
  const submitSession = useCallback(() => {
    const reviews: PronunciationReviewIn[] = [];
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const scores = practice.scoresBySentence[i];
      if (!it.cardId || !scores || practice.simulatedIndices.has(i)) continue;
      reviews.push({
        cardId: it.cardId,
        focusText: it.focusText,
        sentenceTarget: sentences[i].target,
        wordBands: scores,
      });
    }
    if (reviews.length === 0) {
      sessionSubmittedRef.current = true;
      setRescheduled([]);
      setSendState("ok");
      return;
    }
    setSendState("sending");
    api
      .submitPronunciationReviews(reviews)
      .then((res) => {
        sessionSubmittedRef.current = true; // marca al confirmar
        setRescheduled(res.rescheduled);
        setSendState("ok");
      })
      .catch(() => {
        setSendState("failed"); // ref NO marcado -> reintentable
      });
  }, [items, sentences, practice.scoresBySentence, practice.simulatedIndices]);

  useEffect(() => {
    if (phase === "summary" && !sessionSubmittedRef.current && sendState === "idle") {
      submitSession();
    }
  }, [phase, sendState, submitSession]);
```

Necesitas `useCallback` en los imports de React (ya hay `useEffect, useMemo, useState`; añade
`useCallback`).

- [ ] **Step 4: Limpiar el guard al reiniciar ("otra ronda")**

En los dos `onClick` que llaman `practice.reset()` + `setPhase(...)` (el del summary "again"
~línea 305 y donde aplique), añade antes:

```tsx
              sessionSubmittedRef.current = false;
              setSendState("idle");
              setRescheduled([]);
```

- [ ] **Step 5: Reescribir la sección "returns" del summary**

Localiza el bloque SUMMARY (líneas ~243-318). Reemplaza el cálculo viejo
`const returns = items.filter((i) => i.reason === "struggled").slice(0, 3);` y la llamada
`tallySummary(total, practice.scoresBySentence)` por:

```tsx
    const { clear, mid, revisit } = tallySummary(items, sentences, practice.scoresBySentence);
    // Glosa local por palabra-foco (reusa focusTx del item; el contrato del backend
    // NO devuelve traducción — spec §4.3 "contrato mínimo").
    const txByFocus: Record<string, string> = {};
    for (const it of items) txByFocus[it.focusText] = it.focusTx;
```

Y reemplaza el `<hr>` + `<section className="kp-returns">...</section>` (líneas ~278-300) por
(gatillado solo cuando hay reprogramaciones reales — oculta sección Y hairline juntos, spec §4.4):

```tsx
        {sendState === "ok" && rescheduled.length > 0 && (
          <>
            <hr className="k-hairline" />
            <section className="kp-returns">
              <header className="kp-returns__head">
                <span className="k-mono">{t("practice.summary.returns.title")}</span>
                <span className="k-mono kp-returns__count">{rescheduled.length}</span>
              </header>
              <ul className="kp-returns__list">
                {rescheduled.map((r) => (
                  <li key={`${r.focusText}-${r.nextReviewAt}`} className="kp-returns__item">
                    <span className="kp-returns__word">{r.focusText}</span>
                    <span className="kp-returns__tx">{txByFocus[r.focusText] ?? ""}</span>
                    <span className="kp-returns__next k-mono">
                      {humanizeNextReview(r.nextReviewAt)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
```

(Cuando `rescheduled` está vacío o el POST falló, no se renderiza ni el `<hr>` ni la sección —
sin "VUELVEN PRONTO — 0" ni separador colgando.)

- [ ] **Step 6: Verificar (typecheck + build + manual)**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: 0 errores; build OK.
Manual (con backend corriendo): hacer una sesión de Practice con al menos una carta due →
al llegar al summary, la sección "VUELVEN PRONTO" lista las palabras con su intervalo REAL. OJO
con la expectativa: el humanizador replica `_bucket_for` con `delta <= 1 → dueNow`, así que una
palabra dicha "good" (intervalo 1.0 día) muestra **"Para hoy"** (dueNow), no "en unos días" — eso
último solo aparece para intervalos en (1, 3]. Recargar el summary NO duplica la reprogramación
(verificar en DB que
`reviews` tiene una sola fila por carta). Forzar un fallo de red en el POST → la sección se oculta
(no intervalos inventados).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routes/Practice.tsx
git commit -m "feat(practice): close SRS loop on summary with real intervals"
```

---

### Task 13: Limpieza i18n (claves posicionales obsoletas)

**Files:**
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`

- [ ] **Step 1: Borrar las 3 claves obsoletas en los 6 locales**

En cada `common.json`, dentro de `practice.summary.returns`, borra las claves `tomorrow`,
`inTwoDays` y `thisWeek` (estaban atadas a posición `i===0/1/2`, ya sin uso). **Conserva**
`returns.title`. Hazlo en los 6: `es, en, de, fr, ja, pt` (el check exige paridad exacta).

- [ ] **Step 2: Verificar paridad de locales**

Run: `cd frontend && npm run i18n:check`
Expected: PASS (sin claves sobrantes/faltantes; las 3 borradas en los 6 a la vez mantienen
paridad). Si reporta una clave faltante en algún locale, borraste de más/de menos en uno.

- [ ] **Step 3: Build final + commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run build`
Expected: todo verde.

```bash
git add frontend/src/locales
git commit -m "chore(i18n): drop obsolete positional returns keys"
```

---

## Self-Review (hecho — registro de cobertura)

- **Spec §2 framing (mantiene/promueve):** Task 2 (scheduler sin promoción) + Task 12 Step 2 (stats por palabra-foco). El copy "memoria→voz" del dek se deja a un pase de microcopy (no bloquea; nota abajo).
- **Spec §4.1 cardId:** Task 3 (schema + cola) + Task 9 (tipo FE).
- **Spec §4.2 maintenance scheduler:** Task 2.
- **Spec §4.3 endpoint batch + validation_alias + target_language server-side:** Tasks 4, 5, 6.
- **Spec §4.4 frontend (disparo único, máquina de estados, oculta vacío/fallo, stats por foco):** Task 12.
- **Spec §6 precondiciones:** Task 1 + Task 7 (tokenizador), Task 8 (flag simulado), Task 5 (persistencia explícita de los 4 campos), Task 4 (validation_alias).
- **Spec §7 deferrals:** struggled-signal NO se toca (correcto); recall futuro; fix `language="de"` aparte. Documentados, sin tarea.
- **Spec §9 testing:** backend cubierto con pytest (Tasks 1-6). Frontend: typecheck/build/i18n:check + manual (sin runner — desviación declarada en Tech Stack).
- **Nota de microcopy (no bloqueante):** los strings del dek/título del summary que hoy dicen "lo que Klara guarda y cuándo vuelve" deberían revisarse para no afirmar "memoria" (framing §2). Es un cambio de copy en `practice.summary.dek` (6 locales) — candidato a un pase con la skill de microcopy tras la implementación, fuera de este plan funcional.
