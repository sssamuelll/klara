# Hoy y Biblioteca — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que al abrir Klara veas en un toque qué te toca hoy y con qué historia (el recorrido ilustrado), con los temas en una estantería.

**Architecture:** el backend calcula el día en `GET /today` con las tablas de actividad que ya existen. Cada historia gana `subtitle` y `scene` desde el mismo JSON que ya genera el modelo. La ilustración (Gemini 3.1 Flash Image, estilo cálido) se guarda en Postgres, una por escena, y se sirve en `/illustrations/{hash}`. El frontend reescribe Inicio como Hoy (`.k-route` + `.k-hero` con `__art`), suma Biblioteca (`.k-shelf` + `.k-cover`) y lleva la barra a tres pestañas.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pytest, httpx; React + Vite + TypeScript, vitest, i18next; `sistema.css` (vocabulario `k-*`).

**Spec:** `docs/superpowers/specs/2026-09-30-hoy-y-biblioteca-design.md` (commit `6eae2d1`, con la aclaración del canal de repasos). Mockups: https://claude.ai/artifact/AauMudVjqVPENieX34qMTH

## Global Constraints

- Rama `hoy-y-biblioteca`, creada desde `main` en `326472b`.
- Migración `20260930_0023`, con `down_revision = "20260829_0022"`.
- `stories` y `story_library` ganan `subtitle` `String(160)` y `scene` `String(600)`, las dos nullable.
- Clave de imagen: `sha256("{STYLE_VERSION}|{escena normalizada}")`, con `STYLE_VERSION = 1`. Normalizar es colapsar espacios y recortar los extremos. El modelo se guarda, pero no entra en la clave.
- Gemini: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`, con cabecera `x-goog-api-key`, `responseModalities: ["IMAGE"]` e `imageConfig: {aspectRatio: "21:9", imageSize: "1K"}`. Timeout de 60 s y tope de 3 MB por imagen. Modelo por defecto `gemini-3.1-flash-image-preview`, a $0,069 por imagen.
- `GET /today?since=`: 422 si `since` no trae zona, si está más de 1 minuto en el futuro o si tiene más de 48 horas. Repasar solo cuenta los `reviews` con `channel = "recall"`.
- `GET /illustrations/{hash}`: no pide sesión. Solo acepta hex en minúsculas de 64 caracteres, y responde con `Cache-Control: public, max-age=31536000, immutable` y `ETag: "<hash>"`.
- La API y sus campos van en inglés. Las rutas y los nombres del view-model del frontend, en castellano (`/biblioteca`, `buildHoyVM`).
- CSS: todo va en `sistema.css`, con cero literales de color. Se suman los átomos 18 (`.k-route`) y 19 (`.k-shelf` + `.k-cover`) y el elemento `.k-hero__art`. `.k-tabs--3` ya existe.
- i18n: cada clave nueva va en las seis carpetas de `frontend/src/locales` (es, en, de, fr, ja, pt), con el tono de cada una: fr con «tu», de con «du», pt con «você».
- Backend: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest <archivo> -v`.
- Frontend: `cd frontend && npx vitest run <archivo>`.
- Commits en castellano, con prefijo convencional y el trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- No se delegan, y los escribe Claude: `routers/illustrations.py`, `config.py`, `docker-compose.yml` y `routers/today.py` (la parte de sesión).

## Review Focus

1. **Un título alemán larguísimo** (un compuesto de 30 letras o más) en el panel, en una fila hecha o en una tapa tiene que partirse sin desbordar en horizontal. Lo prueban el escenario `titulo-largo` del arnés (tarea 14), la medida de desborde por contenedor y la muestra `compuesto-largo` de la hoja (tarea 10).
2. **La ilustración que anuncia `/today` no carga** (404 tras subir `STYLE_VERSION`, o red caída). El panel tiene que quedar tipográfico, sin icono de imagen rota. Lo prueban el `onError` de la tarea 12 y el escenario `arte-rota` de la tarea 14.
3. **Doble toque en «Empezar»** sobre una historia `new`: tiene que haber un solo reclamo, no dos historias clonadas. Lo prueban el candado de la tarea 12 y el conteo de `POST` de la tarea 14.
4. **Repasar hecho, pero con fichas todavía vencidas.** La fila dice HECHO y conserva «N fichas por repasar». Lo prueba la tarea 9.
5. **Una sesión de pronunciación escribe `reviews` con `channel = "pronunciation"`.** Eso no puede marcar Repasar como hecho. Lo prueba la tarea 7.

## Mapa de archivos

**Backend** (`backend/`):

| archivo | qué hace |
|---|---|
| `alembic/versions/20260930_0023_portadas_de_historias.py` (nuevo) | columnas `subtitle` y `scene`, y tabla `illustrations` |
| `src/klara/models/illustration.py` (nuevo) | modelo `Illustration` |
| `src/klara/models/{__init__,story,library}.py` | exporta `Illustration`; `subtitle` y `scene` |
| `src/klara/config.py` | `gemini_api_key` e `illustration_model` |
| `src/klara/services/illustration.py` (nuevo) | hash, prompt de estilo, `ensure_illustration`, `illustrate_in_background` |
| `src/klara/routers/illustrations.py` (nuevo) | `GET /illustrations/{hash}` |
| `src/klara/llm/prompts.py`, `src/klara/services/story_gen.py` | el modelo devuelve `subtitle` y `scene`; el borrador los limpia |
| `src/klara/curriculum/library.py` | reclamo y reciclaje copian los dos campos |
| `src/klara/scripts/build_story_library.py` | guarda los campos e ilustra cada entrada nueva |
| `src/klara/routers/stories.py` | agenda la ilustración al crear una historia |
| `src/klara/schemas/today.py`, `src/klara/services/today.py`, `src/klara/routers/today.py` (nuevos) | `GET /today` |
| `src/klara/main.py` | registra los dos routers nuevos |
| `src/klara/scripts/backfill_portadas.py` (nuevo) | backfill de textos e imágenes |
| `tests/conftest.py` | `illustrations` entra al `TRUNCATE` |

En la raíz: `docker-compose.yml` pasa `GEMINI_API_KEY` e `ILLUSTRATION_MODEL`.

**Frontend** (`frontend/src/`):

| archivo | qué hace |
|---|---|
| `api/types.ts`, `api/client.ts` | `TodayOut` y `api.today()` |
| `lib/hoyView.ts` (nuevo) | `buildHoyVM`, `medianocheLocal`, `arteSrc` (funciones puras) |
| `lib/tabs.ts` (nuevo) | `tabActiva` (función pura) |
| `lib/useCourseData.ts` (nuevo) | el hook que hoy vive en `Inicio.tsx` |
| `lib/courseView.ts` | pierde `pasos`, que queda muerto |
| `routes/Hoy.tsx` (nuevo, reemplaza a `Inicio.tsx`), `routes/Biblioteca.tsx` (nuevo), `routes/Portada.tsx`, `components/TabBar.tsx`, `App.tsx` | pantallas y navegación |
| `styles/sistema.css` | átomos 18 y 19, y `.k-hero__art` |
| `locales/*/common.json` (×6) | textos |

**Sistema de diseño y verificación:**

- `docs/design/klara-sistema/{CONTRATO.md,hoja.html,hoja.check.mjs}`: los átomos nuevos, sus muestras y sus estados obligatorios.
- `docs/design/klara-hoy/ilustracion-flash.jpg` (nuevo): la referencia del estilo aprobado. El arnés la sirve como ilustración.
- `frontend/scripts/capturas-hoy.mjs` (nuevo): el arnés visual.

## Preparación (una vez, antes de la tarea 1)

- [ ] Docker arriba. Si `docker ps` falla, usa la skill `levantar-docker`.
- [ ] Crea la base de pruebas si falta. El superusuario del contenedor es `german`:

```bash
docker exec klara_postgres psql -U german -d postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='klara'" | grep -q 1 \
  || docker exec klara_postgres psql -U german -d postgres -c "CREATE ROLE klara LOGIN PASSWORD 'klara_test'"
docker exec klara_postgres psql -U german -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='klara_test'" | grep -q 1 \
  || docker exec klara_postgres psql -U german -d postgres -c "CREATE DATABASE klara_test OWNER klara"
```

- [ ] `cd backend && uv sync` y `cd frontend && npm ci`.
- [ ] Línea base verde. Anota cuántos tests pasan; ese es el número contra el que se compara al final:

```bash
cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/ -q
cd frontend && npm test
```

---

### Task 1: Esquema — `subtitle` y `scene`, y la tabla `illustrations`

**Files:**
- Create: `backend/alembic/versions/20260930_0023_portadas_de_historias.py`
- Create: `backend/src/klara/models/illustration.py`
- Modify: `backend/src/klara/models/__init__.py`, `backend/src/klara/models/story.py` (clase `Story`, después de `title`), `backend/src/klara/models/library.py` (clase `StoryLibrary`, después de `title`)
- Modify: `backend/tests/conftest.py:77` (la lista del `TRUNCATE`)
- Test: `backend/tests/test_portadas_esquema.py`

**Interfaces:**
- Produces: `klara.models.Illustration`, con `id, hash, scene, style_version, model, mime_type, image_data, size_bytes, created_at`. También `Story.subtitle`, `Story.scene`, `StoryLibrary.subtitle` y `StoryLibrary.scene`, todos `str | None`.

- [ ] **Step 1: escribe la prueba que falla**

```python
"""Esquema de las portadas (spec §3.1-3.2): subtítulo y escena en historias y
biblioteca, y la tabla de ilustraciones con su hash único."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from klara.models import Illustration, Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel

CONTENT = {"sentences": [{"target": "Ich trinke Kaffee.", "native": "Bebo café."}]}
SUB = "Una panadería, un sábado a las ocho."
ESCENA = "A small bakery at dawn, a bicycle by the door."


@pytest.mark.asyncio
async def test_historia_y_biblioteca_guardan_subtitulo_y_escena(db_session):
    user = User(
        id=uuid.uuid4(), email=None, hashed_password=None, is_active=True,
        is_verified=False, is_superuser=False, display_name="Ana",
        level=CEFRLevel.A2, native_language="es", target_language="de",
    )
    module = Module(
        id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A2, sequence_order=1,
        title="En la panadería", can_dos=[], grammatical_focus=[],
    )
    db_session.add_all([user, module])
    await db_session.flush()
    db_session.add_all([
        Story(
            user_id=user.id, level=CEFRLevel.A2, target_language="de", native_language="es",
            title="Die Bäckerei", content=CONTENT, target_vocab_item_ids=[],
            subtitle=SUB, scene=ESCENA,
        ),
        StoryLibrary(
            module_id=module.id, language="de", native_language="es", level=CEFRLevel.A2,
            title="Die Bäckerei", content=CONTENT, target_vocab_item_ids=[], source="seed",
            content_hash="e" * 64, subtitle=SUB, scene=ESCENA,
        ),
    ])
    await db_session.commit()

    story = (await db_session.execute(select(Story))).scalar_one()
    entry = (await db_session.execute(select(StoryLibrary))).scalar_one()
    assert (story.subtitle, story.scene) == (SUB, ESCENA)
    assert (entry.subtitle, entry.scene) == (SUB, ESCENA)


@pytest.mark.asyncio
async def test_ilustracion_hash_unico(db_session):
    def fila() -> Illustration:
        return Illustration(
            hash="a" * 64, scene="x", style_version=1, model="m",
            mime_type="image/jpeg", image_data=b"\xff\xd8", size_bytes=2,
        )

    db_session.add(fila())
    await db_session.commit()
    db_session.add(fila())
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

- [ ] **Step 2: córrela y mírala fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_portadas_esquema.py -v`
Expected: FAIL con `ImportError: cannot import name 'Illustration'`.

- [ ] **Step 3: el modelo nuevo**, en `backend/src/klara/models/illustration.py`:

```python
from sqlalchemy import Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, uuid_pk


class Illustration(Base):
    """Portada de una historia: una imagen por escena (spec 2026-09-30 §3.2).

    `hash` = sha256("{style_version}|{escena normalizada}"). El modelo se guarda
    pero no entra en la clave: si cambiamos de modelo, las imágenes ya hechas
    siguen sirviendo."""

    __tablename__ = "illustrations"

    id: Mapped[uuid_pk]
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scene: Mapped[str] = mapped_column(Text, nullable=False)
    style_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(40), nullable=False)
    image_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[created_ts]
```

- [ ] **Step 4: las columnas.** En `models/story.py`, dentro de `Story`, justo después de la línea de `title`. Lo mismo en `models/library.py`, dentro de `StoryLibrary`:

```python
    # Portada (spec 2026-09-30 §3.1): una línea en la lengua del estudiante y la
    # escena en inglés que dibuja la ilustración. Nullable: las historias viejas
    # los reciben del backfill.
    subtitle: Mapped[str | None] = mapped_column(String(160), nullable=True)
    scene: Mapped[str | None] = mapped_column(String(600), nullable=True)
```

Comprueba que `String` ya esté importado en los dos archivos. Si falta, súmalo al `from sqlalchemy import …`.

- [ ] **Step 5: el registro.** En `models/__init__.py`, agrega `from klara.models.illustration import Illustration` entre las importaciones de `gender_lexicon` e `invitation`, y `"Illustration"` en `__all__` entre `"GenderLexicon"` e `"Invitation"`.

- [ ] **Step 6: la migración**, en `backend/alembic/versions/20260930_0023_portadas_de_historias.py`:

```python
"""portadas de historias — subtítulo y escena, y la tabla de ilustraciones

Aditiva. Dos columnas nullable en `stories` y `story_library` (subtitle,
scene) y una tabla nueva, `illustrations`, con una imagen por escena
(spec 2026-09-30-hoy-y-biblioteca §3).

Revision ID: 20260930_0023
Revises: 20260829_0022
Create Date: 2026-09-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260930_0023"
down_revision: str | None = "20260829_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLAS = ("stories", "story_library")


def upgrade() -> None:
    for tabla in TABLAS:
        op.add_column(tabla, sa.Column("subtitle", sa.String(160), nullable=True))
        op.add_column(tabla, sa.Column("scene", sa.String(600), nullable=True))
    op.create_table(
        "illustrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
        sa.Column("scene", sa.Text(), nullable=False),
        sa.Column("style_version", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("mime_type", sa.String(40), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("illustrations")
    for tabla in TABLAS:
        op.drop_column(tabla, "scene")
        op.drop_column(tabla, "subtitle")
```

- [ ] **Step 7: la limpieza entre pruebas.** En `tests/conftest.py`, `_clean_tables`: `illustrations` no tiene FK hacia nada, así que el `CASCADE` no la vacía. Agrégala al principio de la lista:

```python
                "TRUNCATE audio_cache, access_tokens, illustrations, invitations, oauth_accounts, reviews, user_cards, "
```

- [ ] **Step 8: córrela y mírala pasar.** El `conftest` baja y sube todas las migraciones al empezar, así que también prueba la nueva.

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_portadas_esquema.py -v`
Expected: PASS (2 tests).

- [ ] **Step 9: estilo y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/alembic/versions/20260930_0023_portadas_de_historias.py backend/src/klara/models backend/tests/conftest.py backend/tests/test_portadas_esquema.py
git commit -m "feat(portadas): subtítulo y escena en las historias, y la tabla de ilustraciones" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Configuración — `gemini_api_key` e `illustration_model` (la escribe Claude)

**Files:**
- Modify: `backend/src/klara/config.py` (campos después de `openai_api_key`; validador junto a los que ya existen, cerca de la línea 96)
- Modify: `docker-compose.yml` (servicio `backend`, después de `OPENAI_API_KEY`)
- Test: `backend/tests/test_portadas_config.py`

**Interfaces:**
- Produces: `Settings.gemini_api_key: SecretStr | None`, que en blanco vale `None`, y `Settings.illustration_model: str`.

- [ ] **Step 1: escribe la prueba que falla**

```python
"""Configuración de las portadas (spec §3.6): la clave de Gemini es secreta, en
blanco cuenta como ausente, y el compose la pasa al contenedor."""

from pathlib import Path

from klara.config import get_settings

REPO = Path(__file__).resolve().parents[2]


def test_clave_en_blanco_es_ausente(app_settings):
    app_settings(GEMINI_API_KEY="")
    assert get_settings().gemini_api_key is None


def test_clave_es_secreta(app_settings):
    app_settings(GEMINI_API_KEY="sk-secreta")
    settings = get_settings()
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "sk-secreta"
    assert "sk-secreta" not in repr(settings)


def test_modelo_por_defecto(app_settings):
    app_settings(ILLUSTRATION_MODEL=None)
    assert get_settings().illustration_model == "gemini-3.1-flash-image-preview"


def test_compose_pasa_la_clave_al_backend():
    # La trampa del #95: el compose pasa las claves una por una. Sin esta línea,
    # la clave del .env nunca llega al contenedor.
    compose = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY: ${GEMINI_API_KEY:-}" in compose
    assert "ILLUSTRATION_MODEL: ${ILLUSTRATION_MODEL:-gemini-3.1-flash-image-preview}" in compose
```

- [ ] **Step 2: córrela y mírala fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_portadas_config.py -v`
Expected: FAIL con `AttributeError: 'Settings' object has no attribute 'gemini_api_key'`.

- [ ] **Step 3: los campos**, en `config.py`, después de `openai_api_key: str | None = None`:

```python
    # Portadas de historias (spec 2026-09-30 §3.6). Sin clave no se genera nada
    # y el panel de Hoy queda tipográfico: la ausencia es un modo, no un error.
    gemini_api_key: SecretStr | None = None
    illustration_model: str = "gemini-3.1-flash-image-preview"
```

- [ ] **Step 4: el validador**, junto al `@field_validator` que ya existe:

```python
    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _blank_gemini_key_is_none(cls, v: object) -> object:
        # El compose pasa `${GEMINI_API_KEY:-}`: sin clave llega "", no None.
        if isinstance(v, str) and not v.strip():
            return None
        return v
```

- [ ] **Step 5: el compose**, en `docker-compose.yml`, servicio `backend`, después de `OPENAI_API_KEY: ${OPENAI_API_KEY:-}`:

```yaml
      # Portadas de historias (spec 2026-09-30 §3.6). Sin clave no hay imágenes.
      GEMINI_API_KEY: ${GEMINI_API_KEY:-}
      ILLUSTRATION_MODEL: ${ILLUSTRATION_MODEL:-gemini-3.1-flash-image-preview}
```

- [ ] **Step 6: córrela y mírala pasar**

Run: el mismo comando del paso 2.
Expected: PASS (4 tests).

- [ ] **Step 7: commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/config.py docker-compose.yml backend/tests/test_portadas_config.py
git commit -m "feat(portadas): la clave de Gemini en la config, secreta y opcional" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: El servicio de ilustraciones

**Files:**
- Create: `backend/src/klara/services/illustration.py`
- Test: `backend/tests/test_illustration_service.py`

**Interfaces:**
- Consumes: `Illustration` (tarea 1) y `Settings.gemini_api_key`/`illustration_model` (tarea 2).
- Produces, en `klara.services.illustration`:
  - `STYLE_VERSION: int`, `STYLE_PROMPT: str`, `MAX_BYTES: int`, `COST_PER_IMAGE_USD = 0.069`
  - `normalize_scene(scene: str | None) -> str`
  - `illustration_hash(scene: str) -> str`
  - `illustration_path(hash_: str) -> str`, que devuelve `"/illustrations/<hash>"`
  - `build_prompt(scene: str) -> str`
  - `async ensure_illustration(db, scene: str | None, *, settings, client: httpx.AsyncClient | None = None) -> str | None`. No hace commit: lo hace quien la llama.
  - `async illustrate_in_background(settings, scene: str | None) -> None`, con su propia sesión. Nunca lanza.

- [ ] **Step 1: escribe la prueba que falla**

```python
"""services/illustration.py (spec §3.3): una imagen por escena, en caché, sin
reintentos y sin lanzar nunca hacia quien la pide."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from klara.config import get_settings
from klara.models import Illustration
from klara.services import illustration as ilus

ESCENA = "A small half-timbered bakery at dawn, a bicycle by the door."
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


def _settings(key: str | None = "k"):
    return get_settings().model_copy(
        update={
            "gemini_api_key": SecretStr(key) if key else None,
            "illustration_model": "gemini-3.1-flash-image-preview",
        }
    )


class Gemini:
    """Transporte falso: cuenta las llamadas y responde lo que se le pida."""

    def __init__(self, response: httpx.Response | None = None) -> None:
        self.calls: list[httpx.Request] = []
        self.response = response or httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [
                {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(JPEG).decode()}}
            ]}}]},
        )

    def client(self) -> httpx.AsyncClient:
        def handler(request: httpx.Request) -> httpx.Response:
            self.calls.append(request)
            return self.response

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _cuantas(db) -> int:
    return (await db.execute(select(func.count()).select_from(Illustration))).scalar_one()


def test_hash_normaliza_la_escena():
    a = ilus.illustration_hash("  A small   bakery\n at dawn ")
    assert a == ilus.illustration_hash("A small bakery at dawn")
    assert len(a) == 64


def test_hash_cambia_con_la_version_de_estilo(monkeypatch):
    antes = ilus.illustration_hash(ESCENA)
    monkeypatch.setattr(ilus, "STYLE_VERSION", ilus.STYLE_VERSION + 1)
    assert ilus.illustration_hash(ESCENA) != antes


@pytest.mark.asyncio
async def test_escena_vacia_no_llama(db_session):
    gemini = Gemini()
    h = await ilus.ensure_illustration(db_session, "   ", settings=_settings(), client=gemini.client())
    assert h is None and gemini.calls == []


@pytest.mark.asyncio
async def test_sin_clave_no_llama(db_session):
    gemini = Gemini()
    h = await ilus.ensure_illustration(db_session, ESCENA, settings=_settings(None), client=gemini.client())
    assert h is None and gemini.calls == []


@pytest.mark.asyncio
async def test_genera_guarda_y_despues_sale_de_cache(db_session):
    gemini = Gemini()
    h = await ilus.ensure_illustration(db_session, ESCENA, settings=_settings(), client=gemini.client())
    await db_session.commit()
    assert h == ilus.illustration_hash(ESCENA)
    fila = (await db_session.execute(select(Illustration))).scalar_one()
    assert (fila.mime_type, fila.image_data, fila.size_bytes) == ("image/jpeg", JPEG, len(JPEG))
    assert (fila.style_version, fila.model) == (ilus.STYLE_VERSION, "gemini-3.1-flash-image-preview")

    pedido = gemini.calls[0]
    cuerpo = json.loads(pedido.content)
    assert pedido.headers["x-goog-api-key"] == "k"
    assert "gemini-3.1-flash-image-preview:generateContent" in str(pedido.url)
    assert cuerpo["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert cuerpo["generationConfig"]["imageConfig"] == {"aspectRatio": "21:9", "imageSize": "1K"}
    assert ESCENA in cuerpo["contents"][0]["parts"][0]["text"]

    otra = await ilus.ensure_illustration(db_session, ESCENA, settings=_settings(), client=gemini.client())
    assert otra == h and len(gemini.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(500, json={"error": "boom"}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "no image"}]}}]}),
        httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
    ],
    ids=["http-500", "sin-imagen", "bloqueo"],
)
async def test_fallos_devuelven_none_y_no_guardan(db_session, respuesta):
    h = await ilus.ensure_illustration(
        db_session, ESCENA, settings=_settings(), client=Gemini(respuesta).client()
    )
    assert h is None
    assert await _cuantas(db_session) == 0


@pytest.mark.asyncio
async def test_imagen_demasiado_grande(db_session, monkeypatch):
    monkeypatch.setattr(ilus, "MAX_BYTES", 4)
    h = await ilus.ensure_illustration(db_session, ESCENA, settings=_settings(), client=Gemini().client())
    assert h is None
    assert await _cuantas(db_session) == 0


@pytest.mark.asyncio
async def test_choque_de_insercion_devuelve_el_hash(db_session, db_engine, monkeypatch):
    """Otra petición guarda la misma escena entre la consulta y el INSERT."""
    real = ilus._generate

    async def generar_y_colarse(settings, scene, client):
        async with async_sessionmaker(db_engine)() as otra:
            otra.add(Illustration(
                hash=ilus.illustration_hash(scene), scene=scene, style_version=ilus.STYLE_VERSION,
                model="otra", mime_type="image/png", image_data=b"x", size_bytes=1,
            ))
            await otra.commit()
        return await real(settings, scene, client)

    monkeypatch.setattr(ilus, "_generate", generar_y_colarse)
    h = await ilus.ensure_illustration(db_session, ESCENA, settings=_settings(), client=Gemini().client())
    await db_session.commit()
    assert h == ilus.illustration_hash(ESCENA)
    assert await _cuantas(db_session) == 1


@pytest.mark.asyncio
async def test_en_segundo_plano_sin_base_no_lanza():
    from klara.db import dispose_engine

    await dispose_engine()
    await ilus.illustrate_in_background(_settings(), ESCENA)
```

- [ ] **Step 2: córrela y mírala fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_illustration_service.py -v`
Expected: FAIL con `ImportError: cannot import name 'illustration' from 'klara.services'`.

- [ ] **Step 3: implementa `backend/src/klara/services/illustration.py`**

```python
"""La portada de una historia: una ilustración por escena, en caché (spec §3).

La clave es sha256("{STYLE_VERSION}|{escena normalizada}"). El modelo se guarda
pero no entra en la clave: si Google retira el preview y cambiamos de modelo,
las imágenes hechas siguen sirviendo. Cambiar el estilo es intencional: se sube
STYLE_VERSION y el backfill regenera.
"""

from __future__ import annotations

import base64
import hashlib

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.config import Settings
from klara.db import get_sessionmaker
from klara.models import Illustration

log = structlog.get_logger(__name__)

STYLE_VERSION = 1
# El estilo cálido que eligió Samuel el 2026-09-30 (la prueba de 3.1 Flash de la
# galería). Se describe entero a propósito: no se deja a que el modelo desobedezca.
STYLE_PROMPT = (
    "Editorial illustration for a short story in a language-learning app, in the look of a "
    "hand-pulled risograph or linocut print on cream paper (#F4EFE6). Warm palette led by warm "
    "black ink (#1A1814) and vermilion (#CB4644), with amber window light, soft pinks and stone "
    "greys. Visible print grain and slight misregistration, flat shapes, confident hand-cut "
    "lines. Wide banner composition with some open paper around the subject. No text, no "
    "letters, no words on signs, no logos, no recognizable people."
)
MAX_BYTES = 3 * 1024 * 1024
COST_PER_IMAGE_USD = 0.069  # medido con la cabecera de costo de LiteLLM, 2026-09-30
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def normalize_scene(scene: str | None) -> str:
    return " ".join((scene or "").split())


def illustration_hash(scene: str) -> str:
    return hashlib.sha256(f"{STYLE_VERSION}|{normalize_scene(scene)}".encode()).hexdigest()


def illustration_path(hash_: str) -> str:
    return f"/illustrations/{hash_}"


def build_prompt(scene: str) -> str:
    return f"{STYLE_PROMPT}\nScene: {normalize_scene(scene)}"


async def _generate(settings: Settings, scene: str, client: httpx.AsyncClient) -> tuple[bytes, str]:
    assert settings.gemini_api_key is not None  # lo comprueba ensure_illustration
    resp = await client.post(
        GEMINI_URL.format(model=settings.illustration_model),
        headers={"x-goog-api-key": settings.gemini_api_key.get_secret_value()},
        json={
            "contents": [{"parts": [{"text": build_prompt(scene)}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": "21:9", "imageSize": "1K"},
            },
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    for candidate in resp.json().get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            data = part.get("inlineData") or part.get("inline_data")
            if data and data.get("data"):
                mime = data.get("mimeType") or data.get("mime_type") or "image/jpeg"
                return base64.b64decode(data["data"]), mime
    raise ValueError("gemini: la respuesta no trae imagen")


async def ensure_illustration(
    db: AsyncSession,
    scene: str | None,
    *,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """El hash de la ilustración de `scene`, generándola si hace falta.

    None si la escena está vacía, si no hay clave o si Gemini falla. Nunca
    lanza por la red. No hace commit: lo hace quien la llama."""
    escena = normalize_scene(scene)
    if not escena:
        return None
    h = illustration_hash(escena)
    if (await db.execute(select(Illustration.hash).where(Illustration.hash == h))).first():
        return h
    if settings.gemini_api_key is None:
        return None
    http = client or httpx.AsyncClient()
    try:
        raw, mime = await _generate(settings, escena, http)
    except Exception as exc:  # red, HTTP, bloqueo de seguridad o respuesta sin imagen
        log.warning("illustration.generate_failed", hash=h, error=str(exc))
        return None
    finally:
        if client is None:
            await http.aclose()
    if len(raw) > MAX_BYTES:
        log.warning("illustration.too_big", hash=h, size=len(raw))
        return None
    await db.execute(
        insert(Illustration)
        .values(
            hash=h,
            scene=escena,
            style_version=STYLE_VERSION,
            model=settings.illustration_model,
            mime_type=mime,
            image_data=raw,
            size_bytes=len(raw),
        )
        .on_conflict_do_nothing(index_elements=["hash"])
    )
    return h


async def illustrate_in_background(settings: Settings, scene: str | None) -> None:
    """Tarea de fondo tras crear una historia: abre su propia sesión y nunca lanza."""
    try:
        sessionmaker = get_sessionmaker()
    except RuntimeError:
        log.warning("illustration.no_db")
        return
    try:
        async with sessionmaker() as db:
            if await ensure_illustration(db, scene, settings=settings):
                await db.commit()
    except Exception as exc:
        log.warning("illustration.background_failed", error=str(exc))
```

- [ ] **Step 4: córrela y mírala pasar**

Run: el mismo comando del paso 2.
Expected: PASS (11 tests).

- [ ] **Step 5: commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/services/illustration.py backend/tests/test_illustration_service.py
git commit -m "feat(portadas): el servicio que dibuja una ilustración por escena" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `GET /illustrations/{hash}` (la escribe Claude)

**Files:**
- Create: `backend/src/klara/routers/illustrations.py`
- Modify: `backend/src/klara/main.py` (el bloque `from klara.routers import (...)` y las líneas `include_router`)
- Test: `backend/tests/test_illustrations_router.py`

**Interfaces:**
- Consumes: `Illustration` (tarea 1). El formato de ruta `/illustrations/{hash}` es el mismo de `illustration_path` (tarea 3).
- Produces: `GET /api/v1/illustrations/{hash}`, sin sesión.

- [ ] **Step 1: escribe la prueba que falla**

```python
"""GET /illustrations/{hash} (spec §3.5): pública, inmutable, 404 si no existe."""

import pytest

from klara.models import Illustration

H = "b" * 64


@pytest.mark.asyncio
async def test_sirve_la_imagen_sin_sesion(client, db_session):
    db_session.add(Illustration(
        hash=H, scene="x", style_version=1, model="m",
        mime_type="image/jpeg", image_data=b"\xff\xd8jpeg", size_bytes=6,
    ))
    await db_session.commit()
    resp = await client.get(f"/api/v1/illustrations/{H}")
    assert resp.status_code == 200
    assert resp.content == b"\xff\xd8jpeg"
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resp.headers["etag"] == f'"{H}"'


@pytest.mark.asyncio
@pytest.mark.parametrize("hash_", ["c" * 64, "B" * 64, "z" * 64, "abc", "b" * 65])
async def test_404(client, hash_):
    resp = await client.get(f"/api/v1/illustrations/{hash_}")
    assert resp.status_code == 404
```

- [ ] **Step 2: córrela y mírala fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_illustrations_router.py -v`
Expected: FAIL. El primer test da 404 porque la ruta no existe.

- [ ] **Step 3: implementa `backend/src/klara/routers/illustrations.py`**

```python
"""GET /illustrations/{hash}: la portada de una historia, sin sesión.

Pública a propósito, como /tts: el <img> de la app nativa no manda el Bearer.
El hash (sha256 de la escena con su versión de estilo) no se puede adivinar sin
conocer la escena, y las escenas no llevan nombres ni personas reconocibles."""

import re

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from klara.dependencies import DBSession
from klara.models import Illustration

router = APIRouter(prefix="/illustrations", tags=["illustrations"])

_HASH = re.compile(r"^[0-9a-f]{64}$")


@router.get("/{hash_}")
async def get_illustration(hash_: str, db: DBSession) -> Response:
    if not _HASH.match(hash_):
        raise HTTPException(status_code=404, detail="illustration.not_found")
    row = (
        await db.execute(
            select(Illustration.image_data, Illustration.mime_type).where(
                Illustration.hash == hash_
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="illustration.not_found")
    return Response(
        content=row.image_data,
        media_type=row.mime_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{hash_}"',
        },
    )
```

- [ ] **Step 4: regístralo en `main.py`.** Agrega `illustrations,` al bloque `from klara.routers import (...)`, entre `health,` e `invitations,`, y esta línea después de `app.include_router(tts.router, prefix="/api/v1")`:

```python
    app.include_router(illustrations.router, prefix="/api/v1")
```

- [ ] **Step 5: córrela y mírala pasar**

Run: el mismo comando del paso 2.
Expected: PASS (6 tests).

- [ ] **Step 6: commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/routers/illustrations.py backend/src/klara/main.py backend/tests/test_illustrations_router.py
git commit -m "feat(portadas): GET /illustrations/{hash}, pública e inmutable como /tts" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Subtítulo y escena en el flujo de historias

**Files:**
- Modify: `backend/src/klara/llm/prompts.py` (contrato JSON de `STORY_SYSTEM_PROMPT`, justo después de la línea `"title": …`)
- Modify: `backend/src/klara/services/story_gen.py` (`trim_text`, las constantes, `StoryDraft`, `generate_story_draft` y `generate_story`)
- Modify: `backend/src/klara/curriculum/library.py` (`claim_library_entry` y `maybe_recycle_to_library`)
- Modify: `backend/src/klara/scripts/build_story_library.py` (el `StoryLibrary(...)` de `build_library`)
- Test: `backend/tests/test_story_portadas.py`

**Interfaces:**
- Consumes: las columnas de la tarea 1.
- Produces:
  - `klara.services.story_gen.trim_text(value, limit) -> str | None`
  - `SUBTITLE_MAX = 160` y `SCENE_MAX = 600`
  - `StoryDraft.subtitle` y `StoryDraft.scene`, las dos `str | None = None` y al final del dataclass

- [ ] **Step 1: escribe la prueba que falla**

```python
"""Subtítulo y escena en el flujo de historias (spec §3.1): el modelo los devuelve,
el borrador los limpia y recorta, y viajan a la historia, a la biblioteca (build y
reciclaje) y a la copia al reclamar."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from klara.curriculum.library import claim_library_entry, maybe_recycle_to_library
from klara.curriculum.modules import load_modules
from klara.llm.base import LLMResponse
from klara.llm.prompts import build_story_system_prompt
from klara.models import Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel
from klara.scripts.build_story_library import build_library
from klara.services.story_gen import SCENE_MAX, SUBTITLE_MAX, generate_story, generate_story_draft


def _json(**extra) -> str:
    return json.dumps({
        "title": "Der Kaffee",
        "sentences": [{
            "target": "Der Kaffee ist heiß.", "native": "El café está caliente.",
            "new_words": ["Kaffee"], "breakdown": [{"word": "Kaffee", "translation": "café"}],
        }],
        "comprehension_questions": [],
        "target_words": [{"lemma": "Kaffee", "pos": "noun", "gender": "der", "translation": "café"}],
        "quiz_items": None,
        **extra,
    })


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content

    async def complete(self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None):
        return LLMResponse(content=self.content, model="fake", provider="fake", cost_usd=0.001)

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


async def _draft(db, content: str):
    return await generate_story_draft(
        db, FakeLLM(content), level=CEFRLevel.A1, target_language="de", native_language="es",
        learning_context=None, topic=None, model=None,
    )


async def _usuario_y_modulo(db):
    user = User(
        id=uuid.uuid4(), email=None, hashed_password=None, is_active=True, is_verified=False,
        is_superuser=False, display_name="Ana", level=CEFRLevel.A1, native_language="es",
        target_language="de",
    )
    module = Module(
        id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A1, sequence_order=1,
        title="En el café", can_dos=[], grammatical_focus=[],
    )
    db.add_all([user, module])
    await db.flush()
    return user, module


def test_el_prompt_pide_subtitulo_y_escena():
    prompt = build_story_system_prompt(
        target_label="alemán", native_label="español", level="A2",
        target_language="de", learning_context=None,
    )
    assert '"subtitle"' in prompt and '"scene"' in prompt
    assert "{native_label}" not in prompt


@pytest.mark.asyncio
async def test_el_borrador_limpia_y_recorta(db_session):
    draft = await _draft(db_session, _json(subtitle="  Una panadería,\n un sábado  ", scene="x" * 900))
    assert draft.subtitle == "Una panadería, un sábado"
    assert draft.scene == "x" * SCENE_MAX
    largo = await _draft(db_session, _json(subtitle="y" * 400, scene="A bakery."))
    assert largo.subtitle == "y" * SUBTITLE_MAX


@pytest.mark.asyncio
async def test_sin_campos_o_raros_quedan_en_none(db_session):
    draft = await _draft(db_session, _json())
    assert (draft.subtitle, draft.scene) == (None, None)
    raros = await _draft(db_session, _json(subtitle=42, scene="   "))
    assert (raros.subtitle, raros.scene) == (None, None)


@pytest.mark.asyncio
async def test_la_historia_generada_los_guarda(db_session):
    user, _ = await _usuario_y_modulo(db_session)
    result = await generate_story(
        db_session, FakeLLM(_json(subtitle="Un café.", scene="A café at noon.")),
        user_id=user.id, level=CEFRLevel.A1, target_language="de", native_language="es",
        learning_context=None, topic=None, model=None,
    )
    assert (result.story.subtitle, result.story.scene) == ("Un café.", "A café at noon.")


@pytest.mark.asyncio
async def test_reclamar_copia_subtitulo_y_escena(db_session):
    user, module = await _usuario_y_modulo(db_session)
    entry = StoryLibrary(
        module_id=module.id, language="de", native_language="es", level=CEFRLevel.A1,
        title="Der Kaffee", content={"sentences": []}, target_vocab_item_ids=[], source="seed",
        content_hash="f" * 64, subtitle="Un café.", scene="A café at noon.",
    )
    db_session.add(entry)
    await db_session.flush()
    story = await claim_library_entry(db_session, user=user, entry=entry, module=module)
    assert (story.subtitle, story.scene) == ("Un café.", "A café at noon.")


@pytest.mark.asyncio
async def test_reciclar_copia_subtitulo_y_escena(db_session):
    user, module = await _usuario_y_modulo(db_session)
    story = Story(
        user_id=user.id, level=CEFRLevel.A1, target_language="de", native_language="es",
        title="Der Kaffee", content={"sentences": [{"target": "Der Kaffee ist heiß."}]},
        target_vocab_item_ids=[], module_id=module.id, subtitle="Un café.", scene="A café at noon.",
    )
    db_session.add(story)
    await db_session.flush()
    await maybe_recycle_to_library(
        db_session, story=story, dropped_lemmas=[], topic=None, topic_origin="none"
    )
    entry = (await db_session.execute(select(StoryLibrary))).scalar_one()
    assert (entry.subtitle, entry.scene) == ("Un café.", "A café at noon.")


@pytest.mark.asyncio
async def test_build_guarda_subtitulo_y_escena(db_session):
    await load_modules(db_session, language="de", modules=[{
        "sequence_order": 1, "title": "En el café", "cefr_level": "A1", "can_dos": ["pedir"],
        "grammatical_focus": ["género"],
        "vocab": [{"lemma": "Kaffee", "pos": "noun", "gender": "der", "translations": {"es": "café"}}],
    }])
    await db_session.commit()
    n = await build_library(
        db_session, FakeLLM(_json(subtitle="Un café.", scene="A café at noon.")),
        language="de", native="es", per_module=1,
    )
    assert n == 1
    entry = (await db_session.execute(select(StoryLibrary))).scalar_one()
    assert (entry.subtitle, entry.scene) == ("Un café.", "A café at noon.")
```

- [ ] **Step 2: córrela y mírala fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_story_portadas.py -v`
Expected: FAIL con `ImportError: cannot import name 'SCENE_MAX'`.

- [ ] **Step 3: el contrato JSON.** En `llm/prompts.py`, dentro de `STORY_SYSTEM_PROMPT`, justo después de `  "title": "string (en {target_label}, corto)",`, van dos líneas. El prompt usa `.format`, así que las llaves literales tienen que ir dobladas y los marcadores quedan simples:

```text
  "subtitle": "una línea en {native_label}, 70 caracteres o menos, que diga de qué va la escena sin contar el final",
  "scene": "la escena principal descrita EN INGLÉS para un ilustrador, 300 caracteres o menos: lugar, momento del día, objetos y luz. Sin texto, letreros, marcas ni personas reconocibles",
```

- [ ] **Step 4: el borrador.** En `services/story_gen.py`:

a) Debajo de los imports:

```python
# Portada (spec 2026-09-30 §3.1). Topes de columna: el prompt pide menos
# (70 y 300 caracteres) y lo que se pase se recorta, no se rechaza.
SUBTITLE_MAX = 160
SCENE_MAX = 600


def trim_text(value: Any, limit: int) -> str | None:
    """Colapsa espacios y recorta. Lo que no es texto, o queda vacío, es None."""
    if not isinstance(value, str):
        return None
    return " ".join(value.split())[:limit] or None
```

b) En el dataclass `StoryDraft`, al final, después de `gender_violations: list[str]`:

```python
    subtitle: str | None = None
    scene: str | None = None
```

c) En `generate_story_draft`, después del bloque que parsea `insight_raw`:

```python
    subtitle = trim_text(data.get("subtitle"), SUBTITLE_MAX)
    scene = trim_text(data.get("scene"), SCENE_MAX)
```

y en el `return StoryDraft(...)` de esa función, al final: `subtitle=subtitle, scene=scene,`.

d) En `generate_story`, dentro de `Story(...)`, después de `insight_body=draft.insight_body,`: `subtitle=draft.subtitle, scene=draft.scene,`.

- [ ] **Step 5: biblioteca, reclamo y reciclaje.**

- En `curriculum/library.py`, en `claim_library_entry`, dentro de `Story(...)`, después de `insight_body=entry.insight_body,`: `subtitle=entry.subtitle, scene=entry.scene,`.
- En la misma función, en `maybe_recycle_to_library`, dentro de `StoryLibrary(...)`, después de `insight_body=story.insight_body,`: `subtitle=story.subtitle, scene=story.scene,`.
- En `scripts/build_story_library.py`, en `build_library`, dentro de `StoryLibrary(...)`, después de `insight_body=draft.insight_body,`: `subtitle=draft.subtitle, scene=draft.scene,`.

- [ ] **Step 6: córrela y mírala pasar, y corre también las suites vecinas**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_story_portadas.py tests/test_build_library.py tests/test_claim_story.py tests/test_create_story_module.py tests/test_library_service.py -v`
Expected: PASS en todo.

- [ ] **Step 7: commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/llm/prompts.py backend/src/klara/services/story_gen.py backend/src/klara/curriculum/library.py backend/src/klara/scripts/build_story_library.py backend/tests/test_story_portadas.py
git commit -m "feat(portadas): cada historia trae su subtítulo y su escena, y viajan con ella" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Cuándo se dibuja la ilustración

**Files:**
- Modify: `backend/src/klara/routers/stories.py` (import y `create_story`, después del `background.add_task(precache_story, …)`)
- Modify: `backend/src/klara/scripts/build_story_library.py` (parámetro `illustrate` de `build_library`, su uso y `_run`)
- Test: `backend/tests/test_portadas_disparadores.py`

**Interfaces:**
- Consumes: `illustrate_in_background`, `ensure_illustration` y `COST_PER_IMAGE_USD` (tarea 3), y `Story.scene` y `StoryDraft.scene` (tarea 5).
- Produces: `build_library(..., illustrate: Callable[[AsyncSession, str], Awaitable[str | None]] | None = None)`.

- [ ] **Step 1: escribe la prueba que falla**

```python
"""Cuándo se dibuja la ilustración (spec §3.4): en segundo plano al crear una
historia con escena, y en build_story_library después de guardar cada entrada."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from klara.curriculum.modules import load_modules
from klara.dependencies import get_story_llm
from klara.llm.base import LLMResponse
from klara.models import StoryLibrary
from klara.scripts.build_story_library import build_library


def _json(**extra) -> str:
    return json.dumps({
        "title": "Der Kaffee",
        "sentences": [{
            "target": "Der Kaffee ist heiß.", "native": "El café está caliente.",
            "new_words": ["Kaffee"], "breakdown": [{"word": "Kaffee", "translation": "café"}],
        }],
        "comprehension_questions": [],
        "target_words": [{"lemma": "Kaffee", "pos": "noun", "gender": "der", "translation": "café"}],
        "quiz_items": None,
        **extra,
    })


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content

    async def complete(self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None):
        return LLMResponse(content=self.content, model="fake", provider="fake", cost_usd=0.001)

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


@pytest_asyncio.fixture
async def app_con_llm():
    """App real con la LLM de historias reemplazada (como test_create_story_module)."""
    from klara.config import get_settings
    from klara.db import dispose_engine, init_engine
    from klara.main import create_app

    init_engine(get_settings())
    app = create_app()
    clientes: list[AsyncClient] = []

    def hacer(content: str) -> AsyncClient:
        app.dependency_overrides[get_story_llm] = lambda: FakeLLM(content)
        cliente = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clientes.append(cliente)
        return cliente

    yield hacer
    for cliente in clientes:
        await cliente.aclose()
    await dispose_engine()


async def _login(client, seed_invite, email: str) -> str:
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def _seed_modulo(db) -> None:
    await load_modules(db, language="de", modules=[{
        "sequence_order": 1, "title": "En el café", "cefr_level": "A1", "can_dos": ["pedir"],
        "grammatical_focus": ["género"],
        "vocab": [{"lemma": "Kaffee", "pos": "noun", "gender": "der", "translations": {"es": "café"}}],
    }])
    await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("extra, esperadas", [
    ({"scene": "A café at noon."}, ["A café at noon."]),
    ({}, []),
], ids=["con-escena", "sin-escena"])
async def test_crear_historia_agenda_la_ilustracion_solo_con_escena(
    app_con_llm, seed_invite, monkeypatch, extra, esperadas
):
    llamadas: list[str] = []

    async def fake(settings, scene):
        llamadas.append(scene)

    monkeypatch.setattr("klara.routers.stories.illustrate_in_background", fake)
    client = app_con_llm(_json(**extra))
    cookie = await _login(client, seed_invite, f"crear-{len(esperadas)}@example.com")
    resp = await client.post(
        "/api/v1/stories",
        json={"topic": "café", "topic_origin": "free"},
        headers={"Cookie": cookie},
    )
    assert resp.status_code == 201, resp.text
    assert llamadas == esperadas


@pytest.mark.asyncio
async def test_build_ilustra_despues_de_guardar(db_session):
    await _seed_modulo(db_session)
    vistas: list[tuple[str, int]] = []

    async def ilustrar(db, scene):
        n = (await db.execute(select(func.count()).select_from(StoryLibrary))).scalar_one()
        vistas.append((scene, n))  # la fila ya está guardada cuando se ilustra
        return "h" * 64

    n = await build_library(
        db_session, FakeLLM(_json(scene="A café at noon.")),
        language="de", native="es", per_module=1, illustrate=ilustrar,
    )
    assert n == 1
    assert vistas == [("A café at noon.", 1)]


@pytest.mark.asyncio
async def test_build_sobrevive_a_una_ilustracion_que_falla(db_session):
    await _seed_modulo(db_session)

    async def rota(db, scene):
        raise RuntimeError("gemini caído")

    n = await build_library(
        db_session, FakeLLM(_json(scene="A café at noon.")),
        language="de", native="es", per_module=1, illustrate=rota,
    )
    assert n == 1
    count = (await db_session.execute(select(func.count()).select_from(StoryLibrary))).scalar_one()
    assert count == 1
```

- [ ] **Step 2: córrela y mírala fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_portadas_disparadores.py -v`
Expected: FAIL. El monkeypatch no encuentra `illustrate_in_background` en `klara.routers.stories`, y `build_library` rechaza el argumento `illustrate`.

- [ ] **Step 3: la historia nueva.** En `routers/stories.py`, agrega `from klara.services.illustration import illustrate_in_background` a los imports. En `create_story`, justo después del `background.add_task(precache_story, …)` y antes del `return serialized`:

```python
    if result.story.scene:
        background.add_task(illustrate_in_background, settings, result.story.scene)
```

- [ ] **Step 4: la biblioteca.** En `scripts/build_story_library.py`:

a) Imports nuevos:

```python
from klara.models import Illustration
from klara.services.illustration import COST_PER_IMAGE_USD, ensure_illustration
```

b) Parámetro de `build_library`, después de `warm_audio`:

```python
    illustrate: Callable[[AsyncSession, str], Awaitable[str | None]] | None = None,
```

c) Dentro del bucle, después del bloque `if warm_audio is not None: …`:

```python
            if illustrate is not None and draft.scene:
                try:
                    if await illustrate(db, draft.scene):
                        await db.commit()
                except Exception as exc:
                    await db.rollback()
                    log.warning("library.build.illustrate_failed", topic=topic, error=str(exc))
```

d) En `_run`, reemplaza el bloque `async with sessionmaker() as db: …` y el `print` por:

```python
        async def illustrate(db: AsyncSession, scene: str) -> str | None:
            return await ensure_illustration(db, scene, settings=settings)

        sessionmaker = get_sessionmaker()
        async with sessionmaker() as db:
            antes = await _count_illustrations(db)
            # build_library commits per inserted row — nothing left to commit here.
            n = await build_library(
                db, llm, language="de", native="es", per_module=PER_MODULE,
                warm_audio=warm, illustrate=illustrate,
            )
            nuevas = await _count_illustrations(db) - antes
        print(f"Insertadas {n} historia(s) en la librería.")
        print(f"Ilustraciones nuevas: {nuevas} (≈ ${nuevas * COST_PER_IMAGE_USD:.2f}).")
```

e) Y el helper, encima de `_run`:

```python
async def _count_illustrations(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(Illustration))).scalar_one()
```

Si `func` no está importado en ese archivo, súmalo al `from sqlalchemy import …`.

- [ ] **Step 5: córrela y mírala pasar, con las vecinas**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_portadas_disparadores.py tests/test_build_library.py tests/test_create_story_module.py -v`
Expected: PASS en todo.

- [ ] **Step 6: commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/routers/stories.py backend/src/klara/scripts/build_story_library.py backend/tests/test_portadas_disparadores.py
git commit -m "feat(portadas): la ilustración se dibuja al crear la historia y al construir la biblioteca" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `GET /today`

**Files:**
- Create: `backend/src/klara/schemas/today.py`, `backend/src/klara/services/today.py`
- Create: `backend/src/klara/routers/today.py` (la escribe Claude: es la validación de `since` y la sesión)
- Modify: `backend/src/klara/main.py`
- Test: `backend/tests/test_today.py`

**Interfaces:**
- Consumes: `illustration_hash` e `illustration_path` (tarea 3); `subtitle` y `scene` (tareas 1 y 5); `pick_library_entry` y `read_active_module`, que ya existen.
- Produces: `GET /api/v1/today?since=` → `TodayOut`, y `klara.services.today.build_today(db, user, *, since, now=None) -> TodayOut`.

- [ ] **Step 1: escribe la prueba que falla**

```python
"""GET /today (spec §2): las cuatro paradas, el «estás aquí», la historia del
panel, la frase de Pronunciar y las fichas que vencen, todo desde `since`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from klara.models import (
    Illustration, Module, PronunciationAttempt, Review, SpeakTurn, Story, StoryLibrary,
    StoryView, User, UserCard, VocabItem,
)
from klara.models.enums import CEFRLevel, ReviewRating
from klara.services.illustration import illustration_hash

AHORA = datetime.now(UTC).replace(microsecond=0)
SINCE = AHORA - timedelta(hours=3)
ANTES = SINCE - timedelta(seconds=1)
CONTENT = {"sentences": [
    {"target": "Der Bäcker öffnet um acht.", "native": "El panadero abre a las ocho."},
]}
EMAIL = "hoy@example.com"


async def _login(client, seed_invite) -> str:
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": EMAIL, "password": "hunter2hunter2", "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": EMAIL, "password": "hunter2hunter2"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def _yo(db) -> User:
    return (await db.execute(select(User).where(User.email == EMAIL))).scalar_one()


async def _hoy(client, cookie) -> dict:
    resp = await client.get(
        "/api/v1/today", params={"since": SINCE.isoformat()}, headers={"Cookie": cookie}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _story(user: User, **kw) -> Story:
    base = dict(
        user_id=user.id, level=CEFRLevel.A2, target_language="de", native_language="es",
        title="Die Bäckerei am Samstag", content=CONTENT, target_vocab_item_ids=[],
    )
    return Story(**{**base, **kw})


def _intento(user: User, story: Story, cuando: datetime) -> PronunciationAttempt:
    return PronunciationAttempt(
        user_id=user.id, story_id=story.id, sentence_index=0,
        reference_text="x", overall_score=80.0, attempted_at=cuando,
    )


def _turno(user: User, cuando: datetime) -> SpeakTurn:
    return SpeakTurn(
        user_id=user.id, client_session_id=uuid.uuid4(), turn_index=0, language="de",
        focus_sound="ch", recognized_text="hallo", created_at=cuando,
    )


async def _ficha(db, user: User, next_review_at: datetime | None = None) -> UserCard:
    vocab = VocabItem(lemma=f"wort-{uuid.uuid4().hex[:8]}")
    db.add(vocab)
    await db.flush()
    card = UserCard(user_id=user.id, vocab_item_id=vocab.id, next_review_at=next_review_at)
    db.add(card)
    await db.flush()
    return card


@pytest.mark.asyncio
async def test_since_fuera_de_rango_es_422(client, seed_invite):
    cookie = await _login(client, seed_invite)
    for since in (
        SINCE.replace(tzinfo=None).isoformat(),        # sin zona
        (AHORA + timedelta(minutes=5)).isoformat(),    # en el futuro
        (AHORA - timedelta(hours=49)).isoformat(),     # más de 48 h
    ):
        resp = await client.get("/api/v1/today", params={"since": since}, headers={"Cookie": cookie})
        assert resp.status_code == 422, since


@pytest.mark.asyncio
async def test_sin_sesion_es_401(client):
    resp = await client.get("/api/v1/today", params={"since": SINCE.isoformat()})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cuenta_nueva(client, seed_invite):
    cookie = await _login(client, seed_invite)
    body = await _hoy(client, cookie)
    assert body["steps"] == {"read": False, "pronounce": False, "speak": False, "review": True}
    assert body["now"] == "read"
    assert body["story"]["state"] == "request" and body["story"]["title"] is None
    assert (body["sentence"], body["module"], body["due"]) == (None, None, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("cuando, hecho", [(ANTES, False), (SINCE, True)], ids=["antes", "en-since"])
async def test_borde_de_since(client, seed_invite, db_session, cuando, hecho):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    story = _story(user)
    db_session.add(story)
    await db_session.flush()
    card = await _ficha(db_session, user, next_review_at=AHORA - timedelta(days=1))  # vence
    db_session.add_all([
        StoryView(story_id=story.id, user_id=user.id, finished_at=cuando),
        _intento(user, story, cuando),
        _turno(user, cuando),
        Review(user_card_id=card.id, user_id=user.id, rating=ReviewRating.GOOD,
               channel="recall", reviewed_at=cuando),
    ])
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["steps"] == {"read": hecho, "pronounce": hecho, "speak": hecho, "review": hecho}
    assert body["due"] == 1


@pytest.mark.asyncio
async def test_pronunciar_no_marca_repasar(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    card = await _ficha(db_session, user)  # sin fecha: vence
    db_session.add(Review(user_card_id=card.id, user_id=user.id, rating=ReviewRating.GOOD,
                          channel="pronunciation", reviewed_at=AHORA))
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["steps"]["review"] is False
    assert body["due"] == 1


@pytest.mark.asyncio
async def test_estas_aqui_es_la_primera_que_falta(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    story = _story(user)
    db_session.add(story)
    await db_session.flush()
    db_session.add_all([
        StoryView(story_id=story.id, user_id=user.id, finished_at=AHORA),
        _intento(user, story, AHORA),
    ])
    await db_session.commit()
    assert (await _hoy(client, cookie))["now"] == "speak"

    db_session.add(_turno(user, AHORA))
    await db_session.commit()
    assert (await _hoy(client, cookie))["now"] is None  # repasar ya estaba hecho: no vence nada


@pytest.mark.asyncio
async def test_historia_terminada_hoy(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    story = _story(user, subtitle="Una panadería, un sábado a las ocho.")
    db_session.add(story)
    await db_session.flush()
    db_session.add(StoryView(story_id=story.id, user_id=user.id, finished_at=AHORA))
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["story"]["state"] == "done"
    assert body["story"]["id"] == str(story.id)
    assert body["story"]["subtitle"] == "Una panadería, un sábado a las ocho."
    assert body["sentence"] == {
        "target": "Der Bäcker öffnet um acht.", "native": "El panadero abre a las ocho.",
    }


@pytest.mark.asyncio
async def test_continuar_solo_mira_la_mas_reciente(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    vieja = _story(user, title="Die alte Geschichte", created_at=AHORA - timedelta(days=5))
    nueva = _story(user, title="Die neue Geschichte", created_at=AHORA - timedelta(days=1))
    db_session.add_all([vieja, nueva])
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert (body["story"]["state"], body["story"]["title"]) == ("continue", "Die neue Geschichte")

    # Si la más reciente se terminó ayer, la vieja abandonada no vuelve.
    db_session.add(StoryView(story_id=nueva.id, user_id=user.id, finished_at=AHORA - timedelta(days=1)))
    await db_session.commit()
    body = await _hoy(client, cookie)
    assert body["story"]["state"] == "request"
    assert body["sentence"]["target"] == "Der Bäcker öffnet um acht."


@pytest.mark.asyncio
async def test_nueva_de_la_biblioteca_sin_reclamar(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    module = Module(id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A2, sequence_order=1,
                    title="En la panadería", can_dos=[], grammatical_focus=[])
    db_session.add(module)
    await db_session.flush()
    entry = StoryLibrary(
        module_id=module.id, language="de", native_language="es", level=CEFRLevel.A2,
        title="Die Bäckerei am Samstag", content=CONTENT, target_vocab_item_ids=[],
        source="seed", content_hash="9" * 64, subtitle="Una panadería.",
        scene="A small bakery at dawn.",
    )
    db_session.add(entry)
    user.current_module_id = module.id
    await db_session.commit()

    body = await _hoy(client, cookie)
    assert body["story"] == {
        "state": "new", "id": None, "library_entry_id": str(entry.id),
        "module_id": str(module.id), "title": "Die Bäckerei am Samstag",
        "subtitle": "Una panadería.", "illustration_path": None,
    }
    assert body["module"] == {"id": str(module.id), "title": "En la panadería", "cefr_level": "A2"}
    assert (await db_session.execute(select(Story))).scalars().all() == []  # mirar no reclama

    h = illustration_hash("A small bakery at dawn.")
    db_session.add(Illustration(hash=h, scene="A small bakery at dawn.", style_version=1, model="m",
                                mime_type="image/jpeg", image_data=b"x", size_bytes=1))
    await db_session.commit()
    assert (await _hoy(client, cookie))["story"]["illustration_path"] == f"/illustrations/{h}"


@pytest.mark.asyncio
async def test_vencen_exactas_con_mas_de_50(client, seed_invite, db_session):
    cookie = await _login(client, seed_invite)
    user = await _yo(db_session)
    for _ in range(55):
        await _ficha(db_session, user)
    await _ficha(db_session, user, next_review_at=AHORA + timedelta(days=2))  # esta no vence
    await db_session.commit()
    assert (await _hoy(client, cookie))["due"] == 55
```

- [ ] **Step 2: córrela y mírala fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_today.py -v`
Expected: FAIL. `/api/v1/today` da 404 (la ruta no existe).

- [ ] **Step 3: los esquemas**, en `backend/src/klara/schemas/today.py`:

```python
"""La respuesta de GET /today (spec 2026-09-30 §2.3)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Step = Literal["read", "pronounce", "speak", "review"]


class TodaySteps(BaseModel):
    read: bool
    pronounce: bool
    speak: bool
    review: bool


class TodayStory(BaseModel):
    state: Literal["done", "continue", "new", "request"]
    id: UUID | None = None
    library_entry_id: UUID | None = None
    module_id: UUID | None = None
    title: str | None = None
    subtitle: str | None = None
    illustration_path: str | None = None


class TodaySentence(BaseModel):
    target: str
    native: str


class TodayModule(BaseModel):
    id: UUID
    title: str
    cefr_level: str


class TodayOut(BaseModel):
    now: Step | None
    steps: TodaySteps
    story: TodayStory
    sentence: TodaySentence | None
    due: int
    module: TodayModule | None
```

- [ ] **Step 4: las reglas**, en `backend/src/klara/services/today.py`:

```python
"""El día de Hoy (spec 2026-09-30 §2.2): qué paradas están hechas desde `since`,
cuál sigue y con qué historia. Solo lee, y todo sale de tablas que ya existen."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.curriculum.library import pick_library_entry
from klara.curriculum.modules import read_active_module
from klara.models import (
    Illustration, Module, PronunciationAttempt, Review, SpeakTurn, Story, StoryView, User,
    UserCard,
)
from klara.schemas.today import TodayModule, TodayOut, TodaySentence, TodaySteps, TodayStory
from klara.services.illustration import illustration_hash, illustration_path, normalize_scene

ORDER = ("read", "pronounce", "speak", "review")


async def _hay(db: AsyncSession, stmt) -> bool:
    return bool((await db.execute(select(exists(stmt)))).scalar())


async def _illustration_for(db: AsyncSession, scene: str | None) -> str | None:
    if not normalize_scene(scene):
        return None
    h = illustration_hash(scene)
    found = (await db.execute(select(Illustration.hash).where(Illustration.hash == h))).first()
    return illustration_path(h) if found else None


def _first_sentence(content: dict | None) -> TodaySentence | None:
    for s in (content or {}).get("sentences") or []:
        target = (s.get("target") or "").strip()
        native = (s.get("native") or "").strip()
        if target and native:
            return TodaySentence(target=target, native=native)
    return None


async def _from_story(db: AsyncSession, story: Story, state: str) -> TodayStory:
    return TodayStory(
        state=state,
        id=story.id,
        module_id=story.module_id,
        title=story.title,
        subtitle=story.subtitle,
        illustration_path=await _illustration_for(db, story.scene),
    )


async def _story_of_the_day(
    db: AsyncSession,
    user: User,
    *,
    read_done: bool,
    last_finished: Story | None,
    module: Module | None,
) -> TodayStory:
    # 1. La historia terminada hoy.
    if read_done and last_finished is not None:
        return await _from_story(db, last_finished, "done")
    # 2. La más reciente, si no está terminada. Solo esa: una vieja abandonada no vuelve.
    latest = (
        await db.execute(
            select(Story).where(Story.user_id == user.id).order_by(Story.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if latest is not None and not await _hay(
        db,
        select(StoryView.id).where(
            StoryView.story_id == latest.id, StoryView.finished_at.is_not(None)
        ),
    ):
        return await _from_story(db, latest, "continue")
    # 3. La próxima de la biblioteca del módulo activo, sin reclamarla.
    if module is not None:
        entry = await pick_library_entry(
            db, user_id=user.id, module_id=module.id, native_language=user.native_language
        )
        if entry is not None:
            return TodayStory(
                state="new",
                library_entry_id=entry.id,
                module_id=module.id,
                title=entry.title,
                subtitle=entry.subtitle,
                illustration_path=await _illustration_for(db, entry.scene),
            )
    # 4. Nada que proponer: que se la pida a Klara.
    return TodayStory(state="request")


async def build_today(
    db: AsyncSession, user: User, *, since: datetime, now: datetime | None = None
) -> TodayOut:
    now = now or datetime.now(UTC)
    due = (
        await db.execute(
            select(func.count())
            .select_from(UserCard)
            .where(
                UserCard.user_id == user.id,
                or_(UserCard.next_review_at.is_(None), UserCard.next_review_at <= now),
            )
        )
    ).scalar_one()
    last_view = (
        await db.execute(
            select(StoryView)
            .where(StoryView.user_id == user.id, StoryView.finished_at.is_not(None))
            .order_by(StoryView.finished_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_finished = await db.get(Story, last_view.story_id) if last_view else None

    steps = TodaySteps(
        read=last_view is not None and last_view.finished_at >= since,
        pronounce=await _hay(
            db,
            select(PronunciationAttempt.id).where(
                PronunciationAttempt.user_id == user.id,
                PronunciationAttempt.attempted_at >= since,
            ),
        ),
        speak=await _hay(
            db,
            select(SpeakTurn.id).where(SpeakTurn.user_id == user.id, SpeakTurn.created_at >= since),
        ),
        # Solo el canal "recall": la práctica de pronunciación también escribe reviews.
        review=due == 0
        or await _hay(
            db,
            select(Review.id).where(
                Review.user_id == user.id,
                Review.channel == "recall",
                Review.reviewed_at >= since,
            ),
        ),
    )
    module = await read_active_module(db, user)
    return TodayOut(
        now=next((s for s in ORDER if not getattr(steps, s)), None),
        steps=steps,
        story=await _story_of_the_day(
            db, user, read_done=steps.read, last_finished=last_finished, module=module
        ),
        sentence=_first_sentence(last_finished.content) if last_finished else None,
        due=due,
        module=TodayModule(id=module.id, title=module.title, cefr_level=module.cefr_level.value)
        if module
        else None,
    )
```

- [ ] **Step 5: el router** (Claude), en `backend/src/klara/routers/today.py`:

```python
"""GET /today: el lobby en una sola llamada (spec 2026-09-30 §2)."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

from klara.dependencies import CurrentUser, DBSession
from klara.schemas.today import TodayOut
from klara.services.today import build_today

router = APIRouter(prefix="/today", tags=["today"])

MAX_PAST = timedelta(hours=48)
MAX_FUTURE = timedelta(minutes=1)


@router.get("", response_model=TodayOut)
async def get_today(db: DBSession, user: CurrentUser, since: datetime = Query(...)) -> TodayOut:
    """`since` es la medianoche local del dispositivo; «hoy» es el día del usuario."""
    now = datetime.now(UTC)
    if since.tzinfo is None or since > now + MAX_FUTURE or since < now - MAX_PAST:
        raise HTTPException(status_code=422, detail="today.since_out_of_range")
    return await build_today(db, user, since=since, now=now)
```

- [ ] **Step 6: regístralo en `main.py`.** Agrega `today,` al bloque de `from klara.routers import (...)`, entre `taller,` y `tts,`, y esta línea después de la de `illustrations`:

```python
    app.include_router(today.router, prefix="/api/v1")
```

- [ ] **Step 7: córrela y mírala pasar**

Run: el mismo comando del paso 2.
Expected: PASS (11 tests).

- [ ] **Step 8: commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/schemas/today.py backend/src/klara/services/today.py backend/src/klara/routers/today.py backend/src/klara/main.py backend/tests/test_today.py
git commit -m "feat(hoy): GET /today calcula el día con la actividad que ya se guarda" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: El backfill de portadas

**Files:**
- Create: `backend/src/klara/scripts/backfill_portadas.py`
- Test: `backend/tests/test_backfill_portadas.py`

**Interfaces:**
- Consumes: `ensure_illustration`, `illustration_hash`, `normalize_scene` y `COST_PER_IMAGE_USD` (tarea 3); `trim_text`, `SUBTITLE_MAX`, `SCENE_MAX` y `_extract_json` (tarea 5 y `story_gen`).
- Produces: `async backfill(db, llm, *, settings, dry_run, limit, only_library, illustrate=ensure_illustration) -> dict[str, int]`, con las claves `library_texts`, `cloned_texts`, `own_texts`, `images`, `images_max` y `failed`. Se corre con `python -m klara.scripts.backfill_portadas [--dry-run] [--limit N] [--only-library]`.

- [ ] **Step 1: escribe la prueba que falla**

```python
"""scripts/backfill_portadas.py (spec §3.4): primero los textos, después una
imagen por escena distinta. --dry-run no escribe ni llama. Es idempotente."""

from __future__ import annotations

import json
import uuid

import pytest

from klara.config import get_settings
from klara.llm.base import LLMResponse
from klara.models import Illustration, Module, Story, StoryLibrary, User
from klara.models.enums import CEFRLevel
from klara.scripts.backfill_portadas import backfill
from klara.services.illustration import illustration_hash

CONTENT = {"sentences": [
    {"target": "Der Bäcker öffnet um acht.", "native": "El panadero abre a las ocho."},
]}


class TextosLLM:
    def __init__(self, respuestas: list[str]) -> None:
        self.respuestas = list(respuestas)
        self.llamadas = 0

    async def complete(self, *, messages, model=None, max_tokens=1024, temperature=0.7, response_format=None):
        self.llamadas += 1
        return LLMResponse(content=self.respuestas.pop(0), model="fake", provider="fake", cost_usd=0.0001)

    async def stream(self, *, messages, model=None, max_tokens=1024, temperature=0.7):
        raise NotImplementedError


class Ilustrador:
    """ensure_illustration falso: guarda una fila por escena y cuenta las llamadas."""

    def __init__(self) -> None:
        self.escenas: list[str] = []

    async def __call__(self, db, scene, *, settings):
        self.escenas.append(scene)
        h = illustration_hash(scene)
        db.add(Illustration(hash=h, scene=scene, style_version=1, model="fake",
                            mime_type="image/jpeg", image_data=b"x", size_bytes=1))
        await db.flush()
        return h


def _textos(sub: str, scene: str) -> str:
    return json.dumps({"subtitle": sub, "scene": scene})


async def _sembrar(db):
    user = User(
        id=uuid.uuid4(), email=None, hashed_password=None, is_active=True, is_verified=False,
        is_superuser=False, display_name="Ana", level=CEFRLevel.A2, native_language="es",
        target_language="de",
    )
    module = Module(id=uuid.uuid4(), language="de", cefr_level=CEFRLevel.A2, sequence_order=1,
                    title="En la panadería", can_dos=[], grammatical_focus=[])
    db.add_all([user, module])
    await db.flush()
    entry = StoryLibrary(
        module_id=module.id, language="de", native_language="es", level=CEFRLevel.A2,
        title="Die Bäckerei", content=CONTENT, target_vocab_item_ids=[], source="seed",
        content_hash="7" * 64,
    )
    db.add(entry)
    await db.flush()
    clon = Story(user_id=user.id, level=CEFRLevel.A2, target_language="de", native_language="es",
                 title="Die Bäckerei", content=CONTENT, target_vocab_item_ids=[],
                 module_id=module.id, library_source_id=entry.id)
    propia = Story(user_id=user.id, level=CEFRLevel.A2, target_language="de", native_language="es",
                   title="Mein Hund", content=CONTENT, target_vocab_item_ids=[])
    db.add_all([clon, propia])
    await db.commit()
    return entry, clon, propia


async def _correr(db, llm, ilustrador, *, dry_run=False, only_library=False):
    return await backfill(db, llm, settings=get_settings(), dry_run=dry_run, limit=None,
                          only_library=only_library, illustrate=ilustrador)


@pytest.mark.asyncio
async def test_dry_run_no_escribe_ni_llama(db_session):
    entry, _, _ = await _sembrar(db_session)
    llm, ilustrador = TextosLLM([]), Ilustrador()
    stats = await _correr(db_session, llm, ilustrador, dry_run=True)
    assert (llm.llamadas, ilustrador.escenas) == (0, [])
    assert (stats["library_texts"], stats["own_texts"], stats["images_max"]) == (1, 1, 2)
    await db_session.refresh(entry)
    assert (entry.subtitle, entry.scene) == (None, None)


@pytest.mark.asyncio
async def test_corrida_real_y_segunda_vuelta(db_session):
    entry, clon, propia = await _sembrar(db_session)
    llm = TextosLLM([_textos("Una panadería.", "A small bakery at dawn."),
                     _textos("Mi perro.", "A dog in a park.")])
    ilustrador = Ilustrador()
    stats = await _correr(db_session, llm, ilustrador)
    for fila in (entry, clon, propia):
        await db_session.refresh(fila)
    assert (entry.subtitle, entry.scene) == ("Una panadería.", "A small bakery at dawn.")
    assert (clon.subtitle, clon.scene) == ("Una panadería.", "A small bakery at dawn.")  # sin LLM
    assert (propia.subtitle, propia.scene) == ("Mi perro.", "A dog in a park.")
    assert llm.llamadas == 2
    assert sorted(ilustrador.escenas) == ["A dog in a park.", "A small bakery at dawn."]
    assert (stats["images"], stats["failed"]) == (2, 0)

    segunda = await _correr(db_session, TextosLLM([]), Ilustrador())
    assert (segunda["library_texts"], segunda["own_texts"], segunda["images"]) == (0, 0, 0)


@pytest.mark.asyncio
async def test_json_invalido_no_frena_a_las_demas(db_session):
    _, _, propia = await _sembrar(db_session)
    llm = TextosLLM(["esto no es json", _textos("Mi perro.", "A dog in a park.")])
    stats = await _correr(db_session, llm, Ilustrador())
    await db_session.refresh(propia)
    assert stats["failed"] == 1
    assert propia.scene == "A dog in a park."


@pytest.mark.asyncio
async def test_only_library_no_toca_historias(db_session):
    _, clon, propia = await _sembrar(db_session)
    llm = TextosLLM([_textos("Una panadería.", "A small bakery at dawn.")])
    await _correr(db_session, llm, Ilustrador(), only_library=True)
    await db_session.refresh(clon)
    await db_session.refresh(propia)
    assert (clon.scene, propia.scene) == (None, None)
```

- [ ] **Step 2: córrela y mírala fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_backfill_portadas.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'klara.scripts.backfill_portadas'`.

- [ ] **Step 3: implementa `backend/src/klara/scripts/backfill_portadas.py`**

```python
"""Backfill de portadas: subtítulo, escena e ilustración para lo que ya existe.

En la caja:
    docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
        python -m klara.scripts.backfill_portadas --dry-run
    ... y sin --dry-run para gastar de verdad (--limit N, --only-library).

Fase 1, textos. Las entradas de la biblioteca sin subtítulo o escena se los
piden a la LLM de historias. Las historias clonadas los copian de su entrada,
sin LLM. Las historias propias sin textos hacen la misma llamada que la
biblioteca. Fase 2, imágenes: cada escena distinta sin fila pasa por
ensure_illustration, de a una. Se puede volver a correr: salta lo que ya está.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.config import Settings, get_settings
from klara.db import dispose_engine, get_sessionmaker, init_engine
from klara.i18n import language_label
from klara.llm.base import LLMClient, Message
from klara.llm.litellm_impl import LiteLLMClient
from klara.models import Illustration, Story, StoryLibrary
from klara.services.illustration import (
    COST_PER_IMAGE_USD,
    ensure_illustration,
    illustration_hash,
    normalize_scene,
)
from klara.services.story_gen import SCENE_MAX, SUBTITLE_MAX, _extract_json, trim_text

log = structlog.get_logger(__name__)

PORTADA_PROMPT = """Te paso una micro-historia en {target_label} con su traducción al {native_label}.
Devuelve SOLO JSON válido con este esquema, sin texto extra:
{{
  "subtitle": "una línea en {native_label}, 70 caracteres o menos, que diga de qué va la escena sin contar el final",
  "scene": "la escena principal descrita EN INGLÉS para un ilustrador, 300 caracteres o menos: lugar, momento del día, objetos y luz. Sin texto, letreros, marcas ni personas reconocibles"
}}

Título: {title}
Historia:
{sentences}"""

Illustrate = Callable[..., Awaitable[str | None]]


async def portada_texts(
    llm: LLMClient, *, title: str, content: dict, target_language: str, native_language: str
) -> tuple[str | None, str | None]:
    sentences = "\n".join(
        f"- {s.get('target', '')} ({s.get('native', '')})" for s in content.get("sentences") or []
    )
    prompt = PORTADA_PROMPT.format(
        target_label=language_label(target_language),
        native_label=language_label(native_language),
        title=title,
        sentences=sentences,
    )
    resp = await llm.complete(
        messages=[Message("user", prompt)],
        max_tokens=400,
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    data: dict[str, Any] = _extract_json(resp.content)
    return trim_text(data.get("subtitle"), SUBTITLE_MAX), trim_text(data.get("scene"), SCENE_MAX)


async def _textos(db: AsyncSession, llm: LLMClient, filas, *, dry_run: bool, stats: dict) -> int:
    hechos = 0
    for fila in filas:
        if dry_run:
            hechos += 1
            continue
        target = fila.target_language if isinstance(fila, Story) else fila.language
        try:
            sub, scene = await portada_texts(
                llm, title=fila.title, content=fila.content or {},
                target_language=target, native_language=fila.native_language,
            )
        except Exception as exc:
            log.warning("backfill.texts_failed", id=str(fila.id), error=str(exc))
            stats["failed"] += 1
            continue
        if scene is None:
            stats["failed"] += 1
            continue
        fila.subtitle = fila.subtitle or sub
        fila.scene = fila.scene or scene
        await db.commit()
        hechos += 1
    return hechos


async def backfill(
    db: AsyncSession,
    llm: LLMClient,
    *,
    settings: Settings,
    dry_run: bool,
    limit: int | None,
    only_library: bool,
    illustrate: Illustrate = ensure_illustration,
) -> dict[str, int]:
    stats = {"library_texts": 0, "cloned_texts": 0, "own_texts": 0,
             "images": 0, "images_max": 0, "failed": 0}
    sin_textos = or_(StoryLibrary.subtitle.is_(None), StoryLibrary.scene.is_(None))
    entradas = (
        await db.execute(
            select(StoryLibrary).where(sin_textos).order_by(StoryLibrary.created_at).limit(limit)
        )
    ).scalars().all()
    stats["library_texts"] = await _textos(db, llm, entradas, dry_run=dry_run, stats=stats)

    if not only_library:
        if not dry_run:
            clones = (
                await db.execute(
                    select(Story, StoryLibrary)
                    .join(StoryLibrary, Story.library_source_id == StoryLibrary.id)
                    .where(
                        or_(Story.subtitle.is_(None), Story.scene.is_(None)),
                        StoryLibrary.scene.is_not(None),
                    )
                )
            ).all()
            for story, entry in clones:
                story.subtitle = story.subtitle or entry.subtitle
                story.scene = story.scene or entry.scene
                stats["cloned_texts"] += 1
            await db.commit()
        propias = (
            await db.execute(
                select(Story)
                .where(
                    Story.library_source_id.is_(None),
                    or_(Story.subtitle.is_(None), Story.scene.is_(None)),
                )
                .order_by(Story.created_at)
                .limit(limit)
            )
        ).scalars().all()
        stats["own_texts"] = await _textos(db, llm, propias, dry_run=dry_run, stats=stats)

    escenas = [s for (s,) in (await db.execute(
        select(StoryLibrary.scene).where(StoryLibrary.scene.is_not(None))
    )).all()]
    if not only_library:
        escenas += [s for (s,) in (await db.execute(
            select(Story.scene).where(Story.scene.is_not(None))
        )).all()]
    hechas = set((await db.execute(select(Illustration.hash))).scalars().all())
    unicas = {normalize_scene(s) for s in escenas} - {""}
    faltan = sorted(s for s in unicas if illustration_hash(s) not in hechas)
    if limit is not None:
        faltan = faltan[:limit]
    if dry_run:
        # Techo: las escenas sin imagen que ya existen, más una por cada texto que
        # se generaría. Los clones comparten la escena de su entrada y no suman.
        stats["images_max"] = len(faltan) + stats["library_texts"] + stats["own_texts"]
        return stats
    for escena in faltan:
        if await illustrate(db, escena, settings=settings):
            await db.commit()
            stats["images"] += 1
        else:
            stats["failed"] += 1
    return stats


def _informe(stats: dict[str, int], *, dry_run: bool) -> str:
    textos = stats["library_texts"] + stats["own_texts"]
    if dry_run:
        return (
            f"En seco. Textos a generar: {textos} (biblioteca {stats['library_texts']}, "
            f"propias {stats['own_texts']}); centavos en DeepSeek.\n"
            f"Imágenes: como mucho {stats['images_max']} × ${COST_PER_IMAGE_USD} = "
            f"${stats['images_max'] * COST_PER_IMAGE_USD:.2f}."
        )
    return (
        f"Textos: {textos} generados y {stats['cloned_texts']} copiados de su entrada. "
        f"Imágenes: {stats['images']} (≈ ${stats['images'] * COST_PER_IMAGE_USD:.2f}). "
        f"Fallos: {stats['failed']} (se puede volver a correr)."
    )


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    init_engine(settings)
    try:
        llm = LiteLLMClient(
            settings,
            default_model=settings.llm_story_model,
            default_extra_body=settings.llm_story_extra_body,
        )
        async with get_sessionmaker()() as db:
            stats = await backfill(
                db, llm, settings=settings, dry_run=args.dry_run,
                limit=args.limit, only_library=args.only_library,
            )
        print(_informe(stats, dry_run=args.dry_run))
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill de subtítulos, escenas e ilustraciones.")
    parser.add_argument("--dry-run", action="store_true", help="contar y estimar, sin escribir ni llamar")
    parser.add_argument("--limit", type=int, default=None, help="tope por fase")
    parser.add_argument("--only-library", action="store_true", help="solo la biblioteca")
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: córrela y mírala pasar**

Run: el mismo comando del paso 2.
Expected: PASS (4 tests).

- [ ] **Step 5: commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests
git add backend/src/klara/scripts/backfill_portadas.py backend/tests/test_backfill_portadas.py
git commit -m "feat(portadas): backfill de subtítulos, escenas e ilustraciones, con --dry-run" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: El view-model de Hoy y la pestaña activa (funciones puras)

**Files:**
- Modify: `frontend/src/api/types.ts` (tipos nuevos al final), `frontend/src/api/client.ts` (entrada `today` en `api`, junto a `listModules`)
- Create: `frontend/src/lib/hoyView.ts`, `frontend/src/lib/hoyView.test.ts`
- Create: `frontend/src/lib/tabs.ts`, `frontend/src/lib/tabs.test.ts`

**Interfaces:**
- Consumes: la respuesta de `GET /today` (tarea 7).
- Produces:
  - `TodayOut`, `TodayStep` y `api.today(since: string): Promise<TodayOut>`
  - En `lib/hoyView.ts`: `buildHoyVM(today: TodayOut | null): HoyVM`, `medianocheLocal(ahora?: Date): string`, `arteSrc(path: string | null): string | null`, `MINUTOS` y los tipos `ParadaId`, `ParadaEstado`, `Accion`, `Parada`, `Panel` y `HoyVM`
  - `tabActiva(pathname: string): "hoy" | "biblioteca" | "mas" | null`

- [ ] **Step 1: los tipos.** Al final de `api/types.ts`:

```ts
/** GET /today (spec 2026-09-30 §2.3). */
export type TodayStep = "read" | "pronounce" | "speak" | "review";

export interface TodayOut {
  now: TodayStep | null;
  steps: Record<TodayStep, boolean>;
  story: {
    state: "done" | "continue" | "new" | "request";
    id: string | null;
    library_entry_id: string | null;
    module_id: string | null;
    title: string | null;
    subtitle: string | null;
    illustration_path: string | null;
  };
  sentence: { target: string; native: string } | null;
  due: number;
  module: { id: string; title: string; cefr_level: string } | null;
}
```

Y en `api/client.ts`, dentro de `export const api = {`, junto a `listModules` (agrega `TodayOut` al `import type` de `./types`):

```ts
  today: (since: string) => request<TodayOut>(`/today?since=${encodeURIComponent(since)}`),
```

- [ ] **Step 2: escribe las pruebas que fallan**

`frontend/src/lib/hoyView.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { TodayOut } from "../api/types";
import { apiBase } from "./apiBase";
import { buildHoyVM, medianocheLocal } from "./hoyView";

const SIN_HISTORIA: TodayOut["story"] = {
  state: "request", id: null, library_entry_id: null, module_id: null,
  title: null, subtitle: null, illustration_path: null,
};

const hoy = (over: Partial<TodayOut> = {}): TodayOut => ({
  now: "read",
  steps: { read: false, pronounce: false, speak: false, review: false },
  story: SIN_HISTORIA,
  sentence: null,
  due: 12,
  module: null,
  ...over,
});

describe("buildHoyVM", () => {
  it("sin datos: cuatro paradas pendientes, sin panel, 15 minutos", () => {
    const vm = buildHoyVM(null);
    expect(vm.paradas.map((p) => p.estado)).toEqual(["pending", "pending", "pending", "pending"]);
    expect(vm.panel).toBeNull();
    expect(vm.minutos).toBe(15);
    expect(vm.paradas[0].accion).toEqual({ tipo: "ir", to: "/story/new" });
  });

  it("historia nueva de la biblioteca: el panel la reclama y trae su ilustración", () => {
    const vm = buildHoyVM(hoy({
      story: {
        state: "new", id: null, library_entry_id: "e1", module_id: "m1",
        title: "Die Bäckerei am Samstag", subtitle: "Una panadería.", illustration_path: "/illustrations/abc",
      },
    }));
    expect(vm.paradas[0].estado).toBe("now");
    expect(vm.panel).toEqual({
      tipo: "leer", estado: "new", titulo: "Die Bäckerei am Samstag", subtitulo: "Una panadería.",
      arte: `${apiBase()}/illustrations/abc`, accion: { tipo: "reclamar", moduleId: "m1" },
    });
  });

  it("una historia pedida fuera de un módulo se abre, nunca se reclama, y sin arte queda tipográfica", () => {
    const vm = buildHoyVM(hoy({
      story: { ...SIN_HISTORIA, state: "continue", id: "s1", title: "Mein Hund" },
    }));
    expect(vm.panel).toMatchObject({ tipo: "leer", arte: null, accion: { tipo: "ir", to: "/estudiar/s1" } });
  });

  it("sin historia ni biblioteca, a /story/new", () => {
    expect(buildHoyVM(hoy()).panel).toMatchObject({
      tipo: "leer", estado: "request", accion: { tipo: "ir", to: "/story/new" },
    });
  });

  it("Leer hecha: la fila muestra la historia y el panel pasa a Pronunciar con su frase", () => {
    const vm = buildHoyVM(hoy({
      now: "pronounce",
      steps: { read: true, pronounce: false, speak: false, review: false },
      story: { ...SIN_HISTORIA, state: "done", id: "s1", module_id: "m1", title: "Die Bäckerei am Samstag" },
      sentence: { target: "Der Bäcker öffnet um acht.", native: "El panadero abre a las ocho." },
    }));
    expect(vm.paradas[0]).toMatchObject({
      estado: "done", historia: "Die Bäckerei am Samstag", accion: { tipo: "ir", to: "/estudiar/s1" },
    });
    expect(vm.panel).toEqual({
      tipo: "pronunciar",
      frase: { target: "Der Bäcker öffnet um acht.", native: "El panadero abre a las ocho." },
      accion: { tipo: "ir", to: "/pronunciar" },
    });
    expect(vm.minutos).toBe(12);
  });

  it("Repasar hecha con fichas vencidas: HECHO, y el número sigue a la vista", () => {
    const vm = buildHoyVM(hoy({ steps: { read: false, pronounce: false, speak: false, review: true }, due: 12 }));
    expect(vm.paradas[3]).toMatchObject({ id: "repasar", estado: "done", vencen: 12 });
  });

  it("todo hecho: sin panel y cero minutos", () => {
    const vm = buildHoyVM(hoy({ now: null, steps: { read: true, pronounce: true, speak: true, review: true }, due: 0 }));
    expect(vm.panel).toBeNull();
    expect(vm.todoHecho).toBe(true);
    expect(vm.minutos).toBe(0);
  });
});

describe("medianocheLocal", () => {
  it("devuelve el instante de la medianoche local del día dado", () => {
    const m = new Date(medianocheLocal(new Date(2026, 8, 30, 17, 40)));
    expect([m.getFullYear(), m.getMonth(), m.getDate(), m.getHours(), m.getMinutes()]).toEqual([2026, 8, 30, 0, 0]);
  });
});
```

`frontend/src/lib/tabs.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { tabActiva } from "./tabs";

describe("tabActiva", () => {
  it.each([
    ["/", "hoy"],
    ["/biblioteca", "biblioteca"],
    ["/curso/aleman", "biblioteca"],
    ["/curso/aleman/mapa", "biblioteca"],
    ["/nuevo", "biblioteca"],
    ["/perfil", "mas"],
    ["/perfil/aprendizaje", "mas"],
    ["/estudiar/s1", null],
  ])("%s → %s", (ruta, tab) => {
    expect(tabActiva(ruta)).toBe(tab);
  });
});
```

- [ ] **Step 3: córrelas y míralas fallar**

Run: `cd frontend && npx vitest run src/lib/hoyView.test.ts src/lib/tabs.test.ts`
Expected: FAIL con `Failed to resolve import "./hoyView"` y `"./tabs"`.

- [ ] **Step 4: implementa `frontend/src/lib/hoyView.ts`**

```ts
import type { TodayOut, TodayStep } from "../api/types";
import { apiBase } from "./apiBase";

/** Las cuatro paradas del recorrido, en el orden fijo del spec §1.2. */
export type ParadaId = "leer" | "pronunciar" | "hablar" | "repasar";
export type ParadaEstado = "now" | "done" | "pending";

const ORDEN: ParadaId[] = ["leer", "pronunciar", "hablar", "repasar"];
const DEL_API: Record<ParadaId, TodayStep> = {
  leer: "read",
  pronunciar: "pronounce",
  hablar: "speak",
  repasar: "review",
};
/** Los minutos de `curso.paso.*.meta`. */
export const MINUTOS: Record<ParadaId, number> = { leer: 3, pronunciar: 4, hablar: 3, repasar: 5 };
const DESTINO: Record<Exclude<ParadaId, "leer">, string> = {
  pronunciar: "/pronunciar",
  hablar: "/chat",
  repasar: "/repaso",
};

export type Accion = { tipo: "ir"; to: string } | { tipo: "reclamar"; moduleId: string };

export interface Parada {
  id: ParadaId;
  estado: ParadaEstado;
  /** Leer: el título de la historia del día, cuando ya se sabe. */
  historia: string | null;
  /** Repasar: las fichas que vencen. Se ve aunque la parada esté hecha. */
  vencen: number | null;
  accion: Accion;
}

export type Panel =
  | {
      tipo: "leer";
      estado: "continue" | "new" | "request";
      titulo: string | null;
      subtitulo: string | null;
      arte: string | null;
      accion: Accion;
    }
  | { tipo: "pronunciar"; frase: { target: string; native: string } | null; accion: Accion }
  | { tipo: "hablar"; accion: Accion }
  | { tipo: "repasar"; vencen: number; accion: Accion };

export interface HoyVM {
  paradas: Parada[];
  panel: Panel | null;
  /** La suma de los minutos de las paradas que faltan. */
  minutos: number;
  todoHecho: boolean;
}

function accionLeer(story: TodayOut["story"] | null): Accion {
  if (story && (story.state === "done" || story.state === "continue") && story.id) {
    return { tipo: "ir", to: `/estudiar/${story.id}` };
  }
  if (story?.state === "new" && story.module_id) return { tipo: "reclamar", moduleId: story.module_id };
  return { tipo: "ir", to: "/story/new" };
}

function accionDe(id: ParadaId, today: TodayOut | null): Accion {
  return id === "leer" ? accionLeer(today?.story ?? null) : { tipo: "ir", to: DESTINO[id] };
}

/** La ruta de la API es relativa a su base, que en la app nativa es absoluta. */
export function arteSrc(path: string | null): string | null {
  return path ? `${apiBase()}${path}` : null;
}

/** El instante de tu medianoche local: desde cuándo cuenta «hoy». */
export function medianocheLocal(ahora: Date = new Date()): string {
  const d = new Date(ahora);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

function panelDe(today: TodayOut): Panel | null {
  switch (today.now) {
    case "read":
      return {
        tipo: "leer",
        // "done" no puede ser la parada actual: si Leer está hecha, `now` es otra.
        estado: today.story.state === "done" ? "continue" : today.story.state,
        titulo: today.story.title,
        subtitulo: today.story.subtitle,
        arte: arteSrc(today.story.illustration_path),
        accion: accionDe("leer", today),
      };
    case "pronounce":
      return { tipo: "pronunciar", frase: today.sentence, accion: accionDe("pronunciar", today) };
    case "speak":
      return { tipo: "hablar", accion: accionDe("hablar", today) };
    case "review":
      return { tipo: "repasar", vencen: today.due, accion: accionDe("repasar", today) };
    default:
      return null;
  }
}

export function buildHoyVM(today: TodayOut | null): HoyVM {
  const paradas: Parada[] = ORDEN.map((id) => {
    const paso = DEL_API[id];
    const estado: ParadaEstado = today?.now === paso ? "now" : today?.steps[paso] ? "done" : "pending";
    return {
      id,
      estado,
      historia: id === "leer" ? (today?.story.title ?? null) : null,
      vencen: id === "repasar" && today ? today.due : null,
      accion: accionDe(id, today),
    };
  });
  return {
    paradas,
    panel: today ? panelDe(today) : null,
    minutos: paradas.filter((p) => p.estado !== "done").reduce((n, p) => n + MINUTOS[p.id], 0),
    todoHecho: today !== null && today.now === null,
  };
}
```

- [ ] **Step 5: implementa `frontend/src/lib/tabs.ts`**

```ts
export type Tab = "hoy" | "biblioteca" | "mas";

/** La pestaña activa de cada ruta (spec §1.1). `/nuevo` se abre desde la estantería. */
export function tabActiva(pathname: string): Tab | null {
  if (pathname === "/") return "hoy";
  if (pathname === "/biblioteca" || pathname === "/nuevo" || pathname.startsWith("/curso/")) {
    return "biblioteca";
  }
  if (pathname.startsWith("/perfil")) return "mas";
  return null;
}
```

- [ ] **Step 6: córrelas y míralas pasar, y corre el typecheck**

Run: `cd frontend && npx vitest run src/lib/hoyView.test.ts src/lib/tabs.test.ts && npm run typecheck`
Expected: PASS (17 tests) y typecheck limpio.

- [ ] **Step 7: commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/lib/hoyView.ts frontend/src/lib/hoyView.test.ts frontend/src/lib/tabs.ts frontend/src/lib/tabs.test.ts
git commit -m "feat(hoy): el view-model del recorrido y la pestaña activa, como funciones puras" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Sistema de diseño — átomos 18 y 19, y `.k-hero__art`

**Files:**
- Modify: `frontend/src/styles/sistema.css`. `.k-hero__art` va dentro de la sección 12, después de `.k-hero__meta strong`. Los átomos 18 y 19 van al final del archivo, antes del bloque `@media (prefers-reduced-motion: reduce)` si hay uno al final; si no, al final.
- Modify: `docs/design/klara-sistema/CONTRATO.md` (dos secciones nuevas después de la 17, y una línea en la 12)
- Modify: `docs/design/klara-sistema/hoja.html` (dos `<section>` nuevas después de `campo-texto`, y una `<figure>` en `bloque-heroe`)
- Modify: `docs/design/klara-sistema/hoja.check.mjs` (`ESTADOS`)

**Interfaces:**
- Produces, para las tareas 12 y 13:
  - `.k-route` con `__stop` (`data-state="now|done|pending"`), `__dot`, `__body`, `__label`, `__row`, `__title`, `__meta`, `__sub` y `__end`
  - `.k-hero__art`
  - `.k-shelf` con `__caption` (`data-accent`)
  - `.k-cover`, con `--new`, `__band`, `__sub`, `__plus` y `__name`

- [ ] **Step 1: los estados obligatorios (la prueba roja).** En `hoja.check.mjs`, dentro de `ESTADOS`, cambia la línea de `bloque-heroe` y agrega dos entradas al final:

```js
  "bloque-heroe": ["activo", "deshabilitado", "quieto", "con-arte"],
  // …
  "recorrido": ["pendiente", "ahora", "hecha", "fin", "compuesto-largo"],
  "estanteria": ["tema", "vencidas", "nuevo", "compuesto-largo"],
```

Run: `PLAYWRIGHT_BROWSERS_PATH=D:/caches/ms-playwright node docs/design/klara-sistema/hoja.check.mjs`
Expected: FAIL. Faltan los átomos `recorrido` y `estanteria`, y el estado `con-arte`.

- [ ] **Step 2: el CSS.** Dentro de la sección 12, después de `.k-hero__meta strong { … }`:

```css
/* La ilustración de la historia (spec 2026-09-30 §1.3): cruza las dos columnas,
   arriba del todo, en 21:9. El héroe es tinta sólida, así que la imagen trae su
   propio papel detrás mientras carga. */
.k-hero__art {
  grid-column: 1 / -1;
  display: block;
  width: 100%;
  max-width: 100%;
  aspect-ratio: 21 / 9;
  object-fit: cover;
  border-radius: var(--r-sm);
  background: var(--paper-2);
  margin-bottom: var(--space-3);
}
```

Al final del archivo, las dos secciones nuevas:

```css
/* ============================================================
   18 · RECORRIDO — .k-route
   Pieza nueva (spec 2026-09-30, Hoy): el plan del día como una línea de
   metro. Una <ol> de paradas: la línea y los puntos los dibuja el átomo; la
   parada actual cuelga el héroe (12), las demás son una fila propia.
   ============================================================ */

.k-route {
  --k-route-rail: 28px;               /* carril: punto de 14px más aire */
  position: relative;
  list-style: none;
  margin: var(--space-3) 0 0;
  padding: 0 0 var(--space-3);
  display: grid;
  gap: var(--space-4);
}

/* La línea: una sola, detrás de los puntos. 3px como el borde del punto, para
   que el punto se lea enhebrado. */
.k-route::before {
  content: "";
  position: absolute;
  left: calc(var(--k-route-rail) / 2 - 1.5px);
  top: 12px;
  bottom: 0;
  width: 3px;
  background: var(--ink);
}

/* El tope: la barra corta de un final de trayecto. */
.k-route::after {
  content: "";
  position: absolute;
  left: calc(var(--k-route-rail) / 2 - 9px);
  bottom: 0;
  width: 18px;
  height: 3px;
  background: var(--ink);
}

.k-route__stop {
  display: grid;
  grid-template-columns: var(--k-route-rail) minmax(0, 1fr);
  column-gap: var(--space-2);
  min-width: 0;
}

.k-route__dot {
  grid-column: 1;
  justify-self: center;
  position: relative;                 /* encima de la línea */
  width: 14px;
  height: 14px;
  margin-top: 6px;                    /* a la altura de la línea de base del título */
  box-sizing: border-box;
  border-radius: 50%;
  border: 3px solid var(--ink);
  background: var(--paper);
}

.k-route__stop[data-state="done"] .k-route__dot { background: var(--ink); }

.k-route__stop[data-state="now"] .k-route__dot {
  border-color: var(--accent);
  background: var(--accent);
  outline: 2px solid var(--accent);
  outline-offset: 3px;
}

.k-route__body {
  grid-column: 2;
  min-width: 0;
}

.k-route__label {
  display: block;
  margin-bottom: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--t-mono);
  letter-spacing: var(--tracking-mark);
  text-transform: uppercase;
  color: var(--accent-ink);
}

/* El héroe dentro de la parada ya no trae su margen de bloque suelto. */
.k-route__body > .k-hero { margin-top: 0; }

.k-route__row {
  grid-column: 2;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: baseline;
  column-gap: var(--space-3);
  min-width: 0;
  min-height: 44px;                   /* §7.2 */
  width: 100%;
  padding: 0;
  border: 0;
  background: none;
  color: var(--ink);
  text-align: left;
  cursor: pointer;
}

.k-route__title {
  font-family: var(--font-serif);
  font-size: var(--t-h3);
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.k-route__stop[data-state="done"] .k-route__title { color: var(--ink-2); }

.k-route__meta {
  font-family: var(--font-mono);
  font-size: var(--t-mono);
  letter-spacing: var(--tracking-mark);
  text-transform: uppercase;
  color: var(--ink-3);
  white-space: nowrap;
}

.k-route__sub {
  grid-column: 1 / -1;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: var(--t-mark);
  line-height: 1.4;
  color: var(--ink-2);
  overflow-wrap: anywhere;
}

.k-route__end {
  margin: var(--space-4) 0 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: var(--t-mark);
  color: var(--ink-2);
}

/* ============================================================
   19 · ESTANTERÍA — .k-shelf + .k-cover
   Pieza nueva (spec 2026-09-30, Biblioteca): los temas como tapas de tela
   sobre una repisa. La tela es CSS sobre tokens, sin imágenes y sin sombra
   (las sombras son de las capas flotantes); el lomo es una franja de luz.
   ============================================================ */

.k-shelf {
  list-style: none;
  margin: var(--space-3) 0 0;
  padding: 0 0 var(--space-3);
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-5) var(--space-3);
  border-bottom: 2px solid var(--ink);   /* la repisa */
}

.k-shelf > li {
  display: grid;
  align-content: start;
  gap: var(--space-2);
  min-width: 0;
}

.k-shelf__caption {
  font-family: var(--font-mono);
  font-size: var(--t-meta);
  letter-spacing: var(--tracking-mark);
  text-transform: uppercase;
  color: var(--ink-3);
  overflow-wrap: anywhere;
}

.k-shelf__caption[data-accent] { color: var(--accent-ink); }

.k-cover {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  aspect-ratio: 2 / 3;
  padding: var(--space-3) var(--space-2);
  border: 0;
  border-radius: var(--r-xs) var(--r-sm) var(--r-sm) var(--r-xs);
  color: var(--paper);
  text-align: center;
  cursor: pointer;
  /* La tela: dos rayados finos cruzados sobre la tinta. */
  background-color: var(--ink);
  background-image:
    repeating-linear-gradient(0deg, color-mix(in srgb, var(--paper) 6%, transparent) 0 1px, transparent 1px 3px),
    repeating-linear-gradient(90deg, color-mix(in srgb, var(--paper) 5%, transparent) 0 1px, transparent 1px 3px);
  transition: transform var(--dur-fast) var(--ease-out);
}

/* El lomo. */
.k-cover::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 6px;
  border-radius: var(--r-xs) 0 0 var(--r-xs);
  background: color-mix(in srgb, var(--paper) 12%, transparent);
}

.k-cover:active { transform: scale(0.985); }

.k-cover__band {
  margin-inline: calc(-1 * var(--space-2));
  padding: var(--space-2) var(--space-1);
  background: var(--accent);
  color: var(--on-accent);
  font-family: var(--font-serif);
  font-size: clamp(15px, 4.4vw, 19px);
  line-height: 1.15;
  overflow-wrap: anywhere;
}

.k-cover__sub {
  font-family: var(--font-mono);
  font-size: var(--t-meta);
  letter-spacing: var(--tracking-mark);
  text-transform: uppercase;
  opacity: 0.72;
  overflow-wrap: anywhere;
}

.k-cover--new {
  color: var(--ink-2);
  background: none;
  border: 1px dashed var(--ink-3);
}

.k-cover--new::before { content: none; }

.k-cover__plus {
  font-family: var(--font-serif);
  font-size: var(--t-h2);
  line-height: 1;
}

.k-cover__name {
  font-family: var(--font-serif);
  font-size: var(--t-body);
  overflow-wrap: anywhere;
}
```

- [ ] **Step 3: el contrato.** En `CONTRATO.md`, dentro de «### 12. Bloque héroe», en **Elementos**, agrega: «`__art` (la ilustración de la historia: 21:9, cruza las dos columnas, arriba del todo; fondo `--paper-2` mientras carga; spec 2026-09-30 §1.3)». Después de la sección «### 17. Campo de texto», antes de «## Orden de borrado seguro», agrega:

````markdown
### 18. Recorrido — `.k-route`

**Reemplaza:** nada, es pieza nueva del spec `2026-09-30-hoy-y-biblioteca` (§1.2). Es la lista del plan de la portada del curso (`Portada.tsx`, filas `.k-row` numeradas 01–04) convertida en línea.

**Elementos:** `__stop` (cada parada, un `<li>`), `__dot` (el punto sobre la línea), `__body` (la columna de la parada actual: rótulo y héroe), `__label` («Estás aquí»), `__row` (la parada cerrada, un `<button>`), `__title`, `__meta`, `__sub` y `__end` (la línea de cierre, hermana de la lista).

**Variantes:** ninguna.

**Estados:** `data-state` en `__stop`. **`pending`**: punto hueco. **`now`**: punto de acento con anillo; la parada lleva `__label` y un `.k-hero` dentro de `__body`. **`done`**: punto lleno; el título baja a `--ink-2` y la meta dice «Hecho». La línea y el tope los dibuja el bloque con `::before` y `::after`.

**Medidas:** carril de 28px (`--k-route-rail`, local al bloque). El punto mide 14px con borde de 3px; la línea mide 3px, como el borde, para que el punto se lea enhebrado. El tope mide 18×3px. Las filas llevan `min-height: 44px` (§7.2). Título en `--t-h3` serif, meta en `--t-mono` mono y subtítulo en `--t-mark` serif cursiva. Entre paradas, `--space-4`.
Literales justificados: los 28px del carril, los 14px y 3px del punto, los 18px del tope, los 6px de `margin-top` del punto (lo bajan a la línea de base del título), los 12px del arranque de la línea (el centro del primer punto) y el `outline-offset` de 3px del punto actual, que es el de la gramática de foco.

**Tokens:** `--ink`, `--ink-2`, `--ink-3`, `--paper`, `--accent`, `--accent-ink`, `--space-2`, `--space-3`, `--space-4`, `--font-serif`, `--font-mono`, `--t-h3`, `--t-mono`, `--t-mark`, `--tracking-mark`.

**Markup canónico:**
```html
<ol class="k-route">
  <li class="k-route__stop" data-state="done">
    <span class="k-route__dot" aria-hidden="true"></span>
    <button type="button" class="k-route__row">
      <span class="k-route__title">Leer</span><span class="k-route__meta">Hecho</span>
      <span class="k-route__sub">Die Bäckerei am Samstag</span>
    </button>
  </li>
  <li class="k-route__stop" data-state="now" aria-current="step">
    <span class="k-route__dot" aria-hidden="true"></span>
    <div class="k-route__body">
      <span class="k-route__label">Estás aquí</span>
      <button type="button" class="k-hero">…</button>
    </div>
  </li>
</ol>
<p class="k-route__end">Mañana, otra historia.</p>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo | nuevo |
|---|---|
| la lista del plan de `Portada.tsx` (`.k-row` con `__n` 01–04) | `.k-route` en `Hoy.tsx`; la portada se queda con el mapa y Género |

**Notas:** la parada actual no es una fila grande: es el héroe (átomo 12) colgado de la línea. Las filas no son `.k-row` porque `.k-row` dibuja su filete, y aquí la estructura la pone la línea: dos filetes en ángulo recto se leían como una tabla. Todas las paradas se tocan en cualquier orden; el orden sugiere, no obliga.

---

### 19. Estantería — `.k-shelf` + `.k-cover`

**Reemplaza:** nada, es pieza nueva del spec `2026-09-30-hoy-y-biblioteca` (§1.4). Sustituye la lista de temas del Inicio viejo (`Inicio.tsx`, filas `.k-row` «Deutsch» y «Nuevo tema»).

**Elementos:** en `.k-shelf`, `__caption` (la línea mono bajo cada tapa). En `.k-cover`: `__band` (la franja con el nombre), `__sub` («Edición Nürnberg»), `__plus` y `__name` (los de la tapa nueva).

**Variantes:** `.k-cover--new`, la tapa punteada de «Nuevo tema».

**Estados:** `data-accent` en `__caption` cuando hay fichas vencidas. La tapa se hunde al pulsar, como el héroe.

**Medidas:** tres tapas por fila, 2:3. La repisa es un filete de 2px de `--ink`. El lomo es una franja de 6px de papel al 12%. La trama son dos rayados de 1px cada 3px, de papel al 6% y al 5%. La franja va en `clamp(15px, 4.4vw, 19px)`.
Literales justificados: la proporción 2:3 (la de un libro), los 2px de la repisa, los 6px del lomo, el rayado de 1px cada 3px y el `clamp` de la franja, que no tiene token porque es la única pieza con un titular dentro de una columna de un tercio.

**Tokens:** `--ink`, `--ink-2`, `--ink-3`, `--paper`, `--accent`, `--accent-ink`, `--on-accent`, `--r-xs`, `--r-sm`, `--space-1` a `--space-5`, `--font-serif`, `--font-mono`, `--t-meta`, `--t-h2`, `--t-body`, `--tracking-mark`, `--dur-fast`, `--ease-out`.

**Markup canónico:**
```html
<ul class="k-shelf">
  <li>
    <button type="button" class="k-cover">
      <span class="k-cover__band">Deutsch</span>
      <span class="k-cover__sub">Edición Nürnberg</span>
    </button>
    <div class="k-bar k-bar--fill">…</div>
    <span class="k-shelf__caption" data-accent="true">A2 · 12 vencen</span>
  </li>
  <li>
    <button type="button" class="k-cover k-cover--new">
      <span class="k-cover__plus" aria-hidden="true">+</span>
      <span class="k-cover__name">Nuevo tema</span>
    </button>
    <span class="k-shelf__caption">Klara arma el plan</span>
  </li>
</ul>
```

**Mapa viejo → nuevo:**

| clase o atributo viejo | nuevo |
|---|---|
| la fila del tema en `Inicio.tsx` (`.k-row` + `.k-bar`) | `.k-cover` + `.k-bar` + `.k-shelf__caption` en `Biblioteca.tsx` |
| la fila «Nuevo tema» (`.k-row` con `__n` «+») | `.k-cover--new` |

**Notas:** en oscuro la tapa se invierte, como el héroe: tela color papel con letras de pizarra. Es la misma decisión que el panel de Hoy (spec §7.3). El bloque «Sigue donde lo dejaste» del mockup C no entra: con un solo tema repetiría lo que ya dice Hoy.
````

- [ ] **Step 4: la hoja.** En `hoja.html`, dentro de `<section … id="bloque-heroe" …>`, antes del `</div>` que cierra `hoja-card__estados`, agrega:

```html
    <figure class="hoja-estado" data-estado="con-arte">
      <figcaption>Con la ilustración de la historia <code>.k-hero__art</code></figcaption>
      <div class="hoja-estado__muestra">
        <button type="button" class="k-hero">
          <span class="k-hero__art" role="img" aria-label="Ilustración de la historia"></span>
          <span class="k-hero__tag"><span>Leer · 3 min</span><span>Empezar</span></span>
          <span class="k-hero__title">Die Bäckerei am Samstag</span>
          <span class="k-hero__arrow" aria-hidden="true">→</span>
          <span class="k-hero__dek">Una panadería, un sábado a las ocho.</span>
        </button>
      </div>
    </figure>
```

Y después de la sección `campo-texto` agrega las dos secciones nuevas:

```html
<section class="hoja-card" id="recorrido" data-atom="recorrido">
  <div class="hoja-card__cabeza"><span class="hoja-card__n">18</span><h2 class="hoja-card__titulo">Recorrido <code>.k-route</code></h2></div>
  <p class="hoja-card__reemplaza"><b>reemplaza</b> la lista del plan de la portada del curso (Portada.tsx, filas 01–04)</p>
  <div class="hoja-card__estados">
    <figure class="hoja-estado" data-estado="pendiente">
      <figcaption>Pendiente <code>data-state="pending"</code></figcaption>
      <div class="hoja-estado__muestra">
        <ol class="k-route">
          <li class="k-route__stop" data-state="pending">
            <span class="k-route__dot" aria-hidden="true"></span>
            <button type="button" class="k-route__row"><span class="k-route__title">Hablar</span><span class="k-route__meta">3 min</span><span class="k-route__sub">Una conversación con Klara</span></button>
          </li>
        </ol>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="ahora">
      <figcaption>Ahora <code>data-state="now"</code>, con el héroe colgado</figcaption>
      <div class="hoja-estado__muestra">
        <ol class="k-route">
          <li class="k-route__stop" data-state="now" aria-current="step">
            <span class="k-route__dot" aria-hidden="true"></span>
            <div class="k-route__body">
              <span class="k-route__label">Estás aquí</span>
              <button type="button" class="k-hero">
                <span class="k-hero__tag"><span>Pronunciar · 4 min</span><span>Empezar</span></span>
                <span class="k-hero__title">„Der Bäcker öffnet um acht.“</span>
                <span class="k-hero__arrow" aria-hidden="true">→</span>
                <span class="k-hero__dek">El panadero abre a las ocho.</span>
              </button>
            </div>
          </li>
        </ol>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="hecha">
      <figcaption>Hecha <code>data-state="done"</code></figcaption>
      <div class="hoja-estado__muestra">
        <ol class="k-route">
          <li class="k-route__stop" data-state="done">
            <span class="k-route__dot" aria-hidden="true"></span>
            <button type="button" class="k-route__row"><span class="k-route__title">Leer</span><span class="k-route__meta">Hecho</span><span class="k-route__sub">Die Bäckerei am Samstag</span></button>
          </li>
        </ol>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="fin">
      <figcaption>Todo hecho, con el cierre <code>.k-route__end</code></figcaption>
      <div class="hoja-estado__muestra">
        <ol class="k-route">
          <li class="k-route__stop" data-state="done"><span class="k-route__dot" aria-hidden="true"></span><button type="button" class="k-route__row"><span class="k-route__title">Hablar</span><span class="k-route__meta">Hecho</span><span class="k-route__sub">Una conversación con Klara</span></button></li>
          <li class="k-route__stop" data-state="done"><span class="k-route__dot" aria-hidden="true"></span><button type="button" class="k-route__row"><span class="k-route__title">Repasar</span><span class="k-route__meta">Hecho</span><span class="k-route__sub">12 fichas por repasar</span></button></li>
        </ol>
        <p class="k-route__end">Listo por hoy. Mañana, otra historia.</p>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="compuesto-largo">
      <figcaption>Compuesto largo: el título parte palabra</figcaption>
      <div class="hoja-estado__muestra">
        <ol class="k-route">
          <li class="k-route__stop" data-state="done"><span class="k-route__dot" aria-hidden="true"></span><button type="button" class="k-route__row"><span class="k-route__title">Leer</span><span class="k-route__meta">Hecho</span><span class="k-route__sub">Die Bundesausbildungsförderungsgesetzberatungsstelle</span></button></li>
        </ol>
      </div>
    </figure>
  </div>
</section>

<section class="hoja-card" id="estanteria" data-atom="estanteria">
  <div class="hoja-card__cabeza"><span class="hoja-card__n">19</span><h2 class="hoja-card__titulo">Estantería <code>.k-shelf</code> + <code>.k-cover</code></h2></div>
  <p class="hoja-card__reemplaza"><b>reemplaza</b> las filas de tema y «Nuevo tema» del Inicio viejo (Inicio.tsx)</p>
  <div class="hoja-card__estados">
    <figure class="hoja-estado" data-estado="tema">
      <figcaption>Tema al día <code>.k-cover</code></figcaption>
      <div class="hoja-estado__muestra">
        <ul class="k-shelf"><li>
          <button type="button" class="k-cover"><span class="k-cover__band">Deutsch</span><span class="k-cover__sub">Edición Nürnberg</span></button>
          <span class="k-shelf__caption">A2 · ● hoy</span>
        </li></ul>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="vencidas">
      <figcaption>Con fichas vencidas <code>data-accent</code></figcaption>
      <div class="hoja-estado__muestra">
        <ul class="k-shelf"><li>
          <button type="button" class="k-cover"><span class="k-cover__band">Deutsch</span><span class="k-cover__sub">Edición Nürnberg</span></button>
          <span class="k-shelf__caption" data-accent="true">A2 · 12 vencen</span>
        </li></ul>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="nuevo">
      <figcaption>Tema nuevo <code>.k-cover--new</code></figcaption>
      <div class="hoja-estado__muestra">
        <ul class="k-shelf"><li>
          <button type="button" class="k-cover k-cover--new"><span class="k-cover__plus" aria-hidden="true">+</span><span class="k-cover__name">Nuevo tema</span></button>
          <span class="k-shelf__caption">Klara arma el plan</span>
        </li></ul>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="compuesto-largo">
      <figcaption>Compuesto largo: la franja parte palabra</figcaption>
      <div class="hoja-estado__muestra">
        <ul class="k-shelf"><li>
          <button type="button" class="k-cover"><span class="k-cover__band">Bundesausbildungsförderungsgesetz</span><span class="k-cover__sub">Edición Nürnberg</span></button>
          <span class="k-shelf__caption">B1 · ● hoy</span>
        </li></ul>
      </div>
    </figure>
  </div>
</section>
```

- [ ] **Step 5: corre el chequeo y míralo pasar**

Run: `PLAYWRIGHT_BROWSERS_PATH=D:/caches/ms-playwright node docs/design/klara-sistema/hoja.check.mjs`
Expected: PASS: cero literales de color, todos los estados presentes, ≥44px, cero scroll horizontal y cero animaciones con reduced-motion, en los dos temas y los dos anchos. Mira las capturas de `.hoja-out/` de las secciones 12, 18 y 19, en claro y en oscuro. Si algo desborda o no calza, corrígelo ahora, porque no hay otra tarea para el CSS.

- [ ] **Step 6: commit**

```bash
git add frontend/src/styles/sistema.css docs/design/klara-sistema/CONTRATO.md docs/design/klara-sistema/hoja.html docs/design/klara-sistema/hoja.check.mjs
git commit -m "feat(sistema): átomos 18 y 19 (recorrido y estantería) y la ilustración del héroe" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Los textos, en seis idiomas

**Files:**
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`

**Interfaces:**
- Produces: las claves `tabbar.hoy`, `tabbar.biblioteca`, `hoy.*` (13 hojas, con `fichas_one` y `fichas_other`), `biblioteca.temas`, `biblioteca.nuevoPie` y `biblioteca.edicion`. Retira `tabbar.inicio`.

- [ ] **Step 1: pasa el castellano por `solace-wren`.** Invoca la skill con esta tabla como microcopy. Si cambia alguna cadena, usa la nueva aquí y en las cinco traducciones. Si no, sigue igual:

| clave | es |
|---|---|
| `tabbar.hoy` | Hoy |
| `tabbar.biblioteca` | Biblioteca |
| `hoy.estasAqui` | Estás aquí |
| `hoy.hecho` | Hecho |
| `hoy.plan` | El plan de hoy · {{min}} min |
| `hoy.planHecho` | El plan de hoy · hecho |
| `hoy.fin` | Mañana, otra historia. |
| `hoy.listo` | Listo por hoy. |
| `hoy.seguir` | Seguir leyendo |
| `hoy.empezar` | Empezar |
| `hoy.pedir` | Pídele una historia a Klara |
| `hoy.fichas_one` | {{count}} ficha por repasar |
| `hoy.fichas_other` | {{count}} fichas por repasar |
| `hoy.error` | No pude cargar tu día. |
| `hoy.reintentar` | Reintentar |
| `biblioteca.temas` | Tus temas |
| `biblioteca.nuevoPie` | Klara arma el plan |
| `biblioteca.edicion` | Edición Nürnberg |

- [ ] **Step 2: escríbelas en los seis archivos.** En cada `common.json` van tres cambios:

1. El objeto `tabbar` queda con `"inicio"` reemplazado por `"hoy"` y `"biblioteca"`. `mas`, `perfil`, `navAria` y `moreAria` no cambian.
2. Dentro del objeto `biblioteca`, que ya existe, van tres claves nuevas al final: `temas`, `nuevoPie` y `edicion`.
3. En el nivel superior, un objeto `hoy` nuevo.

En `es`:

```json
"tabbar": {
  "hoy": "Hoy",
  "biblioteca": "Biblioteca",
  "mas": "Más",
  "perfil": "Perfil",
  "navAria": "Navegación",
  "moreAria": "Más opciones"
},
"hoy": {
  "estasAqui": "Estás aquí",
  "hecho": "Hecho",
  "plan": "El plan de hoy · {{min}} min",
  "planHecho": "El plan de hoy · hecho",
  "fin": "Mañana, otra historia.",
  "listo": "Listo por hoy.",
  "seguir": "Seguir leyendo",
  "empezar": "Empezar",
  "pedir": "Pídele una historia a Klara",
  "fichas_one": "{{count}} ficha por repasar",
  "fichas_other": "{{count}} fichas por repasar",
  "error": "No pude cargar tu día.",
  "reintentar": "Reintentar"
}
```

y, al final del objeto `biblioteca` existente:

```json
  "temas": "Tus temas",
  "nuevoPie": "Klara arma el plan",
  "edicion": "Edición Nürnberg"
```

Para las otras cinco, las mismas claves con estos valores (`tabbar.mas`, `perfil`, `navAria` y `moreAria` se quedan como están en cada archivo):

| clave | en | de | fr | ja | pt |
|---|---|---|---|---|---|
| `tabbar.hoy` | Today | Heute | Aujourd'hui | 今日 | Hoje |
| `tabbar.biblioteca` | Library | Bibliothek | Bibliothèque | ライブラリ | Biblioteca |
| `hoy.estasAqui` | You are here | Du bist hier | Tu es ici | 現在地 | Você está aqui |
| `hoy.hecho` | Done | Erledigt | Fait | 完了 | Feito |
| `hoy.plan` | Today's plan · {{min}} min | Der Plan für heute · {{min}} Min. | Le plan du jour · {{min}} min | 今日のプラン · {{min}}分 | O plano de hoje · {{min}} min |
| `hoy.planHecho` | Today's plan · done | Der Plan für heute · erledigt | Le plan du jour · fait | 今日のプラン · 完了 | O plano de hoje · feito |
| `hoy.fin` | Tomorrow, another story. | Morgen eine neue Geschichte. | Demain, une autre histoire. | 明日はまた新しいお話。 | Amanhã, outra história. |
| `hoy.listo` | Done for today. | Fertig für heute. | C'est fini pour aujourd'hui. | 今日はここまで。 | Pronto por hoje. |
| `hoy.seguir` | Keep reading | Weiterlesen | Continuer la lecture | 続きを読む | Continuar lendo |
| `hoy.empezar` | Start | Starten | Commencer | はじめる | Começar |
| `hoy.pedir` | Ask Klara for a story | Bitte Klara um eine Geschichte | Demande une histoire à Klara | クララにお話をたのむ | Peça uma história à Klara |
| `hoy.fichas_one` | {{count}} card to review | {{count}} Karte zum Wiederholen | {{count}} fiche à réviser | 復習カード {{count}} 枚 | {{count}} cartão para revisar |
| `hoy.fichas_other` | {{count}} cards to review | {{count}} Karten zum Wiederholen | {{count}} fiches à réviser | 復習カード {{count}} 枚 | {{count}} cartões para revisar |
| `hoy.error` | Couldn't load your day. | Dein Tag konnte nicht geladen werden. | Impossible de charger ta journée. | 今日のプランを読み込めませんでした。 | Não consegui carregar o seu dia. |
| `hoy.reintentar` | Try again | Erneut versuchen | Réessayer | もう一度 | Tentar de novo |
| `biblioteca.temas` | Your topics | Deine Themen | Tes sujets | あなたのテーマ | Seus temas |
| `biblioteca.nuevoPie` | Klara builds the plan | Klara erstellt den Plan | Klara construit le plan | クララがプランを組みます | A Klara monta o plano |
| `biblioteca.edicion` | Nürnberg edition | Nürnberger Ausgabe | Édition Nuremberg | ニュルンベルク版 | Edição Nürnberg |

- [ ] **Step 3: el chequeo de paridad**

Run: `cd frontend && npm run i18n:check`
Expected: PASS. Los seis archivos tienen el mismo conjunto de claves.

- [ ] **Step 4: commit**

```bash
git add frontend/src/locales
git commit -m "feat(hoy): los textos de Hoy y Biblioteca en los seis idiomas" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: La pantalla de Hoy

**Files:**
- Create: `frontend/src/routes/Hoy.tsx`, `frontend/src/lib/useCourseData.ts`
- Delete: `frontend/src/routes/Inicio.tsx`
- Modify: `frontend/src/App.tsx` (import de `Inicio` → `Hoy`, y `RootGate`), `frontend/src/routes/Portada.tsx` (import de `useCourseData`)

**Interfaces:**
- Consumes: `buildHoyVM`, `medianocheLocal` y los tipos (tarea 9); los átomos (tarea 10); las claves `hoy.*` (tarea 11); y `api.claimModuleStory` y `ApiError`, que ya existen.
- Produces: `useCourseData()` en `lib/useCourseData.ts`, con la misma firma que tenía en `Inicio.tsx`: `{ vm: CourseVM }`.

- [ ] **Step 1: muda `useCourseData`.** Crea `frontend/src/lib/useCourseData.ts` con el mismo código que hoy vive en `routes/Inicio.tsx`. La tarea 13 lo simplifica:

```ts
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { CardOut, ModulePathItem, StoryListItem } from "../api/types";
import { buildCourseVM, type CourseVM } from "./courseView";

export function useCourseData(): { vm: CourseVM } {
  const [vm, setVm] = useState<CourseVM>(() =>
    buildCourseVM({ modules: null, due: null, latestStoryId: null })
  );
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [modules, due, stories] = await Promise.all([
        api.listModules().catch(() => null),
        // ponytail: el 50 es explícito — el default del cliente es 20 y capa el badge.
        api.dueCards(50).catch(() => null),
        api.listStories(1, 0).catch(() => [] as StoryListItem[]),
      ]);
      if (cancelled) return;
      setVm(
        buildCourseVM({
          modules: modules as ModulePathItem[] | null,
          due: due as CardOut[] | null,
          latestStoryId: stories[0]?.id ?? null,
        })
      );
    })();
    return () => { cancelled = true; };
  }, []);
  return { vm };
}
```

En `routes/Portada.tsx`, cambia `import { useCourseData } from "./Inicio";` por `import { useCourseData } from "../lib/useCourseData";`.

- [ ] **Step 2: la pantalla**, en `frontend/src/routes/Hoy.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";
import { ApiError, api } from "../api/client";
import type { TodayOut } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import { useGreeting } from "../lib/dateLabel";
import { buildHoyVM, medianocheLocal, type Accion, type Panel, type Parada } from "../lib/hoyView";
import { languageLabel } from "../lib/languages";
import { useUser } from "../lib/user";

export default function Hoy() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const hola = useGreeting();
  const [today, setToday] = useState<TodayOut | null>(null);
  const [fallo, setFallo] = useState(false);
  const [intento, setIntento] = useState(0);
  const [reclamando, setReclamando] = useState(false);

  useEffect(() => {
    let cancelado = false;
    setFallo(false);
    api.today(medianocheLocal()).then(
      (d) => { if (!cancelado) setToday(d); },
      () => { if (!cancelado) setFallo(true); },
    );
    return () => { cancelado = true; };
  }, [intento]);

  const vm = buildHoyVM(today);
  const tema = user ? languageLabel(user.target_language) : "…";

  async function actuar(accion: Accion) {
    if (accion.tipo === "ir") {
      navigate(accion.to, { state: { from: "/" } });
      return;
    }
    if (reclamando) return; // doble toque: un solo reclamo
    setReclamando(true);
    try {
      const story = await api.claimModuleStory(accion.moduleId);
      navigate(`/estudiar/${story.id}`, { state: { from: "/" } });
    } catch (e) {
      // El código "library.empty" viaja en el mensaje del ApiError (ver Module.tsx).
      if (e instanceof ApiError && e.status === 404 && e.message.includes("library.empty")) {
        navigate("/story/new", { state: { from: "/" } });
        return;
      }
      setReclamando(false);
      setFallo(true);
    }
  }

  return (
    <main className="k-page">
      <header className="k-topline">
        <span className="k-topline__mark">
          <button
            type="button"
            className="k-btn k-btn--text"
            aria-label={t("biblioteca.titulo")}
            onClick={() => navigate("/biblioteca")}
          >
            {tema} <span aria-hidden="true">⌄</span>
          </button>
          <span className="k-topline__meta">{t("biblioteca.cursoSub", { level: user?.level ?? "" })}</span>
        </span>
        <KlaraMark size={14} />
      </header>
      <div className="k-live">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">
            <Trans
              i18nKey="home.greeting.conNombre"
              values={{ hola, name: user?.display_name ?? "…" }}
              components={{ 1: <em /> }}
            />
          </h1>
        </header>
        <h2 className="k-cap k-cap--rule">
          {vm.todoHecho ? t("hoy.planHecho") : t("hoy.plan", { min: vm.minutos })}
        </h2>
        {fallo && (
          <p className="k-error" role="alert">
            {t("hoy.error")}{" "}
            <button type="button" className="k-btn k-btn--text" onClick={() => setIntento((n) => n + 1)}>
              {t("hoy.reintentar")}
            </button>
          </p>
        )}
        <ol className="k-route">
          {vm.paradas.map((p) => (
            <li
              key={p.id}
              className="k-route__stop"
              data-state={p.estado}
              aria-current={p.estado === "now" ? "step" : undefined}
            >
              <span className="k-route__dot" aria-hidden="true" />
              {p.estado === "now" && vm.panel ? (
                <div className="k-route__body">
                  <span className="k-route__label">{t("hoy.estasAqui")}</span>
                  <PanelActual panel={vm.panel} ocupado={reclamando} onAccion={actuar} />
                </div>
              ) : (
                <FilaParada parada={p} onAccion={actuar} />
              )}
            </li>
          ))}
        </ol>
        <p className="k-route__end">{vm.todoHecho ? `${t("hoy.listo")} ${t("hoy.fin")}` : t("hoy.fin")}</p>
      </div>
    </main>
  );
}

function FilaParada({ parada, onAccion }: { parada: Parada; onAccion: (a: Accion) => void }) {
  const { t } = useTranslation();
  const sub =
    parada.id === "leer" && parada.historia
      ? parada.historia
      : parada.id === "repasar" && parada.vencen
        ? t("hoy.fichas", { count: parada.vencen })
        : t(`curso.paso.${parada.id}.dek`);
  return (
    <button type="button" className="k-route__row" onClick={() => onAccion(parada.accion)}>
      <span className="k-route__title">{t(`curso.paso.${parada.id}.titulo`)}</span>
      <span className="k-route__meta">
        {parada.estado === "done" ? t("hoy.hecho") : t(`curso.paso.${parada.id}.meta`)}
      </span>
      <span className="k-route__sub">{sub}</span>
    </button>
  );
}

function PanelActual({
  panel,
  ocupado,
  onAccion,
}: {
  panel: Panel;
  ocupado: boolean;
  onAccion: (a: Accion) => void;
}) {
  const { t } = useTranslation();
  const [arteRota, setArteRota] = useState(false);
  const tag = `${t(`curso.paso.${panel.tipo}.titulo`)} · ${t(`curso.paso.${panel.tipo}.meta`)}`;

  let titulo = "";
  let dek: string | null = null;
  let cta: string | null = t("hoy.empezar");
  switch (panel.tipo) {
    case "leer":
      titulo = panel.estado === "request" ? t("hoy.pedir") : (panel.titulo ?? t("curso.paso.leer.dek"));
      dek = panel.estado === "request" ? null : panel.subtitulo;
      cta = panel.estado === "continue" ? t("hoy.seguir") : panel.estado === "new" ? t("hoy.empezar") : null;
      break;
    case "pronunciar":
      titulo = panel.frase ? `„${panel.frase.target}“` : t("curso.paso.pronunciar.titulo");
      dek = panel.frase ? panel.frase.native : t("curso.paso.pronunciar.dek");
      break;
    case "hablar":
      titulo = t("curso.paso.hablar.dek");
      dek = null;
      break;
    case "repasar":
      titulo = t("hoy.fichas", { count: panel.vencen });
      dek = t("curso.paso.repasar.dek");
      break;
  }

  return (
    <button type="button" className="k-hero" disabled={ocupado} onClick={() => onAccion(panel.accion)}>
      {panel.tipo === "leer" && panel.arte && !arteRota && (
        <img className="k-hero__art" src={panel.arte} alt="" onError={() => setArteRota(true)} />
      )}
      <span className="k-hero__tag">
        <span>{tag}</span>
        {cta && <span>{cta}</span>}
      </span>
      <span className="k-hero__title">{titulo}</span>
      <span className="k-hero__arrow" aria-hidden="true">→</span>
      {dek && <span className="k-hero__dek">{dek}</span>}
    </button>
  );
}
```

- [ ] **Step 3: la raíz.** En `App.tsx`, cambia `import Inicio from "./routes/Inicio";` por `import Hoy from "./routes/Hoy";` y, dentro de `RootGate`, `<Inicio />` por `<Hoy />`. Después borra `frontend/src/routes/Inicio.tsx` (`git rm`).

- [ ] **Step 4: typecheck, pruebas y build**

Run: `cd frontend && npm run typecheck && npm test && npm run build`
Expected: todo en verde. Si el typecheck rechaza alguna clave de plantilla (`curso.paso.${…}`), es la misma forma que ya usaba `Portada.tsx`: revisa que el `panel.tipo` y el `parada.id` sean de la unión `ParadaId`.

- [ ] **Step 5: commit**

```bash
git add frontend/src/routes/Hoy.tsx frontend/src/lib/useCourseData.ts frontend/src/App.tsx frontend/src/routes/Portada.tsx
git rm frontend/src/routes/Inicio.tsx
git commit -m "feat(hoy): el lobby es el recorrido del día, con la historia ilustrada en la parada actual" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: La barra de tres pestañas, la Biblioteca y la portada del tema

**Files:**
- Modify: `frontend/src/components/TabBar.tsx`
- Create: `frontend/src/routes/Biblioteca.tsx`
- Modify: `frontend/src/App.tsx` (ruta `/biblioteca` dentro de `<Route element={<V4Shell />}>`)
- Modify: `frontend/src/routes/Portada.tsx` (fuera la lista del plan; el «←» vuelve a `/biblioteca`)
- Modify: `frontend/src/lib/courseView.ts` y `frontend/src/lib/courseView.test.ts` (fuera `pasos`, `PasoVM` y `PasoId`, que quedan muertos)

**Interfaces:**
- Consumes: `tabActiva` (tarea 9), `.k-shelf` y `.k-cover` (tarea 10), las claves de la tarea 11 y `useCourseData` (tarea 12).

- [ ] **Step 1: la barra.** En `TabBar.tsx`: agrega `import { tabActiva } from "../lib/tabs";` y el icono de Hoy junto a los otros dos:

```tsx
function IcHoy() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
      <path d="M8 3.5v17" />
      <circle cx="8" cy="9" r="2.5" fill="currentColor" stroke="none" />
      <path d="M13 9h7M13 15h5" />
    </svg>
  );
}
```

Cambia `const enPerfil = pathname.startsWith("/perfil");` por:

```tsx
  const activa = tabActiva(pathname);
  const enPerfil = activa === "mas";
```

Y el `<nav>` pasa a `k-tabs--3`, con tres botones. El de «Más» queda igual que hoy:

```tsx
      <nav className="k-tabs k-tabs--3" aria-label={t("tabbar.navAria")}>
        <button
          type="button"
          className="k-tabs__tab"
          data-active={activa === "hoy" ? "true" : "false"}
          aria-current={activa === "hoy" ? "page" : undefined}
          onClick={() => { setMenu(false); navigate("/"); }}
        >
          <span className="k-tabs__ic" aria-hidden="true"><IcHoy /></span>
          <span className="k-tabs__lbl">{t("tabbar.hoy")}</span>
        </button>
        <button
          type="button"
          className="k-tabs__tab"
          data-active={activa === "biblioteca" ? "true" : "false"}
          aria-current={activa === "biblioteca" ? "page" : undefined}
          onClick={() => { setMenu(false); navigate("/biblioteca"); }}
        >
          <span className="k-tabs__ic" aria-hidden="true"><IcLib /></span>
          <span className="k-tabs__lbl">{t("tabbar.biblioteca")}</span>
        </button>
        <button
          type="button"
          className="k-tabs__tab"
          data-active={menu || enPerfil ? "true" : "false"}
          aria-current={enPerfil ? "page" : undefined}
          aria-haspopup="menu"
          aria-expanded={menu ? "true" : "false"}
          onClick={() => setMenu((v) => !v)}
        >
          <span className="k-tabs__ic" aria-hidden="true"><IcMas /></span>
          <span className="k-tabs__lbl">{t("tabbar.mas")}</span>
        </button>
      </nav>
```

- [ ] **Step 2: la Biblioteca**, en `frontend/src/routes/Biblioteca.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import KlaraMark from "../components/KlaraMark";
import { useMastheadDate } from "../lib/dateLabel";
import { languageLabel } from "../lib/languages";
import { useCourseData } from "../lib/useCourseData";
import { useUser } from "../lib/user";

export default function Biblioteca() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const { vm } = useCourseData();
  const fecha = useMastheadDate();
  const tema = user ? languageLabel(user.target_language) : "…";
  const pct = Math.round(vm.progreso * 100);
  const vencen = vm.vencen ?? 0;
  const estado = vencen > 0 ? t("biblioteca.estadoDue", { count: vencen }) : t("biblioteca.estadoHoy");

  return (
    <main className="k-page">
      <header className="k-topline">
        <span className="k-topline__mark">
          <KlaraMark size={14} />
          <span className="wordmark">Klara</span>
        </span>
        <span className="k-topline__meta">{fecha}</span>
      </header>
      <div className="k-live">
        <header className="k-hero k-hero--quiet">
          <h1 className="k-hero__title">{t("biblioteca.titulo")}</h1>
        </header>
        <h2 className="k-cap k-cap--rule">{t("biblioteca.temas")}</h2>
        <ul className="k-shelf">
          <li>
            <button type="button" className="k-cover" onClick={() => navigate("/curso/aleman")}>
              <span className="k-cover__band">{tema}</span>
              <span className="k-cover__sub">{t("biblioteca.edicion")}</span>
            </button>
            <div className="k-bar k-bar--fill">
              <div
                className="k-bar__track"
                role="progressbar"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={t("mapa.progressAria", { pct })}
              >
                <i className="k-bar__fill" style={{ width: `${pct}%` }} />
              </div>
            </div>
            <span className="k-shelf__caption" data-accent={vencen > 0 ? "true" : undefined}>
              {user?.level ?? ""} · {estado}
            </span>
          </li>
          <li>
            <button type="button" className="k-cover k-cover--new" onClick={() => navigate("/nuevo")}>
              <span className="k-cover__plus" aria-hidden="true">+</span>
              <span className="k-cover__name">{t("biblioteca.nuevoTitulo")}</span>
            </button>
            <span className="k-shelf__caption">{t("biblioteca.nuevoPie")}</span>
          </li>
        </ul>
      </div>
    </main>
  );
}
```

- [ ] **Step 3: la ruta.** En `App.tsx`, importa `Biblioteca` y, dentro de `<Route element={<V4Shell />}>`, antes de `/curso/:id`:

```tsx
        <Route
          path="/biblioteca"
          element={
            <ProtectedRoute>
              <Biblioteca />
            </ProtectedRoute>
          }
        />
```

- [ ] **Step 4: la portada del tema.** En `Portada.tsx`:
  - el botón de la tira pasa a `onClick={() => navigate("/biblioteca")}`;
  - quita el `<h2 className="k-cap k-cap--rule">{t("curso.planTitulo")}</h2>` y el bloque `{vm.pasos.map(…)}` completo;
  - quedan dentro del `<ul>` las dos filas «El mapa del curso» y «Género». Borra el comentario `ponytail: una sola lista…`, que ya no aplica.

- [ ] **Step 5: `pasos` muere, y con él `latestStoryId`**, que solo lo alimentaba. En `lib/courseView.ts`, todo lo que va de la primera línea hasta antes de `export type RowEstado` queda así (`RowEstado` y `moduleRowEstado` no cambian):

```ts
import type { CardOut, ModulePathItem } from "../api/types";

export interface CourseVM {
  id: "aleman";
  progreso: number;
  vencen: number | null;
  modules: ModulePathItem[] | null;
}

export function buildCourseVM(args: {
  modules: ModulePathItem[] | null;
  due: CardOut[] | null;
}): CourseVM {
  const { modules, due } = args;
  const total = modules?.length ?? 0;
  const done = modules?.filter((m) => m.completed).length ?? 0;
  return {
    id: "aleman",
    progreso: total ? done / total : 0,
    vencen: due ? due.length : null,
    modules,
  };
}
```

En `lib/courseView.test.ts`, el `describe("buildCourseVM", …)` entero queda así (el `mod()` y el `describe("moduleRowEstado", …)` no cambian):

```ts
describe("buildCourseVM", () => {
  it("deriva progreso de módulos completados", () => {
    const vm = buildCourseVM({
      modules: [mod({ completed: true }), mod({ id: "m2", is_current: true }), mod({ id: "m3" })],
      due: [],
    });
    expect(vm.progreso).toBeCloseTo(1 / 3);
    expect(vm.modules?.length).toBe(3);
  });

  it("sin datos: progreso 0, vencen null", () => {
    const vm = buildCourseVM({ modules: null, due: null });
    expect(vm.progreso).toBe(0);
    expect(vm.vencen).toBeNull();
    expect(vm.modules).toBeNull();
  });
});
```

Y `lib/useCourseData.ts` queda sin la llamada a `listStories`:

```ts
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { CardOut, ModulePathItem } from "../api/types";
import { buildCourseVM, type CourseVM } from "./courseView";

export function useCourseData(): { vm: CourseVM } {
  const [vm, setVm] = useState<CourseVM>(() => buildCourseVM({ modules: null, due: null }));
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [modules, due] = await Promise.all([
        api.listModules().catch(() => null),
        // ponytail: el 50 es explícito — el default del cliente es 20 y capa el badge.
        api.dueCards(50).catch(() => null),
      ]);
      if (cancelled) return;
      setVm(buildCourseVM({ modules: modules as ModulePathItem[] | null, due: due as CardOut[] | null }));
    })();
    return () => { cancelled = true; };
  }, []);
  return { vm };
}
```

Revisa que no quede ningún uso:

Run: `cd frontend && grep -rn "pasos\|PasoVM\|PasoId\|latestStoryId\|curso.planTitulo" src --include=*.ts --include=*.tsx`
Expected: sin resultados. `curso.planTitulo` queda sin uso: bórralo de los seis `common.json` y vuelve a correr `npm run i18n:check`.

- [ ] **Step 6: typecheck, pruebas, i18n y build**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm test && npm run build`
Expected: todo en verde.

- [ ] **Step 7: commit**

```bash
git add frontend/src
git commit -m "feat(hoy): tres pestañas, la estantería como biblioteca y la portada del tema sin el plan" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: El arnés visual

**Files:**
- Create: `frontend/scripts/capturas-hoy.mjs`
- Create: `docs/design/klara-hoy/ilustracion-flash.jpg`. Es la prueba de estilo aprobada el 2026-09-30. Descárgala de la galería con `Artifact` (`action: "read"`, `url: https://claude.ai/artifact/AauMudVjqVPENieX34qMTH`, `path: "img/ilustracion-flash.jpg"`) y cópiala ahí.

**Interfaces:**
- Consumes: el `dist/` de `npm run build`, el Playwright de `.ds-sync/` (el mismo de `hoja.check.mjs`) y todas las pantallas de las tareas 12 y 13.

- [ ] **Step 1: el arnés**, en `frontend/scripts/capturas-hoy.mjs`:

```js
// Arnés visual de Hoy y Biblioteca (plan 2026-09-30, tarea 14).
//
//   cd frontend && npm run build && node scripts/capturas-hoy.mjs
//
// Levanta `vite preview` sobre el dist que haya (no compila), simula la API y
// fotografía cada escenario en claro y oscuro, a 390×844 y a 390×667. Escribe los
// PNG y un informe en .hoja-out/hoy/. Sale con 1 si algo desborda en horizontal,
// si hay controles de menos de 44px, si la imagen rota deja un icono roto o si
// el doble toque reclama dos veces.
//
// Usa el Playwright del arnés de design-sync (.ds-sync/, gitignored), como hoja.check.mjs.

import { spawn, execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONT = resolve(HERE, "..");
const REPO = resolve(FRONT, "..");
const OUT = join(REPO, ".hoja-out", "hoy");
const PW = join(REPO, ".ds-sync/node_modules/playwright/index.mjs");
const ARTE = join(REPO, "docs/design/klara-hoy/ilustracion-flash.jpg");
const PORT = 4175;
const BASE = `http://localhost:${PORT}`;

if (!existsSync(PW)) { console.error(`No está ${PW} (ver .design-sync/NOTES.md).`); process.exit(2); }
if (!existsSync(join(FRONT, "dist", "index.html"))) { console.error("No hay dist/: corre `npm run build`."); process.exit(2); }
const { chromium } = await import(pathToFileURL(PW).href);
mkdirSync(OUT, { recursive: true });

const user = { id: "u1", email: "samuel@example.com", is_superuser: false, display_name: "Samuel", level: "A2",
  native_language: "es", target_language: "de", learning_context: null, auth_methods: ["password"], needs_onboarding: false };
const modules = Array.from({ length: 8 }, (_, i) => ({ id: `m${i}`, sequence_order: i + 1, title: `Módulo ${i + 1}`,
  cefr_level: "A2", can_dos: [], grammatical_focus: [], encountered: 10, mastered: i < 2 ? 10 : 3, total: 10,
  gender_encountered: 0, gender_mastered: 0, gender_total: 0, stories_finished: i < 2 ? 3 : 1,
  stories_to_complete: 3, completed: i < 2, is_current: i === 2, unlocked: i <= 3, library_available: 2 }));
const due = Array.from({ length: 12 }, (_, i) => ({ id: `c${i}` }));

const NINGUNA = { read: false, pronounce: false, speak: false, review: false };
const historia = (over = {}) => ({ state: "new", id: null, library_entry_id: "e1", module_id: "m2",
  title: "Die Bäckerei am Samstag", subtitle: "Una panadería, un sábado a las ocho.",
  illustration_path: "/illustrations/muestra", ...over });
const hecha = historia({ state: "done", id: "s1", library_entry_id: null });

const ESCENARIOS = {
  "entrar": { ruta: "/", today: { now: "read", steps: NINGUNA, story: historia(), sentence: null, due: 12, module: null } },
  "despues-de-leer": { ruta: "/", today: { now: "pronounce", steps: { ...NINGUNA, read: true }, story: hecha,
    sentence: { target: "Der Bäcker öffnet um acht.", native: "El panadero abre a las ocho." }, due: 12, module: null } },
  "todo-hecho": { ruta: "/", today: { now: null, steps: { read: true, pronounce: true, speak: true, review: true },
    story: hecha, sentence: null, due: 0, module: null } },
  "sin-historia": { ruta: "/", today: { now: "read", steps: { ...NINGUNA, review: true },
    story: { state: "request", id: null, library_entry_id: null, module_id: null, title: null, subtitle: null, illustration_path: null },
    sentence: null, due: 0, module: null } },
  "titulo-largo": { ruta: "/", today: { now: "read", steps: NINGUNA,
    story: historia({ title: "Die Bundesausbildungsförderungsgesetzberatungsstelle am Samstag" }), sentence: null, due: 12, module: null } },
  "arte-rota": { ruta: "/", arteRota: true, today: { now: "read", steps: NINGUNA, story: historia(), sentence: null, due: 12, module: null } },
  "biblioteca": { ruta: "/biblioteca", today: null },
};

const arte = readFileSync(ARTE);
const servidor = spawn("npx", ["vite", "preview", "--port", String(PORT), "--strictPort"], { cwd: FRONT, shell: true });
function apagar() {
  if (process.platform === "win32") {
    try { execSync(`taskkill /pid ${servidor.pid} /T /F`, { stdio: "ignore" }); } catch { /* ya murió */ }
  } else {
    servidor.kill();
  }
}
for (let i = 0; i < 60; i++) {
  try { if ((await fetch(BASE)).ok) break; } catch { /* todavía no */ }
  await new Promise((r) => setTimeout(r, 500));
}

async function medir(page) {
  return page.evaluate(() => {
    const desbordes = [];
    for (const el of [document.documentElement, ...document.querySelectorAll(".k-live, .k-page")]) {
      const d = el.scrollWidth - el.clientWidth;
      if (d > 0) desbordes.push({ el: el.className || el.tagName, d });
    }
    const chicos = [...document.querySelectorAll("button, a[href]")]
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.width > 0 && (r.width < 44 || r.height < 44))
      .map(({ el, r }) => ({ txt: el.textContent.trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) }));
    const rota = [...document.querySelectorAll("img.k-hero__art")].some((img) => img.complete && img.naturalWidth === 0);
    return { desbordes, chicos, rota };
  });
}

const fallos = [];
const informe = {};
const browser = await chromium.launch();
try {
  for (const [nombre, esc] of Object.entries(ESCENARIOS)) {
    for (const scheme of ["light", "dark"]) {
      for (const height of [844, 667]) {
        const clave = `${nombre}-${scheme}-${height}`;
        const reclamos = { n: 0 };
        const ctx = await browser.newContext({
          viewport: { width: 390, height }, deviceScaleFactor: 2, locale: "es-ES",
          colorScheme: scheme, serviceWorkers: "block",
        });
        await ctx.route("**/api/v1/**", async (route) => {
          const req = route.request();
          const p = new URL(req.url()).pathname.replace(/^\/api\/v1/, "");
          if (p.startsWith("/illustrations/")) {
            return esc.arteRota
              ? route.fulfill({ status: 404, body: "" })
              : route.fulfill({ status: 200, contentType: "image/jpeg", body: arte });
          }
          let body = [];
          let status = 200;
          if (p === "/me") body = user;
          else if (p === "/modules") body = modules;
          else if (p.startsWith("/srs/cards/due")) body = due;
          else if (p === "/today") body = esc.today;
          else if (p.startsWith("/modules/") && p.endsWith("/story") && req.method() === "POST") {
            reclamos.n += 1;
            status = 201;
            body = { id: "s-nueva", title: "Die Bäckerei am Samstag" };
          }
          return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
        });
        const page = await ctx.newPage();
        await page.clock.setFixedTime(new Date("2026-09-30T17:40:00"));
        await page.goto(BASE + esc.ruta);
        await page.waitForSelector(esc.ruta === "/biblioteca" ? ".k-shelf" : ".k-route");
        await page.waitForTimeout(500);
        await page.screenshot({ path: join(OUT, `${clave}.png`), animations: "disabled" });
        const m = await medir(page);
        informe[clave] = m;
        if (m.desbordes.length) fallos.push(`${clave}: desborda ${JSON.stringify(m.desbordes)}`);
        if (m.chicos.length) fallos.push(`${clave}: controles < 44px ${JSON.stringify(m.chicos)}`);
        if (m.rota) fallos.push(`${clave}: icono de imagen rota`);
        if (nombre === "entrar" && scheme === "light" && height === 844) {
          await page.locator(".k-hero").first().dblclick();
          await page.waitForTimeout(600);
          if (reclamos.n !== 1) fallos.push(`doble toque: ${reclamos.n} reclamos (se espera 1)`);
        }
        await ctx.close();
      }
    }
  }
} finally {
  await browser.close();
  apagar();
}

writeFileSync(join(OUT, "informe.json"), JSON.stringify({ fallos, informe }, null, 2));
console.log(`${Object.keys(informe).length} capturas en ${OUT}`);
if (fallos.length) {
  console.error(fallos.join("\n"));
  process.exit(1);
}
console.log("Sin desbordes, sin controles chicos, sin imagen rota, un solo reclamo.");
```

- [ ] **Step 2: córrelo**

Run: `cd frontend && npm run build && PLAYWRIGHT_BROWSERS_PATH=D:/caches/ms-playwright node scripts/capturas-hoy.mjs`
Expected: `28 capturas en …/.hoja-out/hoy` y la línea final sin fallos. Si falla, arregla la causa en el CSS o en la pantalla (tareas 10, 12 y 13) y vuelve a correrlo. En Git Bash la ruta de los navegadores va con barras normales.

- [ ] **Step 3: compáralo con los mockups.** Mira `entrar-light-844`, `entrar-dark-844`, `despues-de-leer-light-844`, `todo-hecho-light-844`, `titulo-largo-light-667`, `arte-rota-light-844` y `biblioteca-light-844` contra `b-ilustrada`, `b-oscuro`, `b-avance` y `c` de la galería. Lo que se espera ver:
  - la línea con el punto actual en acento;
  - la ilustración arriba del panel, y el panel tipográfico en `arte-rota`;
  - el panel en oscuro invertido (papel sobre pizarra), por decisión del spec §7.3;
  - las tapas como libros en la repisa.

- [ ] **Step 4: publícalo en la galería.** Lee el artifact (`action: "read"`), agrega al final una sección «Lo que salió», con esas siete capturas y un pie de una línea cada una, y republícalo en la misma URL con las capturas en `files`.

- [ ] **Step 5: commit**

```bash
git add frontend/scripts/capturas-hoy.mjs docs/design/klara-hoy/ilustracion-flash.jpg
git commit -m "test(hoy): el arnés visual de Hoy y Biblioteca, con desbordes, 44px, imagen rota y doble toque" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Calibrar el estilo, con compuerta de Samuel

**Files:** ninguno del repo, salvo que haya que ajustar `STYLE_PROMPT` en `backend/src/klara/services/illustration.py`.

- [ ] **Step 1: el backup en local.** Restaura el último dump de `D:\Desktop\projects\_backups\klara\` en un Postgres desechable. Es la receta de la memoria `consultas-db-desde-backup`. El `MSYS_NO_PATHCONV=1` va solo en la línea del `exec`:

```bash
docker run -d --name klara-backup-scratch -e POSTGRES_USER=klara -e POSTGRES_PASSWORD=scratch -e POSTGRES_DB=klara postgres:16-alpine
DUMP=$(ls -t /d/Desktop/projects/_backups/klara/* | head -1)
docker cp "$DUMP" klara-backup-scratch:/tmp/k.dump
MSYS_NO_PATHCONV=1 docker exec klara-backup-scratch pg_restore -U klara -d klara --no-owner --no-privileges /tmp/k.dump
MSYS_NO_PATHCONV=1 docker exec klara-backup-scratch psql -U klara -d klara -At -c \
  "SELECT DISTINCT ON (module_id) title, content FROM story_library WHERE is_active ORDER BY module_id, created_at LIMIT 4" > "$SCRATCH/calibracion.txt"
```

`$SCRATCH` es el scratchpad de la sesión, con barras normales. Ahí van también el script y las imágenes del paso 2.

- [ ] **Step 2: cuatro escenas y cuatro imágenes con el prompt de producción.** Los textos salen de `PORTADA_PROMPT` (tarea 8) y las imágenes de `build_prompt` (tarea 3), así que se prueba el texto exacto que va a mandar el backend. Todo pasa por el proxy local `127.0.0.1:4000`: `gemini-3.5-flash` para las escenas y `gemini-image` (3.1 Flash) para las imágenes. Cuestan unos $0,28. Guarda este script en el scratchpad de la sesión (`$SCRATCH`) como `calibrar.py`:

```python
"""Calibración del estilo (plan, tarea 15): cuatro escenas reales y el prompt de producción."""

import base64
import json
import sys
import urllib.request
from pathlib import Path

from klara.i18n import language_label
from klara.scripts.backfill_portadas import PORTADA_PROMPT
from klara.services.illustration import build_prompt
from klara.services.story_gen import _extract_json

PROXY = "http://127.0.0.1:4000/v1"
ENTRADA, SALIDA = Path(sys.argv[1]), Path(sys.argv[2])


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        PROXY + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


for i, linea in enumerate(ENTRADA.read_text(encoding="utf-8").splitlines()):
    titulo, contenido = linea.split("|", 1)  # psql -At separa con "|"
    frases = "\n".join(
        f"- {s.get('target', '')} ({s.get('native', '')})"
        for s in json.loads(contenido).get("sentences") or []
    )
    prompt = PORTADA_PROMPT.format(
        target_label=language_label("de"), native_label=language_label("es"),
        title=titulo, sentences=frases,
    )
    chat = post("/chat/completions", {
        "model": "gemini-3.5-flash",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    })
    textos = _extract_json(chat["choices"][0]["message"]["content"])
    img = post("/images/generations", {
        "model": "gemini-image", "prompt": build_prompt(textos["scene"]), "n": 1,
        "imageConfig": {"aspectRatio": "21:9", "imageSize": "1K"},
    })
    (SALIDA / f"calibracion-{i}.jpg").write_bytes(base64.b64decode(img["data"][0]["b64_json"]))
    print(i, titulo, "|", textos.get("subtitle"), "|", textos["scene"])
```

Para correrlo:

```bash
cd backend && uv run python "$SCRATCH/calibrar.py" "$SCRATCH/calibracion.txt" "$SCRATCH"
```

- [ ] **Step 3: compuerta.** Agrega las cuatro imágenes a la galería, en una sección «Calibración del estilo», y pregúntale a Samuel si las cuatro se ven como una misma colección. Si dice que no, ajusta `STYLE_PROMPT` (mientras no haya backfill en prod, `STYLE_VERSION` sigue en 1) y repite el paso 2. Si Flash no logra una colección coherente, el plan B del spec es `ILLUSTRATION_MODEL=gemini-3-pro-image-preview` con el mismo prompt, a $0,137 por imagen.

- [ ] **Step 4: limpieza**

```bash
docker rm -f klara-backup-scratch
```

---

### Task 16: Los gates y el PR

- [ ] **Step 1: gates completos.** Invoca la skill `gates-locales`. Si la corres a mano, estos son los mismos comandos de `ci.yml` más la hoja:

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests
cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/ -q
cd backend && DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run alembic downgrade base && DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run alembic upgrade head
cd frontend && npm run typecheck && npm run i18n:check && npm test && npm run build
PLAYWRIGHT_BROWSERS_PATH=D:/caches/ms-playwright node docs/design/klara-sistema/hoja.check.mjs
```

Expected: todo en verde. Pytest tiene que sumar exactamente los tests nuevos a la línea base de la preparación.

- [ ] **Step 2: la revisión final.** Pide una revisión de la rama completa (skill `requesting-code-review`), con foco en las cinco líneas de «Review Focus» y en los cuatro archivos que escribió Claude.

- [ ] **Step 3: push y PR, con el visto bueno de Samuel.** Pídele permiso antes de empujar. Con el sí:

```bash
git push -u origin hoy-y-biblioteca
gh pr create --title "Hoy y Biblioteca: el recorrido ilustrado y la estantería" --body "$(cat <<'EOF'
Spec: docs/superpowers/specs/2026-09-30-hoy-y-biblioteca-design.md
Plan: docs/superpowers/plans/2026-09-30-hoy-y-biblioteca.md
Mockups y capturas: https://claude.ai/artifact/AauMudVjqVPENieX34qMTH

- GET /today calcula el día con las tablas de actividad que ya existen.
- Cada historia trae subtítulo y escena; la ilustración (3.1 Flash) se guarda por escena y se sirve en /illustrations/{hash}.
- Hoy = el recorrido; Biblioteca = la estantería; tres pestañas.
- Migración 20260930_0023, aditiva.

Despliegue: ver la sección «Despliegue» del plan (primero sin GEMINI_API_KEY; la clave y el backfill, después de aprobar el estilo).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Despliegue (lo corre Samuel)

La clave de Gemini entra después de aprobar el estilo y de decidir el tamaño de las imágenes. Desde que la clave está puesta, cada historia nueva se dibuja y se guarda con `STYLE_VERSION = 1`; si el prompt cambia después, esas imágenes se quedan en el estilo viejo y hay que subir la versión y pagar otra vez.

0. **Recarga el saldo de DeepSeek.** El 2026-09-30 la cuenta de reasonix estaba en $0. Si es la misma que usa prod, pedir historias y Hablar ya están fallando, y el backfill de textos también lo necesita.
1. **Merge del PR y deploy, sin `GEMINI_API_KEY`**, en una terminal aparte (no cabe en el `!`): `bash scripts/deploy-prod.sh`. La migración corre sola al arrancar el contenedor. Sin la clave no se dibuja nada: Hoy sale con el panel tipográfico y todo lo demás igual.
2. **Aprueba el estilo.** La compuerta de calibración de la tarea 15 sigue abierta: la imagen 3 salió como dibujo de línea y falta que digas si las cuatro se ven como una misma colección. Si hay que tocar `STYLE_PROMPT`, es un cambio de código y se hace ahora, antes de la clave, con `STYLE_VERSION` todavía en 1; después se vuelve a desplegar. Si Flash no logra una colección coherente, el plan B es `ILLUSTRATION_MODEL=gemini-3-pro-image-preview`, a $0,137 por imagen, y se decide aquí.
3. **Decide el tamaño de las imágenes.** Gemini las devuelve de unos 0,8 MB (un JPEG de 1584×672) para un hueco de unos 350×150 px, y se guardan enteras en Postgres, o sea en cada `pg_dump`. Si las quieres más chicas (recomprimir con Pillow a unos 1200 px, calidad 85, más o menos 0,1 MB), se hace antes de la clave y del backfill: después ya hay 150 filas gordas o más guardadas y se vuelve una migración de recompresión.
4. **La clave de Gemini en prod.** Agrega `GEMINI_API_KEY=<clave>` a `~/klara/.env` en la caja, sin sourcear ese archivo, y recrea los contenedores para que el backend la reciba. El `IMAGE_TAG` es el del deploy del paso 1: el sha que imprime la línea `Desplegado:` del script, en lugar de `sha-XXXXXXX`. Sin él, el compose de prod levanta `latest`.

   ```bash
   ssh atrium-aws "cd ~/klara && IMAGE_TAG=sha-XXXXXXX docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
   ```

   Desde aquí cada historia nueva se dibuja.
5. **El backfill en seco:**

   ```bash
   ssh atrium-aws "cd ~/klara && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m klara.scripts.backfill_portadas --dry-run"
   ```

   Lo primero que imprime es `GEMINI_API_KEY: presente`; si dice `ausente`, la clave no llegó al contenedor. Después revisa el costo.
6. **El backfill de la biblioteca:** el mismo comando con `--only-library` y sin `--dry-run`. Es lo que Hoy enseña de verdad: la historia nueva de la biblioteca. Si algo falla, se puede volver a correr.
7. **Decide si pasar por las historias propias.** Es el mismo comando sin `--only-library`. Hoy solo muestra la más reciente sin terminar y la terminada hoy, pero esa pasada dibuja también cada historia propia anterior de cada usuario; el techo que imprimió el paso 5 ya la incluye.
8. **Verificación:** abre Klara en el teléfono. Hoy tiene que mostrar el recorrido con la ilustración en la parada actual, y la Biblioteca, la tapa de Deutsch.
