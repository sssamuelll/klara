# Learning Sequence — Slice 1 (Lexical Axis, German) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar el lazo evidencia→competencia→generación en el eje léxico para alemán: la historia se construye alrededor de palabras objetivo elegidas por frecuencia − lo-que-ya-sabes, no improvisadas por el LLM, con cobertura validada y el "por qué" visible.

**Architecture:** Un módulo nuevo `klara/curriculum/` con piezas de una sola responsabilidad: registro de ejes, lematizador, interfaz de competencia (sobre `UserCard`, sin tabla nueva), regla de selección, validación de cobertura, carga del inventario de frecuencia. La selección se inyecta en `generate_story` donde hoy va `recent_vocab`; el LLM redacta, no cura. `frequency_rank` (hoy dormido, ya indexado) se puebla desde una lista curada externa vía script idempotente.

**Tech Stack:** FastAPI + SQLAlchemy async + Pydantic v2 + pytest (`uv run pytest`, requiere Postgres de test). Nueva dependencia: `simplemma` (lematizador ligero, MIT, soporta alemán). Frontend: React + TS (typecheck/build/i18n:check; sin runner de unit tests).

**Spec:** `docs/superpowers/specs/2026-06-15-learning-sequence-slice1-design.md`

**Decisiones de plan fijadas:** módulo `klara/curriculum/`. Scripts en `klara/scripts/` (convención nueva, no existía). El re-etiquetado agresivo de `language="de"` mal puesto se **difiere** (forense de datos costoso); en su lugar, competencia y cobertura **canonicalizan al leer**, así el matching cuenta familias aunque el lema almacenado esté sucio, y la carga **sobrescribe** el `cefr_level` inferido por LLM. La lista de frecuencia real (Kelly/SUBTLEX-DE) se adquiere aparte por licencia; los tests usan un fixture pequeño embebido. **Aislamiento de tests:** `vocab_items` NO se trunca entre tests (es tabla padre, no cae por CASCADE — ver `test_practice_queue.py:129`) y `next_target_words` consulta el pool global por idioma; los tests que tocan ese pool usan un **código de idioma único por test** (p.ej. `selt1`, `invt1`) para no filtrarse entre sí. **Desviación de §9 (declarada):** el spec decía "reusar el campo insight"; el modelo real no tiene un campo `insight` único (tiene `insight_title`/`insight_body`, prosa lingüística LLM-generada de otro propósito), así que se introduce un campo **nuevo** `curriculum_note` en `StoryOut` (computado, sin columna) + `frequency_rank` por palabra — en vez de sobrecargar `insight`.

**Verificación:** Backend `cd backend && uv run pytest tests/ -v` · `uv run ruff check src tests` · `uv run ruff format --check src tests`. Frontend `cd frontend && npm run typecheck && npm run i18n:check && npm run build`.

---

## File Structure

**Backend (crear):**
- `src/klara/curriculum/__init__.py`
- `src/klara/curriculum/axes.py` — `LANGUAGE_AXES` (registro de ejes por idioma).
- `src/klara/curriculum/lemmatize.py` — `canonical_lemma(word, language)`.
- `src/klara/curriculum/competence.py` — `known_set(db, user_id, language)`.
- `src/klara/curriculum/selection.py` — `next_target_words(db, ...)`, `CONTENT_POS`, `CEFR_ORDER`.
- `src/klara/curriculum/coverage.py` — `verify_coverage(content, lemmas, language)`.
- `src/klara/curriculum/inventory.py` — `FrequencyRow`, `parse_frequency_tsv`, `load_frequency`.
- `src/klara/scripts/__init__.py`, `src/klara/scripts/load_de_lexical.py` — CLI wrapper.
- Tests: `tests/test_curriculum_lemmatize.py`, `tests/test_curriculum_competence.py`, `tests/test_curriculum_selection.py`, `tests/test_curriculum_coverage.py`, `tests/test_curriculum_inventory.py`, additions to `tests/test_stories.py` (or new `tests/test_story_curriculum.py`).

**Backend (modificar):**
- `pyproject.toml` — añadir `simplemma`.
- `src/klara/llm/prompts.py` — `STORY_USER_PROMPT` gana línea de palabras objetivo.
- `src/klara/services/story_gen.py` — `generate_story` gana `target_lemmas` + corre cobertura.
- `src/klara/routers/stories.py` — `create_story` computa selección y la pasa; `_serialize_story` expone `frequency_rank` + `curriculum_note`.
- `src/klara/schemas/story.py` — `StoryWordOut.frequency_rank`, `StoryOut.curriculum_note`.

**Frontend (modificar):**
- `src/api/types.ts` — `StoryWord.frequency_rank`.
- `src/components/WordPopover.tsx` — línea callada de rango.
- `src/locales/{es,en,de,fr,ja,pt}/common.json` — clave `wpop.freq`.

---

## Task 1: Dependencia + lematizador (`curriculum/lemmatize.py`)

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/src/klara/curriculum/__init__.py`, `backend/src/klara/curriculum/lemmatize.py`
- Test: `backend/tests/test_curriculum_lemmatize.py`

- [ ] **Step 1: Añadir `simplemma` a dependencias**

En `backend/pyproject.toml`, dentro de `[project].dependencies` (tras la última línea, `azure-cognitiveservices-speech>=1.40`), añade:
```toml
    "simplemma>=1.1",
```
Luego sincroniza: `cd backend && uv sync`

- [ ] **Step 2: Escribir el test que falla**

```python
# backend/tests/test_curriculum_lemmatize.py
"""El lematizador mapea flexiones alemanas a un lema canónico (minúsculas),
para que cobertura y known-set cuenten familias y no flexiones."""

import pytest

from klara.curriculum.lemmatize import canonical_lemma


@pytest.mark.parametrize(
    "surface,expected",
    [
        ("läuft", "laufen"),
        ("gelaufen", "laufen"),
        ("Häuser", "haus"),
        ("Tische", "tisch"),
        ("Haus", "haus"),
    ],
)
def test_german_inflections_map_to_lemma(surface, expected):
    assert canonical_lemma(surface, "de") == expected


def test_blank_and_unknown_are_safe():
    assert canonical_lemma("", "de") == ""
    # idioma no soportado → identidad en minúsculas, sin crash
    assert canonical_lemma("Casa", "xx") == "casa"
```

- [ ] **Step 3: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_curriculum_lemmatize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum'`.

- [ ] **Step 4: Implementar**

Crea `backend/src/klara/curriculum/__init__.py` vacío. Crea `backend/src/klara/curriculum/lemmatize.py`:
```python
"""Lematizador canónico por idioma sobre simplemma.

Mapea una forma de superficie a su lema canónico EN MINÚSCULAS, para que el
conteo de cobertura y el known-set agrupen flexiones bajo una familia. Para un
idioma que simplemma no soporta, degrada a la identidad en minúsculas (nunca
crashea): la secuencia de ese idioma sigue genérica (deuda visible, spec §10).
"""

from __future__ import annotations

import simplemma


def canonical_lemma(word: str, language: str) -> str:
    # NO bajar a minúsculas ANTES de lematizar: simplemma usa la mayúscula inicial
    # del sustantivo alemán como señal de su categoría (Tische→tisch, Haus→haus).
    # Forzar minúsculas primero lo trata como verbo y sobre-lematiza
    # (Tische→tischen, Haus→hausen). Lematiza sobre la forma original; baja DESPUÉS.
    w = word.strip()
    if not w:
        return ""
    try:
        return simplemma.lemmatize(w, lang=language).lower()
    except (ValueError, KeyError):
        # idioma no soportado por simplemma → identidad en minúsculas
        return w.lower()
```

- [ ] **Step 5: Correr para verificar verde**

Run: `cd backend && uv run pytest tests/test_curriculum_lemmatize.py -v`
Expected: PASS (6 casos) — verificado contra simplemma 1.2.0 con el orden corregido (lematizar la forma original, bajar a minúsculas después). **NO ajustes los `expected` para acomodar un lematizador que baja a minúsculas primero** — eso fijaría un lematizador roto (Tische→tischen) que corrompe known-set, selección, cobertura e inventario. El único ajuste legítimo del `expected` sería por una diferencia genuina de VERSIÓN de simplemma.

- [ ] **Step 6: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/pyproject.toml backend/uv.lock backend/src/klara/curriculum/__init__.py backend/src/klara/curriculum/lemmatize.py backend/tests/test_curriculum_lemmatize.py
git commit -m "feat(curriculum): German lemmatizer over simplemma"
```

---

## Task 2: Registro de ejes (`curriculum/axes.py`)

**Files:**
- Create: `backend/src/klara/curriculum/axes.py`
- Test: `backend/tests/test_curriculum_lemmatize.py` (añadir; o un test propio)

- [ ] **Step 1: Escribir el test que falla** (añadir a `test_curriculum_lemmatize.py` o crear `test_curriculum_axes.py`)

```python
# backend/tests/test_curriculum_axes.py
from klara.curriculum.axes import LANGUAGE_AXES, axes_for


def test_german_declares_grammatical_axes_but_only_lexical_is_active_now():
    # El espacio de competencia del alemán está DECLARADO (compromiso de forma),
    # aunque v1 solo pueble el léxico.
    assert "lexical" in LANGUAGE_AXES["de"]
    assert "gender" in LANGUAGE_AXES["de"]


def test_every_supported_language_has_at_least_lexical():
    for code in ("de", "en", "fr", "ja", "pt", "es"):
        assert axes_for(code)[0] == "lexical"
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_curriculum_axes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum.axes'`.

- [ ] **Step 3: Implementar**

```python
# backend/src/klara/curriculum/axes.py
"""Registro de ejes de competencia por idioma.

Declarar los ejes (no poblarlos todos) es el compromiso del modelo híbrido: el
espacio de competencia de cada idioma queda nombrado, y v1 solo puebla
`lexical`. Los ejes gramaticales/ortográficos existen como forma, no código
muerto; la Rebanada 2 (género) implementa el primero sobre la misma interfaz.
"""

from __future__ import annotations

LANGUAGE_AXES: dict[str, list[str]] = {
    "de": ["lexical", "gender", "case", "word_order"],
    "ja": ["lexical", "orthography", "particles", "pitch"],
    "en": ["lexical"],
    "fr": ["lexical"],
    "pt": ["lexical"],
    "es": ["lexical"],
}


def axes_for(language: str) -> list[str]:
    """Ejes declarados de un idioma; cae a sólo léxico si no está registrado."""
    return LANGUAGE_AXES.get(language, ["lexical"])
```

- [ ] **Step 4: Correr para verificar verde**

Run: `cd backend && uv run pytest tests/test_curriculum_axes.py -v`
Expected: PASS (2 casos).

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/curriculum/axes.py backend/tests/test_curriculum_axes.py
git commit -m "feat(curriculum): declare per-language competence axes"
```

---

## Task 3: Interfaz de competencia (`curriculum/competence.py`)

**Files:**
- Create: `backend/src/klara/curriculum/competence.py`
- Test: `backend/tests/test_curriculum_competence.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/tests/test_curriculum_competence.py
"""known_set deriva los lemas que el usuario ya tiene en SRS (UserCard),
canonicalizados, restringido al idioma. Es el sustraendo de la selección."""

import uuid

import pytest

from klara.curriculum.competence import known_set
from klara.models import User, UserCard, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


async def _user(db) -> uuid.UUID:
    u = User(
        id=uuid.uuid4(), email=f"c-{uuid.uuid4().hex[:6]}@k.app", hashed_password="x",
        is_active=True, is_verified=True, is_superuser=False, display_name="C",
        level=CEFRLevel.A1, native_language="es", target_language="de",
    )
    db.add(u); await db.flush(); return u.id


async def _vocab(db, lemma, language="de") -> uuid.UUID:
    v = VocabItem(id=uuid.uuid4(), language=language, lemma=lemma, pos=PartOfSpeech.NOUN)
    db.add(v); await db.flush(); return v.id


@pytest.mark.asyncio
async def test_known_set_is_canonical_lemmas_with_a_card_in_language(db_session):
    uid = await _user(db_session)
    vid_de = await _vocab(db_session, "Haus", "de")
    vid_en = await _vocab(db_session, "house", "en")
    for vid in (vid_de, vid_en):
        db_session.add(UserCard(id=uuid.uuid4(), user_id=uid, vocab_item_id=vid))
    await db_session.commit()

    ks = await known_set(db_session, user_id=uid, language="de")
    assert "haus" in ks            # canonicalizado (minúsculas)
    assert "house" not in ks       # otro idioma excluido


@pytest.mark.asyncio
async def test_known_set_empty_when_no_cards(db_session):
    uid = await _user(db_session)
    await db_session.commit()
    assert await known_set(db_session, user_id=uid, language="de") == set()
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum.competence'`.

- [ ] **Step 3: Implementar**

```python
# backend/src/klara/curriculum/competence.py
"""Estado de competencia del usuario, eje léxico, sobre lo que YA existe.

No hay tabla nueva: el known-set son los lemas con UserCard del usuario en el
idioma, canonicalizados. Es la implementación léxica de la interfaz de
competencia; la Rebanada 2 (género) añade otra implementación del mismo contrato.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.lemmatize import canonical_lemma
from klara.models import UserCard, VocabItem


async def known_set(db: AsyncSession, *, user_id: UUID, language: str) -> set[str]:
    """Lemas canónicos que el usuario ya tiene en SRS para `language`."""
    stmt = (
        select(VocabItem.lemma)
        .join(UserCard, UserCard.vocab_item_id == VocabItem.id)
        .where(UserCard.user_id == user_id, VocabItem.language == language)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {canonical_lemma(lemma, language) for lemma in rows}
```

- [ ] **Step 4: Correr para verificar verde**

Run: `cd backend && uv run pytest tests/test_curriculum_competence.py -v`
Expected: PASS (2 casos).

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/curriculum/competence.py backend/tests/test_curriculum_competence.py
git commit -m "feat(curriculum): lexical known-set over UserCard"
```

---

## Task 4: Regla de selección (`curriculum/selection.py`)

**Files:**
- Create: `backend/src/klara/curriculum/selection.py`
- Test: `backend/tests/test_curriculum_selection.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/tests/test_curriculum_selection.py
"""next_target_words: top por frequency_rank, palabras de CONTENIDO, banda
<= user.level, MENOS el known-set. Es el cierre del lazo."""

import uuid

import pytest

from klara.curriculum.selection import next_target_words
from klara.models import User, UserCard, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


async def _user(db, level=CEFRLevel.A2) -> uuid.UUID:
    u = User(
        id=uuid.uuid4(), email=f"s-{uuid.uuid4().hex[:6]}@k.app", hashed_password="x",
        is_active=True, is_verified=True, is_superuser=False, display_name="S",
        level=level, native_language="es", target_language="de",
    )
    db.add(u); await db.flush(); return u.id


async def _vocab(db, *, lemma, rank, cefr, language, pos=PartOfSpeech.NOUN) -> uuid.UUID:
    v = VocabItem(
        id=uuid.uuid4(), language=language, lemma=lemma, pos=pos,
        frequency_rank=rank, cefr_level=cefr,
    )
    db.add(v); await db.flush(); return v.id


# AISLAMIENTO: vocab_items NO se trunca entre tests (conftest.py) y next_target_words
# consulta el pool GLOBAL por idioma — usa un código de idioma único por test para
# que lemas de otros tests no se filtren y rompan las aserciones de igualdad exacta.
@pytest.mark.asyncio
async def test_selects_top_frequency_content_words_minus_known(db_session):
    lang = "selt1"
    uid = await _user(db_session, CEFRLevel.A2)
    # función de altísima frecuencia: NO debe seleccionarse (no es contenido)
    await _vocab(db_session, lemma="und", rank=1, cefr=CEFRLevel.A1, language=lang, pos=PartOfSpeech.CONJUNCTION)
    # contenido frecuente, no sabido → debe salir primero
    await _vocab(db_session, lemma="Haus", rank=10, cefr=CEFRLevel.A1, language=lang)
    # contenido más raro → después
    await _vocab(db_session, lemma="Brücke", rank=900, cefr=CEFRLevel.A2, language=lang)
    # fuera de banda (B2 > A2) → excluido
    await _vocab(db_session, lemma="Verfassung", rank=20, cefr=CEFRLevel.B2, language=lang)
    # ya sabido → excluido
    known_vid = await _vocab(db_session, lemma="Tisch", rank=5, cefr=CEFRLevel.A1, language=lang)
    db_session.add(UserCard(id=uuid.uuid4(), user_id=uid, vocab_item_id=known_vid))
    await db_session.commit()

    words = await next_target_words(db_session, user_id=uid, language=lang, level=CEFRLevel.A2, n=5)
    lemmas = [w.lemma for w in words]
    assert lemmas == ["Haus", "Brücke"]   # orden por rank, sin und/Verfassung/Tisch


@pytest.mark.asyncio
async def test_respects_limit_n(db_session):
    lang = "selt2"   # código distinto al otro test → pools aislados
    uid = await _user(db_session, CEFRLevel.B1)
    for i in range(8):
        await _vocab(db_session, lemma=f"Wort{i}", rank=i + 1, cefr=CEFRLevel.A1, language=lang)
    await db_session.commit()
    words = await next_target_words(db_session, user_id=uid, language=lang, level=CEFRLevel.B1, n=3)
    assert len(words) == 3
    assert [w.frequency_rank for w in words] == [1, 2, 3]
```

> Nota: `next_target_words` con un código de idioma no soportado por simplemma usa la identidad en minúsculas para canonicalizar — consistente entre stored y known-set, así que el aislamiento por idioma no afecta la lógica probada.

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_curriculum_selection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum.selection'`.

- [ ] **Step 3: Implementar**

```python
# backend/src/klara/curriculum/selection.py
"""Selección del próximo objetivo léxico = (corpus por frecuencia) − (known-set),
filtrado a palabras de contenido y a la banda del nivel del usuario.

Esto INVIERTE la dirección de control: el LLM recibe estos lemas como objetivo y
redacta la historia alrededor; deja de improvisar la secuencia (spec §6).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.competence import known_set
from klara.curriculum.lemmatize import canonical_lemma
from klara.models import VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech

# Palabras de contenido: el eje léxico drillea sustantivos/verbos/adj/adv. Las
# function words de altísima frecuencia (der/die/das/und/ist) NO entran aquí —
# der/die/das es el eje de GÉNERO (Rebanada 2), no un ítem léxico (spec D4).
CONTENT_POS = (
    PartOfSpeech.NOUN,
    PartOfSpeech.VERB,
    PartOfSpeech.ADJECTIVE,
    PartOfSpeech.ADVERB,
)

# Orden CEFR para la compuerta de banda (cefr_level <= user.level).
CEFR_ORDER: dict[CEFRLevel, int] = {
    CEFRLevel.A0: 0,
    CEFRLevel.A1: 1,
    CEFRLevel.A2: 2,
    CEFRLevel.B1: 3,
    CEFRLevel.B2: 4,
    CEFRLevel.C1: 5,
}


async def next_target_words(
    db: AsyncSession, *, user_id: UUID, language: str, level: CEFRLevel, n: int = 5
) -> list[VocabItem]:
    """Próximos `n` lemas de contenido por frecuencia, en banda, no sabidos."""
    known = await known_set(db, user_id=user_id, language=language)
    ceiling = CEFR_ORDER[level]
    allowed = [lvl for lvl, order in CEFR_ORDER.items() if order <= ceiling]
    stmt = (
        select(VocabItem)
        .where(
            VocabItem.language == language,
            VocabItem.pos.in_(CONTENT_POS),
            VocabItem.cefr_level.in_(allowed),
            VocabItem.frequency_rank.is_not(None),
        )
        .order_by(VocabItem.frequency_rank.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    # El cut por known-set es en memoria (igual que practice_queue): el inventario
    # por usuario está acotado y no se puede restar un set en SQL sin acoplar.
    out: list[VocabItem] = []
    for v in rows:
        if canonical_lemma(v.lemma, language) in known:
            continue
        out.append(v)
        if len(out) >= n:
            break
    return out
```

- [ ] **Step 4: Correr para verificar verde**

Run: `cd backend && uv run pytest tests/test_curriculum_selection.py -v`
Expected: PASS (2 casos).

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/curriculum/selection.py backend/tests/test_curriculum_selection.py
git commit -m "feat(curriculum): next-target-words selection (frequency minus known)"
```

---

## Task 5: Validación de cobertura (`curriculum/coverage.py`)

**Files:**
- Create: `backend/src/klara/curriculum/coverage.py`
- Test: `backend/tests/test_curriculum_coverage.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/tests/test_curriculum_coverage.py
"""verify_coverage devuelve el subconjunto de lemas que SÍ aparecen (lematizados)
en la historia. Lo no cubierto no se afirma enseñar (spec §8)."""

from klara.curriculum.coverage import verify_coverage


def _content(*targets_in_sentences: str) -> dict:
    return {
        "sentences": [
            {"target": s, "native": "", "new_words": [], "breakdown": []}
            for s in targets_in_sentences
        ]
    }


def test_covered_lemmas_match_inflected_forms():
    content = _content("Die Häuser sind groß.", "Er läuft schnell.")
    # objetivos pedidos en forma de lema; aparecen flexionados en el texto
    covered = verify_coverage(content, ["haus", "laufen", "brücke"], "de")
    assert covered == {"haus", "laufen"}   # "brücke" no aparece → no cubierto


def test_empty_targets_returns_empty():
    assert verify_coverage(_content("Hallo."), [], "de") == set()
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_curriculum_coverage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum.coverage'`.

- [ ] **Step 3: Implementar**

```python
# backend/src/klara/curriculum/coverage.py
"""¿La historia generada REALMENTE contiene los lemas objetivo pedidos?

Sin esto el currículo alucina niveles en silencio. Tokeniza con el tokenizador
canónico del repo, lematiza cada token, y devuelve qué lemas objetivo aparecen.
"""

from __future__ import annotations

from klara.curriculum.lemmatize import canonical_lemma
from klara.services.tokens import word_tokens_by_index


def verify_coverage(content: dict, lemmas: list[str], language: str) -> set[str]:
    """Subconjunto de `lemmas` (canónicos) presente en el contenido de la historia."""
    targets = {canonical_lemma(lemma, language) for lemma in lemmas if lemma}
    if not targets:
        return set()
    seen: set[str] = set()
    for sentence in content.get("sentences", []) or []:
        text = sentence.get("target") or ""
        for token in word_tokens_by_index(text).values():
            seen.add(canonical_lemma(token, language))
        for entry in sentence.get("breakdown") or []:
            word = entry.get("word") if isinstance(entry, dict) else None
            if isinstance(word, str):
                seen.add(canonical_lemma(word, language))
    return targets & seen
```

- [ ] **Step 4: Correr para verificar verde**

Run: `cd backend && uv run pytest tests/test_curriculum_coverage.py -v`
Expected: PASS (2 casos).

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/curriculum/coverage.py backend/tests/test_curriculum_coverage.py
git commit -m "feat(curriculum): story coverage validation (lemmatized)"
```

---

## Task 6: Carga del inventario de frecuencia (`curriculum/inventory.py`)

**Files:**
- Create: `backend/src/klara/curriculum/inventory.py`
- Test: `backend/tests/test_curriculum_inventory.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# backend/tests/test_curriculum_inventory.py
"""load_frequency upsertea VocabItem desde una lista curada: puebla frequency_rank
y SOBREESCRIBE cefr_level (el inferido por LLM es ruido). Idempotente."""

import uuid

import pytest
from sqlalchemy import select

from klara.curriculum.inventory import FrequencyRow, load_frequency, parse_frequency_tsv
from klara.models import VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


def test_parse_tsv_rows():
    text = "lemma\tpos\tcefr\trank\nHaus\tnoun\tA1\t10\nlaufen\tverb\tA1\t12\n"
    rows = parse_frequency_tsv(text)
    assert rows == [
        FrequencyRow(lemma="Haus", pos=PartOfSpeech.NOUN, cefr_level=CEFRLevel.A1, frequency_rank=10),
        FrequencyRow(lemma="laufen", pos=PartOfSpeech.VERB, cefr_level=CEFRLevel.A1, frequency_rank=12),
    ]


@pytest.mark.asyncio
async def test_load_populates_rank_and_overwrites_cefr_idempotently(db_session):
    lang = "invt1"  # idioma de prueba aislado (vocab_items NO se trunca entre tests)
    # pre-existente YA canónico (minúsculas) con cefr ruidoso y rank NULL, para que
    # el on_conflict por uq_vocab_lemma_lang_pos ACTUALICE: load canonicaliza
    # "Haus"→"haus"; si el pre fuera "Haus" (capital) no colisionaría → duplicaría.
    pre = VocabItem(
        id=uuid.uuid4(), language=lang, lemma="haus", pos=PartOfSpeech.NOUN,
        cefr_level=CEFRLevel.B2, frequency_rank=None,
    )
    db_session.add(pre); await db_session.commit()

    rows = [FrequencyRow(lemma="Haus", pos=PartOfSpeech.NOUN, cefr_level=CEFRLevel.A1, frequency_rank=10)]
    n1 = await load_frequency(db_session, language=lang, rows=rows)
    n2 = await load_frequency(db_session, language=lang, rows=rows)  # idempotente

    items = (
        await db_session.execute(
            select(VocabItem).where(VocabItem.language == lang, VocabItem.lemma == "haus")
        )
    ).scalars().all()
    assert len(items) == 1                      # no duplica
    assert items[0].frequency_rank == 10        # rank poblado
    assert items[0].cefr_level == CEFRLevel.A1  # cefr sobrescrito (era B2)
    assert n1 == 1 and n2 == 1
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_curriculum_inventory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.curriculum.inventory'`.

- [ ] **Step 3: Implementar**

```python
# backend/src/klara/curriculum/inventory.py
"""Carga del inventario de referencia (eje léxico) desde una lista curada externa.

El rank y la banda CEFR vienen de una fuente CURADA (Kelly / SUBTLEX-DE + CEFR),
NUNCA del LLM. Upsert por (lema canónico, idioma, pos): puebla frequency_rank y
SOBREESCRIBE cefr_level (el inferido por LLM en story_gen es ruido, no verdad de
terreno). Idempotente. La canonicalización del lema cuenta familias, no flexiones.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.lemmatize import canonical_lemma
from klara.models import VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech


@dataclass(frozen=True, slots=True)
class FrequencyRow:
    lemma: str
    pos: PartOfSpeech
    cefr_level: CEFRLevel
    frequency_rank: int


def parse_frequency_tsv(text: str) -> list[FrequencyRow]:
    """Parsea un TSV `lemma<TAB>pos<TAB>cefr<TAB>rank` (con cabecera)."""
    out: list[FrequencyRow] = []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    for ln in lines[1:]:  # salta la cabecera
        lemma, pos, cefr, rank = (c.strip() for c in ln.split("\t"))
        out.append(
            FrequencyRow(
                lemma=lemma,
                pos=PartOfSpeech(pos.lower()),
                cefr_level=CEFRLevel(cefr.upper()),
                frequency_rank=int(rank),
            )
        )
    return out


async def load_frequency(db: AsyncSession, *, language: str, rows: list[FrequencyRow]) -> int:
    """Upsertea el inventario. Devuelve cuántas filas se procesaron. Idempotente."""
    for r in rows:
        lemma = canonical_lemma(r.lemma, language)
        stmt = (
            pg_insert(VocabItem)
            .values(
                lemma=lemma,
                language=language,
                pos=r.pos,
                frequency_rank=r.frequency_rank,
                cefr_level=r.cefr_level,
            )
            .on_conflict_do_update(
                constraint="uq_vocab_lemma_lang_pos",
                set_={
                    "frequency_rank": r.frequency_rank,
                    "cefr_level": r.cefr_level,
                },
            )
        )
        await db.execute(stmt)
    await db.commit()
    return len(rows)
```

- [ ] **Step 4: Correr para verificar verde**

Run: `cd backend && uv run pytest tests/test_curriculum_inventory.py -v`
Expected: PASS (2 casos).

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/curriculum/inventory.py backend/tests/test_curriculum_inventory.py
git commit -m "feat(curriculum): idempotent frequency-inventory loader"
```

---

## Task 7: Script CLI de carga (`scripts/load_de_lexical.py`)

**Files:**
- Create: `backend/src/klara/scripts/__init__.py`, `backend/src/klara/scripts/load_de_lexical.py`

- [ ] **Step 1: Implementar el wrapper CLI** (es orquestación delgada sobre lógica ya testeada — sin test unitario propio; se valida corriéndolo)

Crea `backend/src/klara/scripts/__init__.py` vacío. Crea `backend/src/klara/scripts/load_de_lexical.py`:
```python
"""Carga la lista de frecuencia léxica de alemán al inventario.

Uso:
    uv run python -m klara.scripts.load_de_lexical <ruta-al-tsv>

El TSV es `lemma<TAB>pos<TAB>cefr<TAB>rank` (con cabecera). La lista real
(Kelly / SUBTLEX-DE + CEFR) se adquiere aparte por licencia; este script NO la
incluye. Wrapper idempotente sobre curriculum.inventory.load_frequency.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from klara.config import get_settings
from klara.curriculum.inventory import load_frequency, parse_frequency_tsv
from klara.db import dispose_engine, get_sessionmaker, init_engine


async def _run(path: Path) -> None:
    rows = parse_frequency_tsv(path.read_text(encoding="utf-8"))
    settings = get_settings()
    init_engine(settings)
    try:
        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            n = await load_frequency(db, language="de", rows=rows)
        print(f"Cargadas {n} filas de frecuencia (de).")
    finally:
        await dispose_engine()


def main() -> None:
    if len(sys.argv) != 2:
        print("uso: python -m klara.scripts.load_de_lexical <ruta-al-tsv>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(_run(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
```

> Verificado: `klara/db.py` expone `init_engine`, `dispose_engine` y `get_sessionmaker` con esos nombres y firmas, y `get_settings()` existe — el snippet aplica tal cual.

- [ ] **Step 2: Smoke local con un TSV mínimo**

```bash
cd backend
printf 'lemma\tpos\tcefr\trank\nHaus\tnoun\tA1\t10\nlaufen\tverb\tA1\t12\n' > /tmp/de_freq_smoke.tsv
uv run python -m klara.scripts.load_de_lexical /tmp/de_freq_smoke.tsv
```
Expected: imprime `Cargadas 2 filas de frecuencia (de).` sin error. (Usa la DB de dev local; inocuo.)

- [ ] **Step 3: Lint + commit**

```bash
cd backend && uv run ruff check src && uv run ruff format src
git add backend/src/klara/scripts/__init__.py backend/src/klara/scripts/load_de_lexical.py
git commit -m "feat(curriculum): CLI to load German frequency inventory"
```

---

## Task 8: Inyectar palabras objetivo al prompt (`prompts.py`)

**Files:**
- Modify: `backend/src/klara/llm/prompts.py`

- [ ] **Step 1: Añadir la línea de palabras objetivo al user prompt**

En `prompts.py`, reemplaza `STORY_USER_PROMPT` (líneas 101-106) por una versión con un bloque de objetivos:
```python
STORY_USER_PROMPT = """Genera una nueva micro-historia.

Tema: {topic}
Vocabulario reciente del estudiante en {target_label} (intenta NO repetir): {recent_vocab}
{target_block}
Genera el JSON ahora."""


def build_story_user_prompt(
    *, topic: str, target_label: str, recent_vocab: str, target_lemmas: list[str]
) -> str:
    if target_lemmas:
        joined = ", ".join(target_lemmas)
        target_block = (
            f"\nPALABRAS OBJETIVO DE HOY (el currículo las eligió por frecuencia; la historia "
            f"DEBE girar en torno a ellas y deben aparecer en `target_words`): {joined}\n"
        )
    else:
        target_block = ""
    return STORY_USER_PROMPT.format(
        topic=topic, target_label=target_label, recent_vocab=recent_vocab, target_block=target_block
    )
```

- [ ] **Step 2: Verificar que no rompe imports/llamadas existentes**

Run: `cd backend && uv run python -c "from klara.llm.prompts import build_story_user_prompt, STORY_USER_PROMPT; print(build_story_user_prompt(topic='t', target_label='alemán', recent_vocab='(ninguno)', target_lemmas=['Haus','laufen'])[:200])"`
Expected: imprime el prompt con la línea "PALABRAS OBJETIVO DE HOY ... Haus, laufen". Sin error.

- [ ] **Step 3: Lint + commit**

```bash
cd backend && uv run ruff check src && uv run ruff format src
git add backend/src/klara/llm/prompts.py
git commit -m "feat(story): target-words block in story user prompt"
```

---

## Task 9: Cablear selección + cobertura en generate_story + router

**Files:**
- Modify: `backend/src/klara/services/story_gen.py`, `backend/src/klara/routers/stories.py`
- Test: `backend/tests/test_story_curriculum.py`

- [ ] **Step 1: Escribir el test de integración que falla**

```python
# backend/tests/test_story_curriculum.py
"""generate_story recibe target_lemmas y filtra target_vocab_item_ids a los lemas
realmente cubiertos por la historia (honestidad de cobertura)."""

import uuid

import pytest

from klara.models import Story, VocabItem
from klara.models.enums import CEFRLevel, PartOfSpeech
from klara.services.story_gen import generate_story


class _FakeLLM:
    """Devuelve una historia fija: contiene 'Haus' (cubierto) pero NO 'Brücke'."""
    def __init__(self):
        self.provider = "fake"; self.model = "fake"; self.cost_usd = 0.0
    async def complete(self, **kwargs):
        import json
        from types import SimpleNamespace
        data = {
            "title": "Das Haus",
            "sentences": [{"target": "Das Haus ist groß.", "native": "La casa es grande.",
                           "new_words": ["Haus"], "breakdown": [{"word": "Haus", "translation": "casa", "pos": "noun"}]}],
            "comprehension_questions": [],
            "target_words": [
                {"lemma": "Haus", "pos": "noun", "translation": "casa", "example_target": "Das Haus."},
                {"lemma": "Brücke", "pos": "noun", "translation": "puente", "example_target": "Die Brücke."},
            ],
        }
        return SimpleNamespace(content=json.dumps(data), provider="fake", model="fake", cost_usd=0.0)


async def _user_id(db) -> uuid.UUID:
    from klara.models import User
    u = User(id=uuid.uuid4(), email=f"g-{uuid.uuid4().hex[:6]}@k.app", hashed_password="x",
             is_active=True, is_verified=True, is_superuser=False, display_name="G",
             level=CEFRLevel.A1, native_language="es", target_language="de")
    db.add(u); await db.flush(); return u.id


@pytest.mark.asyncio
async def test_uncovered_target_word_dropped_from_story(db_session):
    uid = await _user_id(db_session)
    result = await generate_story(
        db_session, _FakeLLM(), user_id=uid, level=CEFRLevel.A1,
        target_language="de", native_language="es", learning_context=None,
        topic=None, model=None, target_lemmas=["Haus", "Brücke"],
    )
    # 'Brücke' fue pedida y devuelta por el LLM, pero NO aparece en la historia →
    # se cae de target_vocab_item_ids (no afirmamos enseñarla).
    kept = (
        await db_session.execute(
            __import__("sqlalchemy").select(VocabItem.lemma).where(
                VocabItem.id.in_(result.story.target_vocab_item_ids)
            )
        )
    ).scalars().all()
    assert "Haus" in kept
    assert "Brücke" not in kept
    # La respuesta (target_words) tampoco debe afirmar enseñar lo no cubierto:
    returned = [w.lemma for w in result.target_words]
    assert "Haus" in returned and "Brücke" not in returned
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_story_curriculum.py -v`
Expected: FAIL — `generate_story() got an unexpected keyword argument 'target_lemmas'`.

- [ ] **Step 3: Modificar `generate_story`** (`services/story_gen.py`)

(a) La línea 13 real es `from klara.llm.prompts import STORY_USER_PROMPT, build_story_system_prompt`. Cámbiala a (quita `STORY_USER_PROMPT` — queda sin uso tras el cambio y `ruff` con select "F" falla por F401; `build_story_system_prompt` se sigue usando en la línea 180):
```python
from klara.llm.prompts import build_story_system_prompt, build_story_user_prompt
```
Y añade arriba estos imports nuevos:
```python
from klara.curriculum.coverage import verify_coverage
from klara.curriculum.lemmatize import canonical_lemma
```
(b) En la firma de `generate_story` (línea ~165-176), añade el parámetro al final:
```python
    model: str | None,
    target_lemmas: list[str] | None = None,
```
(c) Reemplaza la construcción del `user` prompt (líneas 187-191) por:
```python
    user = build_story_user_prompt(
        topic=topic or "libre — algo cotidiano",
        target_label=target_label,
        recent_vocab=", ".join(recent) if recent else "(ninguno)",
        target_lemmas=target_lemmas or [],
    )
```
(d) Tras `target_words = await _upsert_vocab_items(...)` (línea ~230-236) y ANTES de construir `story`, filtra por cobertura (los imports `verify_coverage`/`canonical_lemma` ya se añadieron en (a)):
```python
    content = {"sentences": sentences, "comprehension_questions": questions}
    covered = verify_coverage(content, [w.lemma for w in target_words], target_language)
    kept_words = [w for w in target_words if canonical_lemma(w.lemma, target_language) in covered]
    kept_ids = [w.id for w in kept_words]
    dropped = [w.lemma for w in target_words if canonical_lemma(w.lemma, target_language) not in covered]
    if dropped:
        log.info("story.coverage.dropped", story_dropped=dropped, target_language=target_language)
    # Registrar qué lemas del CURRÍCULO ignoró el LLM (señal de calidad, no bloquea):
    if target_lemmas:
        missed = [lemma for lemma in target_lemmas if canonical_lemma(lemma, target_language) not in covered]
        if missed:
            log.info("story.curriculum.missed", missed=missed, target_language=target_language)
```
(e) Usa `content` (ya construido) y `kept_ids` al crear el `Story` (línea ~238-252):
```python
    story = Story(
        user_id=user_id,
        level=level,
        target_language=target_language,
        native_language=native_language,
        title=title,
        content=content,
        target_vocab_item_ids=kept_ids,
        generated_by_provider=response.provider,
        generated_by_model=response.model,
        generation_cost_usd=response.cost_usd,
        quiz_items=quiz_items_raw if isinstance(quiz_items_raw, list) else None,
        insight_title=insight_title,
        insight_body=insight_body,
    )
```
(f) Cambia el `return` final de `generate_story` (línea ~265, hoy `return GeneratedStory(story=story, target_words=target_words)`) a devolver **solo las palabras cubiertas**, o el lema descartado seguiría apareciendo en la respuesta del POST (con su `frequency_rank`/`curriculum_note` de Task 10) — exactamente lo que §8 prohíbe:
```python
    return GeneratedStory(story=story, target_words=kept_words)
```

- [ ] **Step 4: Cablear la selección en el router** (`routers/stories.py`, `create_story`, líneas 105-116)

Añade el import: `from klara.curriculum.selection import next_target_words`. Antes de llamar `generate_story`, computa los objetivos:
```python
    level = payload.level or user.level
    target_words_sel = await next_target_words(
        db, user_id=user.id, language=user.target_language, level=level, n=5
    )
    result = await generate_story(
        db,
        llm,
        user_id=user.id,
        level=level,
        target_language=user.target_language,
        native_language=user.native_language,
        learning_context=user.learning_context,
        topic=payload.topic,
        model=None,
        target_lemmas=[w.lemma for w in target_words_sel],
    )
```
(Si el inventario está vacío para el idioma — p.ej. no-alemán sin lista cargada — `next_target_words` devuelve `[]` y `generate_story` cae al comportamiento actual: el LLM improvisa. Deuda visible, spec §10.)

- [ ] **Step 5: Correr el test (y la regresión de historias)**

Run: `cd backend && uv run pytest tests/test_story_curriculum.py tests/test_stories.py -v`
Expected: PASS (el nuevo + los de historias existentes; si `test_stories.py` no existe, corre solo el nuevo + `uv run pytest -q` para confirmar que nada se rompió).

- [ ] **Step 6: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/services/story_gen.py backend/src/klara/routers/stories.py backend/tests/test_story_curriculum.py
git commit -m "feat(story): drive target words by curriculum selection + coverage"
```

---

## Task 10: Exponer `frequency_rank` + `curriculum_note` en la API

**Files:**
- Modify: `backend/src/klara/schemas/story.py`, `backend/src/klara/routers/stories.py`
- Test: `backend/tests/test_story_curriculum.py` (añadir)

- [ ] **Step 1: Escribir el test que falla** (añade a `test_story_curriculum.py`)

```python
def test_serialize_exposes_frequency_rank_and_note():
    from klara.routers.stories import _serialize_story
    from klara.models import Story as StoryModel

    v = VocabItem(id=uuid.uuid4(), language="de", lemma="Haus", pos=PartOfSpeech.NOUN,
                  frequency_rank=10, cefr_level=CEFRLevel.A1, translations={"es": "casa"})
    story = StoryModel(
        id=uuid.uuid4(), user_id=uuid.uuid4(), level=CEFRLevel.A1, target_language="de",
        native_language="es", title="Das Haus",
        content={"sentences": [], "comprehension_questions": []}, target_vocab_item_ids=[v.id],
    )
    out = _serialize_story(story, [v], "es")
    assert out.target_words[0].frequency_rank == 10
    assert out.curriculum_note is not None and "Haus" in out.curriculum_note
```

- [ ] **Step 2: Correr para verificar que falla**

Run: `cd backend && uv run pytest tests/test_story_curriculum.py::test_serialize_exposes_frequency_rank_and_note -v`
Expected: FAIL — `StoryWordOut` no acepta `frequency_rank` / `StoryOut` no tiene `curriculum_note`.

- [ ] **Step 3: Añadir los campos al schema** (`schemas/story.py`)

En `StoryWordOut` añade tras `example_target`:
```python
    frequency_rank: int | None = None
```
En `StoryOut` añade tras `created_at` (o donde encaje):
```python
    curriculum_note: str | None = None
```
(Verifica los nombres reales de las clases en `schemas/story.py`; el router importa `StoryOut`, `StoryWordOut`.)

- [ ] **Step 4: Poblar en `_serialize_story`** (`routers/stories.py`, líneas 57-85)

En el `StoryWordOut(...)` de la comprensión de lista, añade `frequency_rank=w.frequency_rank,`. Tras construir `target`, computa la nota y pásala a `StoryOut`:
```python
    ranked = [w for w in words if w.frequency_rank is not None]
    if ranked:
        lemmas = ", ".join(w.lemma for w in ranked)
        curriculum_note = (
            f"Estas palabras están entre las más comunes en {language_label(story.target_language)} "
            f"que aún no dominas: {lemmas}."
        )
    else:
        curriculum_note = None
```
Añade `curriculum_note=curriculum_note,` al `return StoryOut(...)`. **`routers/stories.py` hoy importa solo `from klara.i18n import t` (NO `language_label`)** — añade `from klara.i18n import language_label` (o amplía la línea existente a `from klara.i18n import language_label, t`), o será un `NameError` en runtime.

- [ ] **Step 5: Correr para verificar verde**

Run: `cd backend && uv run pytest tests/test_story_curriculum.py -v`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/schemas/story.py backend/src/klara/routers/stories.py backend/tests/test_story_curriculum.py
git commit -m "feat(story): expose frequency_rank + curriculum_note in API"
```

---

## Task 11: El "por qué" en el frontend (mínimo)

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/components/WordPopover.tsx`, `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`

- [ ] **Step 1: Añadir `frequency_rank` al tipo `StoryWord`**

En `frontend/src/api/types.ts`, en `interface StoryWord` (tras `example_target: string | null;`):
```ts
  frequency_rank: number | null;
```

- [ ] **Step 2: Renderizar la línea callada en `WordPopover`**

En `WordPopover.tsx`, tras el bloque `{word.example_target && (...)}` (línea ~103-107) y antes de `<div className="wpop__foot">`:
```tsx
      {word.frequency_rank != null && (
        <div className="wpop__freq k-mono">
          {t("wpop.freq", { rank: word.frequency_rank })}
        </div>
      )}
```

- [ ] **Step 3: Añadir la clave i18n en los 6 locales**

En `frontend/src/locales/es/common.json`, dentro de `"wpop"` (junto a `audio`/`add`/`pos`), añade:
```json
      "freq": "entre las ~{{rank}} más comunes",
```
Espeja en los otros 5 (mismo lugar, dentro de `wpop`):
- en: `"freq": "among the ~{{rank}} most common"`
- de: `"freq": "unter den ~{{rank}} häufigsten"`
- fr: `"freq": "parmi les ~{{rank}} plus courants"`
- ja: `"freq": "最頻 ~{{rank}} 語のひとつ"`
- pt: `"freq": "entre as ~{{rank}} mais comuns"`

- [ ] **Step 4: Verificar (typecheck + i18n + build)**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run build`
Expected: typecheck limpio; `i18n:check` → 6 locales alineados (la clave nueva presente en los 6); build OK.
Manual: abrir el popover de una palabra objetivo con rank → muestra "entre las ~N más comunes"; una palabra sin rank no muestra la línea.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/components/WordPopover.tsx frontend/src/locales
git commit -m "feat(story): show frequency rationale in word popover"
```

---

## Self-Review (cobertura del spec)

- **§4 columna vertebral (ejes + interfaz):** Task 2 (axes) + Task 3 (competence interface sobre UserCard, sin tabla nueva).
- **§5 inventario de referencia:** Task 6 (loader idempotente, sobrescribe cefr) + Task 7 (CLI). Fuente curada externa; fixture en tests; lista real adquirida aparte (documentado).
- **§6 regla de selección:** Task 4 (frequency − known, content words, banda) + Task 9 (inyección en generate_story/router).
- **§7 paso 0 (saneamiento + lematizador):** Task 1 (simplemma + canonical_lemma); cefr-overwrite vía Task 6; canonicalización al leer en Tasks 3/5. **Re-etiquetado agresivo de `language="de"` diferido** (declarado en el header — forense costoso; canonicalización al leer lo mitiga).
- **§8 cobertura:** Task 5 (verify_coverage) + Task 9 (filtra target_vocab_item_ids + log de curriculum-missed; regeneración diferida).
- **§9 el "por qué":** Task 10 (API: frequency_rank + curriculum_note) + Task 11 (frontend).
- **§10 fronteras:** género/Rebanada 2, otros idiomas, japonés, árbitro, placement, derivar user.level — ninguna tarea (diferido explícito).
- **§11 testing:** Tasks 1-10 con pytest; Task 11 con typecheck/i18n/build.

**Consistencia de tipos:** `canonical_lemma(word, language)` usado idéntico en competence/selection/coverage/inventory. `next_target_words(db, *, user_id, language, level, n)` idéntico en selection y router. `verify_coverage(content, lemmas, language) -> set[str]` idéntico en coverage y story_gen. `FrequencyRow(lemma, pos, cefr_level, frequency_rank)` idéntico en inventory y sus tests. `StoryWordOut.frequency_rank` / `StoryOut.curriculum_note` consistentes entre schema, router y test.

**Nota de placeholders:** el Task 7 contiene una NOTA al implementador sobre verificar los helpers reales de `klara.db` (init/dispose/sessionmaker) — es la única incertidumbre de API conocida; el resto es código completo.
