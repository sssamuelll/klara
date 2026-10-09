# Klara en tres idiomas, plan 1: el núcleo y el japonés

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el núcleo de Klara en tres idiomas (ítems con facetas, catálogo de dinámicas, reproductor de lecciones, Hoy con una línea por idioma) y la rebanada de japonés (hiragana con trazo), para que Samuel estudie japonés a diario desde el teléfono.

**Architecture:** El catálogo vive en archivos JSON del repo (`backend/src/klara/mapas/`), se valida al arrancar y lo sirve un router nuevo. FSRS agenda cada (usuario, ítem, faceta) en `user_facets` con el motor que ya existe (`apply_review`). En el frontend, un reproductor único (`routes/Sesion.tsx` + el reducer puro `lib/sesion.ts`) monta dinámicas intercambiables (`src/dinamicas/`) que devuelven evidencias.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic + pydantic v2 + py-fsrs (backend, Python 3.12, `uv`); React + Vite + TypeScript + react-i18next + vitest (frontend); Azure Speech (TTS para generar el audio, y el puntaje para validarlo); KanjiVG (trazos).

**Spec:** `docs/superpowers/specs/2026-10-09-klara-tres-idiomas-design.md`. Pantallas aprobadas: `docs/design/tres-idiomas/pantallas.html`.

**Este es el plan 1 de 4.** Los otros tres (alemán, inglés, y el mapa con Biblioteca) se escriben cuando este esté mergeado, contra el código real.

## Ajustes respecto a la spec

Cada uno está decidido aquí; la ejecución no los reabre.

1. **Ajustes («Idiomas que estudias») entra en este plan.** Sin él, la cuenta de Samuel solo vería alemán, y el alemán llega en el plan 2. La spec lo ponía en el paso 6.
2. **El audio de los kana se genera con Azure TTS (`ja-JP-NanamiNeural`), no con ElevenLabs.** Así la voz es nativa sin tener que elegirla, y basta una sola clave, la misma que valida el audio.
3. **`lesson_runs` lleva una columna más, `repasos`.** Es la cantidad de repasos de la corrida, y con ella Hoy muestra lo que hiciste («6 repasos · か き く け こ»).
4. **`GET /api/v1/mapas` devuelve todos los idiomas que tienen mapa, cada uno con `estudias: bool`.** Ajustes lo necesita así, y Biblioteca (plan 4) filtrará.
5. **Las actividades no llevan `contenido` explícito.** Ninguna rebanada lo necesita; entrará cuando una lección lo pida.
6. **Hay dos piezas de sistema más que en la spec:**
   - `.k-glifo`: el carácter grande de la pregunta de `eleccion`.
   - `.k-wrap--centro`: la nube de opciones centrada.
7. **La fuente japonesa entra en las pilas de fuentes,** sin reglas `:lang(ja)`. Se agrega `"Noto Serif JP"` antes de los genéricos en `--font-serif`, `--font-sans` y `--font-mono`, y el navegador la usa solo para los glifos que Source Serif, Inter y JetBrains no traen.
8. **«Mañana» son las facetas que vencen en las próximas 24 horas.** El servidor no conoce la zona horaria del teléfono.
9. **`CAP_REPASOS` vive en `klara/catalogo/dinamicas.py`,** para que `schemas/` lo use sin depender de `services/`.

## Antes de empezar

- **Rama:** se sale de `spec/tres-idiomas` hacia `feat/tres-idiomas-nucleo` (lo hace la tarea 1).
- **Base de tests:** un Postgres 16 con el rol `klara` / `klara_test` y la base `klara_test` en `localhost:5432`. Es la misma receta que `ci.yml`. Si no hay ninguno, la tarea 1 lo levanta.
- **La tarea 7 necesita que Samuel ponga dos líneas en `backend/.env`** (ese archivo está en `.gitignore`):
  ```
  AZURE_SPEECH_KEY=<la clave de Azure Speech>
  AZURE_SPEECH_REGION=<su región, p. ej. eastus>
  ```
  Ninguna tarea imprime esas claves, ni las copia, ni las sube. Si al llegar a la tarea 7 no están, se pregunta a Samuel y se espera; no se salta.

## Global Constraints

- **Comandos de backend** (los pasos los escriben enteros):
  - Tests: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest <ruta> -v`
  - Lint: `cd backend && uv run ruff check src tests && uv run ruff format --check src tests`
- **Comandos de frontend:**
  - `cd frontend && npx vitest run <ruta>`
  - `npm run typecheck`
  - `npm run i18n:check`
  - `npm run build`
  - Vitest solo corre `src/**/*.test.ts`, en Node y sin DOM. Por eso la lógica que se prueba va en `.ts` puros, nunca en `.tsx`.
- **Hoja del sistema:** `node docs/design/klara-sistema/hoja.check.mjs` (usa el Playwright de `.ds-sync/`).
- **Claves de ítem:** `<idioma>:<tipo>:<id>`, por ejemplo `ja:kana:あ`. Los identificadores de faceta van en ASCII (`oir`, `genero`), y la interfaz los muestra con tilde.
- **Constantes fijadas por la spec:**

  | Constante | Valor |
  |---|---|
  | `CAP_REPASOS` | 25 |
  | `AUTO_AVANCE_MS` | 700 |
  | `N` (puntos por trazo) | 24 |
  | `UMBRAL_MEDIA` | 12 |
  | `LARGO_MIN` / `LARGO_MAX` | 0,55 / 1,7 |
  | `TOQUE_MIN` | 4 |
  | Tablero de `emparejar` | 45 s |
  | Reintento en práctica | 3 actividades después |
  | Umbral de audio | 70 |

- **Nota FSRS:**
  - Falla: `again`.
  - Acierto con pistas, o con `ms > ms_lento`: `hard`.
  - Cualquier otro acierto: `good`.
  - `easy` nunca.
  - Solo `comprobar` mueve FSRS.
- **Sistema de diseño:** ninguna pantalla define estilos propios. Cada pieza nueva va en `frontend/src/styles/sistema.css` (sin colores literales, solo `var(--…)`) y en la hoja `docs/design/klara-sistema/hoja.html`, con sus estados declarados en `hoja.check.mjs`.
- **i18n:**
  - Toda cadena nueva de interfaz va en los 6 locales: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`.
  - `es` es la fuente, y `npm run i18n:check` exige paridad de claves.
  - Las claves están tipadas: `t()` solo acepta literales o plantillas de uniones conocidas, nunca un `string` suelto.
  - El contenido de las lecciones (bajadas, mnemotecnias) va solo en español.
- **Sin LLM en vivo:** nada del flujo nuevo llama a un LLM.
- **Commits:** en español, con prefijo `feat(tres-idiomas):` o `test(tres-idiomas):`. Cada mensaje termina con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

Estas son las entradas que la spec implica y que es más probable que fallen en el uso real. Cada línea apunta a su test.

1. **Doble toque en una opción, o una dinámica que reporta dos veces.** Tiene que contar una sola respuesta.
   - Tarea 14: `un segundo resultado en la misma actividad se ignora`.
   - Tarea 16: la guarda `respondida` en la ruta.
2. **Reintentar un envío fallido.** Si se reenvía la misma evidencia, no puede mover FSRS dos veces. Tarea 9: `la misma evidencia dos veces cuenta una`.
3. **Cerrar la app a mitad de lección.** Una corrida sin `finished_at` no puede marcar la línea como hecha ni la lección como terminada.
   - Tarea 8: `ni el mapa ni una corrida abierta cuentan`.
   - Tarea 11: `corrida abierta o del mapa no marcan`.
4. **El borde de medianoche.** Una línea terminada a las 23:59 de ayer no cuenta como hoy. Tarea 11: `lo de ayer no marca hoy`.
5. **Escribir, escuchar o hablar desactivado.** Las actividades que lo necesitan se saltan, y si se salta todo, la sesión termina en vez de colgarse. Tarea 14: `apagar escribir salta los trazos` y `si se salta todo, termina`.

## File Structure

**Backend (nuevo):**

| Archivo | Responsabilidad |
|---|---|
| `backend/alembic/versions/20261009_0024_facetas.py` | tres tablas y una columna, aditiva |
| `backend/src/klara/models/facetas.py` | `UserFacet`, `FacetReview`, `LessonRun` |
| `backend/src/klara/catalogo/__init__.py` | paquete del catálogo |
| `backend/src/klara/catalogo/facetas.py` | facetas por tipo de ítem; partir claves |
| `backend/src/klara/catalogo/nota.py` | evidencia → `ReviewRating` |
| `backend/src/klara/catalogo/dinamicas.py` | metadatos de cada dinámica; dinámica de repaso; `CAP_REPASOS` |
| `backend/src/klara/catalogo/modelo.py` | modelos pydantic del catálogo y `Catalogo` |
| `backend/src/klara/catalogo/plantillas.py` | plantillas de lección (`kana`) |
| `backend/src/klara/catalogo/cargar.py` | cargar y validar; `get_catalogo()` |
| `backend/src/klara/catalogo/generar.py` | contenido de cada actividad |
| `backend/src/klara/scripts/importar_kanjivg.py` | trazos de KanjiVG → `kana.json` |
| `backend/src/klara/scripts/generar_audio_catalogo.py` | audio de kana con Azure, validado |
| `backend/src/klara/mapas/ja/{mapa.json,kana.json,KANJIVG.txt,audio/*.mp3}` | el mapa de japonés |
| `backend/src/klara/services/sesion.py` | componer la sesión; idiomas de estudio; vencidas |
| `backend/src/klara/services/evidencias.py` | registrar evidencias y aplicar FSRS |
| `backend/src/klara/schemas/catalogo.py` | entrada y salida de las rutas nuevas |
| `backend/src/klara/routers/catalogo.py` | `/sesiones`, `/lecciones`, `/lesson-runs`, `/evidencias`, `/audio`, `/mapas` |

**Backend (cambia):**
- `models/user.py` y `models/__init__.py`.
- `main.py`: router y arranque.
- `schemas/today.py`, `services/today.py` y `routers/today.py`: reescritos.
- `schemas/user.py` y `routers/users.py`: `study_languages`.
- `tests/conftest.py`: fixture `catalogo_mini`.

**Tests nuevos:**
- Ayudas: `tests/ayudas.py` y `tests/catalogo_mini.py`.
- `test_facetas_modelo.py`
- `test_catalogo_facetas.py`
- `test_catalogo_cargar.py`
- `test_catalogo_generar.py`
- `test_importar_kanjivg.py`
- `test_generar_audio_catalogo.py`
- `test_catalogo_real.py`
- `test_sesion.py`
- `test_evidencias.py`
- `test_catalogo_router.py`
- `test_users_study_languages.py`

Además se reescribe `test_today.py` y se extiende `test_srs_engine_paridad.py`.

**Frontend (nuevo):**

| Archivo | Responsabilidad |
|---|---|
| `frontend/src/lib/sesion.ts` (+test) | el reproductor como reducer puro |
| `frontend/src/lib/dinamicas/eleccion.ts` (+test) | evaluar una elección; tonos |
| `frontend/src/lib/dinamicas/trazo.ts` (+test) | remuestreo, juicio y progreso del trazo |
| `frontend/src/lib/dinamicas/emparejar.ts` (+test) | el tablero de parejas |
| `frontend/src/lib/idiomasEstudio.ts` (+test) | marcar o desmarcar un idioma de estudio |
| `frontend/src/lib/tts.src.test.ts` | el audio de archivo pasa por `speak()` |
| `frontend/src/dinamicas/{tipos.ts,registro.ts,Eleccion.tsx,Trazo.tsx,Emparejar.tsx}` | contrato y componentes |
| `frontend/src/routes/Sesion.tsx` | la ruta del reproductor |

**Frontend (cambia):**
- `api/types.ts` y `api/client.ts`.
- `lib/tts.ts`: el seam `src`.
- `lib/hoyView.ts` (+test) y `routes/Hoy.tsx`: reescritos.
- `routes/Settings.tsx` y `App.tsx`.
- `styles/{tokens,global,sistema}.css`.
- Los 6 `locales/*/common.json`.
- `docs/design/klara-sistema/{hoja.html,hoja.check.mjs}`.

---

## Fase A — El núcleo en el backend

### Task 1: Tablas nuevas y su paridad con FSRS

**Files:**
- Create: `backend/alembic/versions/20261009_0024_facetas.py`
- Create: `backend/src/klara/models/facetas.py`
- Modify: `backend/src/klara/models/user.py` (columna `study_languages`)
- Modify: `backend/src/klara/models/__init__.py` (exportar los tres modelos)
- Modify: `backend/tests/test_srs_engine_paridad.py` (paridad de `UserFacet`)
- Test: `backend/tests/test_facetas_modelo.py`

**Interfaces:**
- Produces:
  - `UserFacet(user_id, idioma, item_key, faceta, + los 9 campos de FsrsCard)`, con único `uq_user_facet` en (`user_id`, `item_key`, `faceta`).
  - `FacetReview(id, user_id, run_id, idioma, item_key, faceta, dinamica, modo, acierto, pistas, ms, nota, detalle)`. El `id` lo pone el cliente.
  - `LessonRun(id, user_id, idioma, leccion_id, origen, repasos, started_at, finished_at)`.
  - `User.study_languages: list[str] | None`.

- [ ] **Step 1: Crear la rama y tener la base de tests**

```bash
cd D:/Desktop/projects/klara
git switch spec/tres-idiomas
git switch -c feat/tres-idiomas-nucleo
docker ps --format '{{.Names}} {{.Ports}}' | grep 5432 || docker run -d --name klara-test-pg -e POSTGRES_USER=klara -e POSTGRES_PASSWORD=klara_test -e POSTGRES_DB=klara_test -p 5432:5432 postgres:16-alpine
```

Si ya hay un Postgres en el 5432 que no tiene el rol `klara`, se levanta el de prueba en el 5433 (`-p 5433:5432`) y se usa `localhost:5433` en todos los comandos de test de este plan.

- [ ] **Step 2: Escribir los tests del modelo**

`backend/tests/test_facetas_modelo.py`:

```python
"""Las tablas nuevas (spec 2026-10-09 §2.2) y la columna de idiomas de estudio."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from klara.models import FacetReview, LessonRun, User, UserFacet
from klara.models.enums import CardState, CEFRLevel, ReviewRating


async def _usuario(db) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"f-{uuid.uuid4().hex[:6]}@klara.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Samuel",
        level=CEFRLevel.A1,
        native_language="es",
        target_language="de",
    )
    db.add(u)
    await db.flush()
    return u


async def test_study_languages_nace_nula(db_session):
    u = await _usuario(db_session)
    await db_session.commit()
    assert u.study_languages is None


async def test_study_languages_guarda_una_lista(db_session):
    u = await _usuario(db_session)
    u.study_languages = ["de", "ja", "en"]
    await db_session.commit()
    await db_session.refresh(u)
    assert u.study_languages == ["de", "ja", "en"]


async def test_una_faceta_por_usuario_item_y_faceta(db_session):
    u = await _usuario(db_session)
    for _ in range(2):
        db_session.add(
            UserFacet(
                user_id=u.id,
                idioma="ja",
                item_key="ja:kana:あ",
                faceta="escribir",
                state=CardState.NEW,
                interval_days=0.0,
                repetitions=0,
            )
        )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_la_evidencia_guarda_su_corrida_y_su_detalle(db_session):
    u = await _usuario(db_session)
    run = LessonRun(user_id=u.id, idioma="ja", leccion_id="ja/hiragana/a", origen="hoy", repasos=3)
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        FacetReview(
            id=uuid.uuid4(),
            user_id=u.id,
            run_id=run.id,
            idioma="ja",
            item_key="ja:kana:あ",
            faceta="escribir",
            dinamica="trazo",
            modo="comprobar",
            acierto=True,
            pistas=1,
            ms=9000,
            nota=ReviewRating.HARD,
            detalle={"trazos": [{"n": 1, "media": 4.2, "largo": 1.0, "fallos": 0}]},
        )
    )
    await db_session.commit()
    guardada = (await db_session.execute(select(FacetReview))).scalar_one()
    assert guardada.run_id == run.id
    assert guardada.detalle["trazos"][0]["media"] == 4.2
    assert run.started_at is not None
    assert run.finished_at is None


async def test_origen_solo_hoy_o_mapa(db_session):
    u = await _usuario(db_session)
    db_session.add(LessonRun(user_id=u.id, idioma="ja", origen="otro"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_el_modo_de_la_evidencia_es_uno_de_los_tres(db_session):
    u = await _usuario(db_session)
    run = LessonRun(user_id=u.id, idioma="ja", origen="hoy")
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        FacetReview(
            id=uuid.uuid4(),
            user_id=u.id,
            run_id=run.id,
            idioma="ja",
            item_key="ja:kana:あ",
            faceta="escribir",
            dinamica="trazo",
            modo="repasar",
            acierto=True,
            pistas=0,
            ms=1,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

- [ ] **Step 3: Extender el test de paridad**

En `backend/tests/test_srs_engine_paridad.py`:
- cambia la línea `from klara.models import StudyCard, UserCard` por `from klara.models import StudyCard, UserCard, UserFacet`;
- agrega este test al final del archivo:

```python
def test_paridad_usercard_userfacet(reloj):
    """`UserFacet` (Klara en tres idiomas) recorre FSRS igual que `UserCard`."""
    user_id = uuid.uuid4()
    aleman = _sembrada(UserCard, user_id=user_id, vocab_item_id=uuid.uuid4(), ease=2.5)
    faceta = _sembrada(
        UserFacet, user_id=user_id, idioma="ja", item_key="ja:kana:あ", faceta="escribir"
    )

    for dias, rating in (
        (0, ReviewRating.GOOD),
        (1, ReviewRating.AGAIN),
        (3, ReviewRating.HARD),
        (10, ReviewRating.EASY),
    ):
        reloj["ahora"] += timedelta(days=dias)
        apply_review(aleman, rating)
        apply_review(faceta, rating)

    divergentes = [a for a in _NUEVE if getattr(aleman, a) != getattr(faceta, a)]
    assert divergentes == []
```

- [ ] **Step 4: Correr los tests y verlos fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_facetas_modelo.py tests/test_srs_engine_paridad.py -v`
Expected: falla en la recolección con `ImportError: cannot import name 'FacetReview' from 'klara.models'`.

- [ ] **Step 5: Escribir la migración**

`backend/alembic/versions/20261009_0024_facetas.py`:

```python
"""facetas: estado FSRS por faceta, evidencias y corridas del reproductor

Aditiva (spec 2026-10-09-klara-tres-idiomas §2.2): tres tablas nuevas y la
columna `users.study_languages`.

Revision ID: 20261009_0024
Revises: 20260930_0023
Create Date: 2026-10-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261009_0024"
down_revision: str | None = "20260930_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CARD_STATE_VALUES = ("new", "learning", "reviewing", "relearning", "suspended")
REVIEW_RATING_VALUES = ("again", "hard", "good", "easy")


def _ahora(nombre: str) -> sa.Column:
    return sa.Column(nombre, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _usuario() -> sa.Column:
    return sa.Column(
        "user_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    # create_type=False: los dos tipos existen desde 20260502_0001.
    card_state = postgresql.ENUM(*CARD_STATE_VALUES, name="card_state", create_type=False)
    review_rating = postgresql.ENUM(*REVIEW_RATING_VALUES, name="review_rating", create_type=False)

    op.add_column("users", sa.Column("study_languages", postgresql.ARRAY(sa.String(5)), nullable=True))

    op.create_table(
        "lesson_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _usuario(),
        sa.Column("idioma", sa.String(5), nullable=False),
        sa.Column("leccion_id", sa.String(80), nullable=True),
        sa.Column("origen", sa.String(8), nullable=False),
        sa.Column("repasos", sa.Integer(), nullable=False, server_default="0"),
        _ahora("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("origen IN ('hoy', 'mapa')", name="ck_lesson_run_origen"),
    )
    op.create_index("ix_lesson_run_user", "lesson_runs", ["user_id", "idioma", "finished_at"])

    op.create_table(
        "user_facets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _usuario(),
        sa.Column("idioma", sa.String(5), nullable=False),
        sa.Column("item_key", sa.Text(), nullable=False),
        sa.Column("faceta", sa.String(20), nullable=False),
        sa.Column("state", card_state, nullable=False, server_default="new"),
        sa.Column("stability", sa.Float(), nullable=True),
        sa.Column("difficulty", sa.Float(), nullable=True),
        sa.Column("fsrs_step", sa.Integer(), nullable=True),
        sa.Column("fsrs_last_review", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interval_days", sa.Float(), nullable=False, server_default="0"),
        _ahora("next_review_at"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        _ahora("created_at"),
        _ahora("updated_at"),
        sa.UniqueConstraint("user_id", "item_key", "faceta", name="uq_user_facet"),
    )
    op.create_index("ix_user_facet_due", "user_facets", ["user_id", "idioma", "next_review_at"])

    op.create_table(
        "facet_reviews",
        # Sin default: el id lo genera el teléfono y es la clave de idempotencia.
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _usuario(),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lesson_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idioma", sa.String(5), nullable=False),
        sa.Column("item_key", sa.Text(), nullable=False),
        sa.Column("faceta", sa.String(20), nullable=False),
        sa.Column("dinamica", sa.String(30), nullable=False),
        sa.Column("modo", sa.String(12), nullable=False),
        sa.Column("acierto", sa.Boolean(), nullable=False),
        sa.Column("pistas", sa.Integer(), nullable=False),
        sa.Column("ms", sa.Integer(), nullable=False),
        sa.Column("nota", review_rating, nullable=True),
        sa.Column("detalle", postgresql.JSONB(), nullable=True),
        _ahora("created_at"),
        sa.CheckConstraint(
            "modo IN ('presentar', 'practicar', 'comprobar')", name="ck_facet_review_modo"
        ),
    )
    op.create_index("ix_facet_review_user_time", "facet_reviews", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_facet_review_user_time", table_name="facet_reviews")
    op.drop_table("facet_reviews")
    op.drop_index("ix_user_facet_due", table_name="user_facets")
    op.drop_table("user_facets")
    op.drop_index("ix_lesson_run_user", table_name="lesson_runs")
    op.drop_table("lesson_runs")
    op.drop_column("users", "study_languages")
```

- [ ] **Step 6: Escribir los modelos**

`backend/src/klara/models/facetas.py`:

```python
"""Klara en tres idiomas (spec 2026-10-09 §2.2): el estado FSRS de cada faceta,
el registro de evidencias y las corridas del reproductor.

`UserFacet` cumple el Protocol `FsrsCard` de `services/srs_engine.py` con los
mismos nueve atributos que `UserCard` y `StudyCard`; `test_srs_engine_paridad.py`
se pone rojo si alguna de las tres deriva.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, nullable_ts, pg_enum, updated_ts, uuid_pk
from klara.models.enums import CardState, ReviewRating


class LessonRun(Base):
    """Una corrida del reproductor: la línea de Hoy, «otra lección» o una lección
    repetida desde el mapa. La posición en el mapa sale de aquí (spec §2.2)."""

    __tablename__ = "lesson_runs"
    __table_args__ = (
        CheckConstraint("origen IN ('hoy', 'mapa')", name="ck_lesson_run_origen"),
        Index("ix_lesson_run_user", "user_id", "idioma", "finished_at"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    idioma: Mapped[str] = mapped_column(String(5), nullable=False)
    # Null en una corrida que fue solo de repasos.
    leccion_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    origen: Mapped[str] = mapped_column(String(8), nullable=False)
    # Cuántas actividades de repaso traía la sesión: Hoy lo enseña en la línea hecha.
    repasos: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    started_at: Mapped[created_ts]
    finished_at: Mapped[nullable_ts]


class UserFacet(Base):
    """El estado FSRS de una (usuario, ítem, faceta). Nace con la primera
    evidencia en `comprobar` de esa faceta (spec §2.2)."""

    __tablename__ = "user_facets"
    __table_args__ = (
        UniqueConstraint("user_id", "item_key", "faceta", name="uq_user_facet"),
        Index("ix_user_facet_due", "user_id", "idioma", "next_review_at"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # El prefijo de la clave, copiado para consultar por idioma sin LIKE.
    idioma: Mapped[str] = mapped_column(String(5), nullable=False)
    item_key: Mapped[str] = mapped_column(Text, nullable=False)
    faceta: Mapped[str] = mapped_column(String(20), nullable=False)

    # --- estado FSRS: los nueve del Protocol FsrsCard ---
    state: Mapped[CardState] = mapped_column(
        pg_enum(CardState, name="card_state"), default=CardState.NEW, nullable=False
    )
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    fsrs_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fsrs_last_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interval_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    next_review_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[created_ts]
    updated_at: Mapped[updated_ts]


class FacetReview(Base):
    """Una evidencia, de cualquier modo. Sin FK a `user_facets`: la de práctica
    llega antes de que exista la fila."""

    __tablename__ = "facet_reviews"
    __table_args__ = (
        CheckConstraint(
            "modo IN ('presentar', 'practicar', 'comprobar')", name="ck_facet_review_modo"
        ),
        Index("ix_facet_review_user_time", "user_id", "created_at"),
    )

    # Lo genera el teléfono: reenviar la misma evidencia no la cuenta dos veces.
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("lesson_runs.id", ondelete="CASCADE"), nullable=False
    )
    idioma: Mapped[str] = mapped_column(String(5), nullable=False)
    item_key: Mapped[str] = mapped_column(Text, nullable=False)
    faceta: Mapped[str] = mapped_column(String(20), nullable=False)
    dinamica: Mapped[str] = mapped_column(String(30), nullable=False)
    modo: Mapped[str] = mapped_column(String(12), nullable=False)
    acierto: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pistas: Mapped[int] = mapped_column(Integer, nullable=False)
    ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # Solo en `comprobar`: la nota que movió FSRS.
    nota: Mapped[ReviewRating | None] = mapped_column(
        pg_enum(ReviewRating, name="review_rating"), nullable=True
    )
    # El resumen propio de la dinámica, nunca los datos crudos.
    detalle: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[created_ts]
```

En `backend/src/klara/models/user.py`, cambia el import `from sqlalchemy import ForeignKey, String, Text` por:

```python
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
```

Y justo debajo de la línea `learning_context: Mapped[str | None] = mapped_column(Text, nullable=True)`, agrega:

```python
    # Los idiomas de las líneas de Hoy (spec 2026-10-09 §2.2). Null vale
    # [target_language]; el orden desempata cuál va primero.
    study_languages: Mapped[list[str] | None] = mapped_column(ARRAY(String(5)), nullable=True)
```

En `backend/src/klara/models/__init__.py`:
- después de `from klara.models.enums import …`, agrega la línea `from klara.models.facetas import FacetReview, LessonRun, UserFacet`;
- en `__all__`, en orden alfabético, agrega `"FacetReview"`, `"LessonRun"` y `"UserFacet"`.

- [ ] **Step 7: Correr los tests y verlos pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_facetas_modelo.py tests/test_srs_engine_paridad.py -v`
Expected: PASS. Son 6 tests de modelo y 4 de paridad. El fixture de sesión ya corre `alembic downgrade base` y `upgrade head`, así que la ida y vuelta de la migración queda probada.

- [ ] **Step 8: Lint**

Run: `cd backend && uv run ruff check src tests && uv run ruff format --check src tests`
Expected: sin errores. Si `format --check` falla, corre `uv run ruff format src tests` y repite.

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/20261009_0024_facetas.py backend/src/klara/models/facetas.py backend/src/klara/models/user.py backend/src/klara/models/__init__.py backend/tests/test_facetas_modelo.py backend/tests/test_srs_engine_paridad.py
git commit -m "feat(tres-idiomas): tablas de facetas, evidencias y corridas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Facetas, nota y dinámicas

**Files:**
- Create: `backend/src/klara/catalogo/__init__.py`
- Create: `backend/src/klara/catalogo/facetas.py`
- Create: `backend/src/klara/catalogo/nota.py`
- Create: `backend/src/klara/catalogo/dinamicas.py`
- Test: `backend/tests/test_catalogo_facetas.py`

**Interfaces:**
- Consumes: `ReviewRating` (`klara.models.enums`).
- Produces:
  - `FACETAS_POR_TIPO: dict[str, frozenset[str]]`
  - `MODOS: tuple[str, ...]`
  - `partes(item) -> tuple[str, str, str]`, `tipo_de(item) -> str`, `idioma_de(item) -> str`, `faceta_valida(item, faceta) -> bool`
  - `nota(*, acierto, pistas, ms, ms_lento) -> ReviewRating`
  - `Dinamica` (dataclass: `nombre`, `modos`, `facetas`, `ms_lento`, `segundos`)
  - `DINAMICAS: dict[str, Dinamica]`
  - `DINAMICA_DE_REPASO: dict[tuple[str, str], str]`
  - `ejercita(dinamica, tipo, faceta) -> bool`
  - `CAP_REPASOS = 25`

- [ ] **Step 1: Escribir los tests**

`backend/tests/test_catalogo_facetas.py`:

```python
"""Facetas, la nota que pone la dinámica y los metadatos de cada dinámica (spec §1, §3)."""

import pytest

from klara.catalogo.dinamicas import CAP_REPASOS, DINAMICA_DE_REPASO, DINAMICAS, ejercita
from klara.catalogo.facetas import (
    FACETAS_POR_TIPO,
    MODOS,
    faceta_valida,
    idioma_de,
    partes,
    tipo_de,
)
from klara.catalogo.nota import nota
from klara.models.enums import ReviewRating


def test_partes_de_una_clave():
    assert partes("ja:kana:あ") == ("ja", "kana", "あ")
    assert tipo_de("de:sustantivo:Frau") == "de:sustantivo"
    assert idioma_de("en:contraste:ɪ-iː") == "en"


@pytest.mark.parametrize("mala", ["", "ja", "ja:kana", "ja::あ", ":kana:あ", "ja:kana:"])
def test_clave_mal_formada(mala):
    with pytest.raises(ValueError):
        partes(mala)


def test_las_facetas_de_la_spec():
    assert FACETAS_POR_TIPO == {
        "ja:kana": frozenset({"reconocer", "oir", "escribir"}),
        "de:sustantivo": frozenset({"genero", "reconocer"}),
        "de:caso": frozenset({"aplicar"}),
        "en:contraste": frozenset({"oir", "pronunciar"}),
    }


def test_faceta_valida():
    assert faceta_valida("ja:kana:あ", "escribir")
    assert not faceta_valida("ja:kana:あ", "genero")
    assert not faceta_valida("xx:raro:a", "oir")
    assert not faceta_valida("mal", "oir")


@pytest.mark.parametrize(
    ("acierto", "pistas", "ms", "esperada"),
    [
        (False, 0, 1000, ReviewRating.AGAIN),
        (False, 3, 1000, ReviewRating.AGAIN),
        (True, 0, 1000, ReviewRating.GOOD),
        (True, 1, 1000, ReviewRating.HARD),
        (True, 0, 9001, ReviewRating.HARD),
        (True, 0, 9000, ReviewRating.GOOD),
    ],
)
def test_nota(acierto, pistas, ms, esperada):
    assert nota(acierto=acierto, pistas=pistas, ms=ms, ms_lento=9000) == esperada


def test_nunca_easy():
    notas = {
        nota(acierto=a, pistas=p, ms=m, ms_lento=5000)
        for a in (True, False)
        for p in (0, 1, 5)
        for m in (0, 4999, 5001)
    }
    assert ReviewRating.EASY not in notas


def test_las_dinamicas_usan_modos_y_facetas_validos():
    assert {"eleccion", "trazo", "emparejar"} <= set(DINAMICAS)
    for nombre, d in DINAMICAS.items():
        assert d.nombre == nombre
        assert d.modos <= set(MODOS)
        assert set(d.segundos) == set(d.modos)
        for tipo, facetas in d.facetas.items():
            assert facetas <= FACETAS_POR_TIPO[tipo]


def test_cada_repaso_usa_una_dinamica_que_lo_comprueba():
    for (tipo, faceta), nombre in DINAMICA_DE_REPASO.items():
        d = DINAMICAS[nombre]
        assert "comprobar" in d.modos
        assert ejercita(d, tipo, faceta)


def test_emparejar_solo_practica():
    assert DINAMICAS["emparejar"].modos == frozenset({"practicar"})


def test_el_tope_de_repasos():
    assert CAP_REPASOS == 25
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_facetas.py -v`
Expected: falla con `ModuleNotFoundError: No module named 'klara.catalogo'`.

- [ ] **Step 3: Implementar**

`backend/src/klara/catalogo/__init__.py`:

```python
"""Klara en tres idiomas (spec 2026-10-09): el catálogo de ítems, facetas,
dinámicas y mapas. Los datos viven en `klara/mapas/`; aquí está el código que
los carga, los valida y genera el contenido de cada actividad."""
```

`backend/src/klara/catalogo/facetas.py`:

```python
"""Facetas por tipo de ítem (spec §1): las únicas válidas. El cargador rechaza
cualquier otra, y también el endpoint de evidencias."""

FACETAS_POR_TIPO: dict[str, frozenset[str]] = {
    "ja:kana": frozenset({"reconocer", "oir", "escribir"}),
    "de:sustantivo": frozenset({"genero", "reconocer"}),
    "de:caso": frozenset({"aplicar"}),
    "en:contraste": frozenset({"oir", "pronunciar"}),
}

MODOS: tuple[str, ...] = ("presentar", "practicar", "comprobar")


def partes(item: str) -> tuple[str, str, str]:
    """`ja:kana:あ` → ("ja", "kana", "あ"). ValueError si no son tres partes llenas."""
    trozos = item.split(":", 2)
    if len(trozos) != 3 or not all(trozos):
        raise ValueError(f"clave de ítem inválida: {item!r}")
    return trozos[0], trozos[1], trozos[2]


def tipo_de(item: str) -> str:
    idioma, tipo, _ = partes(item)
    return f"{idioma}:{tipo}"


def idioma_de(item: str) -> str:
    return partes(item)[0]


def faceta_valida(item: str, faceta: str) -> bool:
    try:
        return faceta in FACETAS_POR_TIPO.get(tipo_de(item), frozenset())
    except ValueError:
        return False
```

`backend/src/klara/catalogo/nota.py`:

```python
"""La nota la pone la dinámica, no el usuario (spec §1). `easy` no se usa."""

from klara.models.enums import ReviewRating


def nota(*, acierto: bool, pistas: int, ms: int, ms_lento: int) -> ReviewRating:
    if not acierto:
        return ReviewRating.AGAIN
    if pistas > 0 or ms > ms_lento:
        return ReviewRating.HARD
    return ReviewRating.GOOD
```

`backend/src/klara/catalogo/dinamicas.py`:

```python
"""Lo que el backend sabe de cada dinámica (spec §3): qué modos soporta, qué
facetas ejercita por tipo de ítem, cuánto tiempo es «lento» y cuánto suele
tardar. El contenido lo generan las funciones de `generar.py`, una por dinámica.

Los planes 2 y 3 agregan `articulo`, `par-minimo` y `sombra`, y amplían las
facetas de `eleccion`."""

from dataclasses import dataclass

# Cuántos repasos entran, como mucho, en la sesión de una línea (spec §4). Lo que
# sobra queda para mañana: FSRS aguanta el atraso.
CAP_REPASOS = 25


@dataclass(frozen=True)
class Dinamica:
    nombre: str
    modos: frozenset[str]
    # tipo de ítem → facetas que ejercita
    facetas: dict[str, frozenset[str]]
    # Un acierto más lento que esto vale `hard` (catalogo/nota.py).
    ms_lento: int
    # modo → segundos típicos por actividad. Hoy suma esto para prometer minutos.
    segundos: dict[str, int]


DINAMICAS: dict[str, Dinamica] = {
    "eleccion": Dinamica(
        nombre="eleccion",
        modos=frozenset({"practicar", "comprobar"}),
        facetas={"ja:kana": frozenset({"reconocer", "oir"})},
        ms_lento=8_000,
        segundos={"practicar": 6, "comprobar": 6},
    ),
    "trazo": Dinamica(
        nombre="trazo",
        modos=frozenset({"presentar", "practicar", "comprobar"}),
        facetas={"ja:kana": frozenset({"escribir"})},
        ms_lento=30_000,
        segundos={"presentar": 20, "practicar": 25, "comprobar": 20},
    ),
    "emparejar": Dinamica(
        nombre="emparejar",
        # Solo práctica: un juego contra el reloj es mala señal para FSRS (spec §3.2).
        modos=frozenset({"practicar"}),
        facetas={"ja:kana": frozenset({"reconocer"})},
        ms_lento=45_000,
        segundos={"practicar": 45},
    ),
}

# Por ahora cada faceta se repasa con una dinámica fija (spec §3; el #129 podrá elegir).
DINAMICA_DE_REPASO: dict[tuple[str, str], str] = {
    ("ja:kana", "reconocer"): "eleccion",
    ("ja:kana", "oir"): "eleccion",
    ("ja:kana", "escribir"): "trazo",
}


def ejercita(dinamica: Dinamica, tipo: str, faceta: str) -> bool:
    return faceta in dinamica.facetas.get(tipo, frozenset())
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_facetas.py -v`
Expected: PASS.

- [ ] **Step 5: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/catalogo backend/tests/test_catalogo_facetas.py
git commit -m "feat(tres-idiomas): facetas, nota y metadatos de dinámicas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: El cargador del catálogo

**Files:**
- Create: `backend/src/klara/catalogo/modelo.py`
- Create: `backend/src/klara/catalogo/plantillas.py`
- Create: `backend/src/klara/catalogo/cargar.py`
- Create: `backend/tests/catalogo_mini.py` (el catálogo de prueba)
- Create: `backend/tests/ayudas.py` (crear usuarios y entrar por HTTP)
- Modify: `backend/tests/conftest.py` (fixture `catalogo_mini`)
- Test: `backend/tests/test_catalogo_cargar.py`

**Interfaces:**
- Consumes: todo lo de la tarea 2.
- Produces:
  - `Actividad(dinamica, modo, items: tuple[str, ...], faceta)` (pydantic, frozen)
  - `Leccion(id, titulo, bajada, plantilla, items, actividades)`
  - `Sabes(vista, filas)`, `Unidad(id, titulo, nivel, puedo, sabes, lecciones)`, `Mapa(idioma, escala, unidades)`
  - `Kana(kana, romaji, sonido, confusiones, trazos, audio, mnemotecnia)`
  - `Item = Kana` (los planes 2 y 3 amplían la unión)
  - `LeccionCompleta(id, idioma, unidad, leccion)`, con `id` de la forma `"ja/hiragana/ka"`
  - `Catalogo(raiz, mapas, items, lecciones)`, con `.lecciones_de(idioma) -> list[LeccionCompleta]` y `.audio_path(idioma, archivo) -> Path`
  - `kana(items) -> tuple[Actividad, ...]` y `PLANTILLAS: dict[str, Callable]`
  - `CatalogoInvalido(errores: list[str])`
  - `RAIZ_MAPAS: Path`
  - `cargar_catalogo(raiz=RAIZ_MAPAS) -> Catalogo`
  - `get_catalogo()`: con `lru_cache`. Respeta la variable de entorno `KLARA_MAPAS_DIR`, que es el seam de los tests.
  - Ayudas de test:
    - `escribir_catalogo_mini(raiz, *, kana=None, mapa=None, sin_audio=()) -> Path`
    - `KANA_MINI` y `MAPA_MINI`
    - fixture `catalogo_mini -> Catalogo`
    - `crear_usuario(db, *, target_language="de", study_languages=None) -> User`
    - `entrar(client, seed_invite, email) -> str` (devuelve la cookie)
    - `usuario_por_email(db, email) -> User`

- [ ] **Step 1: Escribir el catálogo de prueba y las ayudas**

`backend/tests/catalogo_mini.py`:

```python
"""Un catálogo japonés de juguete en disco: seis kana en dos lecciones.

Incluye お y を, que suenan igual («o»), para probar que `oír` nunca los pone
juntos. Los trazos son rectas: aquí no se evalúa la escritura."""

from __future__ import annotations

import copy
import json
from pathlib import Path


def _k(kana: str, romaji: str, *, sonido: str | None = None, confusiones=(), trazos=2) -> dict:
    return {
        "kana": kana,
        "romaji": romaji,
        "sonido": sonido or romaji,
        "confusiones": list(confusiones),
        "trazos": [f"M{10 + 10 * i},20 L{20 + 10 * i},90" for i in range(trazos)],
        "audio": f"{romaji}.mp3",
        "mnemotecnia": f"Suena «{sonido or romaji}».",
    }


KANA_MINI: list[dict] = [
    _k("あ", "a", confusiones=["お"], trazos=3),
    _k("い", "i"),
    _k("う", "u"),
    _k("え", "e"),
    _k("お", "o", confusiones=["あ"], trazos=3),
    _k("を", "wo", sonido="o", confusiones=["お"], trazos=3),
]

MAPA_MINI: dict = {
    "idioma": "ja",
    "escala": ["かな", "N5"],
    "unidades": [
        {
            "id": "hiragana",
            "titulo": "Hiragana",
            "nivel": "かな",
            "puedo": ["Puedo leer, oír y escribir estos kana."],
            "sabes": {
                "vista": "tabla",
                "filas": [
                    ["ja:kana:あ", "ja:kana:い", "ja:kana:う"],
                    ["ja:kana:え", "ja:kana:お", "ja:kana:を"],
                ],
            },
            "lecciones": [
                {
                    "id": "a",
                    "titulo": "あ い う",
                    "bajada": "la fila de あ",
                    "plantilla": "kana",
                    "items": ["ja:kana:あ", "ja:kana:い", "ja:kana:う"],
                },
                {
                    "id": "e",
                    "titulo": "え お を",
                    "bajada": "え, お y を",
                    "plantilla": "kana",
                    "items": ["ja:kana:え", "ja:kana:お", "ja:kana:を"],
                },
            ],
        }
    ],
}


def mapa_mini() -> dict:
    """Una copia que el test puede cambiar sin tocar la de los demás."""
    return copy.deepcopy(MAPA_MINI)


def kana_mini() -> list[dict]:
    return copy.deepcopy(KANA_MINI)


def escribir_catalogo_mini(
    raiz: Path,
    *,
    kana: list[dict] | None = None,
    mapa: dict | None = None,
    sin_audio: tuple[str, ...] = (),
) -> Path:
    ja = raiz / "ja"
    (ja / "audio").mkdir(parents=True, exist_ok=True)
    kana = KANA_MINI if kana is None else kana
    for k in kana:
        if k["audio"] not in sin_audio:
            (ja / "audio" / k["audio"]).write_bytes(b"ID3")
    (ja / "kana.json").write_text(
        json.dumps({"fuente": "prueba", "kana": kana}, ensure_ascii=False), encoding="utf-8"
    )
    (ja / "mapa.json").write_text(
        json.dumps(MAPA_MINI if mapa is None else mapa, ensure_ascii=False), encoding="utf-8"
    )
    return raiz
```

`backend/tests/ayudas.py`:

```python
"""Ayudas compartidas por los tests de Klara en tres idiomas."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from klara.models import User
from klara.models.enums import CEFRLevel

PASSWORD = "hunter2hunter2"


async def crear_usuario(
    db, *, target_language: str = "de", study_languages: list[str] | None = None
) -> User:
    u = User(
        id=uuid.uuid4(),
        email=f"u-{uuid.uuid4().hex[:8]}@klara.app",
        hashed_password="x",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        display_name="Samuel",
        level=CEFRLevel.A1,
        native_language="es",
        target_language=target_language,
        study_languages=study_languages,
    )
    db.add(u)
    await db.commit()
    return u


async def entrar(client, seed_invite, email: str) -> str:
    """Registra una cuenta por invitación, inicia sesión y devuelve la cookie."""
    token = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "invite_token": token},
    )
    assert r.status_code == 201, r.text
    r2 = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": email, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r2.status_code == 204, r2.text
    return r2.headers["set-cookie"].split(";")[0]


async def usuario_por_email(db, email: str) -> User:
    return (await db.execute(select(User).where(User.email == email))).scalar_one()
```

Al final de `backend/tests/conftest.py`, agrega:

```python
@pytest.fixture
def catalogo_mini(tmp_path, monkeypatch):
    """El catálogo de juguete (tests/catalogo_mini.py), servido por get_catalogo()
    a todo el que lo pida durante el test, incluida la app de `client`."""
    from klara.catalogo.cargar import get_catalogo
    from tests.catalogo_mini import escribir_catalogo_mini

    raiz = escribir_catalogo_mini(tmp_path / "mapas")
    monkeypatch.setenv("KLARA_MAPAS_DIR", str(raiz))
    get_catalogo.cache_clear()
    yield get_catalogo()
    get_catalogo.cache_clear()
```

- [ ] **Step 2: Escribir los tests del cargador**

`backend/tests/test_catalogo_cargar.py`:

```python
"""Cargar y validar el catálogo (spec §2.1): si algo no cuadra, CatalogoInvalido
con TODOS los errores."""

import pytest

from klara.catalogo.cargar import CatalogoInvalido, cargar_catalogo
from tests.catalogo_mini import escribir_catalogo_mini, kana_mini, mapa_mini


def _errores(tmp_path, **kw) -> list[str]:
    with pytest.raises(CatalogoInvalido) as e:
        cargar_catalogo(escribir_catalogo_mini(tmp_path / "mapas", **kw))
    return e.value.errores


def _con_leccion(actividades: list[dict]) -> dict:
    m = mapa_mini()
    m["unidades"][0]["lecciones"].append(
        {"id": "x", "titulo": "x", "bajada": "x", "actividades": actividades}
    )
    return m


def _act(dinamica, modo, faceta, items=("ja:kana:あ",)) -> dict:
    return {"dinamica": dinamica, "modo": modo, "items": list(items), "faceta": faceta}


def test_carga_el_catalogo_mini(tmp_path):
    cat = cargar_catalogo(escribir_catalogo_mini(tmp_path / "mapas"))
    assert list(cat.mapas) == ["ja"]
    assert len(cat.items) == 6
    assert list(cat.lecciones) == ["ja/hiragana/a", "ja/hiragana/e"]
    acts = cat.lecciones["ja/hiragana/a"].leccion.actividades
    # 3 kana: trazo presentar+practicar (6), elección reconocer+oír (6), tablero (1),
    # prueba: trazo, reconocer y oír (9).
    assert len(acts) == 22
    assert [(a.dinamica, a.modo) for a in acts[:2]] == [("trazo", "presentar"), ("trazo", "practicar")]
    assert cat.audio_path("ja", "a.mp3").is_file()
    assert [lec.id for lec in cat.lecciones_de("ja")] == ["ja/hiragana/a", "ja/hiragana/e"]


def test_item_que_no_existe(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["lecciones"][0]["items"].append("ja:kana:か")
    assert any("ja:kana:か" in e and "no existe" in e for e in _errores(tmp_path, mapa=m))


def test_faceta_que_no_es_del_tipo(tmp_path):
    m = _con_leccion([_act("trazo", "practicar", "genero"), _act("trazo", "comprobar", "genero")])
    assert any("'genero' no es faceta de ja:kana" in e for e in _errores(tmp_path, mapa=m))


def test_modo_que_la_dinamica_no_soporta(tmp_path):
    m = _con_leccion([_act("emparejar", "comprobar", "reconocer", ("ja:kana:あ", "ja:kana:い"))])
    assert any("emparejar no soporta el modo comprobar" in e for e in _errores(tmp_path, mapa=m))


def test_dinamica_que_no_ejercita_esa_faceta(tmp_path):
    m = _con_leccion([_act("eleccion", "practicar", "escribir"), _act("eleccion", "comprobar", "escribir")])
    assert any("eleccion no ejercita ja:kana × escribir" in e for e in _errores(tmp_path, mapa=m))


def test_dinamica_desconocida(tmp_path):
    m = _con_leccion([_act("dictado", "comprobar", "oir")])
    assert any("dinámica desconocida 'dictado'" in e for e in _errores(tmp_path, mapa=m))


def test_practica_sin_prueba(tmp_path):
    m = _con_leccion([_act("eleccion", "practicar", "reconocer")])
    assert any(
        "practica ja:kana:あ × reconocer y no lo comprueba" in e for e in _errores(tmp_path, mapa=m)
    )


def test_falta_un_audio(tmp_path):
    assert any("falta el audio i.mp3" in e for e in _errores(tmp_path, sin_audio=("i.mp3",)))


def test_kana_sin_trazos(tmp_path):
    kana = kana_mini()
    kana[1]["trazos"] = []
    assert any("い sin trazos" in e for e in _errores(tmp_path, kana=kana))


def test_confusion_fuera_del_inventario(tmp_path):
    kana = kana_mini()
    kana[0]["confusiones"] = ["ぬ"]
    assert any("confunde con ぬ" in e for e in _errores(tmp_path, kana=kana))


def test_plantilla_desconocida(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["lecciones"][0]["plantilla"] = "kanji"
    assert any("plantilla desconocida 'kanji'" in e for e in _errores(tmp_path, mapa=m))


def test_nivel_fuera_de_la_escala(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["nivel"] = "N1"
    assert any("'N1' no está en la escala" in e for e in _errores(tmp_path, mapa=m))


def test_lo_que_sabes_nombra_algo_de_otra_unidad(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["lecciones"][1]["items"].remove("ja:kana:を")
    assert any(
        "nombra ja:kana:を, que no está en la unidad" in e for e in _errores(tmp_path, mapa=m)
    )


def test_leccion_repetida(tmp_path):
    m = mapa_mini()
    m["unidades"][0]["lecciones"][1]["id"] = "a"
    assert any("id de lección repetido" in e for e in _errores(tmp_path, mapa=m))


def test_el_mapa_dice_otro_idioma(tmp_path):
    m = mapa_mini()
    m["idioma"] = "de"
    assert any("dice idioma 'de'" in e for e in _errores(tmp_path, mapa=m))


def test_json_roto(tmp_path):
    raiz = escribir_catalogo_mini(tmp_path / "mapas")
    (raiz / "ja" / "mapa.json").write_text("{ esto no es json", encoding="utf-8")
    with pytest.raises(CatalogoInvalido) as e:
        cargar_catalogo(raiz)
    assert any("mapa.json" in err for err in e.value.errores)


def test_idioma_sin_inventario(tmp_path):
    raiz = escribir_catalogo_mini(tmp_path / "mapas")
    (raiz / "xx").mkdir()
    with pytest.raises(CatalogoInvalido) as e:
        cargar_catalogo(raiz)
    assert any("xx: no hay inventario registrado" in err for err in e.value.errores)


def test_junta_todos_los_errores(tmp_path):
    errores = _errores(tmp_path, sin_audio=("i.mp3", "u.mp3"))
    assert any("i.mp3" in e for e in errores)
    assert any("u.mp3" in e for e in errores)


def test_get_catalogo_usa_klara_mapas_dir(catalogo_mini):
    assert list(catalogo_mini.mapas) == ["ja"]
    assert len(catalogo_mini.items) == 6
```

- [ ] **Step 3: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_cargar.py -v`
Expected: falla con `ModuleNotFoundError: No module named 'klara.catalogo.cargar'`.

- [ ] **Step 4: Implementar el modelo**

`backend/src/klara/catalogo/modelo.py`:

```python
"""El catálogo como datos (spec §2.1): mapas, unidades, lecciones, actividades e
inventarios. Aquí solo hay forma; la validación cruzada vive en `cargar.py`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Modo = Literal["presentar", "practicar", "comprobar"]


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Actividad(_Estricto):
    dinamica: str
    modo: Modo
    items: tuple[str, ...] = Field(min_length=1)
    faceta: str


class Leccion(_Estricto):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    titulo: str
    bajada: str
    plantilla: str | None = None
    items: tuple[str, ...] = ()
    actividades: tuple[Actividad, ...] = ()


class Sabes(_Estricto):
    vista: Literal["tabla", "lista"]
    filas: tuple[tuple[str | None, ...], ...] | None = None


class Unidad(_Estricto):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    titulo: str
    nivel: str
    puedo: tuple[str, ...] = Field(min_length=1)
    sabes: Sabes
    lecciones: tuple[Leccion, ...] = Field(min_length=1)


class Mapa(_Estricto):
    idioma: str
    escala: tuple[str, ...] = Field(min_length=1)
    unidades: tuple[Unidad, ...] = Field(min_length=1)


class Kana(_Estricto):
    kana: str = Field(min_length=1, max_length=1)
    romaji: str
    # Lo que suena. お y を suenan igual: `oír` nunca los pone juntos.
    sonido: str
    confusiones: tuple[str, ...] = ()
    trazos: tuple[str, ...] = ()
    audio: str = Field(pattern=r"^[a-z0-9_-]+\.mp3$")
    mnemotecnia: str


class InventarioKana(_Estricto):
    fuente: str
    kana: tuple[Kana, ...]


# Los planes 2 y 3 amplían la unión (Sustantivo, Caso, Contraste).
Item = Kana


@dataclass(frozen=True)
class LeccionCompleta:
    id: str  # "ja/hiragana/ka"
    idioma: str
    unidad: str
    leccion: Leccion  # con `actividades` ya expandidas


@dataclass(frozen=True)
class Catalogo:
    raiz: Path
    mapas: dict[str, Mapa]
    items: dict[str, Item]
    # En el orden de los mapas: la siguiente lección es la primera sin terminar.
    lecciones: dict[str, LeccionCompleta]

    def lecciones_de(self, idioma: str) -> list[LeccionCompleta]:
        return [lec for lec in self.lecciones.values() if lec.idioma == idioma]

    def audio_path(self, idioma: str, archivo: str) -> Path:
        return self.raiz / idioma / "audio" / archivo
```

- [ ] **Step 5: Implementar la plantilla `kana`**

`backend/src/klara/catalogo/plantillas.py`:

```python
"""Plantillas de lección (spec §2.1, §6): convierten los ítems de una lección en
actividades. Cada plantilla comprueba todo lo que practica; el cargador lo
verifica igual."""

from collections.abc import Callable

from klara.catalogo.modelo import Actividad


def _a(dinamica: str, modo: str, items, faceta: str) -> Actividad:
    return Actividad(dinamica=dinamica, modo=modo, items=tuple(items), faceta=faceta)


def kana(items: tuple[str, ...]) -> tuple[Actividad, ...]:
    """Una fila de kana (spec §6.1): presentar y practicar el trazo de cada uno,
    elegir (reconocer y oír), el tablero, y la prueba."""
    acts: list[Actividad] = []
    for k in items:
        acts.append(_a("trazo", "presentar", [k], "escribir"))
        acts.append(_a("trazo", "practicar", [k], "escribir"))
    acts += [_a("eleccion", "practicar", [k], "reconocer") for k in items]
    acts += [_a("eleccion", "practicar", [k], "oir") for k in reversed(items)]
    if len(items) > 1:
        acts.append(_a("emparejar", "practicar", items, "reconocer"))
    acts += [_a("trazo", "comprobar", [k], "escribir") for k in items]
    acts += [_a("eleccion", "comprobar", [k], "reconocer") for k in reversed(items)]
    acts += [_a("eleccion", "comprobar", [k], "oir") for k in items]
    return tuple(acts)


PLANTILLAS: dict[str, Callable[[tuple[str, ...]], tuple[Actividad, ...]]] = {"kana": kana}
```

- [ ] **Step 6: Implementar el cargador**

`backend/src/klara/catalogo/cargar.py`:

```python
"""Carga y valida el catálogo (spec §2.1). Si algo no cuadra, el servidor no
arranca: `CatalogoInvalido` junta TODOS los errores, no solo el primero."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ValidationError

from klara.catalogo.dinamicas import DINAMICAS, ejercita
from klara.catalogo.facetas import faceta_valida, partes, tipo_de
from klara.catalogo.modelo import (
    Actividad,
    Catalogo,
    InventarioKana,
    Item,
    Leccion,
    LeccionCompleta,
    Mapa,
)
from klara.catalogo.plantillas import PLANTILLAS

RAIZ_MAPAS = Path(__file__).resolve().parent.parent / "mapas"


class CatalogoInvalido(Exception):
    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__("catálogo inválido:\n- " + "\n- ".join(errores))


def _leer[M: BaseModel](path: Path, modelo: type[M], errores: list[str]) -> M | None:
    try:
        return modelo.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as e:
        errores.append(f"{path.parent.name}/{path.name}: {e}")
        return None


def _inventario_ja(dir_: Path, errores: list[str]) -> dict[str, Item]:
    inv = _leer(dir_ / "kana.json", InventarioKana, errores)
    if inv is None:
        return {}
    items: dict[str, Item] = {}
    for k in inv.kana:
        clave = f"ja:kana:{k.kana}"
        if clave in items:
            errores.append(f"ja/kana.json: {k.kana} repetido")
        if not k.trazos:
            errores.append(f"ja/kana.json: {k.kana} sin trazos")
        if not (dir_ / "audio" / k.audio).is_file():
            errores.append(f"ja/kana.json: falta el audio {k.audio}")
        items[clave] = k
    for k in inv.kana:
        for c in k.confusiones:
            if f"ja:kana:{c}" not in items:
                errores.append(f"ja/kana.json: {k.kana} confunde con {c}, que no está en el inventario")
    return items


# Un cargador de inventario por idioma. Los planes 2 y 3 agregan «de» y «en».
INVENTARIOS: dict[str, Callable[[Path, list[str]], dict[str, Item]]] = {"ja": _inventario_ja}


def _validar_actividad(a: Actividad, donde: str, items: dict[str, Item], errores: list[str]) -> None:
    d = DINAMICAS.get(a.dinamica)
    if d is None:
        errores.append(f"{donde}: dinámica desconocida {a.dinamica!r}")
        return
    if a.modo not in d.modos:
        errores.append(f"{donde}: {a.dinamica} no soporta el modo {a.modo}")
    for item in a.items:
        if item not in items:
            errores.append(f"{donde}: el ítem {item!r} no existe")
        elif not faceta_valida(item, a.faceta):
            errores.append(f"{donde}: {a.faceta!r} no es faceta de {tipo_de(item)}")
        elif not ejercita(d, tipo_de(item), a.faceta):
            errores.append(f"{donde}: {a.dinamica} no ejercita {tipo_de(item)} × {a.faceta}")


def _expandir(leccion: Leccion, donde: str, errores: list[str]) -> Leccion:
    if leccion.plantilla is None:
        if not leccion.actividades:
            errores.append(f"{donde}: sin plantilla ni actividades")
        return leccion
    plantilla = PLANTILLAS.get(leccion.plantilla)
    if plantilla is None:
        errores.append(f"{donde}: plantilla desconocida {leccion.plantilla!r}")
        return leccion
    if not leccion.items:
        errores.append(f"{donde}: la plantilla {leccion.plantilla} necesita items")
        return leccion
    return leccion.model_copy(update={"actividades": plantilla(leccion.items) + leccion.actividades})


def _comprueba_lo_que_practica(leccion: Leccion, donde: str, errores: list[str]) -> None:
    def pares(modo: str) -> set[tuple[str, str]]:
        return {(i, a.faceta) for a in leccion.actividades if a.modo == modo for i in a.items}

    for item, faceta in sorted(pares("practicar") - pares("comprobar")):
        errores.append(f"{donde}: practica {item} × {faceta} y no lo comprueba")


def cargar_catalogo(raiz: Path = RAIZ_MAPAS) -> Catalogo:
    errores: list[str] = []
    mapas: dict[str, Mapa] = {}
    items: dict[str, Item] = {}
    lecciones: dict[str, LeccionCompleta] = {}

    for dir_ in sorted(p for p in raiz.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        idioma = dir_.name
        cargar_inventario = INVENTARIOS.get(idioma)
        if cargar_inventario is None:
            errores.append(f"{idioma}: no hay inventario registrado para este idioma")
            continue
        items.update(cargar_inventario(dir_, errores))
        mapa = _leer(dir_ / "mapa.json", Mapa, errores)
        if mapa is None:
            continue
        if mapa.idioma != idioma:
            errores.append(f"{idioma}/mapa.json: dice idioma {mapa.idioma!r}")
        unidades_vistas: set[str] = set()
        for unidad in mapa.unidades:
            if unidad.id in unidades_vistas:
                errores.append(f"{idioma}/{unidad.id}: unidad repetida")
            unidades_vistas.add(unidad.id)
            if unidad.nivel not in mapa.escala:
                errores.append(f"{idioma}/{unidad.id}: el nivel {unidad.nivel!r} no está en la escala")
            ids: set[str] = set()
            de_la_unidad: set[str] = set()
            for leccion in unidad.lecciones:
                donde = f"{idioma}/{unidad.id}/{leccion.id}"
                if leccion.id in ids:
                    errores.append(f"{donde}: id de lección repetido")
                ids.add(leccion.id)
                expandida = _expandir(leccion, donde, errores)
                for n, a in enumerate(expandida.actividades):
                    _validar_actividad(a, f"{donde}#{n}", items, errores)
                    for item in a.items:
                        if item in items and partes(item)[0] != idioma:
                            errores.append(f"{donde}#{n}: {item} es de otro idioma")
                _comprueba_lo_que_practica(expandida, donde, errores)
                de_la_unidad.update(i for a in expandida.actividades for i in a.items)
                lecciones[donde] = LeccionCompleta(
                    id=donde, idioma=idioma, unidad=unidad.id, leccion=expandida
                )
            for fila in unidad.sabes.filas or ():
                for item in fila:
                    if item is not None and item not in de_la_unidad:
                        errores.append(
                            f"{idioma}/{unidad.id}: «lo que sabes» nombra {item}, que no está en la unidad"
                        )
        mapas[idioma] = mapa

    if errores:
        raise CatalogoInvalido(errores)
    return Catalogo(raiz=raiz, mapas=mapas, items=items, lecciones=lecciones)


@lru_cache(maxsize=1)
def get_catalogo() -> Catalogo:
    """El catálogo de la app. `KLARA_MAPAS_DIR` lo apunta a otra carpeta (los tests)."""
    raiz = os.environ.get("KLARA_MAPAS_DIR")
    return cargar_catalogo(Path(raiz) if raiz else RAIZ_MAPAS)
```

Nota: `_leer` usa la sintaxis de genéricos de Python 3.12 (`def _leer[M: BaseModel]`). El backend corre en 3.12 (`Dockerfile.base`). Si ruff marca la sintaxis porque su `target-version` es anterior, cámbiala por un `TypeVar` sin tocar nada más.

- [ ] **Step 7: Correr y ver pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_cargar.py -v`
Expected: PASS, 19 tests.

- [ ] **Step 8: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/catalogo backend/tests/catalogo_mini.py backend/tests/ayudas.py backend/tests/conftest.py backend/tests/test_catalogo_cargar.py
git commit -m "feat(tres-idiomas): cargar y validar el catálogo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Los generadores de contenido

**Files:**
- Create: `backend/src/klara/catalogo/generar.py`
- Test: `backend/tests/test_catalogo_generar.py`

**Interfaces:**
- Consumes: `Catalogo`, `Actividad`, `Kana` (tarea 3) y `DINAMICAS` (tarea 2).
- Produces:
  - `Contexto(rng: random.Random, conocidos: frozenset[str])`
  - `GENERADORES: dict[str, Callable[[Catalogo, Actividad, Contexto], dict]]`
  - `generar(cat, act, ctx) -> dict`
  - Formas del contenido (el frontend las usa tal cual):
    - `eleccion`: `{item, faceta, pregunta: {texto, lang, audio}, opciones: [{item, texto, lang}], correcta}`
    - `trazo`: `{item, kana, romaji, audio, trazos, mnemotecnia}`
    - `emparejar`: `{pares: [{item, izquierda, derecha}], segundos, lang_izquierda, faceta}`
  - El audio va como ruta bajo la API: `"/audio/ja/a.mp3"`.

- [ ] **Step 1: Escribir los tests**

`backend/tests/test_catalogo_generar.py`:

```python
"""El contenido de cada actividad (spec §3.1): sale del catálogo, igual para
lecciones y repasos."""

import random

from klara.catalogo.dinamicas import DINAMICAS
from klara.catalogo.generar import GENERADORES, Contexto, generar
from klara.catalogo.modelo import Actividad


def _ctx(cat, conocidos=None, semilla=1) -> Contexto:
    return Contexto(
        rng=random.Random(semilla),
        conocidos=frozenset(cat.items if conocidos is None else conocidos),
    )


def _act(dinamica, modo, items, faceta) -> Actividad:
    return Actividad(dinamica=dinamica, modo=modo, items=tuple(items), faceta=faceta)


def test_hay_un_generador_por_dinamica():
    assert set(GENERADORES) == set(DINAMICAS)


def test_eleccion_reconocer(catalogo_mini):
    c = generar(
        catalogo_mini, _act("eleccion", "practicar", ["ja:kana:あ"], "reconocer"), _ctx(catalogo_mini)
    )
    assert c["pregunta"] == {"texto": "あ", "lang": "ja", "audio": None}
    assert c["correcta"] == "ja:kana:あ"
    assert c["faceta"] == "reconocer"
    assert len(c["opciones"]) == 4
    assert {"item": "ja:kana:あ", "texto": "a", "lang": None} in c["opciones"]


def test_la_confusion_va_siempre(catalogo_mini):
    act = _act("eleccion", "practicar", ["ja:kana:あ"], "reconocer")
    for semilla in range(10):
        c = generar(catalogo_mini, act, _ctx(catalogo_mini, semilla=semilla))
        assert "ja:kana:お" in {o["item"] for o in c["opciones"]}


def test_distractores_solo_de_lo_conocido(catalogo_mini):
    conocidos = {"ja:kana:あ", "ja:kana:い", "ja:kana:う"}
    c = generar(
        catalogo_mini,
        _act("eleccion", "practicar", ["ja:kana:あ"], "reconocer"),
        _ctx(catalogo_mini, conocidos),
    )
    assert {o["item"] for o in c["opciones"]} <= conocidos
    assert len(c["opciones"]) == 3  # solo hay dos distractores conocidos


def test_oir_nunca_junta_dos_que_suenan_igual(catalogo_mini):
    act = _act("eleccion", "comprobar", ["ja:kana:を"], "oir")
    for semilla in range(20):
        c = generar(catalogo_mini, act, _ctx(catalogo_mini, semilla=semilla))
        assert "ja:kana:お" not in {o["item"] for o in c["opciones"]}
        assert c["pregunta"] == {"texto": None, "lang": "ja", "audio": "/audio/ja/wo.mp3"}
        assert all(o["lang"] == "ja" for o in c["opciones"])


def test_misma_semilla_mismo_contenido(catalogo_mini):
    act = _act("eleccion", "practicar", ["ja:kana:い"], "reconocer")
    assert generar(catalogo_mini, act, _ctx(catalogo_mini, semilla=7)) == generar(
        catalogo_mini, act, _ctx(catalogo_mini, semilla=7)
    )


def test_trazo(catalogo_mini):
    c = generar(catalogo_mini, _act("trazo", "comprobar", ["ja:kana:あ"], "escribir"), _ctx(catalogo_mini))
    assert c["item"] == "ja:kana:あ"
    assert c["kana"] == "あ"
    assert c["romaji"] == "a"
    assert len(c["trazos"]) == 3
    assert c["audio"] == "/audio/ja/a.mp3"
    assert c["mnemotecnia"]


def test_emparejar(catalogo_mini):
    items = ["ja:kana:あ", "ja:kana:い", "ja:kana:う"]
    c = generar(catalogo_mini, _act("emparejar", "practicar", items, "reconocer"), _ctx(catalogo_mini))
    assert sorted(p["item"] for p in c["pares"]) == sorted(items)
    assert {p["izquierda"]: p["derecha"] for p in c["pares"]} == {"あ": "a", "い": "i", "う": "u"}
    assert c["segundos"] == 45
    assert c["lang_izquierda"] == "ja"
    assert c["faceta"] == "reconocer"
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_generar.py -v`
Expected: falla con `ModuleNotFoundError: No module named 'klara.catalogo.generar'`.

- [ ] **Step 3: Implementar**

`backend/src/klara/catalogo/generar.py`:

```python
"""El contenido de cada actividad, generado del catálogo (spec §3.1). Las
lecciones y los repasos usan los mismos generadores, así nunca se separan.

Los distractores salen solo de lo que ya se presentó (`Contexto.conocidos`): una
opción que nunca viste no enseña nada."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from klara.catalogo.modelo import Actividad, Catalogo, Kana

TABLERO_SEGUNDOS = 45


@dataclass(frozen=True)
class Contexto:
    rng: random.Random
    conocidos: frozenset[str]


def _audio(idioma: str, archivo: str) -> str:
    """Ruta bajo la API; el frontend le antepone apiBase()."""
    return f"/audio/{idioma}/{archivo}"


def _kana(cat: Catalogo, item: str) -> Kana:
    return cat.items[item]


def _distractores(cat: Catalogo, item: str, ctx: Contexto, n: int = 3) -> list[str]:
    """Primero las confusiones que ya viste, después lo demás que ya viste; nunca
    un kana que suene igual (お/を)."""
    k = _kana(cat, item)

    def vale(otro: str) -> bool:
        return otro != item and otro in ctx.conocidos and _kana(cat, otro).sonido != k.sonido

    primero = [f"ja:kana:{c}" for c in k.confusiones if vale(f"ja:kana:{c}")]
    resto = sorted(o for o in ctx.conocidos if o.startswith("ja:kana:") and vale(o) and o not in primero)
    ctx.rng.shuffle(resto)
    return (primero + resto)[:n]


def eleccion(cat: Catalogo, act: Actividad, ctx: Contexto) -> dict:
    item = act.items[0]
    k = _kana(cat, item)
    opciones = [item, *_distractores(cat, item, ctx)]
    ctx.rng.shuffle(opciones)
    if act.faceta == "reconocer":
        return {
            "item": item,
            "faceta": "reconocer",
            "pregunta": {"texto": k.kana, "lang": "ja", "audio": None},
            "opciones": [{"item": o, "texto": _kana(cat, o).romaji, "lang": None} for o in opciones],
            "correcta": item,
        }
    return {
        "item": item,
        "faceta": "oir",
        "pregunta": {"texto": None, "lang": "ja", "audio": _audio("ja", k.audio)},
        "opciones": [{"item": o, "texto": _kana(cat, o).kana, "lang": "ja"} for o in opciones],
        "correcta": item,
    }


def trazo(cat: Catalogo, act: Actividad, ctx: Contexto) -> dict:
    item = act.items[0]
    k = _kana(cat, item)
    return {
        "item": item,
        "kana": k.kana,
        "romaji": k.romaji,
        "audio": _audio("ja", k.audio),
        "trazos": list(k.trazos),
        "mnemotecnia": k.mnemotecnia,
    }


def emparejar(cat: Catalogo, act: Actividad, ctx: Contexto) -> dict:
    pares = [
        {"item": i, "izquierda": _kana(cat, i).kana, "derecha": _kana(cat, i).romaji}
        for i in act.items
    ]
    ctx.rng.shuffle(pares)
    # La faceta viaja en el contenido: en alemán (plan 2) el tablero ejercita el género.
    return {"pares": pares, "segundos": TABLERO_SEGUNDOS, "lang_izquierda": "ja", "faceta": act.faceta}


GENERADORES: dict[str, Callable[[Catalogo, Actividad, Contexto], dict]] = {
    "eleccion": eleccion,
    "trazo": trazo,
    "emparejar": emparejar,
}


def generar(cat: Catalogo, act: Actividad, ctx: Contexto) -> dict:
    return GENERADORES[act.dinamica](cat, act, ctx)
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_generar.py -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/catalogo/generar.py backend/tests/test_catalogo_generar.py
git commit -m "feat(tres-idiomas): generar el contenido de las actividades

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Importador de trazos de KanjiVG

**Files:**
- Create: `backend/src/klara/scripts/importar_kanjivg.py`
- Test: `backend/tests/test_importar_kanjivg.py`

**Interfaces:**
- Produces:
  - `TRAZOS_ESPERADOS: dict[str, int]`: los 46 hiragana básicos y su número de trazos.
  - `codigo(kana) -> str`: el nombre de archivo de KanjiVG, p. ej. `"03042"`.
  - `trazos_de_svg(svg) -> list[str]`: los `d` de los trazos, en orden.
  - `aplicar_trazos(data, bajar) -> list[str]`: devuelve los errores, y si hay alguno no toca `data`.
  - El CLI: `uv run python -m klara.scripts.importar_kanjivg [--ref master]`.

- [ ] **Step 1: Escribir los tests**

`backend/tests/test_importar_kanjivg.py`:

```python
"""Trazos de KanjiVG → kana.json (spec §7): se leen como datos y se cuentan."""

from klara.scripts.importar_kanjivg import TRAZOS_ESPERADOS, aplicar_trazos, codigo, trazos_de_svg

HIRAGANA = (
    "あいうえおかきくけこさしすせそたちつてとなにぬねの"
    "はひふへほまみむめもやゆよらりるれろわをん"
)

SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="109" height="109" viewBox="0 0 109 109">
<g id="kvg:StrokePaths_03042" style="fill:none;stroke:#000000;stroke-width:3;">
<g id="kvg:03042" kvg:element="あ">
  <path id="kvg:03042-s2" kvg:type="㇕" d="M51.27,18.88c0.75,1.26,0.98,2.62,0.62,4.32"/>
  <path id="kvg:03042-s1" kvg:type="㇐" d="M31.01,33.21c0.83,0.79,3.07,1.36,4.68,1.25"/>
  <path id="kvg:03042-s3" kvg:type="㇒" d="M66.91,46.29c0.45,1.41,0.24,2.82-0.24,4.39"/>
</g>
</g>
<g id="kvg:StrokeNumbers_03042"><text transform="matrix(1 0 0 1 24.5 34.5)">1</text></g>
</svg>"""


def test_la_tabla_tiene_los_46():
    assert set(TRAZOS_ESPERADOS) == set(HIRAGANA)
    assert len(HIRAGANA) == 46
    assert TRAZOS_ESPERADOS["あ"] == 3
    assert TRAZOS_ESPERADOS["ん"] == 1


def test_codigo():
    assert codigo("あ") == "03042"
    assert codigo("ん") == "03093"


def test_trazos_en_orden_y_sin_lo_que_no_es_trazo():
    assert trazos_de_svg(SVG) == [
        "M31.01,33.21c0.83,0.79,3.07,1.36,4.68,1.25",
        "M51.27,18.88c0.75,1.26,0.98,2.62,0.62,4.32",
        "M66.91,46.29c0.45,1.41,0.24,2.82-0.24,4.39",
    ]


def _svg_con(n: int) -> str:
    paths = "".join(f'<path id="kvg:0-s{i}" d="M{i},0 L{i},9"/>' for i in range(1, n + 1))
    return f"<svg>{paths}</svg>"


def test_aplicar_trazos_cuando_cuadran():
    data = {"kana": [{"kana": "あ", "trazos": []}, {"kana": "ん", "trazos": []}]}
    errores = aplicar_trazos(data, lambda k: _svg_con(TRAZOS_ESPERADOS[k]))
    assert errores == []
    assert [len(e["trazos"]) for e in data["kana"]] == [3, 1]


def test_si_no_cuadra_no_toca_nada():
    data = {"kana": [{"kana": "あ", "trazos": []}, {"kana": "ん", "trazos": []}]}
    errores = aplicar_trazos(data, lambda k: _svg_con(2))
    assert errores == ["あ: KanjiVG trae 2 trazos y la tabla dice 3", "ん: KanjiVG trae 2 trazos y la tabla dice 1"]
    assert all(e["trazos"] == [] for e in data["kana"])
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_importar_kanjivg.py -v`
Expected: falla con `ModuleNotFoundError: No module named 'klara.scripts.importar_kanjivg'`.

- [ ] **Step 3: Implementar**

`backend/src/klara/scripts/importar_kanjivg.py`:

```python
"""Importa los trazos de los kana desde KanjiVG (CC BY-SA 3.0) a `mapas/ja/kana.json`.

Corre una vez al preparar el contenido (spec §7):
1. Baja un SVG por kana del repo de KanjiVG.
2. Saca los `d` de sus trazos, en orden.
3. Compara el número de trazos con la tabla estándar.

Si un solo kana no cuadra, no escribe nada. Lo descargado es dato, no código:
solo se lee con expresiones regulares.

    uv run python -m klara.scripts.importar_kanjivg [--ref master]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

KANJIVG_RAW = "https://raw.githubusercontent.com/KanjiVG/kanjivg/{ref}/kanji/{codigo}.svg"
KANA_JSON = Path(__file__).resolve().parents[1] / "mapas" / "ja" / "kana.json"

# Los trazos de los 46 hiragana básicos, según KanjiVG.
TRAZOS_ESPERADOS: dict[str, int] = {
    "あ": 3, "い": 2, "う": 2, "え": 2, "お": 3,
    "か": 3, "き": 4, "く": 1, "け": 3, "こ": 2,
    "さ": 3, "し": 1, "す": 2, "せ": 3, "そ": 1,
    "た": 4, "ち": 2, "つ": 1, "て": 1, "と": 2,
    "な": 4, "に": 3, "ぬ": 2, "ね": 2, "の": 1,
    "は": 3, "ひ": 1, "ふ": 4, "へ": 1, "ほ": 4,
    "ま": 3, "み": 2, "む": 3, "め": 2, "も": 3,
    "や": 3, "ゆ": 2, "よ": 2,
    "ら": 2, "り": 2, "る": 1, "れ": 2, "ろ": 1,
    "わ": 2, "を": 3, "ん": 1,
}  # fmt: skip

_PATH = re.compile(r"<path\b[^>]*>")
_ID = re.compile(r'\bid="kvg:[0-9a-f]+-s(\d+)"')
_D = re.compile(r'\bd="([^"]+)"')


def codigo(kana: str) -> str:
    return f"{ord(kana):05x}"


def trazos_de_svg(svg: str) -> list[str]:
    """Los `d` de los trazos, en el orden de KanjiVG (s1, s2…). Los <path> sin id
    de trazo y los <text> de los números se ignoran."""
    trazos: list[tuple[int, str]] = []
    for tag in _PATH.findall(svg):
        m_id, m_d = _ID.search(tag), _D.search(tag)
        if m_id and m_d:
            trazos.append((int(m_id.group(1)), m_d.group(1)))
    return [d for _, d in sorted(trazos)]


def aplicar_trazos(data: dict, bajar: Callable[[str], str]) -> list[str]:
    """Pone en cada kana de `data` los trazos de KanjiVG. Devuelve los errores; si
    hay alguno, no toca `data`."""
    nuevos: dict[str, list[str]] = {}
    errores: list[str] = []
    for entrada in data["kana"]:
        k = entrada["kana"]
        trazos = trazos_de_svg(bajar(k))
        esperados = TRAZOS_ESPERADOS.get(k)
        if esperados is None:
            errores.append(f"{k}: no está en la tabla de trazos")
        elif len(trazos) != esperados:
            errores.append(f"{k}: KanjiVG trae {len(trazos)} trazos y la tabla dice {esperados}")
        nuevos[k] = trazos
    if not errores:
        for entrada in data["kana"]:
            entrada["trazos"] = nuevos[entrada["kana"]]
    return errores


def _bajar(ref: str) -> Callable[[str], str]:
    def bajar(kana: str) -> str:
        url = KANJIVG_RAW.format(ref=ref, codigo=codigo(kana))
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.read().decode("utf-8")

    return bajar


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Trazos de KanjiVG → mapas/ja/kana.json")
    p.add_argument("--ref", default="master", help="rama o tag de KanjiVG (por defecto: master)")
    args = p.parse_args(argv)

    data = json.loads(KANA_JSON.read_text(encoding="utf-8"))
    errores = aplicar_trazos(data, _bajar(args.ref))
    if errores:
        print("No se escribió nada:\n  " + "\n  ".join(errores), file=sys.stderr)
        return 1
    data["fuente"] = f"KanjiVG {args.ref} (CC BY-SA 3.0, Ulrich Apel y colaboradores)"
    KANA_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(data['kana'])} kana con trazos en {KANA_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_importar_kanjivg.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/scripts/importar_kanjivg.py backend/tests/test_importar_kanjivg.py
git commit -m "feat(tres-idiomas): importar los trazos de KanjiVG

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Generador de audio del catálogo

**Files:**
- Create: `backend/src/klara/scripts/generar_audio_catalogo.py`
- Test: `backend/tests/test_generar_audio_catalogo.py`

**Interfaces:**
- Consumes:
  - `RAIZ_MAPAS` (tarea 3);
  - `get_settings()` (`azure_speech_key`, `azure_speech_region`);
  - `score_pronunciation(wav_path, reference_text, language, *, azure_key, azure_region) -> ScoreResponse` (`klara.pronunciation.azure_client`), cuya puntuación está en `.scores.accuracy`.
- Produces:
  - `pendientes(kana, audio_dir, *, solo, forzar) -> list[dict]`
  - `ssml(texto, idioma, *, lento) -> str`
  - El CLI: `uv run python -m klara.scripts.generar_audio_catalogo [--solo あ,か] [--forzar]`.

- [ ] **Step 1: Escribir los tests de las partes puras**

`backend/tests/test_generar_audio_catalogo.py`:

```python
"""El generador de audio (spec §7). Lo que habla con Azure se prueba corriéndolo
(tarea 7); aquí, qué se genera y con qué SSML."""

from klara.scripts.generar_audio_catalogo import pendientes, ssml

KANA = [{"kana": "あ", "audio": "a.mp3"}, {"kana": "い", "audio": "i.mp3"}]


def test_pendientes_son_los_que_no_tienen_archivo(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"ID3")
    assert [k["kana"] for k in pendientes(KANA, tmp_path, solo=None, forzar=False)] == ["い"]


def test_forzar_los_regenera_todos(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"ID3")
    assert [k["kana"] for k in pendientes(KANA, tmp_path, solo=None, forzar=True)] == ["あ", "い"]


def test_solo_los_pedidos_aunque_existan(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"ID3")
    assert [k["kana"] for k in pendientes(KANA, tmp_path, solo={"あ"}, forzar=False)] == ["あ"]


def test_ssml_con_la_voz_y_el_idioma():
    s = ssml("あ", "ja", lento=False)
    assert 'xml:lang="ja-JP"' in s
    assert '<voice name="ja-JP-NanamiNeural">あ</voice>' in s
    assert "<prosody" not in s


def test_ssml_lento():
    assert '<prosody rate="-25%">あ</prosody>' in ssml("あ", "ja", lento=True)
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_generar_audio_catalogo.py -v`
Expected: falla con `ModuleNotFoundError: No module named 'klara.scripts.generar_audio_catalogo'`.

- [ ] **Step 3: Implementar**

`backend/src/klara/scripts/generar_audio_catalogo.py`:

```python
"""Genera y valida el audio de los kana (spec §7).

Usa Azure TTS con una voz nativa (ja-JP-NanamiNeural) y guarda el mp3 en
`mapas/ja/audio/`. Antes de guardarlo lo valida con el puntaje de Azure:
- si no pasa, prueba una vez más leyendo despacio;
- si tampoco pasa, igual lo guarda, pero lo lista para que Samuel lo escuche.

Necesita AZURE_SPEECH_KEY y AZURE_SPEECH_REGION en backend/.env, y nunca las
imprime.

    uv run python -m klara.scripts.generar_audio_catalogo [--solo あ,か] [--forzar]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from klara.catalogo.cargar import RAIZ_MAPAS
from klara.config import get_settings

VOZ = {"ja": "ja-JP-NanamiNeural"}
LOCALE = {"ja": "ja-JP"}
UMBRAL = 70.0


def pendientes(kana: list[dict], audio_dir: Path, *, solo: set[str] | None, forzar: bool) -> list[dict]:
    """Los kana que necesitan audio: los pedidos con --solo, todos con --forzar,
    o los que no tienen archivo."""
    out = []
    for k in kana:
        if solo is not None:
            if k["kana"] in solo:
                out.append(k)
        elif forzar or not (audio_dir / k["audio"]).is_file():
            out.append(k)
    return out


def ssml(texto: str, idioma: str, *, lento: bool) -> str:
    cuerpo = f'<prosody rate="-25%">{texto}</prosody>' if lento else texto
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{LOCALE[idioma]}">'
        f'<voice name="{VOZ[idioma]}">{cuerpo}</voice></speak>'
    )


def _sintetizar(texto: str, idioma: str, destino: Path, formato, *, lento: bool, key: str, region: str) -> None:
    import azure.cognitiveservices.speech as speechsdk

    cfg = speechsdk.SpeechConfig(subscription=key, region=region)
    cfg.set_speech_synthesis_output_format(formato)
    salida = speechsdk.audio.AudioOutputConfig(filename=str(destino))
    r = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=salida).speak_ssml_async(
        ssml(texto, idioma, lento=lento)
    ).get()
    if r.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(f"Azure no sintetizó {texto!r}: {r.reason}")


def _puntaje(wav: Path, texto: str, idioma: str, *, key: str, region: str) -> float:
    from klara.pronunciation.azure_client import score_pronunciation

    return score_pronunciation(wav, texto, LOCALE[idioma], azure_key=key, azure_region=region).scores.accuracy


def main(argv: list[str] | None = None) -> int:
    import azure.cognitiveservices.speech as speechsdk

    p = argparse.ArgumentParser(description="Audio de los kana con Azure, validado")
    p.add_argument("--solo", help="kana separados por coma, p. ej. あ,か")
    p.add_argument("--forzar", action="store_true", help="regenera aunque el archivo exista")
    args = p.parse_args(argv)

    s = get_settings()
    if not s.azure_speech_key:
        print("Falta AZURE_SPEECH_KEY en backend/.env", file=sys.stderr)
        return 2
    claves = {"key": s.azure_speech_key, "region": s.azure_speech_region}
    formato = speechsdk.SpeechSynthesisOutputFormat

    ja = RAIZ_MAPAS / "ja"
    audio_dir = ja / "audio"
    audio_dir.mkdir(exist_ok=True)
    data = json.loads((ja / "kana.json").read_text(encoding="utf-8"))
    solo = set(args.solo.split(",")) if args.solo else None

    escuchar: list[str] = []
    for k in pendientes(data["kana"], audio_dir, solo=solo, forzar=args.forzar):
        texto, destino = k["kana"], audio_dir / k["audio"]
        aprobado = None
        for lento in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                wav = Path(tmp) / "prueba.wav"
                _sintetizar(texto, "ja", wav, formato.Riff16Khz16BitMonoPcm, lento=lento, **claves)
                puntos = _puntaje(wav, texto, "ja", **claves)
            print(f"{texto} ({k['romaji']}){' despacio' if lento else ''}: {puntos:.0f}")
            if puntos >= UMBRAL:
                aprobado = lento
                break
        _sintetizar(
            texto, "ja", destino, formato.Audio24Khz48KBitRateMonoMp3, lento=bool(aprobado), **claves
        )
        if aprobado is None:
            escuchar.append(f"{texto} ({k['romaji']}) → {destino.name}")

    if escuchar:
        print("\nAzure no confirmó estos; escúchalos antes de dar el audio por bueno:")
        print("  " + "\n  ".join(escuchar))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_generar_audio_catalogo.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/scripts/generar_audio_catalogo.py backend/tests/test_generar_audio_catalogo.py
git commit -m "feat(tres-idiomas): generar y validar el audio del catálogo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: El mapa de japonés

Esta tarea produce contenido y llama a servicios externos (GitHub, Azure). Antes del paso 6, Samuel tiene que haber puesto las claves de Azure en `backend/.env` (ver «Antes de empezar»).

**Files:**
- Create: `backend/src/klara/mapas/ja/kana.json`
- Create: `backend/src/klara/mapas/ja/mapa.json`
- Create: `backend/src/klara/mapas/ja/KANJIVG.txt`
- Create: `backend/src/klara/mapas/ja/audio/*.mp3` (46, generados)
- Test: `backend/tests/test_catalogo_real.py`

**Interfaces:**
- Consumes: `cargar_catalogo` (tarea 3), `TRAZOS_ESPERADOS` (tarea 5), los dos scripts (tareas 5 y 6).
- Produces:
  - el catálogo real con el mapa `ja`;
  - una unidad `hiragana` con nivel `かな`;
  - 10 lecciones, `ja/hiragana/{a,ka,sa,ta,na,ha,ma,ya,ra,wa}`;
  - 46 ítems `ja:kana:*`.

- [ ] **Step 1: Escribir el test del catálogo real**

`backend/tests/test_catalogo_real.py`:

```python
"""El catálogo de verdad (backend/src/klara/mapas) carga sin errores (spec §2.1)."""

from klara.catalogo.cargar import cargar_catalogo
from klara.scripts.importar_kanjivg import TRAZOS_ESPERADOS

FILAS = ("a", "ka", "sa", "ta", "na", "ha", "ma", "ya", "ra", "wa")


def test_carga_el_mapa_de_japones():
    cat = cargar_catalogo()
    assert cat.mapas["ja"].escala == ("かな", "N5", "N4", "N3")
    kana = {k.split(":")[2] for k in cat.items if k.startswith("ja:kana:")}
    assert kana == set(TRAZOS_ESPERADOS)
    assert [lec.id for lec in cat.lecciones_de("ja")] == [f"ja/hiragana/{f}" for f in FILAS]


def test_cada_kana_con_sus_trazos_y_su_audio():
    cat = cargar_catalogo()
    for clave, k in cat.items.items():
        if clave.startswith("ja:kana:"):
            assert len(k.trazos) == TRAZOS_ESPERADOS[k.kana], k.kana
            assert cat.audio_path("ja", k.audio).stat().st_size > 1000, k.kana


def test_o_y_wo_suenan_igual_y_se_escriben_distinto():
    cat = cargar_catalogo()
    assert cat.items["ja:kana:お"].sonido == cat.items["ja:kana:を"].sonido == "o"
    assert cat.items["ja:kana:を"].romaji == "wo"
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_real.py -v`
Expected: FAIL: `FileNotFoundError` en `raiz.iterdir()`, porque `mapas/` todavía no existe.

- [ ] **Step 3: Escribir `kana.json` (sin trazos; los pone el importador)**

`backend/src/klara/mapas/ja/kana.json`:
- Las mnemotecnias son contenido: Samuel las revisa en el paso 9.
- Las confusiones son parecidos visuales, todos dentro de los 46.
- を se escribe «wo» y suena «o».

```json
{
  "fuente": "KanjiVG (pendiente de importar)",
  "kana": [
    {"kana": "あ", "romaji": "a", "sonido": "a", "confusiones": ["お", "め", "ぬ"], "trazos": [], "audio": "a.mp3", "mnemotecnia": "Una «A» con un remolino abajo: suena «a», como en «agua»."},
    {"kana": "い", "romaji": "i", "sonido": "i", "confusiones": ["り", "こ"], "trazos": [], "audio": "i.mp3", "mnemotecnia": "Dos palitos, como dos «i» sin punto: «i»."},
    {"kana": "う", "romaji": "u", "sonido": "u", "confusiones": ["つ", "ら"], "trazos": [], "audio": "u.mp3", "mnemotecnia": "Una oreja con un pelito encima: «u», como en «uña»."},
    {"kana": "え", "romaji": "e", "sonido": "e", "confusiones": ["ん", "そ"], "trazos": [], "audio": "e.mp3", "mnemotecnia": "Un pájaro elegante con su penacho: «e», de «elegante»."},
    {"kana": "お", "romaji": "o", "sonido": "o", "confusiones": ["あ", "を", "す"], "trazos": [], "audio": "o.mp3", "mnemotecnia": "Una «o» con una cruz al lado: «o», como en «oso»."},
    {"kana": "か", "romaji": "ka", "sonido": "ka", "confusiones": ["や", "け"], "trazos": [], "audio": "ka.mp3", "mnemotecnia": "Un karateca lanzando un golpe: «ka»."},
    {"kana": "き", "romaji": "ki", "sonido": "ki", "confusiones": ["さ", "ち"], "trazos": [], "audio": "ki.mp3", "mnemotecnia": "Una llave con dos dientes, «key» en inglés: «ki»."},
    {"kana": "く", "romaji": "ku", "sonido": "ku", "confusiones": ["へ", "し"], "trazos": [], "audio": "ku.mp3", "mnemotecnia": "El pico abierto de un pájaro que canta «cu-cú»: «ku»."},
    {"kana": "け", "romaji": "ke", "sonido": "ke", "confusiones": ["は", "ほ", "に"], "trazos": [], "audio": "ke.mp3", "mnemotecnia": "Un barril con un palo al lado, lleno de «queso»: «ke»."},
    {"kana": "こ", "romaji": "ko", "sonido": "ko", "confusiones": ["い", "に", "た"], "trazos": [], "audio": "ko.mp3", "mnemotecnia": "Dos lombrices que «co»nviven: «ko»."},
    {"kana": "さ", "romaji": "sa", "sonido": "sa", "confusiones": ["き", "ち"], "trazos": [], "audio": "sa.mp3", "mnemotecnia": "Un letrero de «sa»lida con el poste torcido: «sa»."},
    {"kana": "し", "romaji": "shi", "sonido": "shi", "confusiones": ["つ", "く", "も"], "trazos": [], "audio": "shi.mp3", "mnemotecnia": "Un anzuelo; suena «shi», con la «sh» de «¡shhh!»."},
    {"kana": "す", "romaji": "su", "sonido": "su", "confusiones": ["お", "む"], "trazos": [], "audio": "su.mp3", "mnemotecnia": "Una cuerda con un nudo, como un columpio: «su», de «subir»."},
    {"kana": "せ", "romaji": "se", "sonido": "se", "confusiones": ["や", "さ"], "trazos": [], "audio": "se.mp3", "mnemotecnia": "Una boca abierta con un diente arriba: «se»."},
    {"kana": "そ", "romaji": "so", "sonido": "so", "confusiones": ["て", "ろ", "え"], "trazos": [], "audio": "so.mp3", "mnemotecnia": "Una «so»ga en zigzag: «so»."},
    {"kana": "た", "romaji": "ta", "sonido": "ta", "confusiones": ["な", "こ", "に"], "trazos": [], "audio": "ta.mp3", "mnemotecnia": "Una «t» y una «a» pegadas: «ta»."},
    {"kana": "ち", "romaji": "chi", "sonido": "chi", "confusiones": ["さ", "ら", "ろ"], "trazos": [], "audio": "chi.mp3", "mnemotecnia": "Es さ en el espejo, pero suena «chi», como en «chicle»."},
    {"kana": "つ", "romaji": "tsu", "sonido": "tsu", "confusiones": ["う", "し"], "trazos": [], "audio": "tsu.mp3", "mnemotecnia": "Una ola de «tsu»nami: «tsu»."},
    {"kana": "て", "romaji": "te", "sonido": "te", "confusiones": ["そ", "ひ"], "trazos": [], "audio": "te.mp3", "mnemotecnia": "Una «T» con la pata doblada: «te»."},
    {"kana": "と", "romaji": "to", "sonido": "to", "confusiones": ["こ", "そ"], "trazos": [], "audio": "to.mp3", "mnemotecnia": "Un dedo del pie («toe» en inglés) con una astilla: «to»."},
    {"kana": "な", "romaji": "na", "sonido": "na", "confusiones": ["た", "は"], "trazos": [], "audio": "na.mp3", "mnemotecnia": "Una cruz y alguien rezando de rodillas: «na», de «Navidad»."},
    {"kana": "に", "romaji": "ni", "sonido": "ni", "confusiones": ["こ", "た", "け"], "trazos": [], "audio": "ni.mp3", "mnemotecnia": "Una raya y dos más al lado, ni una ni dos: «ni»."},
    {"kana": "ぬ", "romaji": "nu", "sonido": "nu", "confusiones": ["め", "ね", "あ"], "trazos": [], "audio": "nu.mp3", "mnemotecnia": "Fideos enredados con un nudo al final: «nu», de «nudo»."},
    {"kana": "ね", "romaji": "ne", "sonido": "ne", "confusiones": ["れ", "わ", "ぬ"], "trazos": [], "audio": "ne.mp3", "mnemotecnia": "Un gato («neko») con la cola enroscada: «ne»."},
    {"kana": "の", "romaji": "no", "sonido": "no", "confusiones": ["め", "あ"], "trazos": [], "audio": "no.mp3", "mnemotecnia": "Una señal de prohibido: «no»."},
    {"kana": "は", "romaji": "ha", "sonido": "ha", "confusiones": ["ほ", "け", "ま"], "trazos": [], "audio": "ha.mp3", "mnemotecnia": "Una «H» y una «a» juntas: «ha»."},
    {"kana": "ひ", "romaji": "hi", "sonido": "hi", "confusiones": ["へ", "て"], "trazos": [], "audio": "hi.mp3", "mnemotecnia": "Una sonrisa grande que se ríe «ji, ji»: «hi»."},
    {"kana": "ふ", "romaji": "fu", "sonido": "fu", "confusiones": ["う", "ら"], "trazos": [], "audio": "fu.mp3", "mnemotecnia": "El monte Fuji con nubes alrededor: «fu»."},
    {"kana": "へ", "romaji": "he", "sonido": "he", "confusiones": ["く", "ひ"], "trazos": [], "audio": "he.mp3", "mnemotecnia": "Una montañita; suena «he», con una «h» casi como «j»."},
    {"kana": "ほ", "romaji": "ho", "sonido": "ho", "confusiones": ["は", "ま", "け"], "trazos": [], "audio": "ho.mp3", "mnemotecnia": "は con una raya más, como el techo de un «ho»tel: «ho»."},
    {"kana": "ま", "romaji": "ma", "sonido": "ma", "confusiones": ["ほ", "も", "よ"], "trazos": [], "audio": "ma.mp3", "mnemotecnia": "Una cruz doble con un lazo abajo, el moño de «ma»má: «ma»."},
    {"kana": "み", "romaji": "mi", "sonido": "mi", "confusiones": ["よ", "め"], "trazos": [], "audio": "mi.mp3", "mnemotecnia": "Un 21 garabateado, los 21 de «mi» cumpleaños: «mi»."},
    {"kana": "む", "romaji": "mu", "sonido": "mu", "confusiones": ["す", "お"], "trazos": [], "audio": "mu.mp3", "mnemotecnia": "Una vaca con su cuerno y su cola, que dice «mu»: «mu»."},
    {"kana": "め", "romaji": "me", "sonido": "me", "confusiones": ["ぬ", "あ", "の"], "trazos": [], "audio": "me.mp3", "mnemotecnia": "Un ojo («me» en japonés) con una pestaña: «me»."},
    {"kana": "も", "romaji": "mo", "sonido": "mo", "confusiones": ["し", "ま"], "trazos": [], "audio": "mo.mp3", "mnemotecnia": "Un anzuelo con dos rayas encima, lleno de «mo»ras: «mo»."},
    {"kana": "や", "romaji": "ya", "sonido": "ya", "confusiones": ["か", "せ"], "trazos": [], "audio": "ya.mp3", "mnemotecnia": "La cabeza de un yak con su cuerno: «ya»."},
    {"kana": "ゆ", "romaji": "yu", "sonido": "yu", "confusiones": ["よ", "る", "ぬ"], "trazos": [], "audio": "yu.mp3", "mnemotecnia": "Un pez de frente, con la aleta en el medio: «yu»."},
    {"kana": "よ", "romaji": "yo", "sonido": "yo", "confusiones": ["ま", "み", "ゆ"], "trazos": [], "audio": "yo.mp3", "mnemotecnia": "Un yoyó colgando de un dedo: «yo»."},
    {"kana": "ら", "romaji": "ra", "sonido": "ra", "confusiones": ["う", "ち", "ろ"], "trazos": [], "audio": "ra.mp3", "mnemotecnia": "Un conejo agachado con la oreja arriba: «ra», de «rápido»."},
    {"kana": "り", "romaji": "ri", "sonido": "ri", "confusiones": ["い", "け"], "trazos": [], "audio": "ri.mp3", "mnemotecnia": "Dos juncos a la orilla de un «rí»o: «ri»."},
    {"kana": "る", "romaji": "ru", "sonido": "ru", "confusiones": ["ろ", "ら", "ゆ"], "trazos": [], "audio": "ru.mp3", "mnemotecnia": "Un 3 con un rizo abajo, como una «ru»leta: «ru»."},
    {"kana": "れ", "romaji": "re", "sonido": "re", "confusiones": ["ね", "わ"], "trazos": [], "audio": "re.mp3", "mnemotecnia": "Como ね pero sin el rizo: alguien que «re»ma: «re»."},
    {"kana": "ろ", "romaji": "ro", "sonido": "ro", "confusiones": ["る", "ら", "そ"], "trazos": [], "audio": "ro.mp3", "mnemotecnia": "る sin el rizo: un 3 «ro»to: «ro»."},
    {"kana": "わ", "romaji": "wa", "sonido": "wa", "confusiones": ["れ", "ね"], "trazos": [], "audio": "wa.mp3", "mnemotecnia": "Como れ pero con la espalda redonda, como un «wa»fle: «wa»."},
    {"kana": "を", "romaji": "wo", "sonido": "o", "confusiones": ["お"], "trazos": [], "audio": "wo.mp3", "mnemotecnia": "Se escribe «wo» pero suena «o»: solo va detrás de una palabra, como partícula."},
    {"kana": "ん", "romaji": "n", "sonido": "n", "confusiones": ["え", "そ"], "trazos": [], "audio": "n.mp3", "mnemotecnia": "Una «n» escrita a mano, de una sola raya: «n»."}
  ]
}
```

- [ ] **Step 4: Escribir `mapa.json` y la atribución**

`backend/src/klara/mapas/ja/mapa.json`:

```json
{
  "idioma": "ja",
  "escala": ["かな", "N5", "N4", "N3"],
  "unidades": [
    {
      "id": "hiragana",
      "titulo": "Hiragana",
      "nivel": "かな",
      "puedo": ["Puedo leer, oír y escribir los 46 hiragana sin pensarlo."],
      "sabes": {
        "vista": "tabla",
        "filas": [
          ["ja:kana:あ", "ja:kana:い", "ja:kana:う", "ja:kana:え", "ja:kana:お"],
          ["ja:kana:か", "ja:kana:き", "ja:kana:く", "ja:kana:け", "ja:kana:こ"],
          ["ja:kana:さ", "ja:kana:し", "ja:kana:す", "ja:kana:せ", "ja:kana:そ"],
          ["ja:kana:た", "ja:kana:ち", "ja:kana:つ", "ja:kana:て", "ja:kana:と"],
          ["ja:kana:な", "ja:kana:に", "ja:kana:ぬ", "ja:kana:ね", "ja:kana:の"],
          ["ja:kana:は", "ja:kana:ひ", "ja:kana:ふ", "ja:kana:へ", "ja:kana:ほ"],
          ["ja:kana:ま", "ja:kana:み", "ja:kana:む", "ja:kana:め", "ja:kana:も"],
          ["ja:kana:や", null, "ja:kana:ゆ", null, "ja:kana:よ"],
          ["ja:kana:ら", "ja:kana:り", "ja:kana:る", "ja:kana:れ", "ja:kana:ろ"],
          ["ja:kana:わ", null, null, null, "ja:kana:を"],
          ["ja:kana:ん", null, null, null, null]
        ]
      },
      "lecciones": [
        {"id": "a", "titulo": "あ い う え お", "bajada": "la fila de あ: leerla, oírla y escribirla", "plantilla": "kana", "items": ["ja:kana:あ", "ja:kana:い", "ja:kana:う", "ja:kana:え", "ja:kana:お"]},
        {"id": "ka", "titulo": "か き く け こ", "bajada": "la fila de か: leerla, oírla y escribirla", "plantilla": "kana", "items": ["ja:kana:か", "ja:kana:き", "ja:kana:く", "ja:kana:け", "ja:kana:こ"]},
        {"id": "sa", "titulo": "さ し す せ そ", "bajada": "la fila de さ: leerla, oírla y escribirla", "plantilla": "kana", "items": ["ja:kana:さ", "ja:kana:し", "ja:kana:す", "ja:kana:せ", "ja:kana:そ"]},
        {"id": "ta", "titulo": "た ち つ て と", "bajada": "la fila de た: leerla, oírla y escribirla", "plantilla": "kana", "items": ["ja:kana:た", "ja:kana:ち", "ja:kana:つ", "ja:kana:て", "ja:kana:と"]},
        {"id": "na", "titulo": "な に ぬ ね の", "bajada": "la fila de な: leerla, oírla y escribirla", "plantilla": "kana", "items": ["ja:kana:な", "ja:kana:に", "ja:kana:ぬ", "ja:kana:ね", "ja:kana:の"]},
        {"id": "ha", "titulo": "は ひ ふ へ ほ", "bajada": "la fila de は: leerla, oírla y escribirla", "plantilla": "kana", "items": ["ja:kana:は", "ja:kana:ひ", "ja:kana:ふ", "ja:kana:へ", "ja:kana:ほ"]},
        {"id": "ma", "titulo": "ま み む め も", "bajada": "la fila de ま: leerla, oírla y escribirla", "plantilla": "kana", "items": ["ja:kana:ま", "ja:kana:み", "ja:kana:む", "ja:kana:め", "ja:kana:も"]},
        {"id": "ya", "titulo": "や ゆ よ", "bajada": "や, ゆ y よ: leerlas, oírlas y escribirlas", "plantilla": "kana", "items": ["ja:kana:や", "ja:kana:ゆ", "ja:kana:よ"]},
        {"id": "ra", "titulo": "ら り る れ ろ", "bajada": "la fila de ら: leerla, oírla y escribirla", "plantilla": "kana", "items": ["ja:kana:ら", "ja:kana:り", "ja:kana:る", "ja:kana:れ", "ja:kana:ろ"]},
        {"id": "wa", "titulo": "わ を ん", "bajada": "わ, を y ん: leerlas, oírlas y escribirlas", "plantilla": "kana", "items": ["ja:kana:わ", "ja:kana:を", "ja:kana:ん"]}
      ]
    }
  ]
}
```

`backend/src/klara/mapas/ja/KANJIVG.txt`:

```
Los trazos del campo "trazos" de kana.json salen de KanjiVG
(https://kanjivg.tagaini.net), de Ulrich Apel y colaboradores, con licencia
Creative Commons Attribution-Share Alike 3.0
(https://creativecommons.org/licenses/by-sa/3.0/).

Los paths se copian sin cambios: scripts/importar_kanjivg.py solo los extrae
del SVG de cada carácter. Ese campo se comparte bajo la misma licencia.
```

- [ ] **Step 5: Importar los trazos**

Run: `cd backend && uv run python -m klara.scripts.importar_kanjivg`
Expected: `46 kana con trazos en …/mapas/ja/kana.json`, y `fuente` pasa a decir `KanjiVG master (CC BY-SA 3.0, Ulrich Apel y colaboradores)`.

Si sale «KanjiVG trae X trazos y la tabla dice Y», no se escribió nada. En ese caso:
1. Abre `https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/<código>.svg` y cuenta los `<path id="kvg:…-sN">`.
2. Si el SVG sigue el orden estándar de escritura, corrige ese número en `TRAZOS_ESPERADOS` (tarea 5) y vuelve a correr el importador.
3. Si el SVG no lo sigue, para y pregúntale a Samuel.

- [ ] **Step 6: Comprobar que están las claves de Azure (sin imprimirlas)**

Run: `cd backend && grep -c "^AZURE_SPEECH_KEY=." .env && grep -c "^AZURE_SPEECH_REGION=." .env`
Expected: `1` y `1`. Si sale `0` o «No such file», para y pídele a Samuel que ponga las dos líneas en `backend/.env`. No sigas sin ellas.

- [ ] **Step 7: Generar y validar el audio**

Run: `cd backend && uv run python -m klara.scripts.generar_audio_catalogo`
Expected:
- 46 líneas del tipo `か (ka): 95`;
- 46 archivos en `backend/src/klara/mapas/ja/audio/`;
- y, si hubo alguno, la lista «escúchalos».

Si hay lista, pásasela a Samuel con la ruta de cada archivo para que los escuche. Para regenerar uno que no le guste: `uv run python -m klara.scripts.generar_audio_catalogo --solo ふ --forzar`.

- [ ] **Step 8: Correr los tests del catálogo**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_real.py tests/test_catalogo_cargar.py -v`
Expected: PASS. Revisa además el tamaño: `du -sh backend/src/klara/mapas/ja/audio` debería salir por debajo de 1,5 MB.

- [ ] **Step 9: Revisión de Samuel**

Pídele a Samuel que revise:
- las 46 mnemotecnias de `kana.json`;
- el audio que haya quedado en la lista.

Lo que corrija se cambia en `kana.json` antes del commit. El test real tiene que seguir en verde.

- [ ] **Step 10: Commit**

```bash
git add backend/src/klara/mapas backend/tests/test_catalogo_real.py
git commit -m "feat(tres-idiomas): el mapa de japonés: hiragana con trazos y audio

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Componer la sesión

**Files:**
- Create: `backend/src/klara/services/sesion.py`
- Test: `backend/tests/test_sesion.py`

**Interfaces:**
- Consumes:
  - `Catalogo`, `Actividad`, `LeccionCompleta` (tarea 3);
  - `CAP_REPASOS`, `DINAMICA_DE_REPASO`, `DINAMICAS` (tarea 2);
  - `Contexto`, `generar` (tarea 4);
  - `UserFacet`, `LessonRun` (tarea 1).
- Produces:
  - `Plan(idioma, repasos: tuple[Actividad, ...], leccion: LeccionCompleta | None, vistos: frozenset[str])`, con la propiedad `.actividades`
  - `idiomas_de_estudio(user, cat) -> list[str]`
  - `orden_de_mapas(cat) -> list[str]`
  - `huerfanas(claves, cat) -> list[str]`
  - `separar_mismo_item(pares) -> list[tuple[str, str]]`
  - `async lecciones_hechas(db, user_id, idioma) -> frozenset[str]`
  - `siguiente_leccion(cat, idioma, hechas) -> LeccionCompleta | None`
  - `async contar_vencidas(db, user_id, idioma, hasta) -> int`
  - `async componer(db, cat, user_id, idioma, ahora, *, con_repasos=True) -> Plan`
  - `plan_para_repetir(leccion, vistos) -> Plan`
  - `async items_vistos(db, cat, user_id, idioma, hechas) -> frozenset[str]`
  - `minutos(plan) -> int`
  - `contenido(cat, plan, semilla) -> list[dict]`. Cada actividad sale como `{id: "a0", dinamica, modo, items, faceta, repaso: bool, contenido}`.

- [ ] **Step 1: Escribir los tests**

`backend/tests/test_sesion.py`:

```python
"""Componer la sesión de una línea (spec §4): repasos vencidos con tope, sin dos
facetas del mismo ítem seguidas, y la siguiente lección del mapa."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from klara.models import LessonRun, UserFacet
from klara.models.enums import CardState
from klara.services import sesion
from klara.services.sesion import (
    Plan,
    componer,
    contenido,
    huerfanas,
    idiomas_de_estudio,
    minutos,
    orden_de_mapas,
    plan_para_repetir,
    separar_mismo_item,
)
from tests.ayudas import crear_usuario

AHORA = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _faceta(user_id, item: str, faceta: str, vence: datetime) -> UserFacet:
    return UserFacet(
        user_id=user_id,
        idioma=item.split(":")[0],
        item_key=item,
        faceta=faceta,
        state=CardState.REVIEWING,
        stability=3.0,
        difficulty=5.0,
        interval_days=3.0,
        repetitions=1,
        next_review_at=vence,
    )


def _corrida(user_id, leccion_id: str, *, origen: str = "hoy", terminada: bool = True) -> LessonRun:
    return LessonRun(
        user_id=user_id,
        idioma="ja",
        leccion_id=leccion_id,
        origen=origen,
        finished_at=AHORA - timedelta(hours=1) if terminada else None,
    )


def test_separar_mismo_item():
    pares = [("a", "x"), ("a", "y"), ("b", "x"), ("c", "x")]
    out = separar_mismo_item(pares)
    assert sorted(out) == sorted(pares)
    assert all(out[i][0] != out[i + 1][0] for i in range(len(out) - 1))
    assert out[0] == ("a", "x")


def test_separar_cuando_no_se_puede():
    assert separar_mismo_item([("a", "x"), ("a", "y")]) == [("a", "x"), ("a", "y")]


async def test_cuenta_nueva_empieza_por_la_primera_leccion(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.repasos == ()
    assert plan.leccion.id == "ja/hiragana/a"


async def test_leccion_hecha_pasa_a_la_siguiente(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add(_corrida(u.id, "ja/hiragana/a"))
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.leccion.id == "ja/hiragana/e"


async def test_ni_el_mapa_ni_una_corrida_abierta_cuentan(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add_all(
        [
            _corrida(u.id, "ja/hiragana/a", origen="mapa"),
            _corrida(u.id, "ja/hiragana/a", terminada=False),
        ]
    )
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.leccion.id == "ja/hiragana/a"


async def test_mapa_terminado(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add_all([_corrida(u.id, "ja/hiragana/a"), _corrida(u.id, "ja/hiragana/e")])
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.leccion is None


async def test_repasos_vencidos_en_orden_y_con_tope(db_session, catalogo_mini, monkeypatch):
    monkeypatch.setattr(sesion, "CAP_REPASOS", 4)
    u = await crear_usuario(db_session)
    items = ["ja:kana:あ", "ja:kana:い", "ja:kana:う", "ja:kana:え", "ja:kana:お"]
    db_session.add_all(
        [_faceta(u.id, it, "reconocer", AHORA - timedelta(hours=10 - n)) for n, it in enumerate(items)]
    )
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert [a.items[0] for a in plan.repasos] == items[:4]
    assert {(a.dinamica, a.modo) for a in plan.repasos} == {("eleccion", "comprobar")}


async def test_fuera_lo_que_no_vence_lo_ajeno_y_lo_huerfano(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    otro = await crear_usuario(db_session)
    db_session.add_all(
        [
            _faceta(u.id, "ja:kana:あ", "escribir", AHORA - timedelta(minutes=5)),
            _faceta(u.id, "ja:kana:い", "escribir", AHORA + timedelta(hours=1)),
            _faceta(otro.id, "ja:kana:う", "escribir", AHORA - timedelta(hours=1)),
            _faceta(u.id, "ja:kana:か", "escribir", AHORA - timedelta(hours=1)),
        ]
    )
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert [(a.dinamica, a.items) for a in plan.repasos] == [("trazo", ("ja:kana:あ",))]


async def test_sin_repasos_cuando_se_pide(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add(_faceta(u.id, "ja:kana:あ", "escribir", AHORA - timedelta(minutes=5)))
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA, con_repasos=False)
    assert plan.repasos == ()
    assert plan.leccion.id == "ja/hiragana/a"


def test_minutos(catalogo_mini):
    plan = Plan(idioma="ja", repasos=(), leccion=catalogo_mini.lecciones["ja/hiragana/a"])
    # trazo 3 x 20 + 3 x 25, elección 6 x 6, tablero 45, prueba: trazo 3 x 20 + elección 6 x 6 = 312 s
    assert minutos(plan) == 6


async def test_contenido_numera_y_marca_los_repasos(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add(_faceta(u.id, "ja:kana:あ", "escribir", AHORA - timedelta(minutes=1)))
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    acts = contenido(catalogo_mini, plan, semilla=1)
    assert (acts[0]["id"], acts[0]["repaso"], acts[0]["dinamica"]) == ("a0", True, "trazo")
    assert all(a["repaso"] is False for a in acts[1:])
    assert len({a["id"] for a in acts}) == len(acts)
    assert acts[0]["contenido"]["kana"] == "あ"


async def test_los_repasos_no_usan_distractores_de_la_leccion_nueva(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    db_session.add_all(
        [
            _corrida(u.id, "ja/hiragana/a"),
            _faceta(u.id, "ja:kana:あ", "reconocer", AHORA - timedelta(minutes=1)),
        ]
    )
    await db_session.commit()
    plan = await componer(db_session, catalogo_mini, u.id, "ja", AHORA)
    assert plan.leccion.id == "ja/hiragana/e"
    repaso = contenido(catalogo_mini, plan, semilla=3)[0]
    assert repaso["repaso"] is True
    vistos = {"ja:kana:あ", "ja:kana:い", "ja:kana:う"}
    assert {o["item"] for o in repaso["contenido"]["opciones"]} <= vistos


def test_plan_para_repetir_no_mueve_fsrs(catalogo_mini):
    plan = plan_para_repetir(catalogo_mini.lecciones["ja/hiragana/a"], frozenset())
    assert plan.repasos == ()
    assert {a.modo for a in plan.actividades} <= {"presentar", "practicar"}
    assert len(plan.actividades) == 22


async def test_idiomas_de_estudio(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    assert idiomas_de_estudio(u, catalogo_mini) == []  # «de» todavía no tiene mapa
    u.study_languages = ["ja", "de"]
    assert idiomas_de_estudio(u, catalogo_mini) == ["ja"]


def test_orden_de_mapas_y_huerfanas(catalogo_mini):
    assert orden_de_mapas(catalogo_mini) == ["ja"]
    assert huerfanas({"ja:kana:あ", "ja:kana:か"}, catalogo_mini) == ["ja:kana:か"]
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_sesion.py -v`
Expected: falla con `ModuleNotFoundError: No module named 'klara.services.sesion'`.

- [ ] **Step 3: Implementar**

`backend/src/klara/services/sesion.py`:

```python
"""Componer la sesión de una línea (spec 2026-10-09 §4): hasta CAP_REPASOS
facetas vencidas y la siguiente lección del mapa. Hoy usa la misma composición
para estimar los minutos, así los que promete son los de la sesión."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.catalogo.dinamicas import CAP_REPASOS, DINAMICA_DE_REPASO, DINAMICAS
from klara.catalogo.facetas import tipo_de
from klara.catalogo.generar import Contexto, generar
from klara.catalogo.modelo import Actividad, Catalogo, LeccionCompleta
from klara.models import LessonRun, User, UserFacet

# El orden en que se listan los mapas (Ajustes y, en el plan 4, Biblioteca).
IDIOMAS_ORDEN = ("de", "ja", "en")


@dataclass(frozen=True)
class Plan:
    idioma: str
    repasos: tuple[Actividad, ...]
    leccion: LeccionCompleta | None
    # Ítems ya presentados: los de las lecciones hechas y los que tienen fila.
    # Los distractores de los repasos salen solo de aquí.
    vistos: frozenset[str] = frozenset()

    @property
    def actividades(self) -> tuple[Actividad, ...]:
        return self.repasos + (self.leccion.leccion.actividades if self.leccion else ())


def idiomas_de_estudio(user: User, cat: Catalogo) -> list[str]:
    """Los idiomas de las líneas de Hoy: `study_languages`, o el idioma de estudio
    si no se eligió nada. Solo los que tienen mapa (spec §2.2)."""
    base = user.study_languages or [user.target_language]
    return [i for i in base if i in cat.mapas]


def orden_de_mapas(cat: Catalogo) -> list[str]:
    def clave(i: str) -> tuple[int, str]:
        return (IDIOMAS_ORDEN.index(i) if i in IDIOMAS_ORDEN else len(IDIOMAS_ORDEN), i)

    return sorted(cat.mapas, key=clave)


def huerfanas(claves: set[str], cat: Catalogo) -> list[str]:
    """Las claves de `user_facets` que ya no están en el catálogo (spec §2.1)."""
    return sorted(claves - set(cat.items))


def separar_mismo_item(pares: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Reordena lo mínimo para que no vayan dos facetas del mismo ítem seguidas,
    respetando el orden de vencimiento todo lo posible."""
    pendientes = list(pares)
    out: list[tuple[str, str]] = []
    while pendientes:
        for i, par in enumerate(pendientes):
            if not out or par[0] != out[-1][0]:
                out.append(pendientes.pop(i))
                break
        else:
            out.append(pendientes.pop(0))  # solo quedan del mismo ítem
    return out


async def lecciones_hechas(db: AsyncSession, user_id: UUID, idioma: str) -> frozenset[str]:
    """Una lección está hecha si tiene una corrida de Hoy terminada (spec §2.2)."""
    filas = await db.execute(
        select(LessonRun.leccion_id).where(
            LessonRun.user_id == user_id,
            LessonRun.idioma == idioma,
            LessonRun.origen == "hoy",
            LessonRun.finished_at.is_not(None),
            LessonRun.leccion_id.is_not(None),
        )
    )
    return frozenset(filas.scalars())


def siguiente_leccion(cat: Catalogo, idioma: str, hechas: frozenset[str]) -> LeccionCompleta | None:
    return next((lec for lec in cat.lecciones_de(idioma) if lec.id not in hechas), None)


async def items_vistos(
    db: AsyncSession, cat: Catalogo, user_id: UUID, idioma: str, hechas: frozenset[str]
) -> frozenset[str]:
    con_fila = await db.execute(
        select(UserFacet.item_key)
        .where(UserFacet.user_id == user_id, UserFacet.idioma == idioma)
        .distinct()
    )
    de_lecciones = {
        i
        for lec in cat.lecciones_de(idioma)
        if lec.id in hechas
        for a in lec.leccion.actividades
        for i in a.items
    }
    return frozenset(de_lecciones | {i for i in con_fila.scalars() if i in cat.items})


async def contar_vencidas(db: AsyncSession, user_id: UUID, idioma: str, hasta: datetime) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(UserFacet)
            .where(
                UserFacet.user_id == user_id,
                UserFacet.idioma == idioma,
                UserFacet.next_review_at <= hasta,
            )
        )
    ).scalar_one()


async def _vencidas(
    db: AsyncSession, cat: Catalogo, user_id: UUID, idioma: str, ahora: datetime
) -> list[tuple[str, str]]:
    filas = await db.execute(
        select(UserFacet.item_key, UserFacet.faceta)
        .where(
            UserFacet.user_id == user_id,
            UserFacet.idioma == idioma,
            UserFacet.next_review_at <= ahora,
        )
        .order_by(UserFacet.next_review_at, UserFacet.item_key, UserFacet.faceta)
    )
    # Las huérfanas (ítem fuera del catálogo) se ignoran (spec §2.1).
    vencidas = [
        (i, f) for i, f in filas.all() if i in cat.items and (tipo_de(i), f) in DINAMICA_DE_REPASO
    ]
    return vencidas[:CAP_REPASOS]


async def componer(
    db: AsyncSession,
    cat: Catalogo,
    user_id: UUID,
    idioma: str,
    ahora: datetime,
    *,
    con_repasos: bool = True,
) -> Plan:
    pares = await _vencidas(db, cat, user_id, idioma, ahora) if con_repasos else []
    repasos = tuple(
        Actividad(
            dinamica=DINAMICA_DE_REPASO[(tipo_de(i), f)], modo="comprobar", items=(i,), faceta=f
        )
        for i, f in separar_mismo_item(pares)
    )
    hechas = await lecciones_hechas(db, user_id, idioma)
    return Plan(
        idioma=idioma,
        repasos=repasos,
        leccion=siguiente_leccion(cat, idioma, hechas),
        vistos=await items_vistos(db, cat, user_id, idioma, hechas),
    )


def plan_para_repetir(leccion: LeccionCompleta, vistos: frozenset[str]) -> Plan:
    """Una lección hecha, repetida desde el mapa: todo en práctica, nada mueve FSRS."""
    practicas = tuple(
        a.model_copy(update={"modo": "practicar"}) if a.modo == "comprobar" else a
        for a in leccion.leccion.actividades
    )
    copia = LeccionCompleta(
        id=leccion.id,
        idioma=leccion.idioma,
        unidad=leccion.unidad,
        leccion=leccion.leccion.model_copy(update={"actividades": practicas}),
    )
    return Plan(idioma=leccion.idioma, repasos=(), leccion=copia, vistos=vistos)


def minutos(plan: Plan) -> int:
    segundos = sum(DINAMICAS[a.dinamica].segundos[a.modo] for a in plan.actividades)
    return math.ceil(segundos / 60)


def contenido(cat: Catalogo, plan: Plan, semilla: int) -> list[dict]:
    rng = random.Random(semilla)
    de_la_leccion = frozenset(
        i for a in (plan.leccion.leccion.actividades if plan.leccion else ()) for i in a.items
    )
    ctx_repaso = Contexto(rng=rng, conocidos=plan.vistos)
    ctx_leccion = Contexto(rng=rng, conocidos=plan.vistos | de_la_leccion)
    n_repasos = len(plan.repasos)
    return [
        {
            "id": f"a{n}",
            "dinamica": a.dinamica,
            "modo": a.modo,
            "items": list(a.items),
            "faceta": a.faceta,
            "repaso": n < n_repasos,
            "contenido": generar(cat, a, ctx_repaso if n < n_repasos else ctx_leccion),
        }
        for n, a in enumerate(plan.actividades)
    ]
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_sesion.py -v`
Expected: PASS, 15 tests.

- [ ] **Step 5: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/services/sesion.py backend/tests/test_sesion.py
git commit -m "feat(tres-idiomas): componer la sesión de una línea

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Registrar evidencias

**Files:**
- Create: `backend/src/klara/schemas/catalogo.py` (por ahora solo `EvidenciaIn`)
- Create: `backend/src/klara/services/evidencias.py`
- Test: `backend/tests/test_evidencias.py`

**Interfaces:**
- Consumes:
  - `DINAMICAS`, `ejercita` (tarea 2);
  - `faceta_valida`, `idioma_de`, `tipo_de` (tarea 2);
  - `nota` (tarea 2);
  - `UserFacet`, `FacetReview`, `LessonRun` (tarea 1);
  - `apply_review(card, rating)` (`klara.services.srs_engine`).
- Produces:
  - `EvidenciaIn(id: UUID, run_id: UUID, dinamica, modo, item, faceta, acierto, pistas, ms, detalle)`, en `klara.schemas.catalogo`
  - `EvidenciaInvalida(ValueError)`
  - `validar(cat, ev) -> None`
  - `async registrar(db, cat, user_id, evidencias, ahora) -> int`: cuántas eran nuevas. Hace el commit.

- [ ] **Step 1: Escribir los tests**

`backend/tests/test_evidencias.py`:

```python
"""Registrar evidencias (spec §4): validación contra el catálogo, idempotencia por
id y FSRS solo en `comprobar`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from klara.models import FacetReview, LessonRun, UserFacet
from klara.models.enums import CardState, ReviewRating
from klara.schemas.catalogo import EvidenciaIn
from klara.services.evidencias import EvidenciaInvalida, registrar
from tests.ayudas import crear_usuario

AHORA = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


async def _corrida(db, user) -> LessonRun:
    run = LessonRun(user_id=user.id, idioma="ja", leccion_id="ja/hiragana/a", origen="hoy")
    db.add(run)
    await db.commit()
    return run


def _ev(run: LessonRun, **kw) -> EvidenciaIn:
    base = dict(
        id=uuid.uuid4(),
        run_id=run.id,
        dinamica="eleccion",
        modo="comprobar",
        item="ja:kana:あ",
        faceta="reconocer",
        acierto=True,
        pistas=0,
        ms=1500,
        detalle={"elegida": "ja:kana:あ"},
    )
    return EvidenciaIn(**{**base, **kw})


async def _facetas(db) -> list[UserFacet]:
    return list((await db.execute(select(UserFacet))).scalars())


async def _registro(db) -> list[FacetReview]:
    return list((await db.execute(select(FacetReview))).scalars())


async def test_la_practica_se_registra_y_no_mueve_fsrs(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    assert await registrar(db_session, catalogo_mini, u.id, [_ev(run, modo="practicar")], AHORA) == 1
    [fila] = await _registro(db_session)
    assert (fila.modo, fila.nota, fila.idioma) == ("practicar", None, "ja")
    assert await _facetas(db_session) == []


async def test_la_primera_prueba_crea_la_faceta(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    await registrar(db_session, catalogo_mini, u.id, [_ev(run)], AHORA)
    [f] = await _facetas(db_session)
    assert (f.item_key, f.faceta, f.idioma) == ("ja:kana:あ", "reconocer", "ja")
    assert f.state != CardState.NEW
    assert f.repetitions == 1
    assert f.next_review_at > AHORA
    [fila] = await _registro(db_session)
    assert fila.nota == ReviewRating.GOOD


@pytest.mark.parametrize(
    ("cambio", "esperada"),
    [
        ({"pistas": 1}, ReviewRating.HARD),
        ({"ms": 60_000}, ReviewRating.HARD),
        ({"acierto": False}, ReviewRating.AGAIN),
    ],
)
async def test_la_nota_sale_de_la_evidencia(db_session, catalogo_mini, cambio, esperada):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    await registrar(db_session, catalogo_mini, u.id, [_ev(run, **cambio)], AHORA)
    [fila] = await _registro(db_session)
    assert fila.nota == esperada


async def test_la_misma_evidencia_dos_veces_cuenta_una(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    ev = _ev(run)
    assert await registrar(db_session, catalogo_mini, u.id, [ev], AHORA) == 1
    assert await registrar(db_session, catalogo_mini, u.id, [ev], AHORA) == 0
    [f] = await _facetas(db_session)
    assert f.repetitions == 1
    assert len(await _registro(db_session)) == 1


async def test_una_respuesta_puede_dar_varias_evidencias(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    evs = [
        _ev(run, dinamica="emparejar", modo="practicar", item=i)
        for i in ("ja:kana:あ", "ja:kana:い", "ja:kana:う")
    ]
    assert await registrar(db_session, catalogo_mini, u.id, evs, AHORA) == 3


@pytest.mark.parametrize(
    "cambio",
    [
        {"dinamica": "dictado"},
        {"dinamica": "emparejar"},  # emparejar no soporta comprobar
        {"item": "ja:kana:か"},
        {"faceta": "genero"},
        {"faceta": "escribir"},  # eleccion no ejercita escribir
    ],
)
async def test_lo_que_no_cuadra_es_invalido_y_no_guarda_nada(db_session, catalogo_mini, cambio):
    u = await crear_usuario(db_session)
    run = await _corrida(db_session, u)
    with pytest.raises(EvidenciaInvalida):
        await registrar(db_session, catalogo_mini, u.id, [_ev(run), _ev(run, **cambio)], AHORA)
    await db_session.rollback()
    assert await _registro(db_session) == []
    assert await _facetas(db_session) == []


async def test_la_corrida_de_otro_es_invalida(db_session, catalogo_mini):
    u = await crear_usuario(db_session)
    otro = await crear_usuario(db_session)
    run_ajena = await _corrida(db_session, otro)
    with pytest.raises(EvidenciaInvalida):
        await registrar(db_session, catalogo_mini, u.id, [_ev(run_ajena)], AHORA)
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_evidencias.py -v`
Expected: falla con `ModuleNotFoundError: No module named 'klara.schemas.catalogo'`.

- [ ] **Step 3: Implementar**

`backend/src/klara/schemas/catalogo.py`:

```python
"""Lo que entra y sale de las rutas del catálogo (spec 2026-10-09 §4)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Modo = Literal["presentar", "practicar", "comprobar"]


class EvidenciaIn(BaseModel):
    # Lo genera el teléfono: reenviar la misma evidencia no la cuenta dos veces.
    id: UUID
    run_id: UUID
    dinamica: str
    modo: Modo
    item: str
    faceta: str
    acierto: bool
    pistas: int = Field(ge=0, le=50)
    ms: int = Field(ge=0, le=3_600_000)
    detalle: dict | None = None
```

`backend/src/klara/services/evidencias.py`:

```python
"""Registrar evidencias (spec 2026-10-09 §4): validar contra el catálogo, guardar
en el registro sin duplicar, y mover FSRS solo en `comprobar`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from klara.catalogo.dinamicas import DINAMICAS, ejercita
from klara.catalogo.facetas import faceta_valida, idioma_de, tipo_de
from klara.catalogo.modelo import Catalogo
from klara.catalogo.nota import nota as calcular_nota
from klara.models import FacetReview, LessonRun, UserFacet
from klara.models.enums import CardState, ReviewRating
from klara.schemas.catalogo import EvidenciaIn
from klara.services.srs_engine import apply_review


class EvidenciaInvalida(ValueError):
    """Una evidencia que no cuadra con el catálogo o con la cuenta: 422."""


def validar(cat: Catalogo, ev: EvidenciaIn) -> None:
    d = DINAMICAS.get(ev.dinamica)
    if d is None:
        raise EvidenciaInvalida(f"dinámica desconocida: {ev.dinamica}")
    if ev.modo not in d.modos:
        raise EvidenciaInvalida(f"{ev.dinamica} no soporta el modo {ev.modo}")
    if ev.item not in cat.items:
        raise EvidenciaInvalida(f"ítem desconocido: {ev.item}")
    if not faceta_valida(ev.item, ev.faceta) or not ejercita(d, tipo_de(ev.item), ev.faceta):
        raise EvidenciaInvalida(f"{ev.dinamica} no ejercita {ev.item} con {ev.faceta}")


async def _aplicar(
    db: AsyncSession, user_id: UUID, ev: EvidenciaIn, n: ReviewRating, ahora: datetime
) -> None:
    # La fila nace con la primera prueba de esa faceta (spec §2.2). Los campos van
    # explícitos: el motor lee `state` y `repetitions` antes de cualquier flush.
    await db.execute(
        pg_insert(UserFacet)
        .values(
            user_id=user_id,
            idioma=idioma_de(ev.item),
            item_key=ev.item,
            faceta=ev.faceta,
            state=CardState.NEW,
            interval_days=0.0,
            repetitions=0,
            next_review_at=ahora,
        )
        .on_conflict_do_nothing(constraint="uq_user_facet")
    )
    faceta = (
        await db.execute(
            select(UserFacet)
            .where(
                UserFacet.user_id == user_id,
                UserFacet.item_key == ev.item,
                UserFacet.faceta == ev.faceta,
            )
            .with_for_update()
        )
    ).scalar_one()
    apply_review(faceta, n)


async def registrar(
    db: AsyncSession,
    cat: Catalogo,
    user_id: UUID,
    evidencias: list[EvidenciaIn],
    ahora: datetime,
) -> int:
    """Devuelve cuántas evidencias nuevas se guardaron; las repetidas no cuentan.
    Si una sola no cuadra, no se guarda ninguna."""
    for ev in evidencias:
        validar(cat, ev)
    corridas = {ev.run_id for ev in evidencias}
    propias = set(
        (
            await db.execute(
                select(LessonRun.id).where(
                    LessonRun.id.in_(list(corridas)), LessonRun.user_id == user_id
                )
            )
        ).scalars()
    )
    if propias != corridas:
        raise EvidenciaInvalida("corrida desconocida")

    guardadas = 0
    for ev in evidencias:
        n = (
            calcular_nota(
                acierto=ev.acierto,
                pistas=ev.pistas,
                ms=ev.ms,
                ms_lento=DINAMICAS[ev.dinamica].ms_lento,
            )
            if ev.modo == "comprobar"
            else None
        )
        nueva = (
            await db.execute(
                pg_insert(FacetReview)
                .values(
                    id=ev.id,
                    user_id=user_id,
                    run_id=ev.run_id,
                    idioma=idioma_de(ev.item),
                    item_key=ev.item,
                    faceta=ev.faceta,
                    dinamica=ev.dinamica,
                    modo=ev.modo,
                    acierto=ev.acierto,
                    pistas=ev.pistas,
                    ms=ev.ms,
                    nota=n,
                    detalle=ev.detalle,
                )
                .on_conflict_do_nothing(index_elements=["id"])
                .returning(FacetReview.id)
            )
        ).scalar_one_or_none()
        if nueva is None:
            continue  # ya estaba: reenviarla no la cuenta dos veces
        guardadas += 1
        if n is not None:
            await _aplicar(db, user_id, ev, n, ahora)
    await db.commit()
    return guardadas
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_evidencias.py -v`
Expected: PASS, 13 tests.

- [ ] **Step 5: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/schemas/catalogo.py backend/src/klara/services/evidencias.py backend/tests/test_evidencias.py
git commit -m "feat(tres-idiomas): registrar evidencias y mover FSRS solo en la prueba

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Rutas del catálogo y arranque

**Files:**
- Modify: `backend/src/klara/schemas/catalogo.py` (agregar las salidas)
- Create: `backend/src/klara/routers/catalogo.py`
- Modify: `backend/src/klara/main.py` (registrar el router; cargar el catálogo y avisar de huérfanas al arrancar)
- Test: `backend/tests/test_catalogo_router.py`

**Interfaces:**
- Consumes:
  - de la tarea 8: `componer`, `contenido`, `plan_para_repetir`, `items_vistos`, `lecciones_hechas`, `siguiente_leccion`, `contar_vencidas`, `idiomas_de_estudio`, `orden_de_mapas`, `huerfanas`;
  - de la tarea 9: `registrar`, `EvidenciaInvalida`;
  - `get_catalogo` (tarea 3);
  - `CurrentUser` y `DBSession` (`klara.dependencies`).
- Produces (todas bajo `/api/v1`):
  - `GET /sesiones/{idioma}?repasos=true|false` → `SesionOut{idioma, leccion: LeccionRef|null, actividades: ActividadOut[]}`
  - `GET /lecciones/{idioma}/{unidad}/{leccion}` → `SesionOut` (todo en práctica)
  - `POST /lesson-runs {idioma, leccion_id?, origen, repasos}` → 201 `{id}`
  - `POST /lesson-runs/{id}/fin` → `{manana}`
  - `POST /evidencias {evidencias: [...]}` → `{guardadas}` (422 si no cuadra)
  - `GET /audio/{idioma}/{archivo}` → `audio/mpeg`, sin sesión
  - `GET /mapas` → `[{idioma, estudias, nivel, progreso, vencen}]`
  - Además, `LeccionRef` queda en `klara.schemas.catalogo` (la tarea 11 la reusa).

- [ ] **Step 1: Escribir los tests**

`backend/tests/test_catalogo_router.py`:

```python
"""Las rutas del catálogo (spec §4), contra el catálogo de juguete."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from klara.models import LessonRun, UserFacet
from klara.models.enums import CardState
from tests.ayudas import crear_usuario, entrar, usuario_por_email

EMAIL = "catalogo@example.com"


async def _cabeceras(client, seed_invite) -> dict:
    return {"Cookie": await entrar(client, seed_invite, EMAIL)}


async def test_la_sesion_pide_cuenta(client, catalogo_mini):
    assert (await client.get("/api/v1/sesiones/ja")).status_code == 401


async def test_sesion_de_una_cuenta_nueva(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    r = await client.get("/api/v1/sesiones/ja", headers=h)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["idioma"] == "ja"
    assert s["leccion"] == {"id": "ja/hiragana/a", "titulo": "あ い う", "bajada": "la fila de あ"}
    assert len(s["actividades"]) == 22
    primera = s["actividades"][0]
    assert (primera["id"], primera["dinamica"], primera["modo"], primera["repaso"]) == (
        "a0",
        "trazo",
        "presentar",
        False,
    )
    assert primera["contenido"]["audio"] == "/audio/ja/a.mp3"


async def test_idioma_sin_mapa_es_404(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    assert (await client.get("/api/v1/sesiones/de", headers=h)).status_code == 404


async def test_sin_repasos_cuando_se_pide(client, seed_invite, db_session, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    u = await usuario_por_email(db_session, EMAIL)
    db_session.add(
        UserFacet(
            user_id=u.id,
            idioma="ja",
            item_key="ja:kana:あ",
            faceta="escribir",
            state=CardState.REVIEWING,
            stability=2.0,
            difficulty=5.0,
            interval_days=2.0,
            repetitions=1,
            next_review_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.commit()
    con = (await client.get("/api/v1/sesiones/ja", headers=h)).json()
    sin = (await client.get("/api/v1/sesiones/ja", params={"repasos": "false"}, headers=h)).json()
    assert con["actividades"][0]["repaso"] is True
    assert not any(a["repaso"] for a in sin["actividades"])


async def test_repetir_una_leccion_es_todo_practica(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    r = await client.get("/api/v1/lecciones/ja/hiragana/a", headers=h)
    assert r.status_code == 200, r.text
    assert {a["modo"] for a in r.json()["actividades"]} <= {"presentar", "practicar"}
    assert (await client.get("/api/v1/lecciones/ja/hiragana/zz", headers=h)).status_code == 404


async def test_abrir_y_cerrar_una_corrida(client, seed_invite, db_session, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    r = await client.post(
        "/api/v1/lesson-runs",
        json={"idioma": "ja", "leccion_id": "ja/hiragana/a", "origen": "hoy", "repasos": 2},
        headers=h,
    )
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]
    r2 = await client.post(f"/api/v1/lesson-runs/{run_id}/fin", headers=h)
    assert r2.status_code == 200, r2.text
    assert r2.json() == {"manana": 0}
    run = (await db_session.execute(select(LessonRun))).scalar_one()
    assert run.finished_at is not None
    assert run.repasos == 2
    primera = run.finished_at
    await client.post(f"/api/v1/lesson-runs/{run_id}/fin", headers=h)
    await db_session.refresh(run)
    assert run.finished_at == primera


async def test_corrida_con_leccion_o_idioma_que_no_existen(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    mala = {"idioma": "ja", "leccion_id": "ja/hiragana/zz", "origen": "hoy"}
    assert (await client.post("/api/v1/lesson-runs", json=mala, headers=h)).status_code == 422
    sin_mapa = {"idioma": "de", "origen": "hoy"}
    assert (await client.post("/api/v1/lesson-runs", json=sin_mapa, headers=h)).status_code == 404


async def test_cerrar_la_corrida_de_otro_es_404(client, seed_invite, db_session, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    otro = await crear_usuario(db_session)
    run = LessonRun(user_id=otro.id, idioma="ja", origen="hoy")
    db_session.add(run)
    await db_session.commit()
    assert (await client.post(f"/api/v1/lesson-runs/{run.id}/fin", headers=h)).status_code == 404


async def test_evidencias(client, seed_invite, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    run_id = (
        await client.post("/api/v1/lesson-runs", json={"idioma": "ja", "origen": "hoy"}, headers=h)
    ).json()["id"]
    ev = {
        "id": str(uuid.uuid4()),
        "run_id": run_id,
        "dinamica": "eleccion",
        "modo": "comprobar",
        "item": "ja:kana:あ",
        "faceta": "reconocer",
        "acierto": True,
        "pistas": 0,
        "ms": 1200,
    }
    r = await client.post("/api/v1/evidencias", json={"evidencias": [ev]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"guardadas": 1}
    malo = {**ev, "id": str(uuid.uuid4()), "faceta": "genero"}
    assert (await client.post("/api/v1/evidencias", json={"evidencias": [malo]}, headers=h)).status_code == 422
    assert (await client.post("/api/v1/evidencias", json={"evidencias": []}, headers=h)).status_code == 422


async def test_audio_sin_cuenta(client, catalogo_mini):
    r = await client.get("/api/v1/audio/ja/a.mp3")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3"
    for ruta in ("/api/v1/audio/ja/zz.mp3", "/api/v1/audio/ja/a.wav", "/api/v1/audio/de/a.mp3"):
        assert (await client.get(ruta)).status_code == 404, ruta


async def test_mapas(client, seed_invite, db_session, catalogo_mini):
    h = await _cabeceras(client, seed_invite)
    assert (await client.get("/api/v1/mapas", headers=h)).json() == [
        {"idioma": "ja", "estudias": False, "nivel": "かな", "progreso": 0.0, "vencen": 0}
    ]
    u = await usuario_por_email(db_session, EMAIL)
    u.study_languages = ["ja"]
    db_session.add(
        LessonRun(
            user_id=u.id,
            idioma="ja",
            leccion_id="ja/hiragana/a",
            origen="hoy",
            finished_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    [m] = (await client.get("/api/v1/mapas", headers=h)).json()
    assert m["estudias"] is True
    assert m["progreso"] == 0.5
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_router.py -v`
Expected: FAIL, con 404 en todas las rutas porque el router todavía no existe.

- [ ] **Step 3: Completar los schemas**

Al final de `backend/src/klara/schemas/catalogo.py`, agrega:

```python
class ActividadOut(BaseModel):
    id: str
    dinamica: str
    modo: Modo
    items: list[str]
    faceta: str
    repaso: bool
    contenido: dict


class LeccionRef(BaseModel):
    id: str
    titulo: str
    bajada: str


class SesionOut(BaseModel):
    idioma: str
    leccion: LeccionRef | None
    actividades: list[ActividadOut]


class RunIn(BaseModel):
    idioma: str
    leccion_id: str | None = None
    origen: Literal["hoy", "mapa"]
    repasos: int = Field(default=0, ge=0, le=CAP_REPASOS)


class RunOut(BaseModel):
    id: UUID


class FinOut(BaseModel):
    # Las facetas de ese idioma que vencen en las próximas 24 horas.
    manana: int


class EvidenciasIn(BaseModel):
    evidencias: list[EvidenciaIn] = Field(min_length=1, max_length=50)


class EvidenciasOut(BaseModel):
    guardadas: int


class MapaResumen(BaseModel):
    idioma: str
    estudias: bool
    nivel: str
    progreso: float
    vencen: int
```

Y arriba, junto a los otros imports, agrega `from klara.catalogo.dinamicas import CAP_REPASOS`.

- [ ] **Step 4: Escribir el router**

`backend/src/klara/routers/catalogo.py`:

```python
"""El catálogo por HTTP (spec 2026-10-09 §4): componer sesiones, abrir y cerrar
corridas, registrar evidencias, servir el audio del catálogo y resumir los mapas."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from klara.catalogo.cargar import get_catalogo
from klara.catalogo.modelo import Catalogo
from klara.dependencies import CurrentUser, DBSession
from klara.models import LessonRun
from klara.schemas.catalogo import (
    ActividadOut,
    EvidenciasIn,
    EvidenciasOut,
    FinOut,
    LeccionRef,
    MapaResumen,
    RunIn,
    RunOut,
    SesionOut,
)
from klara.services.evidencias import EvidenciaInvalida, registrar
from klara.services.sesion import (
    Plan,
    componer,
    contar_vencidas,
    contenido,
    idiomas_de_estudio,
    items_vistos,
    lecciones_hechas,
    orden_de_mapas,
    plan_para_repetir,
    siguiente_leccion,
)

router = APIRouter(tags=["catalogo"])

_ARCHIVO = re.compile(r"[a-z0-9_-]+\.mp3")


def _con_mapa(cat: Catalogo, idioma: str) -> None:
    if idioma not in cat.mapas:
        raise HTTPException(status_code=404, detail="catalogo.idioma_sin_mapa")


def _sesion_out(cat: Catalogo, plan: Plan, ahora: datetime) -> SesionOut:
    lec = plan.leccion
    return SesionOut(
        idioma=plan.idioma,
        leccion=LeccionRef(id=lec.id, titulo=lec.leccion.titulo, bajada=lec.leccion.bajada)
        if lec
        else None,
        actividades=[
            ActividadOut(**a) for a in contenido(cat, plan, semilla=int(ahora.timestamp()))
        ],
    )


@router.get("/sesiones/{idioma}", response_model=SesionOut)
async def get_sesion(
    idioma: str, db: DBSession, user: CurrentUser, repasos: bool = True
) -> SesionOut:
    cat = get_catalogo()
    _con_mapa(cat, idioma)
    ahora = datetime.now(UTC)
    plan = await componer(db, cat, user.id, idioma, ahora, con_repasos=repasos)
    return _sesion_out(cat, plan, ahora)


@router.get("/lecciones/{idioma}/{unidad}/{leccion}", response_model=SesionOut)
async def get_leccion(
    idioma: str, unidad: str, leccion: str, db: DBSession, user: CurrentUser
) -> SesionOut:
    cat = get_catalogo()
    _con_mapa(cat, idioma)
    lec = cat.lecciones.get(f"{idioma}/{unidad}/{leccion}")
    if lec is None:
        raise HTTPException(status_code=404, detail="catalogo.leccion_inexistente")
    hechas = await lecciones_hechas(db, user.id, idioma)
    vistos = await items_vistos(db, cat, user.id, idioma, hechas)
    return _sesion_out(cat, plan_para_repetir(lec, vistos), datetime.now(UTC))


@router.post("/lesson-runs", response_model=RunOut, status_code=201)
async def abrir_corrida(body: RunIn, db: DBSession, user: CurrentUser) -> RunOut:
    cat = get_catalogo()
    _con_mapa(cat, body.idioma)
    if body.leccion_id is not None:
        lec = cat.lecciones.get(body.leccion_id)
        if lec is None or lec.idioma != body.idioma:
            raise HTTPException(status_code=422, detail="catalogo.leccion_inexistente")
    run_id = uuid4()
    db.add(
        LessonRun(
            id=run_id,
            user_id=user.id,
            idioma=body.idioma,
            leccion_id=body.leccion_id,
            origen=body.origen,
            repasos=body.repasos,
        )
    )
    await db.commit()
    return RunOut(id=run_id)


@router.post("/lesson-runs/{run_id}/fin", response_model=FinOut)
async def cerrar_corrida(run_id: UUID, db: DBSession, user: CurrentUser) -> FinOut:
    run = (
        await db.execute(
            select(LessonRun).where(LessonRun.id == run_id, LessonRun.user_id == user.id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="catalogo.corrida_inexistente")
    ahora = datetime.now(UTC)
    idioma = run.idioma
    if run.finished_at is None:
        run.finished_at = ahora
        await db.commit()
    return FinOut(manana=await contar_vencidas(db, user.id, idioma, ahora + timedelta(days=1)))


@router.post("/evidencias", response_model=EvidenciasOut)
async def post_evidencias(body: EvidenciasIn, db: DBSession, user: CurrentUser) -> EvidenciasOut:
    try:
        guardadas = await registrar(db, get_catalogo(), user.id, body.evidencias, datetime.now(UTC))
    except EvidenciaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return EvidenciasOut(guardadas=guardadas)


@router.get("/audio/{idioma}/{archivo}")
async def get_audio(idioma: str, archivo: str) -> FileResponse:
    """El audio del catálogo es contenido público: sin sesión, para que el
    <audio> del teléfono lo cargue directo."""
    cat = get_catalogo()
    if idioma not in cat.mapas or not _ARCHIVO.fullmatch(archivo):
        raise HTTPException(status_code=404)
    path = cat.audio_path(idioma, archivo)
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"}
    )


@router.get("/mapas", response_model=list[MapaResumen])
async def get_mapas(db: DBSession, user: CurrentUser) -> list[MapaResumen]:
    cat = get_catalogo()
    ahora = datetime.now(UTC)
    estudia = set(idiomas_de_estudio(user, cat))
    out: list[MapaResumen] = []
    for idioma in orden_de_mapas(cat):
        mapa = cat.mapas[idioma]
        lecciones = cat.lecciones_de(idioma)
        hechas = await lecciones_hechas(db, user.id, idioma)
        actual = siguiente_leccion(cat, idioma, hechas)
        nivel = (
            next(u.nivel for u in mapa.unidades if u.id == actual.unidad)
            if actual
            else mapa.unidades[-1].nivel
        )
        out.append(
            MapaResumen(
                idioma=idioma,
                estudias=idioma in estudia,
                nivel=nivel,
                progreso=round(sum(1 for lec in lecciones if lec.id in hechas) / len(lecciones), 3),
                vencen=await contar_vencidas(db, user.id, idioma, ahora),
            )
        )
    return out
```

- [ ] **Step 5: Registrar el router y cargar el catálogo al arrancar**

En `backend/src/klara/main.py`:

1. En el bloque `from klara.routers import (…)`, agrega `catalogo,` después de `auth_native,`.
2. Junto a los imports de `klara`, agrega:

```python
from klara.catalogo.cargar import get_catalogo
from klara.catalogo.modelo import Catalogo
from klara.services.sesion import huerfanas
```

3. Cambia `from klara.models import User` por `from klara.models import User, UserFacet`.
4. Justo antes de `@asynccontextmanager`, agrega:

```python
async def _avisar_huerfanas(cat: Catalogo) -> None:
    """Las facetas cuyo ítem ya no está en el catálogo se avisan y se ignoran;
    nunca se borran (spec 2026-10-09 §2.1)."""
    async for db in get_session():
        claves = set((await db.execute(select(UserFacet.item_key).distinct())).scalars())
        sobran = huerfanas(claves, cat)
        if sobran:
            log.warning("catalogo.huerfanas", total=len(sobran), ejemplos=sobran[:10])
```

5. En `lifespan`, justo después de `log.info("startup", env=settings.app_env)`, agrega:

```python
    # Un catálogo roto no arranca (spec 2026-10-09 §2.1): CatalogoInvalido sube.
    cat = get_catalogo()
    log.info("startup.catalogo", idiomas=sorted(cat.mapas), lecciones=len(cat.lecciones))
    try:
        await _avisar_huerfanas(cat)
    except Exception as exc:
        log.warning("startup.huerfanas_skip", error=str(exc))
```

6. Junto a `app.include_router(today.router, prefix="/api/v1")`, agrega `app.include_router(catalogo.router, prefix="/api/v1")`.

- [ ] **Step 6: Correr y ver pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_catalogo_router.py -v`
Expected: PASS, 11 tests.

- [ ] **Step 7: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/schemas/catalogo.py backend/src/klara/routers/catalogo.py backend/src/klara/main.py backend/tests/test_catalogo_router.py
git commit -m "feat(tres-idiomas): rutas de sesiones, corridas, evidencias, audio y mapas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Hoy con una línea por idioma (backend)

**Files:**
- Modify (reescribir): `backend/src/klara/schemas/today.py`
- Modify (reescribir): `backend/src/klara/services/today.py`
- Modify: `backend/src/klara/routers/today.py` (solo el docstring; la ruta y la validación de `since` quedan igual)
- Modify (reescribir): `backend/tests/test_today.py`

**Interfaces:**
- Consumes:
  - de la tarea 8: `componer`, `minutos`, `idiomas_de_estudio`;
  - `LeccionRef` (tarea 10);
  - `get_catalogo` (tarea 3).
- Produces:
  - `GET /api/v1/today?since=…` → `TodayOut{lineas: Linea[]}`
  - `Linea{idioma, estado: "hecha"|"ahora"|"pendiente", minutos, repasos, leccion: LeccionRef|null, hecho: {repasos, leccion}|null}`
  - `ordenar_idiomas(idiomas, ultimas) -> list[str]`, en `klara.services.today`.

- [ ] **Step 1: Confirmar que nadie más usa lo viejo**

Run: `cd backend && grep -rn "schemas.today\|services.today" src --include=*.py`
Expected: solo `src/klara/routers/today.py` y `src/klara/services/today.py`. Si aparece otro archivo, para y avísale a Samuel antes de reescribir.

- [ ] **Step 2: Reescribir los tests**

Reemplaza todo `backend/tests/test_today.py` por:

```python
"""GET /today (spec 2026-10-09 §5.1): una línea por idioma de estudio, en el
orden que pone primero al que lleva más tiempo sin terminarse."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from klara.models import LessonRun, UserFacet
from klara.models.enums import CardState
from klara.services.today import ordenar_idiomas
from tests.ayudas import entrar, usuario_por_email

AHORA = datetime.now(UTC).replace(microsecond=0)
SINCE = AHORA - timedelta(hours=3)
EMAIL = "hoy@example.com"


async def _hoy(client, cookie: str) -> dict:
    r = await client.get(
        "/api/v1/today", params={"since": SINCE.isoformat()}, headers={"Cookie": cookie}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _con_japones(db):
    u = await usuario_por_email(db, EMAIL)
    u.study_languages = ["ja"]
    await db.commit()
    return u


def _corrida(user, **kw) -> LessonRun:
    base = dict(
        user_id=user.id,
        idioma="ja",
        leccion_id="ja/hiragana/a",
        origen="hoy",
        repasos=4,
        started_at=AHORA - timedelta(hours=1),
        finished_at=AHORA - timedelta(minutes=30),
    )
    return LessonRun(**{**base, **kw})


async def test_since_fuera_de_rango_es_422(client, seed_invite, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    for since in (AHORA + timedelta(minutes=5), AHORA - timedelta(hours=49), AHORA.replace(tzinfo=None)):
        r = await client.get(
            "/api/v1/today", params={"since": since.isoformat()}, headers={"Cookie": cookie}
        )
        assert r.status_code == 422, since


async def test_sin_sesion_es_401(client, catalogo_mini):
    r = await client.get("/api/v1/today", params={"since": SINCE.isoformat()})
    assert r.status_code == 401


async def test_sin_idiomas_con_mapa_no_hay_lineas(client, seed_invite, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    assert await _hoy(client, cookie) == {"lineas": []}


async def test_cuenta_nueva_una_linea_con_la_primera_leccion(client, seed_invite, db_session, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    await _con_japones(db_session)
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea == {
        "idioma": "ja",
        "estado": "ahora",
        "minutos": 6,
        "repasos": 0,
        "leccion": {"id": "ja/hiragana/a", "titulo": "あ い う", "bajada": "la fila de あ"},
        "hecho": None,
    }


async def test_linea_hecha_hoy(client, seed_invite, db_session, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    db_session.add(_corrida(u))
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["estado"] == "hecha"
    assert linea["hecho"] == {"repasos": 4, "leccion": "あ い う"}
    assert linea["leccion"]["id"] == "ja/hiragana/e"


async def test_lo_de_ayer_no_marca_hoy(client, seed_invite, db_session, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    db_session.add(
        _corrida(u, started_at=SINCE - timedelta(hours=1), finished_at=SINCE - timedelta(seconds=1))
    )
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["estado"] == "ahora"
    assert linea["hecho"] is None


async def test_corrida_abierta_o_del_mapa_no_marcan(client, seed_invite, db_session, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    db_session.add_all([_corrida(u, finished_at=None), _corrida(u, origen="mapa")])
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["estado"] == "ahora"


async def test_repasos_que_vencen(client, seed_invite, db_session, catalogo_mini):
    cookie = await entrar(client, seed_invite, EMAIL)
    u = await _con_japones(db_session)
    for kana in "あいうえおを":
        db_session.add(
            UserFacet(
                user_id=u.id,
                idioma="ja",
                item_key=f"ja:kana:{kana}",
                faceta="escribir",
                state=CardState.REVIEWING,
                stability=2.0,
                difficulty=5.0,
                interval_days=2.0,
                repetitions=1,
                next_review_at=AHORA - timedelta(hours=1),
            )
        )
    await db_session.commit()
    [linea] = (await _hoy(client, cookie))["lineas"]
    assert linea["repasos"] == 6
    # 6 trazos de repaso x 20 s más los 312 s de la lección = 432 s
    assert linea["minutos"] == 8


def test_ordenar_idiomas():
    ayer, antier = AHORA - timedelta(days=1), AHORA - timedelta(days=2)
    assert ordenar_idiomas(["de", "ja", "en"], {}) == ["de", "ja", "en"]
    assert ordenar_idiomas(["de", "ja", "en"], {"de": ayer, "ja": antier}) == ["en", "ja", "de"]
    assert ordenar_idiomas(["de", "ja"], {"de": ayer, "ja": ayer}) == ["de", "ja"]
```

- [ ] **Step 3: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_today.py -v`
Expected: falla en la recolección con `ImportError: cannot import name 'ordenar_idiomas'`.

- [ ] **Step 4: Reescribir el schema y el servicio**

Reemplaza todo `backend/src/klara/schemas/today.py` por:

```python
"""La respuesta de GET /today (spec 2026-10-09 §5.1): una línea por idioma."""

from typing import Literal

from pydantic import BaseModel

from klara.schemas.catalogo import LeccionRef


class HechoHoy(BaseModel):
    repasos: int
    leccion: str | None


class Linea(BaseModel):
    idioma: str
    estado: Literal["hecha", "ahora", "pendiente"]
    minutos: int
    repasos: int
    leccion: LeccionRef | None
    hecho: HechoHoy | None


class TodayOut(BaseModel):
    lineas: list[Linea]
```

Reemplaza todo `backend/src/klara/services/today.py` por:

```python
"""El día de Hoy (spec 2026-10-09 §5.1): una línea por idioma de estudio. Va
primero el que lleva más tiempo sin una línea terminada, contando solo lo
terminado antes de hoy: así el orden no cambia a mitad del día."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from klara.catalogo.cargar import get_catalogo
from klara.models import LessonRun, User
from klara.schemas.catalogo import LeccionRef
from klara.schemas.today import HechoHoy, Linea, TodayOut
from klara.services.sesion import componer, idiomas_de_estudio, minutos

_NUNCA = datetime.min.replace(tzinfo=UTC)


def ordenar_idiomas(idiomas: list[str], ultimas: dict[str, datetime]) -> list[str]:
    """Primero el idioma con la última línea terminada más vieja (o ninguna); con
    empate, el orden de `study_languages`."""
    return sorted(idiomas, key=lambda i: (ultimas.get(i, _NUNCA), idiomas.index(i)))


async def build_today(db: AsyncSession, user: User, *, since: datetime, now: datetime) -> TodayOut:
    cat = get_catalogo()
    idiomas = idiomas_de_estudio(user, cat)
    if not idiomas:
        return TodayOut(lineas=[])

    de_hoy = (
        LessonRun.user_id == user.id,
        LessonRun.origen == "hoy",
        LessonRun.finished_at.is_not(None),
    )
    ultimas = dict(
        (
            await db.execute(
                select(LessonRun.idioma, func.max(LessonRun.finished_at))
                .where(*de_hoy, LessonRun.finished_at < since)
                .group_by(LessonRun.idioma)
            )
        ).all()
    )
    terminadas_hoy = (
        (
            await db.execute(
                select(LessonRun)
                .where(*de_hoy, LessonRun.finished_at >= since)
                .order_by(LessonRun.finished_at)
            )
        )
        .scalars()
        .all()
    )

    lineas: list[Linea] = []
    for idioma in ordenar_idiomas(idiomas, ultimas):
        plan = await componer(db, cat, user.id, idioma, now)
        corridas = [r for r in terminadas_hoy if r.idioma == idioma]
        hecho = None
        if corridas:
            ultima = next((r.leccion_id for r in reversed(corridas) if r.leccion_id in cat.lecciones), None)
            hecho = HechoHoy(
                repasos=sum(r.repasos for r in corridas),
                leccion=cat.lecciones[ultima].leccion.titulo if ultima else None,
            )
        if hecho:
            estado = "hecha"
        elif any(linea.estado == "ahora" for linea in lineas):
            estado = "pendiente"
        else:
            estado = "ahora"
        lec = plan.leccion
        lineas.append(
            Linea(
                idioma=idioma,
                estado=estado,
                minutos=minutos(plan),
                repasos=len(plan.repasos),
                leccion=LeccionRef(id=lec.id, titulo=lec.leccion.titulo, bajada=lec.leccion.bajada)
                if lec
                else None,
                hecho=hecho,
            )
        )
    return TodayOut(lineas=lineas)
```

En `backend/src/klara/routers/today.py`, cambia el docstring del módulo por `"""GET /today: las líneas de Hoy (spec 2026-10-09 §5.1)."""`. El resto del archivo no cambia.

- [ ] **Step 5: Correr y ver pasar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_today.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 6: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/schemas/today.py backend/src/klara/services/today.py backend/src/klara/routers/today.py backend/tests/test_today.py
git commit -m "feat(tres-idiomas): Hoy con una línea por idioma

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Idiomas de estudio en /me

**Files:**
- Modify: `backend/src/klara/schemas/user.py` (`UserOut.study_languages` y `UserUpdate.study_languages`)
- Modify: `backend/src/klara/routers/users.py` (`_to_out` y `update_me`)
- Test: `backend/tests/test_users_study_languages.py`

**Interfaces:**
- Consumes: `idiomas_de_estudio` (tarea 8), `get_catalogo` (tarea 3).
- Produces:
  - `GET /api/v1/me` incluye `study_languages: list[str]`, la lista efectiva y nunca null;
  - `PATCH /api/v1/me` acepta `study_languages`: entre 1 y 3, sin repetir, todos con mapa. Si va `null`, vuelve al valor por defecto.

- [ ] **Step 1: Escribir los tests**

`backend/tests/test_users_study_languages.py`:

```python
"""`study_languages` en /me (spec 2026-10-09 §2.2 y §5.6)."""

import pytest

from tests.ayudas import entrar

EMAIL = "idiomas@example.com"


async def _me(client, h) -> dict:
    r = await client.get("/api/v1/me", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_sin_elegir_vale_el_idioma_de_estudio_si_tiene_mapa(client, seed_invite, catalogo_mini):
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    assert (await _me(client, h))["study_languages"] == []  # «de» todavía no tiene mapa


async def test_elegir_japones(client, seed_invite, catalogo_mini):
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    r = await client.patch("/api/v1/me", json={"study_languages": ["ja"]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["study_languages"] == ["ja"]
    assert (await _me(client, h))["study_languages"] == ["ja"]


@pytest.mark.parametrize("valor", [["fr"], ["xx"], [], ["ja", "ja"], ["ja", "de", "en", "fr"]])
async def test_lo_que_no_vale_es_422(client, seed_invite, catalogo_mini, valor):
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    r = await client.patch("/api/v1/me", json={"study_languages": valor}, headers=h)
    assert r.status_code == 422, valor


async def test_null_vuelve_al_idioma_de_estudio(client, seed_invite, catalogo_mini):
    h = {"Cookie": await entrar(client, seed_invite, EMAIL)}
    await client.patch("/api/v1/me", json={"study_languages": ["ja"]}, headers=h)
    await client.patch("/api/v1/me", json={"target_language": "ja"}, headers=h)
    r = await client.patch("/api/v1/me", json={"study_languages": None}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["study_languages"] == ["ja"]  # sale de target_language
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_users_study_languages.py -v`
Expected: FAIL con `KeyError: 'study_languages'`, y los 422 salen 200.

- [ ] **Step 3: Implementar**

En `backend/src/klara/schemas/user.py`:

1. En `UserOut`, después de `needs_onboarding: bool = False`, agrega:

```python
    # Los idiomas de las líneas de Hoy, ya resueltos: nunca null (spec 2026-10-09 §2.2).
    study_languages: list[str] = Field(default_factory=list)
```

2. En `UserUpdate`, después de `learning_context`, agrega el campo y su validador:

```python
    study_languages: list[str] | None = Field(default=None, min_length=1, max_length=3)

    @field_validator("study_languages")
    @classmethod
    def _check_study_languages(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if len(set(v)) != len(v):
            raise ValueError("study_languages no puede repetir idiomas")
        for code in v:
            _validate_lang(code)
        return v
```

En `backend/src/klara/routers/users.py`:

1. Agrega los imports:

```python
from klara.catalogo.cargar import get_catalogo
from klara.services.sesion import idiomas_de_estudio
```

2. En `_to_out`, dentro de `UserOut(...)`, después de `needs_onboarding=…`, agrega:

```python
        study_languages=idiomas_de_estudio(user, get_catalogo()),
```

3. En `update_me`, justo antes de `await db.commit()`, agrega:

```python
    if "study_languages" in data:
        nuevos = data["study_languages"]
        if nuevos is not None and any(i not in get_catalogo().mapas for i in nuevos):
            raise HTTPException(status_code=422, detail="study_languages.sin_mapa")
        user.study_languages = nuevos
```

- [ ] **Step 4: Correr y ver pasar, y la suite de usuarios entera**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/test_users_study_languages.py tests/test_users_onboarding.py tests/test_owner_adoption.py -v`
Expected: PASS. Los dos archivos de usuarios que ya existían siguen en verde. `/me` ahora carga el catálogo real de la tarea 7.

- [ ] **Step 5: La suite completa del backend**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/ -q > ../.pytest-tres-idiomas.log 2>&1; tail -5 ../.pytest-tres-idiomas.log`
Expected: `N passed`, sin fallos. Se redirige a un archivo porque medir a través de un pipe puede colgar la corrida; la nota está en la skill `gates-locales`. Borra el log después: `rm ../.pytest-tres-idiomas.log`.

- [ ] **Step 6: Lint y commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && cd ..
git add backend/src/klara/schemas/user.py backend/src/klara/routers/users.py backend/tests/test_users_study_languages.py
git commit -m "feat(tres-idiomas): elegir los idiomas de estudio en /me

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Fase B — El frontend

### Task 13: Tipos, cliente y audio de archivo

**Files:**
- Modify: `frontend/src/api/types.ts` (tipos nuevos; `study_languages` en `User` y `UserUpdate`)
- Modify: `frontend/src/api/client.ts` (métodos nuevos)
- Modify: `frontend/src/lib/tts.ts` (`speak()` acepta `src`)
- Test: `frontend/src/lib/tts.src.test.ts`

**Interfaces:**
- Produces:
  - Tipos: `Modo`, `Faceta`, `Evidencia`, `EvidenciaIn`, `ActividadOut`, `LeccionRef`, `SesionOut`, `RunIn`, `MapaResumen`, `Linea`.
  - En `User`, `study_languages: string[]`; en `UserUpdate`, `study_languages?: string[] | null`.
  - Métodos de `api`:
    - `sesion(idioma, repasos = true)`
    - `leccion(idioma, unidad, leccion)`
    - `abrirRun(body)`
    - `cerrarRun(id)`
    - `evidencias(lote)`
    - `mapas()`
  - `speak(text, language, { src })`: reproduce ese archivo por el mismo elemento, y si falla cae al mismo respaldo de Web Speech.
  - `TodayOut` se queda como está hasta la tarea 19.

- [ ] **Step 1: Escribir el test del audio de archivo**

`frontend/src/lib/tts.src.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

// El audio del catálogo (kana, pares mínimos) suena por speak() con `src`: el
// mismo elemento desbloqueado y el mismo respaldo que el TTS en vivo.
vi.mock("./native", () => ({
  isNative: () => false,
  getToken: async () => null,
  setToken: async () => undefined,
  clearToken: async () => undefined,
  authHeaders: async () => ({}),
  tap: () => undefined,
}));

class FakeAudio {
  static creados: FakeAudio[] = [];
  src = "";
  preload = "";
  preservesPitch = true;
  playbackRate = 1;
  currentTime = 0;
  duration = Number.NaN;
  constructor() {
    FakeAudio.creados.push(this);
  }
  addEventListener() {}
  load() {}
  pause() {}
  play() {
    return Promise.resolve();
  }
}
vi.stubGlobal("Audio", FakeAudio);

const { speak, stop } = await import("./tts");
const ultimo = () => FakeAudio.creados[FakeAudio.creados.length - 1];
const tic = () => new Promise((r) => setTimeout(r, 0));

afterEach(() => stop());

describe("speak con un archivo", () => {
  it("reproduce el archivo y no pide TTS", async () => {
    speak("あ", "ja", { src: "/api/v1/audio/ja/a.mp3" });
    await tic();
    expect(ultimo().src).toBe("/api/v1/audio/ja/a.mp3");
  });

  it("sin src sigue pidiendo TTS", async () => {
    speak("Hallo", "de");
    await tic();
    expect(ultimo().src).toContain("/tts?text=Hallo");
  });
});
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd frontend && npx vitest run src/lib/tts.src.test.ts`
Expected: FAIL en el primer test. `src` contiene `/tts?text=%E3%81%82…` en vez del archivo, porque hoy `opts.src` se ignora.

- [ ] **Step 3: Agregar `src` a `speak()`**

En `frontend/src/lib/tts.ts`:

1. En la firma de `speak`, cambia el tipo de `opts` a:

```ts
  opts?: {
    rate?: number;
    mode?: TTSMode;
    /** Un archivo del catálogo: suena en vez del TTS en vivo (spec 2026-10-09 §3.1). */
    src?: string;
    onDone?: (reason: TTSDoneReason) => void;
  },
```

2. Reemplaza la línea `void ttsSource(text, language, opts?.mode, () => gen !== generation)` por:

```ts
  // Un archivo del catálogo suena por el mismo elemento y con el mismo respaldo
  // de Web Speech que el TTS; solo cambia de dónde sale el audio.
  const fuente = opts?.src
    ? Promise.resolve(opts.src)
    : ttsSource(text, language, opts?.mode, () => gen !== generation);
  void fuente
```

El `.then(...)` y el `.catch(...)` que siguen quedan igual, ahora encadenados a `fuente`.

- [ ] **Step 4: Correr y ver pasar, con los tests de TTS que ya existen**

Run: `cd frontend && npx vitest run src/lib/tts.src.test.ts src/lib/tts.native.test.ts src/lib/tts.nativo.test.ts`
Expected: PASS.

- [ ] **Step 5: Agregar los tipos**

Al final de `frontend/src/api/types.ts`, agrega:

```ts
// --- Klara en tres idiomas (spec 2026-10-09) ---

export type Modo = "presentar" | "practicar" | "comprobar";
export type Faceta = "reconocer" | "oir" | "escribir" | "genero" | "aplicar" | "pronunciar";

/** Lo que devuelve una dinámica por cada respuesta (spec §3.1). */
export interface Evidencia {
  item: string;
  faceta: Faceta;
  acierto: boolean;
  pistas: number;
  ms: number;
  detalle?: Record<string, unknown>;
}

/** Lo que viaja a POST /evidencias: la evidencia, su id, su corrida y de dónde salió. */
export interface EvidenciaIn extends Evidencia {
  id: string;
  run_id: string;
  dinamica: string;
  modo: Modo;
}

export interface ActividadOut {
  id: string;
  dinamica: string;
  modo: Modo;
  items: string[];
  faceta: Faceta;
  /** Viene de la cola de repasos (se rotula «Repaso», no «Prueba»). */
  repaso: boolean;
  contenido: unknown;
}

export interface LeccionRef {
  id: string;
  titulo: string;
  bajada: string;
}

export interface SesionOut {
  idioma: string;
  leccion: LeccionRef | null;
  actividades: ActividadOut[];
}

export interface RunIn {
  idioma: string;
  leccion_id: string | null;
  origen: "hoy" | "mapa";
  repasos: number;
}

export interface MapaResumen {
  idioma: string;
  estudias: boolean;
  nivel: string;
  progreso: number;
  vencen: number;
}

/** Una línea de Hoy (spec §5.1). */
export interface Linea {
  idioma: string;
  estado: "hecha" | "ahora" | "pendiente";
  minutos: number;
  repasos: number;
  leccion: LeccionRef | null;
  hecho: { repasos: number; leccion: string | null } | null;
}
```

En `export interface User`, después de `needs_onboarding: boolean;`, agrega `study_languages: string[];`.
En `export interface UserUpdate`, después de `learning_context?: string | null;`, agrega `study_languages?: string[] | null;`.

- [ ] **Step 6: Agregar los métodos del cliente**

En `frontend/src/api/client.ts`:

1. En el `import type { … } from "./types";`, agrega en orden alfabético: `EvidenciaIn`, `MapaResumen`, `RunIn`, `SesionOut`.
2. Dentro del objeto `api`, justo después de la línea de `today:`, agrega:

```ts
  // --- Klara en tres idiomas (spec 2026-10-09 §4) ---
  sesion: (idioma: string, repasos = true) =>
    request<SesionOut>(`/sesiones/${encodeURIComponent(idioma)}?repasos=${repasos}`),
  leccion: (idioma: string, unidad: string, leccion: string) =>
    request<SesionOut>(`/lecciones/${[idioma, unidad, leccion].map((p) => encodeURIComponent(p)).join("/")}`),
  abrirRun: (body: RunIn) =>
    request<{ id: string }>("/lesson-runs", { method: "POST", body: JSON.stringify(body) }),
  cerrarRun: (id: string) =>
    request<{ manana: number }>(`/lesson-runs/${encodeURIComponent(id)}/fin`, { method: "POST" }),
  evidencias: (evidencias: EvidenciaIn[]) =>
    request<{ guardadas: number }>("/evidencias", {
      method: "POST",
      body: JSON.stringify({ evidencias }),
    }),
  mapas: () => request<MapaResumen[]>("/mapas"),
```

- [ ] **Step 7: Arreglar los literales de `User` que ya existan**

Run: `cd frontend && grep -rn "needs_onboarding:" src --include=*.ts --include=*.tsx | grep -v "api/types.ts"`

A cada objeto literal de tipo `User` que salga (normalmente fixtures de tests), agrégale `study_languages: []`. Si no sale ninguno, no hay nada que hacer.

- [ ] **Step 8: Typecheck y tests**

Run: `cd frontend && npm run typecheck && npx vitest run`
Expected: typecheck sin errores y todos los tests en verde.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/lib/tts.ts frontend/src/lib/tts.src.test.ts
git add -u frontend/src
git commit -m "feat(tres-idiomas): tipos y cliente del catálogo; speak() con audio de archivo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: El reproductor como máquina de estados

**Files:**
- Create: `frontend/src/lib/sesion.ts`
- Test: `frontend/src/lib/sesion.test.ts`

**Interfaces:**
- Consumes: `ActividadOut`, `Evidencia` y `Faceta` (tarea 13).
- Produces:
  - Tipos: `Capacidad = "escuchar" | "hablar" | "escribir"`, `Fase`, `Marca = "bien" | "pista" | "mal"`.
  - `EstadoSesion{fase, cola, idx, apagadas, saltadas, reintentadas, todoBien, resumen, enviosFallidos}`.
  - `AccionSesion`: `cargando`, `cargada`, `fallo`, `resultado`, `seguir`, `apagar`, `envioFallido`.
  - Constantes: `AUTO_AVANCE_MS = 700`, `REINTENTO_TRAS = 3`.
  - `inicialSesion`
  - `sesionReducer(estado, accion)`
  - `necesita(actividad) -> Capacidad | null`
  - `porReforzar(estado) -> string[]`
  - `etiquetaItem(item) -> string`

- [ ] **Step 1: Escribir los tests**

`frontend/src/lib/sesion.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { ActividadOut, Evidencia } from "../api/types";
import {
  etiquetaItem,
  inicialSesion,
  necesita,
  porReforzar,
  sesionReducer,
  type AccionSesion,
  type EstadoSesion,
} from "./sesion";

const act = (id: string, over: Partial<ActividadOut> = {}): ActividadOut => ({
  id,
  dinamica: "eleccion",
  modo: "practicar",
  items: ["ja:kana:あ"],
  faceta: "reconocer",
  repaso: false,
  contenido: {},
  ...over,
});
const ev = (over: Partial<Evidencia> = {}): Evidencia => ({
  item: "ja:kana:あ",
  faceta: "reconocer",
  acierto: true,
  pistas: 0,
  ms: 900,
  ...over,
});
const correr = (acciones: AccionSesion[], e: EstadoSesion = inicialSesion) =>
  acciones.reduce(sesionReducer, e);
const cargar = (actividades: ActividadOut[]): AccionSesion => ({ tipo: "cargada", actividades });
const responde = (over: Partial<Evidencia> = {}): AccionSesion => ({ tipo: "resultado", evidencias: [ev(over)] });

describe("sesionReducer", () => {
  it("sin actividades queda vacía", () => {
    expect(correr([cargar([])]).fase).toBe("vacia");
  });

  it("presentar avanza sin pasar por resultado", () => {
    const e = correr([
      cargar([act("a0", { dinamica: "trazo", modo: "presentar", faceta: "escribir" }), act("a1")]),
      { tipo: "resultado", evidencias: [] },
    ]);
    expect([e.fase, e.idx]).toEqual(["actividad", 1]);
  });

  it("si acierta, queda en resultado con todoBien y luego sigue", () => {
    let e = correr([cargar([act("a0"), act("a1")]), responde()]);
    expect([e.fase, e.todoBien]).toEqual(["resultado", true]);
    e = sesionReducer(e, { tipo: "seguir" });
    expect([e.fase, e.idx]).toEqual(["actividad", 1]);
  });

  it("un acierto con pista no es todoBien", () => {
    expect(correr([cargar([act("a0")]), responde({ pistas: 1 })]).todoBien).toBe(false);
  });

  it("un segundo resultado en la misma actividad se ignora", () => {
    const una = correr([cargar([act("a0"), act("a1")]), responde({ acierto: false })]);
    expect(sesionReducer(una, responde())).toBe(una);
  });

  it("lo fallado en práctica vuelve una vez, tres actividades después", () => {
    const cola = ["a0", "a1", "a2", "a3", "a4", "a5"].map((id) => act(id));
    let e = correr([cargar(cola), responde({ acierto: false })]);
    expect(e.cola.map((a) => a.id)).toEqual(["a0", "a1", "a2", "a3", "a0~r", "a4", "a5"]);
    const sigueBien: AccionSesion[] = [responde(), { tipo: "seguir" }];
    e = correr([{ tipo: "seguir" }, ...sigueBien, ...sigueBien, ...sigueBien], e);
    expect(e.cola[e.idx].id).toBe("a0~r");
    e = sesionReducer(e, responde({ acierto: false }));
    expect(e.cola.filter((a) => a.id.startsWith("a0")).length).toBe(2);
  });

  it("cerca del final, el reintento va al final", () => {
    const e = correr([cargar([act("a0"), act("a1")]), responde({ acierto: false })]);
    expect(e.cola.map((a) => a.id)).toEqual(["a0", "a1", "a0~r"]);
  });

  it("en prueba no se repite y entra al resumen", () => {
    const e = correr([cargar([act("a0", { modo: "comprobar" }), act("a1")]), responde({ acierto: false })]);
    expect(e.cola).toHaveLength(2);
    expect(e.resumen).toEqual({ "ja:kana:あ": { reconocer: "mal" } });
  });

  it("el resumen se queda con lo peor de cada faceta", () => {
    const prueba = (id: string) => act(id, { modo: "comprobar" });
    const e = correr([
      cargar([prueba("a0"), prueba("a1"), prueba("a2")]),
      responde({ acierto: false }),
      { tipo: "seguir" },
      responde(),
      { tipo: "seguir" },
      responde({ pistas: 1, faceta: "oir" }),
    ]);
    expect(e.resumen).toEqual({ "ja:kana:あ": { reconocer: "mal", oir: "pista" } });
    expect(porReforzar(e)).toEqual(["ja:kana:あ"]);
  });

  it("la práctica no entra al resumen", () => {
    expect(correr([cargar([act("a0")]), responde()]).resumen).toEqual({});
  });

  it("apagar escribir salta los trazos, también el de ahora", () => {
    const trazo = (id: string) => act(id, { dinamica: "trazo", faceta: "escribir" });
    const e = correr([cargar([trazo("a0"), trazo("a1"), act("a2")]), { tipo: "apagar", capacidad: "escribir" }]);
    expect([e.fase, e.idx]).toEqual(["actividad", 2]);
    expect(e.saltadas).toEqual(["a0", "a1"]);
  });

  it("si se salta todo, termina", () => {
    const oir = (id: string) => act(id, { faceta: "oir" });
    const e = correr([cargar([oir("a0"), oir("a1")]), { tipo: "apagar", capacidad: "escuchar" }]);
    expect(e.fase).toBe("fin");
  });

  it("termina después de la última", () => {
    const e = correr([cargar([act("a0")]), responde(), { tipo: "seguir" }]);
    expect(e.fase).toBe("fin");
  });

  it("cuenta los envíos fallidos sin cambiar de fase", () => {
    const e = correr([cargar([act("a0")]), { tipo: "envioFallido" }, { tipo: "envioFallido" }]);
    expect([e.fase, e.enviosFallidos]).toEqual(["actividad", 2]);
  });

  it("cargando vuelve a empezar", () => {
    const e = correr([cargar([act("a0")]), responde({ acierto: false }), { tipo: "cargando" }]);
    expect(e).toEqual(inicialSesion);
  });
});

describe("necesita", () => {
  it("el trazo pide escribir salvo al presentar; oír pide escuchar", () => {
    expect(necesita(act("x", { dinamica: "trazo", faceta: "escribir" }))).toBe("escribir");
    expect(necesita(act("x", { dinamica: "trazo", modo: "presentar", faceta: "escribir" }))).toBeNull();
    expect(necesita(act("x", { faceta: "oir" }))).toBe("escuchar");
    expect(necesita(act("x"))).toBeNull();
    expect(necesita(act("x", { dinamica: "emparejar" }))).toBeNull();
  });
});

describe("etiquetaItem", () => {
  it("se queda con lo que va después del tipo", () => {
    expect(etiquetaItem("ja:kana:か")).toBe("か");
    expect(etiquetaItem("de:sustantivo:Frau")).toBe("Frau");
  });
});
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd frontend && npx vitest run src/lib/sesion.test.ts`
Expected: falla con `Failed to resolve import "./sesion"`.

- [ ] **Step 3: Implementar**

`frontend/src/lib/sesion.ts`:

```ts
import type { ActividadOut, Evidencia, Faceta } from "../api/types";

/**
 * El reproductor de lecciones como máquina de estados pura (spec 2026-10-09
 * §5.4). La ruta (routes/Sesion.tsx) pone los efectos: pedir la sesión, abrir y
 * cerrar la corrida, mandar las evidencias y el avance automático. Aquí solo
 * hay transiciones, para poder probarlas sin DOM.
 */
export type Capacidad = "escuchar" | "hablar" | "escribir";
export type Fase = "cargando" | "fallo" | "vacia" | "actividad" | "resultado" | "fin";
export type Marca = "bien" | "pista" | "mal";

export interface EstadoSesion {
  fase: Fase;
  cola: ActividadOut[];
  idx: number;
  apagadas: Capacidad[];
  saltadas: string[];
  /** Ids originales que ya volvieron una vez: no vuelven dos. */
  reintentadas: string[];
  todoBien: boolean;
  /** Lo que pasó en las pruebas, por ítem y faceta; se queda con lo peor. */
  resumen: Record<string, Partial<Record<Faceta, Marca>>>;
  enviosFallidos: number;
}

export type AccionSesion =
  | { tipo: "cargando" }
  | { tipo: "cargada"; actividades: ActividadOut[] }
  | { tipo: "fallo" }
  | { tipo: "resultado"; evidencias: Evidencia[] }
  | { tipo: "seguir" }
  | { tipo: "apagar"; capacidad: Capacidad }
  | { tipo: "envioFallido" };

/** Si acertó todo, el reproductor sigue solo después de esto. */
export const AUTO_AVANCE_MS = 700;
/** Una actividad de práctica fallada vuelve una vez, después de estas otras. */
export const REINTENTO_TRAS = 3;

export const inicialSesion: EstadoSesion = {
  fase: "cargando",
  cola: [],
  idx: 0,
  apagadas: [],
  saltadas: [],
  reintentadas: [],
  todoBien: false,
  resumen: {},
  enviosFallidos: 0,
};

/** La capacidad sin la que una actividad no se puede hacer. */
export function necesita(a: ActividadOut): Capacidad | null {
  switch (a.dinamica) {
    case "trazo":
      return a.modo === "presentar" ? null : "escribir";
    case "eleccion":
      return a.faceta === "oir" ? "escuchar" : null;
    case "par-minimo":
      return "escuchar";
    case "sombra":
      return "hablar";
    default:
      return null;
  }
}

const GRAVEDAD: Record<Marca, number> = { bien: 0, pista: 1, mal: 2 };

function marcaDe(e: Evidencia): Marca {
  if (!e.acierto) return "mal";
  return e.pistas > 0 ? "pista" : "bien";
}

/** Avanza a `desde` y salta lo que pide una capacidad apagada. */
function avanzar(e: EstadoSesion, desde: number): EstadoSesion {
  let i = desde;
  const saltadas = [...e.saltadas];
  while (i < e.cola.length) {
    const c = necesita(e.cola[i]);
    if (c === null || !e.apagadas.includes(c)) break;
    saltadas.push(e.cola[i].id);
    i++;
  }
  return { ...e, idx: i, saltadas, fase: i >= e.cola.length ? "fin" : "actividad" };
}

export function sesionReducer(e: EstadoSesion, a: AccionSesion): EstadoSesion {
  switch (a.tipo) {
    case "cargando":
      return inicialSesion;
    case "cargada":
      return a.actividades.length === 0
        ? { ...inicialSesion, fase: "vacia" }
        : avanzar({ ...inicialSesion, cola: a.actividades }, 0);
    case "fallo":
      return { ...e, fase: "fallo" };
    case "resultado": {
      if (e.fase !== "actividad") return e;
      if (a.evidencias.length === 0) return avanzar(e, e.idx + 1);
      const act = e.cola[e.idx];
      const original = act.id.replace(/~r$/, "");
      let { cola, reintentadas, resumen } = e;
      if (act.modo === "practicar" && a.evidencias.some((ev) => !ev.acierto) && !reintentadas.includes(original)) {
        const en = Math.min(e.idx + 1 + REINTENTO_TRAS, cola.length);
        cola = [...cola.slice(0, en), { ...act, id: `${original}~r` }, ...cola.slice(en)];
        reintentadas = [...reintentadas, original];
      }
      if (act.modo === "comprobar") {
        resumen = { ...resumen };
        for (const ev of a.evidencias) {
          const previa = resumen[ev.item]?.[ev.faceta];
          const nueva = marcaDe(ev);
          const queda = previa !== undefined && GRAVEDAD[previa] > GRAVEDAD[nueva] ? previa : nueva;
          resumen[ev.item] = { ...resumen[ev.item], [ev.faceta]: queda };
        }
      }
      return {
        ...e,
        cola,
        reintentadas,
        resumen,
        todoBien: a.evidencias.every((ev) => ev.acierto && ev.pistas === 0),
        fase: "resultado",
      };
    }
    case "seguir":
      return e.fase === "resultado" ? avanzar(e, e.idx + 1) : e;
    case "apagar": {
      if (e.apagadas.includes(a.capacidad)) return e;
      const s = { ...e, apagadas: [...e.apagadas, a.capacidad] };
      return s.fase === "actividad" ? avanzar(s, s.idx) : s;
    }
    case "envioFallido":
      return { ...e, enviosFallidos: e.enviosFallidos + 1 };
  }
}

/** Los ítems con alguna faceta fallada en la prueba. */
export function porReforzar(e: EstadoSesion): string[] {
  return Object.entries(e.resumen)
    .filter(([, facetas]) => Object.values(facetas).includes("mal"))
    .map(([item]) => item);
}

/** `ja:kana:か` → `か`; `de:sustantivo:Frau` → `Frau`. */
export function etiquetaItem(item: string): string {
  return item.split(":").slice(2).join(":");
}
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd frontend && npx vitest run src/lib/sesion.test.ts`
Expected: PASS, 17 tests.

- [ ] **Step 5: Typecheck y commit**

```bash
cd frontend && npm run typecheck && cd ..
git add frontend/src/lib/sesion.ts frontend/src/lib/sesion.test.ts
git commit -m "feat(tres-idiomas): el reproductor como máquina de estados

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: La dinámica `eleccion` y la tipografía japonesa

**Files:**
- Create: `frontend/src/dinamicas/tipos.ts`
- Create: `frontend/src/lib/dinamicas/eleccion.ts`
- Test: `frontend/src/lib/dinamicas/eleccion.test.ts`
- Create: `frontend/src/dinamicas/Eleccion.tsx`
- Create: `frontend/src/dinamicas/registro.ts`
- Modify: `frontend/src/styles/tokens.css` (Noto Serif JP en las tres pilas)
- Modify: `frontend/src/styles/global.css` (cargar Noto Serif JP)
- Modify: `frontend/src/styles/sistema.css` (`.k-wrap--centro`, `.k-fill > .k-rbtn`, sección 20 `.k-glifo`)
- Modify: `docs/design/klara-sistema/hoja.html` (fuente y tarjeta «glifo»)
- Modify: `docs/design/klara-sistema/hoja.check.mjs` (estados de «glifo» y la fuente)
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` (`dinamica.oirOtraVez`, `dinamica.eleccion.*`)

**Interfaces:**
- Consumes: `Evidencia`, `Faceta`, `Modo` (tarea 13); `Capacidad` (tarea 14).
- Produces:
  - En `dinamicas/tipos.ts`: `AudioRef{src, texto, idioma}`, `Capacidades{reproducir(audio, {lento?}), puede(c)}`, `PropsDinamica<C>{contenido, modo, capacidades, onResultado}`.
  - `ContenidoEleccion`, con la forma del generador de la tarea 4.
  - `evaluarEleccion(c, elegida, ms) -> Evidencia`, `tonoOpcion(c, opcion, elegida) -> "good" | "bad" | undefined`, `textoCorrecto(c) -> string`.
  - `DINAMICAS: Record<string, ComponentType<PropsDinamica<any>>>`, con `eleccion` por ahora.
  - Piezas del sistema: `.k-glifo`, `.k-wrap--centro`.

- [ ] **Step 1: Escribir los tests de la lógica**

`frontend/src/lib/dinamicas/eleccion.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { evaluarEleccion, textoCorrecto, tonoOpcion, type ContenidoEleccion } from "./eleccion";

const c: ContenidoEleccion = {
  item: "ja:kana:か",
  faceta: "reconocer",
  pregunta: { texto: "か", lang: "ja", audio: null },
  opciones: [
    { item: "ja:kana:か", texto: "ka", lang: null },
    { item: "ja:kana:や", texto: "ya", lang: null },
    { item: "ja:kana:け", texto: "ke", lang: null },
  ],
  correcta: "ja:kana:か",
};

describe("evaluarEleccion", () => {
  it("acierta con la correcta y guarda cuál eligió", () => {
    expect(evaluarEleccion(c, "ja:kana:か", 1200)).toEqual({
      item: "ja:kana:か",
      faceta: "reconocer",
      acierto: true,
      pistas: 0,
      ms: 1200,
      detalle: { elegida: "ja:kana:か" },
    });
  });

  it("falla con otra", () => {
    const e = evaluarEleccion(c, "ja:kana:や", 800);
    expect(e.acierto).toBe(false);
    expect(e.detalle).toEqual({ elegida: "ja:kana:や" });
  });
});

describe("tonoOpcion", () => {
  it("sin respuesta, sin tonos", () => {
    expect(tonoOpcion(c, "ja:kana:か", null)).toBeUndefined();
  });

  it("la correcta en bien y la elegida en mal; las demás, nada", () => {
    expect(tonoOpcion(c, "ja:kana:か", "ja:kana:や")).toBe("good");
    expect(tonoOpcion(c, "ja:kana:や", "ja:kana:や")).toBe("bad");
    expect(tonoOpcion(c, "ja:kana:け", "ja:kana:や")).toBeUndefined();
  });
});

describe("textoCorrecto", () => {
  it("es el texto de la opción correcta", () => {
    expect(textoCorrecto(c)).toBe("ka");
  });
});
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd frontend && npx vitest run src/lib/dinamicas/eleccion.test.ts`
Expected: falla con `Failed to resolve import "./eleccion"`.

- [ ] **Step 3: Implementar la lógica y el contrato**

`frontend/src/lib/dinamicas/eleccion.ts`:

```ts
import type { Evidencia, Faceta } from "../../api/types";

/** El contenido que arma el backend para `eleccion` (catalogo/generar.py). */
export interface OpcionEleccion {
  item: string;
  texto: string;
  lang: string | null;
}

export interface ContenidoEleccion {
  item: string;
  faceta: Faceta;
  pregunta: { texto: string | null; lang: string | null; audio: string | null };
  opciones: OpcionEleccion[];
  correcta: string;
}

export type Tono = "good" | "bad";

export function evaluarEleccion(c: ContenidoEleccion, elegida: string, ms: number): Evidencia {
  return { item: c.item, faceta: c.faceta, acierto: elegida === c.correcta, pistas: 0, ms, detalle: { elegida } };
}

/** Ya respondida: la correcta en bien y la elegida, si falló, en mal. */
export function tonoOpcion(c: ContenidoEleccion, opcion: string, elegida: string | null): Tono | undefined {
  if (elegida === null) return undefined;
  if (opcion === c.correcta) return "good";
  return opcion === elegida ? "bad" : undefined;
}

/** El texto de la respuesta correcta: lo que dice Web Speech si el audio falla. */
export function textoCorrecto(c: ContenidoEleccion): string {
  return c.opciones.find((o) => o.item === c.correcta)?.texto ?? "";
}
```

`frontend/src/dinamicas/tipos.ts`:

```ts
import type { Evidencia, Modo } from "../api/types";
import type { Capacidad } from "../lib/sesion";

/** Un audio que la dinámica quiere hacer sonar (spec 2026-10-09 §3.1). */
export interface AudioRef {
  /** Ruta bajo la API (`/audio/ja/a.mp3`), o null para TTS en vivo. */
  src: string | null;
  /** Lo que se dice: el TTS lo sintetiza y Web Speech lo lee si el archivo falla. */
  texto: string;
  idioma: string;
}

/** Lo que el reproductor le presta a una dinámica: la voz y qué está apagado. */
export interface Capacidades {
  reproducir: (audio: AudioRef, opts?: { lento?: boolean }) => void;
  puede: (c: Capacidad) => boolean;
}

/** Una dinámica no sabe nada de lecciones, de Hoy ni de la API: recibe contenido
 *  y devuelve evidencias. */
export interface PropsDinamica<C> {
  contenido: C;
  modo: Modo;
  capacidades: Capacidades;
  /** Solo en practicar y comprobar, una vez por actividad. Presentar avanza con
   *  el botón del reproductor. */
  onResultado: (evidencias: Evidencia[]) => void;
}
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd frontend && npx vitest run src/lib/dinamicas/eleccion.test.ts`
Expected: PASS, 5 tests.

- [ ] **Step 5: El componente y el registro**

`frontend/src/dinamicas/Eleccion.tsx`:

```tsx
/**
 * `eleccion` (spec 2026-10-09 §3.2): ves un kana y eliges su sonido, u oyes un
 * sonido y eliges el kana. La pregunta va en `.k-glifo` o detrás de un
 * `.k-rbtn`; las opciones son chips que, ya respondidos, se tiñen.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  evaluarEleccion,
  textoCorrecto,
  tonoOpcion,
  type ContenidoEleccion,
} from "../lib/dinamicas/eleccion";
import type { PropsDinamica } from "./tipos";

function IcOir() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4Z" />
      <path d="M15.5 9.5a3.5 3.5 0 0 1 0 5" />
      <path d="M18 7a7 7 0 0 1 0 10" />
    </svg>
  );
}

export default function Eleccion({ contenido, capacidades, onResultado }: PropsDinamica<ContenidoEleccion>) {
  const { t } = useTranslation();
  const [elegida, setElegida] = useState<string | null>(null);
  const inicio = useRef(performance.now());
  const { pregunta } = contenido;

  const oir = useCallback(() => {
    if (!pregunta.audio) return;
    capacidades.reproducir({ src: pregunta.audio, texto: textoCorrecto(contenido), idioma: pregunta.lang ?? "ja" });
  }, [capacidades, contenido, pregunta]);

  // La pregunta de oír suena sola al aparecer, una vez.
  useEffect(() => {
    oir();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const elegir = useCallback(
    (item: string) => {
      if (elegida !== null) return;
      setElegida(item);
      onResultado([evaluarEleccion(contenido, item, Math.round(performance.now() - inicio.current))]);
    },
    [contenido, elegida, onResultado],
  );

  // En escritorio, 1–4 eligen.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const n = Number(e.key);
      if (Number.isInteger(n) && n >= 1 && n <= contenido.opciones.length) elegir(contenido.opciones[n - 1].item);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [contenido, elegir]);

  return (
    <>
      {pregunta.texto !== null ? (
        <p className="k-glifo" lang={pregunta.lang ?? undefined}>
          {pregunta.texto}
        </p>
      ) : (
        <button type="button" className="k-rbtn k-rbtn--lg k-rbtn--ink" onClick={oir} aria-label={t("dinamica.oirOtraVez")}>
          <IcOir />
        </button>
      )}
      <p className="k-cap k-cap--center">
        {pregunta.texto !== null ? t("dinamica.eleccion.comoSuena") : t("dinamica.eleccion.cualOyes")}
      </p>
      <div className="k-wrap k-wrap--centro">
        {contenido.opciones.map((o) => {
          const tono = tonoOpcion(contenido, o.item, elegida);
          return (
            <button
              key={o.item}
              type="button"
              className="k-chip"
              data-tone={tono}
              disabled={elegida !== null && tono === undefined}
              lang={o.lang ?? undefined}
              onClick={() => elegir(o.item)}
            >
              {tono && <span className="k-chip__dot" aria-hidden="true" />}
              {o.texto}
            </button>
          );
        })}
      </div>
    </>
  );
}
```

`frontend/src/dinamicas/registro.ts`:

```ts
import type { ComponentType } from "react";
import Eleccion from "./Eleccion";
import type { PropsDinamica } from "./tipos";

/** Nombre de la dinámica (el mismo del backend) → componente. Cada dinámica trae
 *  su propio tipo de contenido; el reproductor las trata igual. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const DINAMICAS: Record<string, ComponentType<PropsDinamica<any>>> = {
  eleccion: Eleccion,
};
```

- [ ] **Step 6: La fuente japonesa y las piezas del sistema**

En `frontend/src/styles/tokens.css`, cambia las tres familias por estas:

```css
  --font-serif: "Source Serif 4", "GT Sectra", "Newsreader", "Noto Serif JP", Georgia, serif;
  --font-sans: "Inter Tight", "Söhne", -apple-system, BlinkMacSystemFont, "Helvetica Neue", "Noto Serif JP", sans-serif;
  --font-mono: "JetBrains Mono", "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, "Noto Serif JP", monospace;
```

En `frontend/src/styles/global.css`, en la línea del `@import url("https://fonts.googleapis.com/css2?…")`, inserta `&family=Noto+Serif+JP:wght@400;600` justo antes de `&display=swap`.

En `frontend/src/styles/sistema.css`:

1. Justo después del bloque `.k-wrap { … }` (el que define `display: flex; flex-wrap: wrap; gap: var(--space-2);`), agrega:

```css
/* La nube centrada: las opciones de una pregunta (dinámicas, spec 2026-10-09). */
.k-wrap--centro { justify-content: center; }
```

2. Justo después de `.k-fill > .k-spinner { align-self: center; }`, agrega:

```css
/* El botón redondo de oír, suelto en la sesión: centrado como el spinner. */
.k-fill > .k-rbtn { align-self: center; }
```

3. Justo antes de `/* ---------- 99-compresion ---------- */`, agrega:

```css
/* ---------- 20-glifo ---------- */
/* ============================================================
   20 · GLIFO — .k-glifo
   Pieza nueva (spec 2026-10-09, dinámicas): un carácter solo, a tamaño
   de cartel, para la pregunta de `eleccion`. El japonés sale de la pila
   de --font-serif (Noto Serif JP va antes de los genéricos).
   ============================================================ */
.k-glifo {
  flex: 0 0 auto;
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--t-display);
  line-height: 1;
  text-align: center;
  color: var(--ink);
}
```

En `docs/design/klara-sistema/hoja.html`:
- en el `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?…">`, inserta `&family=Noto+Serif+JP:wght@400;600` antes de `&display=swap`;
- justo antes de la línea `  <!-- /ÁTOMOS -->`, agrega:

```html
<section class="hoja-card" id="glifo" data-atom="glifo">
  <div class="hoja-card__cabeza"><span class="hoja-card__n">20</span><h2 class="hoja-card__titulo">Glifo <code>.k-glifo</code></h2></div>
  <p class="hoja-card__reemplaza"><b>nuevo</b> — la pregunta de <code>eleccion</code> (spec 2026-10-09)</p>
  <div class="hoja-card__estados">
    <figure class="hoja-estado" data-estado="latino">
      <figcaption>Latino</figcaption>
      <div class="hoja-estado__muestra"><p class="k-glifo">ß</p></div>
    </figure>
    <figure class="hoja-estado" data-estado="japones">
      <figcaption>Japonés, con <code>lang="ja"</code></figcaption>
      <div class="hoja-estado__muestra"><p class="k-glifo" lang="ja">か</p></div>
    </figure>
  </div>
</section>

```

En `docs/design/klara-sistema/hoja.check.mjs`:
- en `ESTADOS`, después de la línea de `"estanteria"`, agrega `  "glifo": ["latino", "japones"],`;
- en la lista de `esperarFuentes`, agrega `'400 17px "Noto Serif JP"'`.

- [ ] **Step 7: Las cadenas**

```bash
cd frontend && PYTHONUTF8=1 python - <<'EOF'
import json, pathlib

NUEVAS = {
    "es": {"dinamica": {"oirOtraVez": "Oír otra vez", "eleccion": {"comoSuena": "¿Cómo suena?", "cualOyes": "¿Cuál oíste?"}}},
    "en": {"dinamica": {"oirOtraVez": "Play again", "eleccion": {"comoSuena": "How does it sound?", "cualOyes": "Which one did you hear?"}}},
    "de": {"dinamica": {"oirOtraVez": "Nochmal hören", "eleccion": {"comoSuena": "Wie klingt es?", "cualOyes": "Welches hast du gehört?"}}},
    "fr": {"dinamica": {"oirOtraVez": "Réécouter", "eleccion": {"comoSuena": "Comment ça se prononce ?", "cualOyes": "Lequel as-tu entendu ?"}}},
    "ja": {"dinamica": {"oirOtraVez": "もう一度聞く", "eleccion": {"comoSuena": "どう読む？", "cualOyes": "どれが聞こえた？"}}},
    "pt": {"dinamica": {"oirOtraVez": "Ouvir de novo", "eleccion": {"comoSuena": "Como soa?", "cualOyes": "Qual você ouviu?"}}},
}

def mezclar(a, b):
    for k, v in b.items():
        if isinstance(v, dict):
            mezclar(a.setdefault(k, {}), v)
        else:
            a[k] = v

for code, nuevas in NUEVAS.items():
    p = pathlib.Path("src/locales") / code / "common.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    mezclar(d, nuevas)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("ok")
EOF
```

- [ ] **Step 8: Gates de esta tarea**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npx vitest run && cd .. && node docs/design/klara-sistema/hoja.check.mjs`
Expected:
- typecheck sin errores;
- «All 6 locales aligned.»;
- vitest en verde;
- la hoja con `✓` en todo, incluido «los N átomos con todos los estados de §5» (N sube en 1).

Abre una de las capturas que deja `.hoja-out/` y comprueba que la か del glifo se ve en Noto Serif JP, y no en una fuente del sistema.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/dinamicas frontend/src/lib/dinamicas frontend/src/styles frontend/src/locales docs/design/klara-sistema/hoja.html docs/design/klara-sistema/hoja.check.mjs
git commit -m "feat(tres-idiomas): la dinámica eleccion, el glifo y la fuente japonesa

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: La ruta del reproductor

**Files:**
- Create: `frontend/src/routes/Sesion.tsx`
- Modify: `frontend/src/App.tsx` (rutas `/sesion/:idioma` y `/leccion/:idioma/:unidad/:leccion`)
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` (`sesion.*`)

**Interfaces:**
- Consumes:
  - de la tarea 14: `sesionReducer`, `inicialSesion`, `AUTO_AVANCE_MS`, `necesita`, `porReforzar`, `etiquetaItem`, `Marca`;
  - `DINAMICAS` y `Capacidades` (tarea 15);
  - `api.sesion`, `api.leccion`, `api.abrirRun`, `api.cerrarRun`, `api.evidencias` (tarea 13);
  - `speak`, `stop`, `unlockAudio` (`lib/tts`);
  - `apiBase` (`lib/apiBase`);
  - `SessTop` (`components/SessTop`).
- Produces: la ruta a la que llevan Hoy (tarea 19) y, en el plan 4, el mapa. Navega con `state: { from }`, como `/repaso`.

- [ ] **Step 1: Escribir la ruta**

`frontend/src/routes/Sesion.tsx`:

```tsx
/**
 * El reproductor de lecciones (spec 2026-10-09 §5.4): la línea de un idioma
 * (repasos y la lección que sigue) o una lección repetida desde el mapa.
 *
 * Superficie suelta, como /repaso: pinta su propio `.k-app`. Aquí viven los
 * efectos (pedir la sesión, abrir y cerrar la corrida, mandar evidencias,
 * avanzar solo); las transiciones están en el reducer puro de `lib/sesion.ts`.
 */
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Evidencia, Faceta, SesionOut } from "../api/types";
import SessTop from "../components/SessTop";
import { DINAMICAS } from "../dinamicas/registro";
import type { Capacidades } from "../dinamicas/tipos";
import { apiBase } from "../lib/apiBase";
import { languageLabel } from "../lib/languages";
import {
  AUTO_AVANCE_MS,
  etiquetaItem,
  inicialSesion,
  necesita,
  porReforzar,
  sesionReducer,
  type Marca,
} from "../lib/sesion";
import { speak, stop, unlockAudio } from "../lib/tts";

const pad2 = (n: number) => String(n).padStart(2, "0");

export default function Sesion(): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { idioma = "", unidad, leccion } = useParams();
  const [params] = useSearchParams();
  const repetir = Boolean(unidad && leccion);
  const conRepasos = params.get("repasos") !== "0";
  const salirA = (location.state as { from?: string } | null)?.from ?? "/";
  const salir = useCallback(() => {
    stop();
    navigate(salirA);
  }, [navigate, salirA]);

  const [estado, dispatch] = useReducer(sesionReducer, inicialSesion);
  const [sesion, setSesion] = useState<SesionOut | null>(null);
  const [manana, setManana] = useState<number | null>(null);
  const [intento, setIntento] = useState(0);
  const runId = useRef<string | null>(null);
  // La guarda del doble toque: una sola respuesta por actividad (Review Focus 1).
  const respondida = useRef<string | null>(null);

  // Pedir la sesión y abrir su corrida. Se repite con «Reintentar» y con «Otra lección».
  useEffect(() => {
    let vivo = true;
    dispatch({ tipo: "cargando" });
    setManana(null);
    respondida.current = null;
    (async () => {
      try {
        const s =
          repetir && unidad && leccion
            ? await api.leccion(idioma, unidad, leccion)
            : await api.sesion(idioma, conRepasos);
        let id: string | null = null;
        if (s.actividades.length > 0) {
          const run = await api.abrirRun({
            idioma,
            leccion_id: s.leccion?.id ?? null,
            origen: repetir ? "mapa" : "hoy",
            repasos: s.actividades.filter((a) => a.repaso).length,
          });
          id = run.id;
        }
        if (!vivo) return;
        runId.current = id;
        setSesion(s);
        dispatch({ tipo: "cargada", actividades: s.actividades });
      } catch {
        if (vivo) dispatch({ tipo: "fallo" });
      }
    })();
    return () => {
      vivo = false;
    };
  }, [idioma, unidad, leccion, repetir, conRepasos, intento]);

  // Al terminar se cierra la corrida y se pregunta qué toca mañana.
  useEffect(() => {
    if (estado.fase !== "fin" || runId.current === null) return;
    const id = runId.current;
    runId.current = null;
    api.cerrarRun(id).then(
      (r) => setManana(r.manana),
      () => setManana(null),
    );
  }, [estado.fase]);

  // Si acertó todo, sigue solo.
  useEffect(() => {
    if (estado.fase !== "resultado" || !estado.todoBien) return;
    const id = window.setTimeout(() => dispatch({ tipo: "seguir" }), AUTO_AVANCE_MS);
    return () => window.clearTimeout(id);
  }, [estado.fase, estado.todoBien, estado.idx]);

  // Al salir de la pantalla, que no siga sonando nada.
  useEffect(() => () => stop(), []);

  const actividad =
    estado.fase === "actividad" || estado.fase === "resultado" ? estado.cola[estado.idx] : undefined;

  const onResultado = useCallback(
    (evidencias: Evidencia[]) => {
      if (!actividad || respondida.current === actividad.id) return;
      respondida.current = actividad.id;
      dispatch({ tipo: "resultado", evidencias });
      const run = runId.current;
      if (run === null || evidencias.length === 0) return;
      const lote = evidencias.map((e) => ({
        ...e,
        id: crypto.randomUUID(),
        run_id: run,
        dinamica: actividad.dinamica,
        modo: actividad.modo,
      }));
      // Mismo lote, mismos ids: el reintento no cuenta doble (idempotente en el servidor).
      api
        .evidencias(lote)
        .catch(() => api.evidencias(lote))
        .catch(() => dispatch({ tipo: "envioFallido" }));
    },
    [actividad],
  );

  const presentarListo = useCallback(() => {
    unlockAudio();
    if (actividad) respondida.current = actividad.id;
    dispatch({ tipo: "resultado", evidencias: [] });
  }, [actividad]);

  const capacidades = useMemo<Capacidades>(
    () => ({
      reproducir: (audio, opts) => {
        if (estado.apagadas.includes("escuchar")) return;
        speak(audio.texto, audio.idioma, {
          src: audio.src ? `${apiBase()}${audio.src}` : undefined,
          rate: opts?.lento ? 0.75 : 1,
        });
      },
      puede: (c) => !estado.apagadas.includes(c),
    }),
    [estado.apagadas],
  );

  // En escritorio: Enter o Espacio siguen.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Enter" && e.code !== "Space") return;
      if (estado.fase === "resultado") {
        e.preventDefault();
        dispatch({ tipo: "seguir" });
      } else if (estado.fase === "actividad" && actividad?.modo === "presentar") {
        e.preventDefault();
        presentarListo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [estado.fase, actividad, presentarListo]);

  const otraLeccion = () => {
    navigate(`/sesion/${idioma}?repasos=0`, { replace: true, state: { from: salirA } });
    setIntento((n) => n + 1);
  };

  const nombre = languageLabel(idioma);

  if (estado.fase === "cargando") {
    return (
      <div className="k-app">
        <SessTop titulo={nombre} right="" onExit={salir} />
        <div className="k-fill">
          <span className="k-spinner" role="status" aria-label={t("sesion.cargando")} />
        </div>
      </div>
    );
  }

  if (estado.fase === "fallo" || estado.fase === "vacia") {
    const fallo = estado.fase === "fallo";
    return (
      <div className="k-app">
        <SessTop titulo={nombre} right="" onExit={salir} />
        <div className="k-fill">
          {fallo ? (
            <p className="k-error" role="alert">{t("sesion.fallo")}</p>
          ) : (
            <p className="k-note">{t("sesion.vacia")}</p>
          )}
        </div>
        <div className="k-dock">
          <div className="k-wrap">
            {fallo && (
              <button type="button" className="k-btn k-btn--ghost k-btn--block" onClick={() => setIntento((n) => n + 1)}>
                {t("sesion.reintentar")}
              </button>
            )}
            <button type="button" className="k-btn k-btn--block" onClick={salir}>
              {t("sesion.aHoy")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (estado.fase === "fin") {
    const reforzar = porReforzar(estado);
    const filas = Object.entries(estado.resumen);
    const hechas = estado.cola.length - estado.saltadas.length;
    return (
      <div className="k-app">
        <SessTop titulo={nombre} right="" onExit={salir} />
        <div className="k-fill">
          <div className="k-live">
            <header className="k-hero k-hero--quiet">
              <span className="k-hero__tag">
                <span lang={idioma}>{nombre}</span>
                <span>{t("sesion.fin.hecho")}</span>
              </span>
              <h1 className="k-hero__title" lang={sesion?.leccion ? idioma : undefined}>
                {sesion?.leccion?.titulo ?? t("sesion.repaso")}
              </h1>
              <p className="k-hero__dek">{t("sesion.fin.resumen", { count: hechas })}</p>
            </header>
            {filas.length > 0 && (
              <ul>
                {filas.map(([item, facetas]) => (
                  <li key={item}>
                    <div className="k-row k-row--quiet">
                      <span className="k-row__title" lang={idioma}>{etiquetaItem(item)}</span>
                      <span className="k-row__meta">
                        {(Object.entries(facetas) as [Faceta, Marca][])
                          .map(([f, m]) => `${t(`sesion.faceta.${f}`)} ${t(`sesion.marca.${m}`)}`)
                          .join(" · ")}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {reforzar.length > 0 && (
              <p className="k-note">{t("sesion.fin.reforzar", { items: reforzar.map(etiquetaItem).join(", ") })}</p>
            )}
            {manana !== null && <p className="k-note">{t("sesion.fin.manana", { count: manana })}</p>}
            {estado.enviosFallidos > 0 && (
              <p className="k-error" role="alert">{t("sesion.fin.noGuardadas", { count: estado.enviosFallidos })}</p>
            )}
          </div>
        </div>
        <div className="k-dock">
          <div className="k-wrap">
            {!repetir && sesion?.leccion && (
              <button type="button" className="k-btn k-btn--ghost k-btn--block" onClick={otraLeccion}>
                {t("sesion.fin.otra")}
              </button>
            )}
            <button type="button" className="k-btn k-btn--block" onClick={salir}>
              {t("sesion.aHoy")} <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!actividad) return <div className="k-app" />;

  const Dinamica = DINAMICAS[actividad.dinamica];
  const cap = necesita(actividad);
  const total = estado.cola.length;
  const titulo = `${nombre} · ${sesion?.leccion?.titulo ?? t("sesion.repaso")}`;
  const modo = actividad.repaso ? t("sesion.modo.repaso") : t(`sesion.modo.${actividad.modo}`);

  return (
    <div className="k-app">
      <SessTop titulo={titulo} right={`${pad2(estado.idx + 1)}/${pad2(total)}`} onExit={salir} />
      <div className="k-bar k-bar--segs">
        <div className="k-bar__track" role="progressbar" aria-valuenow={estado.idx + 1} aria-valuemin={0} aria-valuemax={total}>
          {estado.cola.map((a, i) => (
            <span
              key={a.id}
              className="k-bar__seg"
              data-state={
                i < estado.idx ? (estado.saltadas.includes(a.id) ? "skipped" : "done") : i === estado.idx ? "now" : undefined
              }
            />
          ))}
        </div>
      </div>

      <div className="k-fill">
        <p className="k-cap k-cap--center">{modo}</p>
        {Dinamica ? (
          <Dinamica
            key={actividad.id}
            contenido={actividad.contenido}
            modo={actividad.modo}
            capacidades={capacidades}
            onResultado={onResultado}
          />
        ) : (
          <p className="k-error" role="alert">{t("sesion.desconocida")}</p>
        )}
      </div>

      <div className="k-dock">
        <div className="k-dock__status">
          <p className="k-cap k-cap--center">
            {estado.fase === "resultado" ? (estado.todoBien ? t("sesion.bien") : t("sesion.mira")) : ""}
          </p>
        </div>
        <div className="k-wrap">
          {actividad.modo === "presentar" ? (
            <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={presentarListo}>
              {t("sesion.ahoraTu")} <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          ) : estado.fase === "resultado" && !estado.todoBien ? (
            <button type="button" className="k-btn k-btn--lg k-btn--block" onClick={() => dispatch({ tipo: "seguir" })}>
              {t("sesion.seguir")} <span className="k-btn__arrow" aria-hidden="true">→</span>
            </button>
          ) : cap !== null && estado.fase === "actividad" ? (
            <button
              type="button"
              className="k-btn k-btn--text"
              onClick={() => {
                stop();
                dispatch({ tipo: "apagar", capacidad: cap });
              }}
            >
              {t(`sesion.noPuedo.${cap}`)}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Registrar las rutas**

En `frontend/src/App.tsx`, junto a los demás imports de rutas (p. ej. el de `Repaso`), agrega `import Sesion from "./routes/Sesion";`. Después del bloque `<Route path="/repaso" …>…</Route>`, agrega:

```tsx
      {/* El reproductor (spec 2026-10-09 §5.4): suelto, como /repaso. La línea de
          Hoy y la lección repetida desde el mapa usan el mismo componente. */}
      <Route
        path="/sesion/:idioma"
        element={
          <ProtectedRoute>
            <Sesion />
          </ProtectedRoute>
        }
      />
      <Route
        path="/leccion/:idioma/:unidad/:leccion"
        element={
          <ProtectedRoute>
            <Sesion />
          </ProtectedRoute>
        }
      />
```

- [ ] **Step 3: Las cadenas**

```bash
cd frontend && PYTHONUTF8=1 python - <<'EOF'
import json, pathlib

def sesion(cargando, fallo, reintentar, vacia, aHoy, repaso, desconocida, modo, ahoraTu, seguir, bien, mira, noPuedo, faceta, marca, fin):
    return {"sesion": {
        "cargando": cargando, "fallo": fallo, "reintentar": reintentar, "vacia": vacia, "aHoy": aHoy,
        "repaso": repaso, "desconocida": desconocida,
        "modo": dict(zip(("presentar", "practicar", "comprobar", "repaso"), modo)),
        "ahoraTu": ahoraTu, "seguir": seguir, "bien": bien, "mira": mira,
        "noPuedo": dict(zip(("escuchar", "hablar", "escribir"), noPuedo)),
        "faceta": dict(zip(("reconocer", "oir", "escribir", "genero", "aplicar", "pronunciar"), faceta)),
        "marca": dict(zip(("bien", "pista", "mal"), marca)),
        "fin": dict(zip(("hecho", "resumen_one", "resumen_other", "reforzar", "manana_one", "manana_other",
                         "noGuardadas_one", "noGuardadas_other", "otra"), fin)),
    }}

NUEVAS = {
    "es": sesion("Preparando la sesión…", "No se pudo preparar la sesión.", "Reintentar",
                 "Hoy no hay repasos ni lecciones nuevas en este idioma.", "A Hoy", "Repaso",
                 "Esta actividad todavía no se puede mostrar.",
                 ("Nuevo", "Práctica", "Prueba", "Repaso"), "Ahora tú", "Seguir", "Bien", "Mira la corrección",
                 ("Ahora no puedo escuchar", "Ahora no puedo hablar", "Ahora no puedo escribir"),
                 ("reconocer", "oír", "escribir", "género", "aplicar", "pronunciar"), ("✓", "con pista", "✗"),
                 ("Hecho", "{{count}} actividad", "{{count}} actividades", "Por reforzar: {{items}}.",
                  "Mañana te toca {{count}} repaso.", "Mañana te tocan {{count}} repasos.",
                  "{{count}} respuesta no se guardó.", "{{count}} respuestas no se guardaron.", "Otra lección")),
    "en": sesion("Getting the session ready…", "Couldn't prepare the session.", "Try again",
                 "No reviews or new lessons in this language today.", "Back to Today", "Review",
                 "This activity can't be shown yet.",
                 ("New", "Practice", "Test", "Review"), "Your turn", "Continue", "Good", "Check the correction",
                 ("I can't listen right now", "I can't speak right now", "I can't write right now"),
                 ("recognize", "hear", "write", "gender", "apply", "pronounce"), ("✓", "with a hint", "✗"),
                 ("Done", "{{count}} activity", "{{count}} activities", "Needs work: {{items}}.",
                  "Tomorrow: {{count}} review.", "Tomorrow: {{count}} reviews.",
                  "{{count}} answer wasn't saved.", "{{count}} answers weren't saved.", "Another lesson")),
    "de": sesion("Sitzung wird vorbereitet…", "Die Sitzung konnte nicht vorbereitet werden.", "Erneut versuchen",
                 "Heute keine Wiederholungen und keine neuen Lektionen in dieser Sprache.", "Zu Heute", "Wiederholung",
                 "Diese Übung kann noch nicht angezeigt werden.",
                 ("Neu", "Übung", "Test", "Wiederholung"), "Jetzt du", "Weiter", "Gut", "Sieh dir die Korrektur an",
                 ("Ich kann gerade nicht hören", "Ich kann gerade nicht sprechen", "Ich kann gerade nicht schreiben"),
                 ("erkennen", "hören", "schreiben", "Genus", "anwenden", "aussprechen"), ("✓", "mit Hinweis", "✗"),
                 ("Fertig", "{{count}} Übung", "{{count}} Übungen", "Noch üben: {{items}}.",
                  "Morgen: {{count}} Wiederholung.", "Morgen: {{count}} Wiederholungen.",
                  "{{count}} Antwort wurde nicht gespeichert.", "{{count}} Antworten wurden nicht gespeichert.",
                  "Noch eine Lektion")),
    "fr": sesion("Préparation de la séance…", "Impossible de préparer la séance.", "Réessayer",
                 "Aucune révision ni nouvelle leçon dans cette langue aujourd’hui.", "Retour à Aujourd’hui", "Révision",
                 "Cette activité ne peut pas encore s’afficher.",
                 ("Nouveau", "Entraînement", "Test", "Révision"), "À toi", "Continuer", "Bien", "Regarde la correction",
                 ("Je ne peux pas écouter maintenant", "Je ne peux pas parler maintenant", "Je ne peux pas écrire maintenant"),
                 ("reconnaître", "entendre", "écrire", "genre", "appliquer", "prononcer"), ("✓", "avec un indice", "✗"),
                 ("Terminé", "{{count}} activité", "{{count}} activités", "À renforcer : {{items}}.",
                  "Demain : {{count}} révision.", "Demain : {{count}} révisions.",
                  "{{count}} réponse n’a pas été enregistrée.", "{{count}} réponses n’ont pas été enregistrées.",
                  "Une autre leçon")),
    "ja": sesion("セッションを準備中…", "セッションを準備できませんでした。", "再試行",
                 "今日はこの言語の復習も新しいレッスンもありません。", "今日へ", "復習",
                 "このアクティビティはまだ表示できません。",
                 ("新規", "練習", "テスト", "復習"), "やってみよう", "次へ", "正解", "訂正を見てください",
                 ("今は聞けない", "今は話せない", "今は書けない"),
                 ("認識", "聞き取り", "書き", "性", "適用", "発音"), ("✓", "ヒントあり", "✗"),
                 ("完了", "{{count}}件のアクティビティ", "{{count}}件のアクティビティ", "要復習：{{items}}。",
                  "明日の復習：{{count}}件。", "明日の復習：{{count}}件。",
                  "{{count}}件の回答が保存されませんでした。", "{{count}}件の回答が保存されませんでした。",
                  "もう1レッスン")),
    "pt": sesion("Preparando a sessão…", "Não foi possível preparar a sessão.", "Tentar de novo",
                 "Hoje não há revisões nem lições novas neste idioma.", "Para Hoje", "Revisão",
                 "Esta atividade ainda não pode ser exibida.",
                 ("Novo", "Prática", "Teste", "Revisão"), "Sua vez", "Continuar", "Certo", "Veja a correção",
                 ("Agora não posso ouvir", "Agora não posso falar", "Agora não posso escrever"),
                 ("reconhecer", "ouvir", "escrever", "gênero", "aplicar", "pronunciar"), ("✓", "com dica", "✗"),
                 ("Feito", "{{count}} atividade", "{{count}} atividades", "Para reforçar: {{items}}.",
                  "Amanhã: {{count}} revisão.", "Amanhã: {{count}} revisões.",
                  "{{count}} resposta não foi salva.", "{{count}} respostas não foram salvas.", "Outra lição")),
}

def mezclar(a, b):
    for k, v in b.items():
        if isinstance(v, dict):
            mezclar(a.setdefault(k, {}), v)
        else:
            a[k] = v

for code, nuevas in NUEVAS.items():
    p = pathlib.Path("src/locales") / code / "common.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    mezclar(d, nuevas)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("ok")
EOF
```

- [ ] **Step 4: Gates de esta tarea**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npx vitest run && npm run build`
Expected: todo en verde. El build tiene que compilar `Sesion.tsx`. Si `typecheck` se queja de `t(\`sesion.modo.${actividad.modo}\`)`, revisa que `sesion.modo` tenga las cuatro claves en `es`, porque las claves de `t()` salen tipadas de `es/common.json`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/Sesion.tsx frontend/src/App.tsx frontend/src/locales
git commit -m "feat(tres-idiomas): la ruta del reproductor de lecciones

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: La dinámica `trazo`

**Files:**
- Create: `frontend/src/lib/dinamicas/trazo.ts`
- Test: `frontend/src/lib/dinamicas/trazo.test.ts`
- Create: `frontend/src/dinamicas/Trazo.tsx`
- Modify: `frontend/src/dinamicas/registro.ts` (agregar `trazo`)
- Modify: `frontend/src/styles/sistema.css` (sección 21 `.k-trazo`)
- Modify: `docs/design/klara-sistema/hoja.html` (tarjeta «lienzo-trazo») y `hoja.check.mjs` (sus estados)
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` (`dinamica.trazo.*`)

**Interfaces:**
- Consumes: `Evidencia`, `Modo` (tarea 13); `PropsDinamica` (tarea 15); el contenido de `trazo` de la tarea 4.
- Produces:
  - Tipos: `Punto`, `Esperado{pts, largo}`, `Juicio{toque, ok, media, largo}`, `EstadoTrazo`.
  - Constantes: `N = 24`, `UMBRAL_MEDIA = 12`, `LARGO_MIN = 0.55`, `LARGO_MAX = 1.7`, `TOQUE_MIN = 4`.
  - Funciones:
    - `largo(pts)`
    - `remuestrear(pts, n?) -> Punto[] | null`
    - `evaluarTrazo(puntos, esperado) -> Juicio`
    - `inicialTrazo`
    - `fallosParaPista(modo) -> number`
    - `alSoltar(estado, juicio, modo, total) -> EstadoTrazo`
    - `evidenciaTrazo(item, estado, ms) -> Evidencia`

- [ ] **Step 1: Escribir los tests**

`frontend/src/lib/dinamicas/trazo.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  alSoltar,
  evaluarTrazo,
  evidenciaTrazo,
  inicialTrazo,
  largo,
  N,
  remuestrear,
  TOQUE_MIN,
  type Esperado,
  type Juicio,
  type Punto,
} from "./trazo";

const linea = (x0: number, y0: number, x1: number, y1: number, n = N): Punto[] =>
  Array.from({ length: n }, (_, i) => [x0 + ((x1 - x0) * i) / (n - 1), y0 + ((y1 - y0) * i) / (n - 1)]);
const ESPERADO: Esperado = { pts: linea(20, 50, 90, 50), largo: 70 };
const bien: Juicio = { toque: false, ok: true, media: 2, largo: 1 };
const mal: Juicio = { toque: false, ok: false, media: 30, largo: 1 };
const toque: Juicio = { toque: true, ok: false, media: 0, largo: 0 };

describe("remuestrear", () => {
  it("un punto solo o un toque corto no es un trazo", () => {
    expect(remuestrear([[10, 10]])).toBeNull();
    expect(remuestrear([[10, 10], [10 + TOQUE_MIN / 2, 10]])).toBeNull();
  });

  it("devuelve N puntos y conserva los extremos", () => {
    const r = remuestrear(linea(0, 0, 100, 0, 7))!;
    expect(r).toHaveLength(N);
    expect(r[0]).toEqual([0, 0]);
    expect(r[N - 1][0]).toBeCloseTo(100);
  });

  it("reparte por largo de arco, no por cantidad de puntos", () => {
    // Muchos puntos al principio y uno solo al final: el punto del medio cae igual a la mitad.
    const pts: Punto[] = [...linea(0, 0, 10, 0, 50), [100, 0]];
    expect(remuestrear(pts, 3)![1][0]).toBeCloseTo(50);
  });
});

describe("evaluarTrazo", () => {
  it("vale el trazo bueno, aunque tiemble un poco", () => {
    const j = evaluarTrazo(linea(21, 52, 89, 51, 40), ESPERADO);
    expect(j.ok).toBe(true);
    expect(j.media).toBeLessThan(3);
  });

  it("no vale el mismo trazo al revés", () => {
    const j = evaluarTrazo(linea(90, 50, 20, 50, 40), ESPERADO);
    expect(j.ok).toBe(false);
    expect(j.media).toBeGreaterThan(30);
  });

  it("no vale otro trazo", () => {
    expect(evaluarTrazo(linea(55, 15, 55, 85, 40), ESPERADO).ok).toBe(false);
  });

  it("no vale uno demasiado corto", () => {
    expect(evaluarTrazo(linea(20, 50, 45, 50, 20), ESPERADO).ok).toBe(false);
  });

  it("un zigzag encima de la guía queda cerca, pero es demasiado largo", () => {
    const zigzag: Punto[] = Array.from({ length: 40 }, (_, i) => [20 + (70 * i) / 39, i % 2 ? 58 : 42]);
    const j = evaluarTrazo(zigzag, ESPERADO);
    expect(j.media).toBeLessThan(12);
    expect(j.ok).toBe(false);
  });

  it("un toque no se juzga", () => {
    expect(evaluarTrazo([[50, 50]], ESPERADO).toque).toBe(true);
  });
});

describe("alSoltar", () => {
  it("un trazo bueno avanza y queda en el detalle", () => {
    const e = alSoltar(inicialTrazo, bien, "practicar", 3);
    expect([e.actual, e.fallos, e.terminado]).toEqual([1, 0, false]);
    expect(e.detalle).toEqual([{ n: 1, media: 2, largo: 1, fallos: 0 }]);
  });

  it("un toque no cuenta", () => {
    expect(alSoltar(inicialTrazo, toque, "practicar", 3)).toBe(inicialTrazo);
  });

  it("en práctica la pista llega al segundo fallo, una sola vez", () => {
    let e = alSoltar(inicialTrazo, mal, "practicar", 3);
    expect([e.fallos, e.pistas, e.mostrando]).toEqual([1, 0, false]);
    e = alSoltar(e, mal, "practicar", 3);
    expect([e.fallos, e.pistas, e.mostrando]).toEqual([2, 1, true]);
    e = alSoltar(e, mal, "practicar", 3);
    expect(e.pistas).toBe(1);
    e = alSoltar(e, bien, "practicar", 3);
    expect([e.actual, e.mostrando, e.detalle[0].fallos]).toEqual([1, false, 3]);
  });

  it("en prueba la pista llega al primer fallo", () => {
    const e = alSoltar(inicialTrazo, mal, "comprobar", 3);
    expect([e.pistas, e.mostrando]).toEqual([1, true]);
  });

  it("termina con el último trazo y ya no cambia", () => {
    let e = inicialTrazo;
    for (let i = 0; i < 3; i++) e = alSoltar(e, bien, "comprobar", 3);
    expect(e.terminado).toBe(true);
    expect(alSoltar(e, mal, "comprobar", 3)).toBe(e);
  });
});

describe("evidenciaTrazo", () => {
  it("hasta dos pistas sigue siendo acierto; tres ya no", () => {
    const con = (pistas: number) => ({ ...inicialTrazo, pistas, terminado: true });
    expect(evidenciaTrazo("ja:kana:あ", con(2), 9000)).toMatchObject({
      item: "ja:kana:あ",
      faceta: "escribir",
      acierto: true,
      pistas: 2,
      ms: 9000,
    });
    expect(evidenciaTrazo("ja:kana:あ", con(3), 9000).acierto).toBe(false);
  });
});

describe("largo", () => {
  it("suma los segmentos", () => {
    expect(largo(linea(0, 0, 30, 40, 2))).toBe(50);
  });
});
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd frontend && npx vitest run src/lib/dinamicas/trazo.test.ts`
Expected: falla con `Failed to resolve import "./trazo"`.

- [ ] **Step 3: Implementar la lógica**

`frontend/src/lib/dinamicas/trazo.ts`:

```ts
import type { Evidencia, Modo } from "../../api/types";

/**
 * El juicio de un trazo (spec 2026-10-09 §5.5), sin DOM: el componente le pasa
 * los puntos del dedo y el trazo de KanjiVG ya muestreado.
 *
 * Remuestrea los dos a N puntos por largo de arco y mira la distancia media
 * entre pares y la razón de largos. La dirección sale gratis: un trazo al revés
 * dispara la media.
 */
export type Punto = [number, number];

export const N = 24;
// Perillas: se afinan con los `media` y `largo` reales que quedan en el detalle.
export const UMBRAL_MEDIA = 12;
export const LARGO_MIN = 0.55;
export const LARGO_MAX = 1.7;
/** Menos que esto es un toque, no un trazo: se ignora. */
export const TOQUE_MIN = 4;

export interface Esperado {
  pts: Punto[];
  largo: number;
}

export interface Juicio {
  toque: boolean;
  ok: boolean;
  media: number;
  largo: number;
}

export function largo(pts: Punto[]): number {
  let total = 0;
  for (let i = 1; i < pts.length; i++) total += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return total;
}

/** Remuestrea por largo de arco a `n` puntos; null si es un toque. */
export function remuestrear(pts: Punto[], n = N): Punto[] | null {
  if (pts.length < 2) return null;
  const acum = [0];
  for (let i = 1; i < pts.length; i++) {
    acum.push(acum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  }
  const total = acum[acum.length - 1];
  if (total < TOQUE_MIN) return null;
  const out: Punto[] = [];
  let j = 0;
  for (let k = 0; k < n; k++) {
    const objetivo = (total * k) / (n - 1);
    while (j < acum.length - 2 && acum[j + 1] < objetivo) j++;
    const tramo = acum[j + 1] - acum[j] || 1;
    const u = Math.min(1, Math.max(0, (objetivo - acum[j]) / tramo));
    out.push([pts[j][0] + (pts[j + 1][0] - pts[j][0]) * u, pts[j][1] + (pts[j + 1][1] - pts[j][1]) * u]);
  }
  return out;
}

export function evaluarTrazo(puntos: Punto[], esperado: Esperado): Juicio {
  const r = remuestrear(puntos);
  if (!r) return { toque: true, ok: false, media: 0, largo: 0 };
  const media = r.reduce((s, p, i) => s + Math.hypot(p[0] - esperado.pts[i][0], p[1] - esperado.pts[i][1]), 0) / N;
  const razon = largo(puntos) / esperado.largo;
  return { toque: false, ok: media < UMBRAL_MEDIA && razon > LARGO_MIN && razon < LARGO_MAX, media, largo: razon };
}

export interface DetalleTrazo {
  n: number;
  media: number;
  largo: number;
  fallos: number;
}

export interface EstadoTrazo {
  /** El índice del trazo que toca. */
  actual: number;
  /** Fallos en el trazo actual. */
  fallos: number;
  pistas: number;
  /** La pista del trazo actual está a la vista. */
  mostrando: boolean;
  detalle: DetalleTrazo[];
  terminado: boolean;
}

export const inicialTrazo: EstadoTrazo = {
  actual: 0,
  fallos: 0,
  pistas: 0,
  mostrando: false,
  detalle: [],
  terminado: false,
};

/** Fallos en un mismo trazo antes de enseñarlo: dos en práctica, uno en prueba. */
export function fallosParaPista(modo: Modo): number {
  return modo === "comprobar" ? 1 : 2;
}

const redondo = (x: number) => Math.round(x * 100) / 100;

export function alSoltar(e: EstadoTrazo, j: Juicio, modo: Modo, total: number): EstadoTrazo {
  if (e.terminado || j.toque) return e;
  if (j.ok) {
    const actual = e.actual + 1;
    return {
      ...e,
      actual,
      fallos: 0,
      mostrando: false,
      terminado: actual >= total,
      detalle: [...e.detalle, { n: actual, media: redondo(j.media), largo: redondo(j.largo), fallos: e.fallos }],
    };
  }
  const fallos = e.fallos + 1;
  const pista = !e.mostrando && fallos >= fallosParaPista(modo);
  return { ...e, fallos, mostrando: e.mostrando || pista, pistas: e.pistas + (pista ? 1 : 0) };
}

/** Una evidencia por kana: hasta dos pistas sigue siendo acierto (`hard`). */
export function evidenciaTrazo(item: string, e: EstadoTrazo, ms: number): Evidencia {
  return { item, faceta: "escribir", acierto: e.pistas <= 2, pistas: e.pistas, ms, detalle: { trazos: e.detalle } };
}
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd frontend && npx vitest run src/lib/dinamicas/trazo.test.ts`
Expected: PASS, 16 tests.

- [ ] **Step 5: El componente**

`frontend/src/dinamicas/Trazo.tsx`:

```tsx
/**
 * `trazo` (spec 2026-10-09 §5.5): escribir un kana con el dedo, en la caja de
 * 109 de KanjiVG. Cada trazo se juzga al soltar (lib/dinamicas/trazo.ts) y, si
 * vale, se reemplaza por el limpio. Pointer Events: el mismo código sirve para
 * dedo, lápiz y mouse; `.k-trazo` lleva `touch-action: none`.
 */
import { useCallback, useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";
import {
  alSoltar,
  evaluarTrazo,
  evidenciaTrazo,
  inicialTrazo,
  N,
  type Esperado,
  type Punto,
} from "../lib/dinamicas/trazo";
import type { PropsDinamica } from "./tipos";

/** El contenido que arma el backend para `trazo` (catalogo/generar.py). */
export interface ContenidoTrazo {
  item: string;
  kana: string;
  romaji: string;
  audio: string;
  trazos: string[];
  mnemotecnia: string;
}

function muestrear(el: SVGPathElement): Esperado {
  const total = el.getTotalLength();
  const pts: Punto[] = Array.from({ length: N }, (_, i) => {
    const p = el.getPointAtLength((total * i) / (N - 1));
    return [p.x, p.y];
  });
  return { pts, largo: total };
}

const camino = (pts: Punto[]) => "M" + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");

export default function Trazo({ contenido, modo, capacidades, onResultado }: PropsDinamica<ContenidoTrazo>) {
  const { t } = useTranslation();
  const svg = useRef<SVGSVGElement>(null);
  const refs = useRef<(SVGPathElement | null)[]>([]);
  // El trazo en curso vive en refs: un toque rápido (bajar y soltar sin render en
  // medio) no puede dejar el lienzo creyendo que el dedo sigue apoyado.
  const apretado = useRef(false);
  const puntos = useRef<Punto[]>([]);
  const inicio = useRef(performance.now());
  const reportado = useRef(false);
  const [esperados, setEsperados] = useState<Esperado[] | null>(null);
  const [estado, setEstado] = useState(inicialTrazo);
  const [mano, setMano] = useState<Punto[] | null>(null);
  const [mal, setMal] = useState(false);
  const [vuelta, setVuelta] = useState(0);
  const total = contenido.trazos.length;

  // Los trazos de referencia se muestrean del propio SVG: getTotalLength necesita el DOM.
  useEffect(() => {
    setEsperados(refs.current.slice(0, total).map((el) => (el ? muestrear(el) : { pts: [], largo: 1 })));
  }, [contenido, total]);

  const oir = useCallback(
    () => capacidades.reproducir({ src: contenido.audio, texto: contenido.kana, idioma: "ja" }),
    [capacidades, contenido],
  );

  // Al presentar y en la prueba suena al aparecer; en la práctica manda el dibujo.
  useEffect(() => {
    if (modo !== "practicar") oir();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (modo === "presentar" || !estado.terminado || reportado.current) return;
    reportado.current = true;
    onResultado([evidenciaTrazo(contenido.item, estado, Math.round(performance.now() - inicio.current))]);
  }, [estado, modo, contenido.item, onResultado]);

  const punto = (e: PointerEvent<SVGSVGElement>): Punto => {
    const caja = svg.current!;
    const p = caja.createSVGPoint();
    p.x = e.clientX;
    p.y = e.clientY;
    const q = p.matrixTransform(caja.getScreenCTM()!.inverse());
    return [q.x, q.y];
  };

  const dibujando = modo !== "presentar" && !estado.terminado && esperados !== null;

  const bajar = (e: PointerEvent<SVGSVGElement>) => {
    if (!dibujando) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    apretado.current = true;
    puntos.current = [punto(e)];
    setMal(false);
    setMano(puntos.current);
  };

  const mover = (e: PointerEvent<SVGSVGElement>) => {
    if (!apretado.current) return;
    puntos.current = [...puntos.current, punto(e)];
    setMano(puntos.current);
  };

  const soltar = () => {
    if (!apretado.current) return;
    apretado.current = false;
    if (!esperados) return;
    const juicio = evaluarTrazo(puntos.current, esperados[estado.actual]);
    setEstado((s) => alSoltar(s, juicio, modo, total));
    if (juicio.toque || juicio.ok) setMano(null);
    else setMal(true);
  };

  const n = estado.actual + 1;
  let nota: string;
  if (estado.terminado) nota = t("dinamica.trazo.listo");
  else if (mal && estado.mostrando) nota = t("dinamica.trazo.asiVa", { n });
  else if (mal) nota = t("dinamica.trazo.eseNo");
  else if (modo === "practicar" && estado.actual === 0) nota = `${t("dinamica.trazo.trazoN", { n, total })} ${t("dinamica.trazo.empieza")}`;
  else nota = t("dinamica.trazo.trazoN", { n, total });

  const inicioTrazo = esperados?.[estado.actual]?.pts[0];

  return (
    <>
      {modo === "comprobar" && (
        <>
          <p className="k-cap k-cap--center">{t("dinamica.trazo.escribe")}</p>
          <p className="k-trazo__son">{contenido.romaji}</p>
        </>
      )}
      <div className="k-trazo" data-modo={modo}>
        <svg
          ref={svg}
          viewBox="0 0 109 109"
          role="img"
          aria-label={contenido.kana}
          onPointerDown={bajar}
          onPointerMove={mover}
          onPointerUp={soltar}
          onPointerCancel={soltar}
        >
          <g className="k-trazo__guia" aria-hidden="true">
            <line x1="54.5" y1="4" x2="54.5" y2="105" />
            <line x1="4" y1="54.5" x2="105" y2="54.5" />
          </g>
          {/* La referencia siempre está en el DOM (para muestrearla); en práctica es la plantilla gris. */}
          <g className="k-trazo__ref" aria-hidden="true">
            {contenido.trazos.map((p, i) => (
              <path
                key={i}
                d={p}
                ref={(el) => {
                  refs.current[i] = el;
                }}
              />
            ))}
          </g>
          {modo === "presentar" ? (
            <g key={vuelta} className="k-trazo__orden">
              {contenido.trazos.map((p, i) => (
                <path key={i} d={p} pathLength={1} style={{ "--i": i } as CSSProperties} />
              ))}
            </g>
          ) : (
            <>
              <g className="k-trazo__tinta">
                {contenido.trazos.slice(0, estado.actual).map((p, i) => (
                  <path key={i} d={p} />
                ))}
              </g>
              {estado.mostrando && !estado.terminado && (
                <path
                  key={`pista-${estado.actual}`}
                  className="k-trazo__pista"
                  d={contenido.trazos[estado.actual]}
                  pathLength={1}
                />
              )}
              {mano && <path className="k-trazo__mano" data-mal={mal || undefined} d={camino(mano)} />}
              {modo === "practicar" && inicioTrazo && !estado.terminado && (
                <circle className="k-trazo__inicio" cx={inicioTrazo[0]} cy={inicioTrazo[1]} r={2.4} />
              )}
            </>
          )}
        </svg>
      </div>
      {modo === "presentar" ? (
        <>
          <p className="k-trazo__son">{contenido.romaji}</p>
          <p className="k-note">{contenido.mnemotecnia}</p>
          <div className="k-wrap k-wrap--centro">
            <button type="button" className="k-btn k-btn--ghost" onClick={oir}>
              {t("dinamica.oirOtraVez")}
            </button>
            <button type="button" className="k-btn k-btn--text" onClick={() => setVuelta((v) => v + 1)}>
              {t("dinamica.trazo.verOtraVez")}
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="k-note" aria-live="polite">{nota}</p>
          {modo === "comprobar" && (
            <div className="k-wrap k-wrap--centro">
              <button type="button" className="k-btn k-btn--text" onClick={oir}>
                {t("dinamica.oirOtraVez")}
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}
```

En `frontend/src/dinamicas/registro.ts`, agrega `import Trazo from "./Trazo";` y la entrada `trazo: Trazo,` en `DINAMICAS`.

- [ ] **Step 6: La pieza del sistema**

En `frontend/src/styles/sistema.css`, justo antes de `/* ---------- 99-compresion ---------- */`, agrega:

```css
/* ---------- 21-trazo ---------- */
/* ============================================================
   21 · TRAZO — .k-trazo
   Pieza nueva (spec 2026-10-09 §5.5): el lienzo de escribir con el
   dedo, en la caja de 109 de KanjiVG. `touch-action: none` es lo que
   deja dibujar sin que la página se mueva. Con movimiento reducido,
   --dur-* valen 0 y los trazos aparecen enteros.
   ============================================================ */
.k-trazo {
  flex: 0 0 auto;
  align-self: center;
  width: min(100%, 272px);
  aspect-ratio: 1;
  background: var(--paper-2);
  border: 1px solid var(--rule);
  border-radius: var(--r-md);
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}
.k-trazo svg { display: block; width: 100%; height: 100%; }
.k-trazo__guia line { stroke: var(--ink-4); stroke-width: 0.45; stroke-dasharray: 2 2.2; opacity: 0.55; }
.k-trazo path { fill: none; stroke-linecap: round; stroke-linejoin: round; }
.k-trazo__ref path { stroke: var(--paper-3); stroke-width: 7.5; visibility: hidden; }
.k-trazo[data-modo="practicar"] .k-trazo__ref path { visibility: visible; }
.k-trazo__tinta path,
.k-trazo__orden path { stroke: var(--ink); stroke-width: 5.6; }
.k-trazo__orden path {
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation: k-trazo-dibuja calc(var(--dur-slow) * 2) var(--ease-out) calc(var(--i, 0) * var(--dur-slow) * 2.2) forwards;
}
.k-trazo__mano {
  stroke: var(--ink-2);
  stroke-width: 5;
  transition: opacity var(--dur-slow) var(--ease-out) var(--dur-med);
}
.k-trazo__mano[data-mal] { stroke: var(--accent); opacity: 0; }
.k-trazo__pista {
  stroke: var(--accent-ink);
  stroke-width: 5.6;
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation: k-trazo-dibuja calc(var(--dur-slow) * 2) var(--ease-out) var(--dur-med) forwards;
}
.k-trazo__inicio { fill: var(--accent); }
@keyframes k-trazo-dibuja { to { stroke-dashoffset: 0; } }
/* El nombre del sonido, debajo del lienzo al presentar y encima en la prueba. */
.k-trazo__son {
  flex: 0 0 auto;
  margin: var(--space-3) 0 0;
  font-family: var(--font-serif);
  font-style: italic;
  font-size: var(--t-h3);
  line-height: 1;
  text-align: center;
}
```

En `docs/design/klara-sistema/hoja.html`, justo antes de `  <!-- /ÁTOMOS -->`, agrega esta tarjeta. Los trazos de muestra son aproximados; los reales salen de KanjiVG.

```html
<section class="hoja-card" id="lienzo-trazo" data-atom="lienzo-trazo">
  <div class="hoja-card__cabeza"><span class="hoja-card__n">21</span><h2 class="hoja-card__titulo">Lienzo de trazo <code>.k-trazo</code></h2></div>
  <p class="hoja-card__reemplaza"><b>nuevo</b> — la dinámica <code>trazo</code> (spec 2026-10-09 §5.5). Trazos de muestra aproximados.</p>
  <div class="hoja-card__estados">
    <figure class="hoja-estado" data-estado="presentar">
      <figcaption>Presentar: los trazos se dibujan en orden</figcaption>
      <div class="hoja-estado__muestra">
        <div class="k-trazo" data-modo="presentar"><svg viewBox="0 0 109 109" role="img" aria-label="あ">
          <g class="k-trazo__guia"><line x1="54.5" y1="4" x2="54.5" y2="105"/><line x1="4" y1="54.5" x2="105" y2="54.5"/></g>
          <g class="k-trazo__orden">
            <path d="M27,34 C40,35 61,31 80,28" pathLength="1" style="--i:0"/>
            <path d="M50,17 C46,40 47,64 57,88" pathLength="1" style="--i:1"/>
            <path d="M68,45 C62,64 48,82 36,83 C24,84 26,66 42,60 C58,54 80,57 84,70 C88,83 76,90 64,92" pathLength="1" style="--i:2"/>
          </g>
        </svg></div>
        <p class="k-trazo__son">a</p>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="practicar">
      <figcaption>Práctica: plantilla gris y el punto donde empieza</figcaption>
      <div class="hoja-estado__muestra">
        <div class="k-trazo" data-modo="practicar"><svg viewBox="0 0 109 109" role="img" aria-label="あ">
          <g class="k-trazo__guia"><line x1="54.5" y1="4" x2="54.5" y2="105"/><line x1="4" y1="54.5" x2="105" y2="54.5"/></g>
          <g class="k-trazo__ref"><path d="M27,34 C40,35 61,31 80,28"/><path d="M50,17 C46,40 47,64 57,88"/><path d="M68,45 C62,64 48,82 36,83 C24,84 26,66 42,60 C58,54 80,57 84,70 C88,83 76,90 64,92"/></g>
          <g class="k-trazo__tinta"><path d="M27,34 C40,35 61,31 80,28"/><path d="M50,17 C46,40 47,64 57,88"/></g>
          <circle class="k-trazo__inicio" cx="68" cy="45" r="2.4"/>
        </svg></div>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="comprobar">
      <figcaption>Prueba: sin plantilla, con el dedo a medio trazo</figcaption>
      <div class="hoja-estado__muestra">
        <div class="k-trazo" data-modo="comprobar"><svg viewBox="0 0 109 109" role="img" aria-label="あ">
          <g class="k-trazo__guia"><line x1="54.5" y1="4" x2="54.5" y2="105"/><line x1="4" y1="54.5" x2="105" y2="54.5"/></g>
          <g class="k-trazo__tinta"><path d="M27,34 C40,35 61,31 80,28"/></g>
          <path class="k-trazo__mano" d="M50,18 L48,40 L49,62"/>
        </svg></div>
      </div>
    </figure>
    <figure class="hoja-estado" data-estado="corregido">
      <figcaption>Corregido: el trazo que falló, enseñado en tinta de acento</figcaption>
      <div class="hoja-estado__muestra">
        <div class="k-trazo" data-modo="comprobar"><svg viewBox="0 0 109 109" role="img" aria-label="あ">
          <g class="k-trazo__guia"><line x1="54.5" y1="4" x2="54.5" y2="105"/><line x1="4" y1="54.5" x2="105" y2="54.5"/></g>
          <g class="k-trazo__tinta"><path d="M27,34 C40,35 61,31 80,28"/><path d="M50,17 C46,40 47,64 57,88"/></g>
          <path class="k-trazo__pista" d="M68,45 C62,64 48,82 36,83 C24,84 26,66 42,60 C58,54 80,57 84,70 C88,83 76,90 64,92" pathLength="1"/>
        </svg></div>
      </div>
    </figure>
  </div>
</section>

```

En `docs/design/klara-sistema/hoja.check.mjs`, en `ESTADOS`, después de la línea de `"glifo"`, agrega `  "lienzo-trazo": ["presentar", "practicar", "comprobar", "corregido"],`.

- [ ] **Step 7: Las cadenas**

```bash
cd frontend && PYTHONUTF8=1 python - <<'EOF'
import json, pathlib

def trazo(ver, n, empieza, ese_no, asi_va, escribe, listo):
    return {"dinamica": {"trazo": {"verOtraVez": ver, "trazoN": n, "empieza": empieza, "eseNo": ese_no,
                                   "asiVa": asi_va, "escribe": escribe, "listo": listo}}}

NUEVAS = {
    "es": trazo("Ver otra vez", "Trazo {{n}} de {{total}}.", "Empieza en el punto.",
                "Ese no. Empieza en el punto y sigue la guía.", "El trazo {{n}} va así. Síguelo.",
                "Escribe la que suena", "Listo."),
    "en": trazo("Watch again", "Stroke {{n}} of {{total}}.", "Start at the dot.",
                "Not that one. Start at the dot and follow the guide.", "Stroke {{n}} goes like this. Trace it.",
                "Write the one you hear", "Done."),
    "de": trazo("Nochmal ansehen", "Strich {{n}} von {{total}}.", "Beginne am Punkt.",
                "Nicht so. Beginne am Punkt und folge der Vorlage.", "Strich {{n}} geht so. Fahr ihn nach.",
                "Schreib, was du hörst", "Fertig."),
    "fr": trazo("Revoir", "Trait {{n}} sur {{total}}.", "Commence au point.",
                "Pas celui-là. Commence au point et suis le modèle.", "Le trait {{n}} se fait ainsi. Repasse-le.",
                "Écris celui que tu entends", "Terminé."),
    "ja": trazo("もう一度見る", "{{total}}画中{{n}}画目。", "点から書き始めよう。",
                "違います。点から始めて、お手本をなぞろう。", "{{n}}画目はこう書きます。なぞってみよう。",
                "聞こえた文字を書こう", "できた。"),
    "pt": trazo("Ver de novo", "Traço {{n}} de {{total}}.", "Comece no ponto.",
                "Não é esse. Comece no ponto e siga o guia.", "O traço {{n}} é assim. Siga-o.",
                "Escreva a que você ouve", "Pronto."),
}

def mezclar(a, b):
    for k, v in b.items():
        if isinstance(v, dict):
            mezclar(a.setdefault(k, {}), v)
        else:
            a[k] = v

for code, nuevas in NUEVAS.items():
    p = pathlib.Path("src/locales") / code / "common.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    mezclar(d, nuevas)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("ok")
EOF
```

- [ ] **Step 8: Gates de esta tarea**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npx vitest run && npm run build && cd .. && node docs/design/klara-sistema/hoja.check.mjs`
Expected: todo en verde.
- `hoja.check` tiene que dar «sistema.css: cero colores literales» y los estados de «lienzo-trazo».
- En `.hoja-out/`, la captura en oscuro tiene que mostrar el lienzo legible (fondo `--paper-2` de pizarra, tinta clara).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/dinamicas/trazo.ts frontend/src/lib/dinamicas/trazo.test.ts frontend/src/dinamicas frontend/src/styles/sistema.css frontend/src/locales docs/design/klara-sistema/hoja.html docs/design/klara-sistema/hoja.check.mjs
git commit -m "feat(tres-idiomas): la dinámica trazo: escribir kana con el dedo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 18: La dinámica `emparejar`

**Files:**
- Create: `frontend/src/lib/dinamicas/emparejar.ts`
- Test: `frontend/src/lib/dinamicas/emparejar.test.ts`
- Create: `frontend/src/dinamicas/Emparejar.tsx`
- Modify: `frontend/src/dinamicas/registro.ts` (agregar `emparejar`)
- Modify: `frontend/src/styles/sistema.css` (sección 22 `.k-tablero`)
- Modify: `docs/design/klara-sistema/hoja.html` (tarjeta «tablero») y `hoja.check.mjs`
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` (`dinamica.emparejar.*`)

**Interfaces:**
- Consumes: `Evidencia`, `Faceta` (tarea 13); `PropsDinamica` (tarea 15); el contenido de `emparejar` de la tarea 4 (con `faceta`).
- Produces:
  - Tipos: `Par`, `ContenidoEmparejar{pares, segundos, lang_izquierda, faceta}`, `Lado = "izq" | "der"`, `EstadoTablero`.
  - Funciones:
    - `inicialTablero(izquierda, derecha)`
    - `tocar(estado, lado, item)`
    - `seAcaboElTiempo(estado)`
    - `estadoFicha(estado, lado, item) -> "elegida" | "hecha" | "mal" | undefined`
    - `evidenciasTablero(contenido, estado, ms) -> Evidencia[]`

- [ ] **Step 1: Escribir los tests**

`frontend/src/lib/dinamicas/emparejar.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  estadoFicha,
  evidenciasTablero,
  inicialTablero,
  seAcaboElTiempo,
  tocar,
  type ContenidoEmparejar,
} from "./emparejar";

const c: ContenidoEmparejar = {
  pares: [
    { item: "ja:kana:か", izquierda: "か", derecha: "ka" },
    { item: "ja:kana:き", izquierda: "き", derecha: "ki" },
    { item: "ja:kana:く", izquierda: "く", derecha: "ku" },
  ],
  segundos: 45,
  lang_izquierda: "ja",
  faceta: "reconocer",
};
const items = c.pares.map((p) => p.item);
const nuevo = () => inicialTablero(items, [...items].reverse());

describe("tocar", () => {
  it("una pareja bien cerrada", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:か");
    expect(e.hechas).toEqual(["ja:kana:か"]);
    expect(e.elegida).toBeNull();
  });

  it("da igual por qué lado se empiece", () => {
    const e = tocar(tocar(nuevo(), "der", "ja:kana:き"), "izq", "ja:kana:き");
    expect(e.hechas).toEqual(["ja:kana:き"]);
  });

  it("tocar otra del mismo lado cambia la elegida", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "izq", "ja:kana:き");
    expect(e.elegida).toEqual({ lado: "izq", item: "ja:kana:き" });
  });

  it("fallar marca las dos fichas y sacude la segunda", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:き");
    expect(e.falladas.sort()).toEqual(["ja:kana:か", "ja:kana:き"]);
    expect(e.hechas).toEqual([]);
    expect(estadoFicha(e, "der", "ja:kana:き")).toBe("mal");
    expect(estadoFicha(e, "izq", "ja:kana:か")).toBeUndefined();
  });

  it("una hecha ya no se toca", () => {
    const e = tocar(tocar(nuevo(), "izq", "ja:kana:か"), "der", "ja:kana:か");
    expect(tocar(e, "izq", "ja:kana:か")).toBe(e);
  });

  it("termina al cerrar todas", () => {
    let e = nuevo();
    for (const i of items) e = tocar(tocar(e, "izq", i), "der", i);
    expect(e.terminado).toBe(true);
  });
});

describe("seAcaboElTiempo", () => {
  it("termina el tablero y suelta la elegida", () => {
    const e = seAcaboElTiempo(tocar(nuevo(), "izq", "ja:kana:か"));
    expect(e.terminado).toBe(true);
    expect(e.elegida).toBeNull();
  });
});

describe("estadoFicha", () => {
  it("elegida y hecha", () => {
    const e = tocar(nuevo(), "izq", "ja:kana:か");
    expect(estadoFicha(e, "izq", "ja:kana:か")).toBe("elegida");
    const f = tocar(e, "der", "ja:kana:か");
    expect(estadoFicha(f, "der", "ja:kana:か")).toBe("hecha");
  });
});

describe("evidenciasTablero", () => {
  it("acierto solo lo cerrado sin fallos; lo demás, fallo", () => {
    let e = nuevo();
    e = tocar(tocar(e, "izq", "ja:kana:か"), "der", "ja:kana:か"); // limpia
    e = tocar(tocar(e, "izq", "ja:kana:き"), "der", "ja:kana:く"); // falla き y く
    e = tocar(tocar(e, "izq", "ja:kana:き"), "der", "ja:kana:き"); // la cierra después
    e = seAcaboElTiempo(e); // く queda sin cerrar
    const evs = evidenciasTablero(c, e, 20000);
    expect(evs.map((x) => [x.item, x.acierto])).toEqual([
      ["ja:kana:か", true],
      ["ja:kana:き", false],
      ["ja:kana:く", false],
    ]);
    expect(evs.every((x) => x.faceta === "reconocer" && x.pistas === 0 && x.ms === 20000)).toBe(true);
  });
});
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd frontend && npx vitest run src/lib/dinamicas/emparejar.test.ts`
Expected: falla con `Failed to resolve import "./emparejar"`.

- [ ] **Step 3: Implementar la lógica**

`frontend/src/lib/dinamicas/emparejar.ts`:

```ts
import type { Evidencia, Faceta } from "../../api/types";

/**
 * El tablero de parejas (spec 2026-10-09 §3.2): dos columnas barajadas, contra
 * el reloj. Cada pareja deja una evidencia, y solo en práctica.
 */
export interface Par {
  item: string;
  izquierda: string;
  derecha: string;
}

export interface ContenidoEmparejar {
  pares: Par[];
  segundos: number;
  lang_izquierda: string | null;
  faceta: Faceta;
}

export type Lado = "izq" | "der";
export type EstadoFicha = "elegida" | "hecha" | "mal";

export interface EstadoTablero {
  /** Ítems en el orden de cada columna. */
  izquierda: string[];
  derecha: string[];
  elegida: { lado: Lado; item: string } | null;
  hechas: string[];
  /** Ítems con algún intento fallido: su pareja ya no cuenta como acierto. */
  falladas: string[];
  /** La última ficha que falló, para sacudirla. */
  ultimoMal: { lado: Lado; item: string } | null;
  terminado: boolean;
}

export function inicialTablero(izquierda: string[], derecha: string[]): EstadoTablero {
  return { izquierda, derecha, elegida: null, hechas: [], falladas: [], ultimoMal: null, terminado: false };
}

/** La primera ficha queda elegida; la segunda, del otro lado, cierra la pareja o falla. */
export function tocar(e: EstadoTablero, lado: Lado, item: string): EstadoTablero {
  if (e.terminado || e.hechas.includes(item)) return e;
  if (e.elegida === null || e.elegida.lado === lado) {
    return { ...e, elegida: { lado, item }, ultimoMal: null };
  }
  if (e.elegida.item === item) {
    const hechas = [...e.hechas, item];
    return { ...e, elegida: null, ultimoMal: null, hechas, terminado: hechas.length === e.izquierda.length };
  }
  const falladas = [...new Set([...e.falladas, e.elegida.item, item])];
  return { ...e, elegida: null, falladas, ultimoMal: { lado, item } };
}

export function seAcaboElTiempo(e: EstadoTablero): EstadoTablero {
  return e.terminado ? e : { ...e, elegida: null, terminado: true };
}

export function estadoFicha(e: EstadoTablero, lado: Lado, item: string): EstadoFicha | undefined {
  if (e.hechas.includes(item)) return "hecha";
  if (e.elegida?.lado === lado && e.elegida.item === item) return "elegida";
  if (e.ultimoMal?.lado === lado && e.ultimoMal.item === item) return "mal";
  return undefined;
}

/** Una por pareja: acierto si la cerró sin ningún intento fallido con sus fichas. */
export function evidenciasTablero(c: ContenidoEmparejar, e: EstadoTablero, ms: number): Evidencia[] {
  return c.pares.map((p) => ({
    item: p.item,
    faceta: c.faceta,
    acierto: e.hechas.includes(p.item) && !e.falladas.includes(p.item),
    pistas: 0,
    ms,
  }));
}
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd frontend && npx vitest run src/lib/dinamicas/emparejar.test.ts`
Expected: PASS, 9 tests.

- [ ] **Step 5: El componente**

`frontend/src/dinamicas/Emparejar.tsx`:

```tsx
/**
 * `emparejar` (spec 2026-10-09 §3.2): el tablero de parejas contra el reloj.
 * Las dos columnas se barajan por separado al montar; la lógica es pura
 * (lib/dinamicas/emparejar.ts).
 */
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  estadoFicha,
  evidenciasTablero,
  inicialTablero,
  seAcaboElTiempo,
  tocar,
  type ContenidoEmparejar,
  type Lado,
} from "../lib/dinamicas/emparejar";
import type { PropsDinamica } from "./tipos";

function barajar<T>(xs: T[]): T[] {
  const out = [...xs];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

export default function Emparejar({ contenido, onResultado }: PropsDinamica<ContenidoEmparejar>) {
  const { t } = useTranslation();
  const [estado, setEstado] = useState(() => {
    const items = contenido.pares.map((p) => p.item);
    return inicialTablero(barajar(items), barajar(items));
  });
  const [quedan, setQuedan] = useState(contenido.segundos);
  const inicio = useRef(performance.now());
  const reportado = useRef(false);
  const pares = useMemo(() => new Map(contenido.pares.map((p) => [p.item, p])), [contenido]);

  useEffect(() => {
    if (estado.terminado) return;
    const id = window.setInterval(() => setQuedan((s) => s - 1), 1000);
    return () => window.clearInterval(id);
  }, [estado.terminado]);

  useEffect(() => {
    if (quedan <= 0) setEstado((e) => seAcaboElTiempo(e));
  }, [quedan]);

  useEffect(() => {
    if (!estado.terminado || reportado.current) return;
    reportado.current = true;
    onResultado(evidenciasTablero(contenido, estado, Math.round(performance.now() - inicio.current)));
  }, [estado, contenido, onResultado]);

  const ficha = (lado: Lado, item: string) => {
    const p = pares.get(item);
    if (!p) return null;
    return (
      <button
        key={`${lado}-${item}`}
        type="button"
        className="k-tablero__ficha"
        data-estado={estadoFicha(estado, lado, item)}
        lang={lado === "izq" ? contenido.lang_izquierda ?? undefined : undefined}
        disabled={estado.terminado || estado.hechas.includes(item)}
        onClick={() => setEstado((e) => tocar(e, lado, item))}
      >
        {lado === "izq" ? p.izquierda : p.derecha}
      </button>
    );
  };

  const restante = Math.max(quedan, 0);
  return (
    <>
      <div className="k-bar k-bar--fill">
        <div className="k-bar__track" role="progressbar" aria-valuenow={restante} aria-valuemin={0} aria-valuemax={contenido.segundos}>
          <i className="k-bar__fill" style={{ width: `${(restante / contenido.segundos) * 100}%` }} />
        </div>
      </div>
      <div className="k-tablero">
        {estado.izquierda.map((item, i) => (
          <Fragment key={item}>
            {ficha("izq", item)}
            {ficha("der", estado.derecha[i])}
          </Fragment>
        ))}
      </div>
      <p className="k-cap k-cap--center">
        {t("dinamica.emparejar.cuenta", { n: estado.hechas.length, total: contenido.pares.length })} ·{" "}
        {t("dinamica.emparejar.instruccion")}
      </p>
    </>
  );
}
```

En `frontend/src/dinamicas/registro.ts`, agrega `import Emparejar from "./Emparejar";` y la entrada `emparejar: Emparejar,`.

- [ ] **Step 6: La pieza del sistema**

En `frontend/src/styles/sistema.css`, justo antes de `/* ---------- 99-compresion ---------- */`, agrega:

```css
/* ---------- 22-tablero ---------- */
/* ============================================================
   22 · TABLERO — .k-tablero + .k-tablero__ficha
   Pieza nueva (spec 2026-10-09 §3.2): el tablero de parejas de
   `emparejar`. Dos columnas; la ficha elegida se marca, la hecha se
   apaga y la que falló se sacude una vez.
   ============================================================ */
.k-tablero {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
  margin-top: var(--space-4);
}
.k-tablero__ficha {
  min-height: 52px;
  min-width: 44px;
  display: grid;
  place-items: center;
  padding: 0 var(--space-2);
  border: 1px solid var(--rule);
  border-radius: var(--r-md);
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-serif);
  font-size: var(--t-read);
  line-height: 1;
  cursor: pointer;
  transition: opacity var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out);
}
.k-tablero__ficha[data-estado="elegida"] { border-color: var(--ink); box-shadow: inset 0 0 0 1px var(--ink); }
.k-tablero__ficha[data-estado="hecha"] { opacity: 0.3; border-style: dashed; cursor: default; }
.k-tablero__ficha[data-estado="mal"] {
  border-color: var(--accent);
  color: var(--accent-ink);
  animation: k-tablero-sacude var(--dur-slow) var(--ease-out);
}
@keyframes k-tablero-sacude {
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}
```

En `docs/design/klara-sistema/hoja.html`, justo antes de `  <!-- /ÁTOMOS -->`, agrega:

```html
<section class="hoja-card" id="tablero" data-atom="tablero">
  <div class="hoja-card__cabeza"><span class="hoja-card__n">22</span><h2 class="hoja-card__titulo">Tablero <code>.k-tablero</code></h2></div>
  <p class="hoja-card__reemplaza"><b>nuevo</b> — la dinámica <code>emparejar</code> (spec 2026-10-09 §3.2)</p>
  <div class="hoja-card__estados">
    <figure class="hoja-estado" data-estado="reposo">
      <figcaption>Reposo</figcaption>
      <div class="hoja-estado__muestra"><div class="k-tablero">
        <button type="button" class="k-tablero__ficha" lang="ja">か</button><button type="button" class="k-tablero__ficha">ki</button>
      </div></div>
    </figure>
    <figure class="hoja-estado" data-estado="elegida">
      <figcaption>Elegida <code>data-estado="elegida"</code></figcaption>
      <div class="hoja-estado__muestra"><div class="k-tablero">
        <button type="button" class="k-tablero__ficha" lang="ja" data-estado="elegida">き</button><button type="button" class="k-tablero__ficha">ka</button>
      </div></div>
    </figure>
    <figure class="hoja-estado" data-estado="hecha">
      <figcaption>Hecha <code>data-estado="hecha"</code></figcaption>
      <div class="hoja-estado__muestra"><div class="k-tablero">
        <button type="button" class="k-tablero__ficha" lang="ja" data-estado="hecha" disabled>か</button><button type="button" class="k-tablero__ficha" data-estado="hecha" disabled>ka</button>
      </div></div>
    </figure>
    <figure class="hoja-estado" data-estado="mal">
      <figcaption>Mal <code>data-estado="mal"</code></figcaption>
      <div class="hoja-estado__muestra"><div class="k-tablero">
        <button type="button" class="k-tablero__ficha" lang="ja">き</button><button type="button" class="k-tablero__ficha" data-estado="mal">ku</button>
      </div></div>
    </figure>
  </div>
</section>

```

En `docs/design/klara-sistema/hoja.check.mjs`, en `ESTADOS`, después de `"lienzo-trazo"`, agrega `  "tablero": ["reposo", "elegida", "hecha", "mal"],`.

- [ ] **Step 7: Las cadenas**

```bash
cd frontend && PYTHONUTF8=1 python - <<'EOF'
import json, pathlib

def emparejar(instruccion, cuenta):
    return {"dinamica": {"emparejar": {"instruccion": instruccion, "cuenta": cuenta}}}

NUEVAS = {
    "es": emparejar("Toca una ficha y su pareja.", "{{n}} de {{total}}"),
    "en": emparejar("Tap a tile and its match.", "{{n}} of {{total}}"),
    "de": emparejar("Tippe eine Karte und ihr Gegenstück an.", "{{n}} von {{total}}"),
    "fr": emparejar("Touche une carte puis sa paire.", "{{n}} sur {{total}}"),
    "ja": emparejar("カードとそのペアをタップしよう。", "{{total}}組中{{n}}組"),
    "pt": emparejar("Toque uma peça e o seu par.", "{{n}} de {{total}}"),
}

def mezclar(a, b):
    for k, v in b.items():
        if isinstance(v, dict):
            mezclar(a.setdefault(k, {}), v)
        else:
            a[k] = v

for code, nuevas in NUEVAS.items():
    p = pathlib.Path("src/locales") / code / "common.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    mezclar(d, nuevas)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("ok")
EOF
```

- [ ] **Step 8: Gates de esta tarea**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npx vitest run && npm run build && cd .. && node docs/design/klara-sistema/hoja.check.mjs`
Expected: todo en verde. El check táctil de la hoja (≥ 44 px) tiene que pasar en las fichas.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/dinamicas/emparejar.ts frontend/src/lib/dinamicas/emparejar.test.ts frontend/src/dinamicas frontend/src/styles/sistema.css frontend/src/locales docs/design/klara-sistema/hoja.html docs/design/klara-sistema/hoja.check.mjs
git commit -m "feat(tres-idiomas): la dinámica emparejar: el tablero de parejas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 19: Hoy con una línea por idioma (frontend)

**Files:**
- Modify (reescribir): `frontend/src/lib/hoyView.ts`
- Modify (reescribir): `frontend/src/lib/hoyView.test.ts`
- Modify (reescribir): `frontend/src/routes/Hoy.tsx`
- Modify: `frontend/src/api/types.ts` (cambiar `TodayOut` por `{ lineas: Linea[] }` y borrar los tipos que solo usaba el Hoy viejo)
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` (claves `hoy.*`)

**Interfaces:**
- Consumes:
  - `Linea` (tarea 13);
  - `api.today(since)` (ya existe, mismo path);
  - `unlockAudio` (`lib/tts`);
  - `useGreeting` y `useMastheadDate` (`lib/dateLabel`);
  - `languageLabel` (`lib/languages`).
- Produces:
  - Tipo `TodayOut{lineas: Linea[]}`.
  - `HoyVM{lineas, ahora, minutos, algunaHecha, todoHecho, sinIdiomas}`.
  - Funciones: `buildHoyVM`, `dekPanel(l) -> TextoLinea`, `subFila(l) -> TextoLinea`, `medianocheLocal`, `frase`.
  - Al tocar una línea se llama `unlockAudio()` y se navega a `/sesion/:idioma`.

- [ ] **Step 1: Reescribir los tests**

Reemplaza todo `frontend/src/lib/hoyView.test.ts` por:

```ts
import { describe, expect, it } from "vitest";
import type { Linea } from "../api/types";
import { buildHoyVM, dekPanel, frase, medianocheLocal, subFila } from "./hoyView";

const BAJADA = "la fila de か: leerla, oírla y escribirla";
const linea = (over: Partial<Linea> = {}): Linea => ({
  idioma: "ja",
  estado: "ahora",
  minutos: 18,
  repasos: 6,
  leccion: { id: "ja/hiragana/ka", titulo: "か き く け こ", bajada: BAJADA },
  hecho: null,
  ...over,
});

describe("buildHoyVM", () => {
  it("sin datos todavía: nada, y sin el aviso de idiomas", () => {
    const vm = buildHoyVM(null);
    expect(vm.lineas).toEqual([]);
    expect(vm.sinIdiomas).toBe(false);
  });

  it("sin líneas: el aviso de Ajustes", () => {
    expect(buildHoyVM({ lineas: [] }).sinIdiomas).toBe(true);
  });

  it("la línea actual y los minutos de lo que falta", () => {
    const vm = buildHoyVM({
      lineas: [
        linea({ estado: "hecha", minutos: 18, hecho: { repasos: 6, leccion: "か き く け こ" } }),
        linea({ idioma: "de", estado: "ahora", minutos: 17 }),
        linea({ idioma: "en", estado: "pendiente", minutos: 15 }),
      ],
    });
    expect(vm.ahora?.idioma).toBe("de");
    expect(vm.minutos).toBe(32);
    expect([vm.algunaHecha, vm.todoHecho]).toEqual([true, false]);
  });

  it("todo hecho", () => {
    const vm = buildHoyVM({ lineas: [linea({ estado: "hecha", hecho: { repasos: 0, leccion: null } })] });
    expect([vm.todoHecho, vm.minutos, vm.ahora]).toEqual([true, 0, null]);
  });
});

describe("dekPanel", () => {
  it("repasos y luego la lección", () => {
    expect(dekPanel(linea())).toEqual({ tipo: "luego", repasos: 6, bajada: BAJADA });
  });

  it("sin repasos, la bajada sola", () => {
    expect(dekPanel(linea({ repasos: 0 }))).toEqual({ tipo: "bajada", bajada: BAJADA });
  });

  it("sin lección, solo repasos", () => {
    expect(dekPanel(linea({ leccion: null }))).toEqual({ tipo: "soloRepasos" });
  });
});

describe("subFila", () => {
  it("hecha: lo que hiciste", () => {
    const l = linea({ estado: "hecha", hecho: { repasos: 6, leccion: "か き く け こ" } });
    expect(subFila(l)).toEqual({ tipo: "repasos", repasos: 6, detalle: "か き く け こ" });
  });

  it("pendiente con repasos: los repasos y la bajada", () => {
    expect(subFila(linea({ estado: "pendiente" }))).toEqual({ tipo: "repasos", repasos: 6, detalle: BAJADA });
  });

  it("pendiente sin repasos: la bajada", () => {
    expect(subFila(linea({ estado: "pendiente", repasos: 0 }))).toEqual({ tipo: "bajada", bajada: BAJADA });
  });

  it("sin lección: solo los repasos", () => {
    expect(subFila(linea({ estado: "pendiente", leccion: null }))).toEqual({ tipo: "repasos", repasos: 6, detalle: null });
  });
});

describe("frase y medianocheLocal", () => {
  it("la bajada como frase suelta", () => {
    expect(frase("la fila de か")).toBe("La fila de か.");
  });

  it("la medianoche local del día", () => {
    expect(medianocheLocal(new Date(2026, 9, 9, 15, 30))).toBe(new Date(2026, 9, 9, 0, 0).toISOString());
  });
});
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd frontend && npx vitest run src/lib/hoyView.test.ts`
Expected: FAIL. `dekPanel`, `subFila` y `frase` no existen, y `buildHoyVM` devuelve la forma vieja.

- [ ] **Step 3: Reescribir la lógica y el tipo**

Reemplaza todo `frontend/src/lib/hoyView.ts` por:

```ts
import type { Linea, TodayOut } from "../api/types";

/** Lo que pinta Hoy (spec 2026-10-09 §5.1): una línea por idioma de estudio. */
export interface HoyVM {
  lineas: Linea[];
  ahora: Linea | null;
  /** Los minutos de lo que falta. */
  minutos: number;
  algunaHecha: boolean;
  todoHecho: boolean;
  /** Ya respondió el servidor y no hay ningún idioma con mapa: aviso de Ajustes. */
  sinIdiomas: boolean;
}

export function buildHoyVM(today: TodayOut | null): HoyVM {
  const lineas = today?.lineas ?? [];
  const faltan = lineas.filter((l) => l.estado !== "hecha");
  return {
    lineas,
    ahora: lineas.find((l) => l.estado === "ahora") ?? null,
    minutos: faltan.reduce((s, l) => s + l.minutos, 0),
    algunaHecha: lineas.some((l) => l.estado === "hecha"),
    todoHecho: lineas.length > 0 && faltan.length === 0,
    sinIdiomas: today !== null && lineas.length === 0,
  };
}

/** Lo que dicen el panel y las filas, sin i18n: Hoy.tsx lo traduce. */
export type TextoLinea =
  | { tipo: "soloRepasos" }
  | { tipo: "bajada"; bajada: string }
  | { tipo: "luego"; repasos: number; bajada: string }
  | { tipo: "repasos"; repasos: number; detalle: string | null };

export function dekPanel(l: Linea): TextoLinea {
  if (!l.leccion) return { tipo: "soloRepasos" };
  if (l.repasos === 0) return { tipo: "bajada", bajada: l.leccion.bajada };
  return { tipo: "luego", repasos: l.repasos, bajada: l.leccion.bajada };
}

export function subFila(l: Linea): TextoLinea {
  if (l.estado === "hecha" && l.hecho) return { tipo: "repasos", repasos: l.hecho.repasos, detalle: l.hecho.leccion };
  if (!l.leccion) return { tipo: "repasos", repasos: l.repasos, detalle: null };
  if (l.repasos === 0) return { tipo: "bajada", bajada: l.leccion.bajada };
  return { tipo: "repasos", repasos: l.repasos, detalle: l.leccion.bajada };
}

/** La bajada como frase suelta: mayúscula al principio y punto al final. */
export function frase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1) + ".";
}

/** La medianoche local del dispositivo, en ISO: el `since` de GET /today. */
export function medianocheLocal(ahora: Date = new Date()): string {
  const d = new Date(ahora);
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}
```

En `frontend/src/api/types.ts`:
1. Busca la definición vieja de `TodayOut`, la que tiene el comentario `/** GET /today (spec 2026-09-30 §2.3). */`.
2. Reemplázala por:

```ts
/** GET /today (spec 2026-10-09 §5.1): una línea por idioma de estudio. */
export interface TodayOut {
  lineas: Linea[];
}
```

3. Borra los tipos que solo usaba el Hoy viejo (`TodayStep` y los que componían la forma vieja), pero solo si `grep -rn "<NombreDelTipo>" frontend/src` muestra que nadie más los importa.

- [ ] **Step 4: Correr y ver pasar**

Run: `cd frontend && npx vitest run src/lib/hoyView.test.ts`
Expected: PASS, 13 tests.

- [ ] **Step 5: Reescribir la pantalla**

Reemplaza todo `frontend/src/routes/Hoy.tsx` por:

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Linea, TodayOut } from "../api/types";
import KlaraMark from "../components/KlaraMark";
import { useGreeting, useMastheadDate } from "../lib/dateLabel";
import { buildHoyVM, dekPanel, frase, medianocheLocal, subFila, type TextoLinea } from "../lib/hoyView";
import { languageLabel } from "../lib/languages";
import { unlockAudio } from "../lib/tts";
import { useUser } from "../lib/user";

/**
 * Hoy (spec 2026-10-09 §5.1): una línea por idioma de estudio. Cada línea son
 * los repasos de ese idioma y la lección que sigue en su mapa, en una sola
 * sesión. El orden lo pone el servidor; la primera sin hacer es «estás aquí».
 */
const ESTADO = { hecha: "done", ahora: "now", pendiente: "pending" } as const;

export default function Hoy() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useUser();
  const hola = useGreeting();
  const fecha = useMastheadDate();
  const [today, setToday] = useState<TodayOut | null>(null);
  const [fallo, setFallo] = useState(false);
  const [intento, setIntento] = useState(0);

  useEffect(() => {
    let cancelado = false;
    setFallo(false);
    api.today(medianocheLocal()).then(
      (d) => {
        if (!cancelado) setToday(d);
      },
      () => {
        if (!cancelado) setFallo(true);
      },
    );
    return () => {
      cancelado = true;
    };
  }, [intento]);

  // La pantalla sigue montada con la app en segundo plano: al volver se pide el día otra vez,
  // y pasada la medianoche llega el día nuevo.
  useEffect(() => {
    const alVolver = () => {
      if (document.visibilityState === "visible") setIntento((n) => n + 1);
    };
    document.addEventListener("visibilitychange", alVolver);
    return () => document.removeEventListener("visibilitychange", alVolver);
  }, []);

  const vm = buildHoyVM(today);

  const texto = (x: TextoLinea): string => {
    switch (x.tipo) {
      case "soloRepasos":
        return t("hoy.soloRepasos");
      case "bajada":
        return frase(x.bajada);
      case "luego":
        return t("hoy.luego", { repasos: t("hoy.repasos", { count: x.repasos }), bajada: x.bajada });
      case "repasos": {
        const r = t("hoy.repasos", { count: x.repasos });
        return x.detalle ? `${r} · ${x.detalle}` : r;
      }
    }
  };

  // El toque que abre la sesión desbloquea el audio: lo primero que suena es un kana.
  const abrir = (l: Linea) => {
    unlockAudio();
    navigate(`/sesion/${l.idioma}`, { state: { from: "/" } });
  };

  const rotulo = vm.todoHecho
    ? t("hoy.planHecho")
    : vm.algunaHecha
      ? t("hoy.quedan", { min: vm.minutos })
      : t("hoy.plan", { min: vm.minutos });

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
          <h1 className="k-hero__title">
            <Trans
              i18nKey="home.greeting.conNombre"
              values={{ hola, name: user?.display_name ?? "…" }}
              components={{ 1: <em /> }}
            />
          </h1>
        </header>
        {fallo && today === null && (
          <p className="k-error" role="alert">
            {t("hoy.error")}{" "}
            <button type="button" className="k-btn k-btn--text" onClick={() => setIntento((n) => n + 1)}>
              {t("hoy.reintentar")}
            </button>
          </p>
        )}
        {vm.sinIdiomas ? (
          <>
            <p className="k-note">{t("hoy.sinIdiomas")}</p>
            <div className="k-wrap">
              <button type="button" className="k-btn k-btn--ghost" onClick={() => navigate("/settings")}>
                {t("hoy.irAjustes")}
              </button>
            </div>
          </>
        ) : (
          <>
            <h2 className="k-cap k-cap--rule">{rotulo}</h2>
            <ol className="k-route" role="list">
              {vm.lineas.map((l) => (
                <li
                  key={l.idioma}
                  className="k-route__stop"
                  data-state={ESTADO[l.estado]}
                  aria-current={l.estado === "ahora" ? "step" : undefined}
                >
                  <span className="k-route__dot" aria-hidden="true" />
                  {l.estado === "ahora" ? (
                    <div className="k-route__body">
                      <span className="k-route__label">{t("hoy.estasAqui")}</span>
                      <button type="button" className="k-hero" onClick={() => abrir(l)}>
                        <span className="k-hero__tag">
                          <span>
                            <span lang={l.idioma}>{languageLabel(l.idioma)}</span> · {t("hoy.minutos", { min: l.minutos })}
                          </span>
                          <span>{t("hoy.empezar")}</span>
                        </span>
                        <span className="k-hero__title" lang={l.leccion ? l.idioma : undefined}>
                          {l.leccion?.titulo ?? t("hoy.repasos", { count: l.repasos })}
                        </span>
                        <span className="k-hero__arrow" aria-hidden="true">→</span>
                        <span className="k-hero__dek">{texto(dekPanel(l))}</span>
                      </button>
                    </div>
                  ) : (
                    <button type="button" className="k-route__row" onClick={() => abrir(l)}>
                      <span className="k-route__title" lang={l.idioma}>{languageLabel(l.idioma)}</span>
                      <span className="k-route__meta">
                        {l.estado === "hecha" ? t("hoy.hecho") : t("hoy.minutos", { min: l.minutos })}
                      </span>
                      <span className="k-route__sub">{texto(subFila(l))}</span>
                    </button>
                  )}
                </li>
              ))}
            </ol>
            {vm.lineas.length > 0 && (
              <p className="k-route__end">{vm.todoHecho ? t("hoy.finHecho") : t("hoy.fin")}</p>
            )}
          </>
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 6: Las cadenas (y fuera las viejas)**

```bash
cd frontend && PYTHONUTF8=1 python - <<'EOF'
import json, pathlib

def hoy(quedan, minutos, uno, varios, luego, solo, sin, ir, fin, fin_hecho):
    return {"hoy": {"quedan": quedan, "minutos": minutos, "repasos_one": uno, "repasos_other": varios,
                    "luego": luego, "soloRepasos": solo, "sinIdiomas": sin, "irAjustes": ir,
                    "fin": fin, "finHecho": fin_hecho}}

NUEVAS = {
    "es": hoy("Te quedan · {{min}} min", "{{min}} min", "{{count}} repaso", "{{count}} repasos",
              "{{repasos}} y luego {{bajada}}.", "Solo repasos: terminaste el mapa.",
              "Elige en Ajustes qué idiomas estudias.", "Ir a Ajustes", "Eso es todo por hoy.", "Listo por hoy."),
    "en": hoy("Left today · {{min}} min", "{{min}} min", "{{count}} review", "{{count}} reviews",
              "{{repasos}}, then {{bajada}}.", "Reviews only: you finished the map.",
              "Pick the languages you study in Settings.", "Go to Settings", "That's all for today.", "Done for today."),
    "de": hoy("Noch übrig · {{min}} Min.", "{{min}} Min.", "{{count}} Wiederholung", "{{count}} Wiederholungen",
              "{{repasos}}, danach {{bajada}}.", "Nur Wiederholungen: Du hast die Karte geschafft.",
              "Wähle in den Einstellungen, welche Sprachen du lernst.", "Zu den Einstellungen",
              "Das ist alles für heute.", "Fertig für heute."),
    "fr": hoy("Il te reste · {{min}} min", "{{min}} min", "{{count}} révision", "{{count}} révisions",
              "{{repasos}}, puis {{bajada}}.", "Que des révisions : tu as fini la carte.",
              "Choisis dans les Réglages les langues que tu étudies.", "Aller aux Réglages",
              "C’est tout pour aujourd’hui.", "Fini pour aujourd’hui."),
    "ja": hoy("残り · {{min}}分", "{{min}}分", "{{count}}件の復習", "{{count}}件の復習",
              "{{repasos}}、そのあと{{bajada}}。", "復習のみ：マップは完了しました。",
              "設定で学ぶ言語を選んでください。", "設定へ", "今日はここまで。", "今日は完了。"),
    "pt": hoy("Faltam · {{min}} min", "{{min}} min", "{{count}} revisão", "{{count}} revisões",
              "{{repasos}} e depois {{bajada}}.", "Só revisões: você terminou o mapa.",
              "Escolha nos Ajustes os idiomas que você estuda.", "Ir para Ajustes",
              "É tudo por hoje.", "Pronto por hoje."),
}
VIEJAS = ("seguir", "pedir", "fichas_one", "fichas_other")

def mezclar(a, b):
    for k, v in b.items():
        if isinstance(v, dict):
            mezclar(a.setdefault(k, {}), v)
        else:
            a[k] = v

for code, nuevas in NUEVAS.items():
    p = pathlib.Path("src/locales") / code / "common.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    mezclar(d, nuevas)
    for k in VIEJAS:
        d["hoy"].pop(k, None)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("ok")
EOF
```

Antes de correrlo, confirma que las claves viejas no se usan en ningún otro lado: `grep -rn "hoy\.\(seguir\|pedir\|fichas\)" src` no tiene que dar nada.

- [ ] **Step 7: Gates de esta tarea**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npx vitest run && npm run build`
Expected: todo en verde. Si `typecheck` marca un tipo viejo de Today en otro archivo, ese archivo era del Hoy viejo: quita la referencia (solo `Hoy.tsx` y `hoyView.ts` lo usaban; tarea 13, paso 7).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/hoyView.ts frontend/src/lib/hoyView.test.ts frontend/src/routes/Hoy.tsx frontend/src/api/types.ts frontend/src/locales
git commit -m "feat(tres-idiomas): Hoy con una línea por idioma

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 20: Ajustes: idiomas que estudias

**Files:**
- Create: `frontend/src/lib/idiomasEstudio.ts`
- Test: `frontend/src/lib/idiomasEstudio.test.ts`
- Modify: `frontend/src/routes/Settings.tsx`
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` (`settings.field.studyLangs`, `settings.studyLangsHint`)

**Interfaces:**
- Consumes: `api.mapas()` y `MapaResumen` (tarea 13); `User.study_languages` y `UserUpdate.study_languages` (tarea 13); `patchUser` (`lib/user`).
- Produces: `alternarIdioma(actual, idioma, orden) -> string[]`.

- [ ] **Step 1: Escribir los tests**

`frontend/src/lib/idiomasEstudio.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { alternarIdioma } from "./idiomasEstudio";

const ORDEN = ["de", "ja", "en"];

describe("alternarIdioma", () => {
  it("marcar uno lo agrega en el orden de los mapas", () => {
    expect(alternarIdioma(["en"], "de", ORDEN)).toEqual(["de", "en"]);
    expect(alternarIdioma(["de", "en"], "ja", ORDEN)).toEqual(["de", "ja", "en"]);
  });

  it("desmarcar uno lo quita", () => {
    expect(alternarIdioma(["de", "ja"], "de", ORDEN)).toEqual(["ja"]);
  });

  it("el último no se puede desmarcar", () => {
    expect(alternarIdioma(["ja"], "ja", ORDEN)).toEqual(["ja"]);
  });
});
```

- [ ] **Step 2: Correr y ver fallar**

Run: `cd frontend && npx vitest run src/lib/idiomasEstudio.test.ts`
Expected: falla con `Failed to resolve import "./idiomasEstudio"`.

- [ ] **Step 3: Implementar**

`frontend/src/lib/idiomasEstudio.ts`:

```ts
/** Marca o desmarca un idioma de estudio (spec 2026-10-09 §5.6). Siempre queda al
 *  menos uno, y la lista sale en el orden de los mapas. */
export function alternarIdioma(actual: string[], idioma: string, orden: string[]): string[] {
  if (actual.includes(idioma)) return actual.length > 1 ? actual.filter((i) => i !== idioma) : actual;
  return orden.filter((i) => i === idioma || actual.includes(i));
}
```

- [ ] **Step 4: Correr y ver pasar**

Run: `cd frontend && npx vitest run src/lib/idiomasEstudio.test.ts`
Expected: PASS, 3 tests.

- [ ] **Step 5: Ajustes**

En `frontend/src/routes/Settings.tsx`:

1. Agrega los imports:

```tsx
import { api } from "../api/client";
import type { MapaResumen } from "../api/types";
import { alternarIdioma } from "../lib/idiomasEstudio";
```

(si `api` ya está importado, no lo repitas).

2. Junto a los demás `useState`, agrega:

```tsx
  const [mapas, setMapas] = useState<MapaResumen[] | null>(null);
  const [estudio, setEstudio] = useState<string[]>([]);
```

3. Dentro del `useEffect` que copia `user` al formulario (el que hace `setTargetLang(user.target_language)`), agrega `setEstudio(user.study_languages);`.

4. Agrega este efecto debajo de ese:

```tsx
  // Los idiomas que se pueden estudiar son los que tienen mapa (spec 2026-10-09 §5.6).
  useEffect(() => {
    api.mapas().then(setMapas, () => setMapas([]));
  }, []);
```

5. En `onSubmit`, dentro de `patchUser({...})`, agrega después de `learning_context: …`:

```tsx
        ...(mapas && mapas.length > 0 && estudio.length > 0 ? { study_languages: estudio } : {}),
```

6. Justo después del `<label className="k-field" …>` del idioma de estudio (el que termina con `{sameLang && <span className="k-field__hint">…}`), agrega:

```tsx
        {mapas && mapas.length > 0 && (
          <div className="k-field">
            <span className="k-field__label" id="ajustes-estudio">
              {t("settings.field.studyLangs")}
            </span>
            <div className="k-wrap" role="group" aria-labelledby="ajustes-estudio">
              {mapas.map((m) => (
                <button
                  key={m.idioma}
                  type="button"
                  className="k-chip"
                  aria-pressed={estudio.includes(m.idioma)}
                  data-selected={estudio.includes(m.idioma)}
                  lang={m.idioma}
                  disabled={saving}
                  onClick={() => setEstudio((a) => alternarIdioma(a, m.idioma, mapas.map((x) => x.idioma)))}
                >
                  {languageLabel(m.idioma)}
                </button>
              ))}
            </div>
            <span className="k-field__hint">{t("settings.studyLangsHint")}</span>
          </div>
        )}
```

- [ ] **Step 6: Las cadenas**

```bash
cd frontend && PYTHONUTF8=1 python - <<'EOF'
import json, pathlib

def ajustes(campo, pista):
    return {"settings": {"field": {"studyLangs": campo}, "studyLangsHint": pista}}

NUEVAS = {
    "es": ajustes("Idiomas que estudias", "Cada uno es una línea en Hoy."),
    "en": ajustes("Languages you study", "Each one is a line in Today."),
    "de": ajustes("Sprachen, die du lernst", "Jede ist eine Linie in Heute."),
    "fr": ajustes("Langues que tu étudies", "Chacune est une ligne dans Aujourd’hui."),
    "ja": ajustes("学んでいる言語", "それぞれが「今日」の1ラインになります。"),
    "pt": ajustes("Idiomas que você estuda", "Cada um é uma linha em Hoje."),
}

def mezclar(a, b):
    for k, v in b.items():
        if isinstance(v, dict):
            mezclar(a.setdefault(k, {}), v)
        else:
            a[k] = v

for code, nuevas in NUEVAS.items():
    p = pathlib.Path("src/locales") / code / "common.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    mezclar(d, nuevas)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("ok")
EOF
```

- [ ] **Step 7: Gates de esta tarea**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npx vitest run && npm run build`
Expected: todo en verde.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/idiomasEstudio.ts frontend/src/lib/idiomasEstudio.test.ts frontend/src/routes/Settings.tsx frontend/src/locales
git commit -m "feat(tres-idiomas): elegir en Ajustes los idiomas que estudias

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Fase C — Cerrar

### Task 21: Copy, gates, prueba en el teléfono y PR

**Files:**
- Modify (si la revisión de copy cambia algo): `frontend/src/locales/*/common.json`

- [ ] **Step 1: Revisión de copy con `solace-wren`**

Invoca la skill `solace-wren` (es la que manda en microcopy según CLAUDE.md) sobre las cadenas nuevas en español de `frontend/src/locales/es/common.json`, en estas ramas:
- `sesion.*`
- `dinamica.*`
- `hoy.quedan`, `hoy.luego`, `hoy.soloRepasos`, `hoy.sinIdiomas`, `hoy.irAjustes`, `hoy.fin`, `hoy.finHecho`
- `settings.field.studyLangs`, `settings.studyLangsHint`

Si cambia alguna, actualiza la misma clave en los otros 5 locales con el mismo sentido.

Las mnemotecnias y bajadas de `kana.json` y `mapa.json` son contenido de lección: ya las revisó Samuel en la tarea 7, y no pasan por aquí.

- [ ] **Step 2: Los gates completos**

Corre la skill `gates-locales`: deriva la receta de `.github/workflows/ci.yml` y audita la cobertura. Como mínimo, todo esto tiene que salir verde:

```bash
cd backend && TEST_DATABASE_URL=postgresql+asyncpg://klara:klara_test@localhost:5432/klara_test uv run pytest tests/ -q > ../.pytest.log 2>&1; tail -3 ../.pytest.log
cd backend && uv run ruff check src tests && uv run ruff format --check src tests
cd backend && DATABASE_URL=postgresql+asyncpg://klara@localhost:5432/klara_test DB_PASSWORD=klara_test uv run alembic upgrade head && DATABASE_URL=postgresql+asyncpg://klara@localhost:5432/klara_test DB_PASSWORD=klara_test uv run alembic downgrade base && DATABASE_URL=postgresql+asyncpg://klara@localhost:5432/klara_test DB_PASSWORD=klara_test uv run alembic upgrade head
cd frontend && npm run typecheck && npm run i18n:check && npm run test && npm run build
node docs/design/klara-sistema/hoja.check.mjs
```

Expected: cero rojos y cero sin correr. Borra `.pytest.log` al final.

- [ ] **Step 3: Prueba en local, a tamaño de teléfono**

Levanta el entorno de desarrollo como dice la memoria `klara-dev-local`:
- `docker compose up -d --build`;
- el registro es por invitación, con bootstrap por `INITIAL_OWNER_EMAIL`;
- antes de probar, confirma que el contenedor monta este checkout y no uno viejo.

En el log del backend tiene que aparecer `startup.catalogo idiomas=['ja'] lecciones=10`. Después, en el navegador con la vista de teléfono (390 × 844):

1. **Ajustes:** aparece «Idiomas que estudias» con 日本語. Márcalo y guarda.
2. **Hoy:** una línea, 日本語, con «estás aquí», el título «あ い う え お» y unos 8 min.
3. **Abrir la línea:**
   - presentar あ: el trazo se dibuja solo y suena «a»;
   - «Ahora tú»: trazo con plantilla, punto pulsante, un trazo bien y otro al revés (rechazado);
   - después vienen las elecciones, el tablero y la prueba.
4. **Saltar:** en una elección de oír, toca «Ahora no puedo escuchar». Las de oír quedan como segmentos saltados.
5. **Final:** la tabla por kana y faceta, «mañana te tocan N repasos» y «A Hoy». Hoy muestra la línea hecha.
6. **En la base local:** `select modo, count(*) from facet_reviews group by modo;` tiene `practicar` y `comprobar`, y `select count(*) from user_facets;` es mayor que 0.

Si algo de esto falla, se arregla antes de seguir, en la tarea que corresponda.

- [ ] **Step 4: Push y PR (con permiso)**

Pregúntale a Samuel antes de hacer push y abrir el PR, porque es visible fuera. Con su sí:

```bash
git push -u origin feat/tres-idiomas-nucleo
gh pr create --base main --title "Klara en tres idiomas: el núcleo y el japonés" --body "$(cat <<'EOF'
Plan 1 de 4 de la spec `docs/superpowers/specs/2026-10-09-klara-tres-idiomas-design.md`
(plan: `docs/superpowers/plans/2026-10-09-tres-idiomas-1-nucleo-japones.md`).

- Catálogo en archivos, validado al arrancar; facetas con FSRS propio (`user_facets`), registro de evidencias y corridas.
- Reproductor de lecciones con dinámicas intercambiables: `eleccion`, `trazo` (kana con el dedo) y `emparejar`.
- Hoy con una línea por idioma; Ajustes para elegir los idiomas.
- El mapa de japonés: 46 hiragana en 10 lecciones, con trazos de KanjiVG (CC BY-SA 3.0) y audio validado con Azure.

Migración aditiva `20261009_0024`. Deploy: `scripts/deploy-prod.sh` (lo corre Samuel).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Después del merge**

Samuel corre `bash scripts/deploy-prod.sh`. Luego, en el teléfono:
1. elige 日本語 en Ajustes;
2. hace la primera línea;
3. confirma que el trazo responde al dedo sin que la página se desplace.

Desde ese día corre el reloj de la medición (spec §11): a las 2 y a las 4 semanas se cuentan, en el backup, los días con evidencias.

---

## Self-Review

**1. Cobertura de la spec.** Esto es lo que entra en este plan:

| Spec | Tareas |
|---|---|
| §1 (conceptos y nota) | 2 |
| §2.1 (catálogo y validación) | 3, 7 |
| §2.2 (tablas) | 1 |
| §2.3 (`/today` reescrito) | 11 |
| §3.1 (contrato) | 4, 15 |
| §3.2, solo `eleccion`, `trazo` y `emparejar` | 15, 17, 18 |
| §3.3, `trazo` | 17 |
| §4 (flujo y endpoints) | 8, 9, 10 |
| §5.1 (Hoy) | 11, 19 |
| §5.4 (reproductor) | 14, 16 |
| §5.5 (trazo) | 17 |
| §5.6 (Ajustes) | 12, 20 |
| §5.7, solo glifo, trazo y tablero | 15, 17, 18 |
| §6.1 (hiragana) | 7 |
| §7, la parte de japonés | 5, 6, 7 |
| §8 (errores) | 9, 10, 14, 16 |
| §9 (pruebas) | todas |
| §10 (deploy) | 21 |

Queda para los planes 2 a 4, a propósito:
- §3.3 de `articulo` y de `sombra`, y §6.2 y §6.3 (alemán, inglés): planes 2 y 3;
- §5.2 y §5.3 (Biblioteca y Mapa), con `.k-sabes`, `.k-hueco`, `.k-par` y `.k-btn--redondo`: plan 4;
- §11 (medición): corre sola desde el deploy.

**2. Marcadores pendientes.** No hay TBD ni «agregar validación». Cada paso de código trae el código.

**3. Consistencia de tipos.**
- La forma de contenido de cada generador (tarea 4) coincide con `ContenidoEleccion`, `ContenidoTrazo` y `ContenidoEmparejar` (tareas 15, 17 y 18), incluido `faceta` en `emparejar`.
- `ActividadOut.repaso` sale de `contenido()` (tarea 8) y lo usa la ruta (tarea 16).
- `LeccionRef` es el mismo en `/sesiones` y `/today`.
- `Capacidad` sale de `lib/sesion.ts` y la usan `dinamicas/tipos.ts` y `necesita()`.

**4. Review Focus.** Cada uno de los cinco tiene su test en la tarea que lo implementa:
- doble respuesta: 14 y 16;
- reenvío idempotente: 9;
- corrida abierta: 8 y 11;
- medianoche: 11;
- capacidades apagadas: 14.

