# F-A0 — API para clientes nativos: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que el backend de Klara acepte un cliente que no es un navegador — token Bearer revocable al lado del cookie, Google por ID token, WebSocket autenticado por el primer frame, CORS del WebView, rate limit en login y un endpoint que diga cuándo vence el próximo repaso — sin que el web note nada.

**Architecture:** un segundo `AuthenticationBackend` de fastapi-users (`BearerTransport` + `DatabaseStrategy` sobre una tabla `access_tokens`) registrado junto al de cookie, así `current_active_user` acepta los dos sin tocar rutas. Google nativo verifica el ID token con `pyjwt` (ya instalado) y entra por el **mismo** `UserManager.oauth_callback` que el callback del navegador, para que la regla de invitación se aplique sola. El WS lee el token del frame de handshake que ya existe; el limitador in-memory del waitlist se generaliza y se aplica a las tres rutas de login.

**Tech Stack:** FastAPI, fastapi-users 15 (`DatabaseStrategy`, `BearerTransport`), `fastapi-users-db-sqlalchemy` (`SQLAlchemyAccessTokenDatabase`), SQLAlchemy async + Alembic, `pyjwt[crypto]`, pytest-asyncio con Postgres real (`tests/conftest.py`).

**Spec:** `docs/superpowers/specs/2026-08-29-android-nativo-design.md` — §2 completa (2.1–2.6), §8 (errores), §11 (tests). Esta fase es **solo backend**; el frontend no cambia.

## Global Constraints

- Código de auth: **no se delega** a reasonix/kimi/codex (`auth/*`, `ws_auth.py`, `ratelimit.py`, el cableado en `main.py`). Subagentes Claude sí.
- **Aditivo.** Cero cambios en tablas existentes; el backend de cookie (`auth/backend.py`) no se toca. El web debe seguir idéntico: `test_auth_signup.py`, `test_auth_verify_reset.py`, `test_owner_adoption.py`, `test_waitlist.py` en verde al final de cada task.
- Migración: `20260829_0022_access_tokens.py`, `down_revision = "20260811_0021"`.
- Token Bearer: `lifetime = 180 días` (`auth_bearer_max_age`), sin rotación. Logout = borrar la fila.
- Rate limit: **10 intentos / 5 min por IP** sobre `/auth/jwt/login`, `/auth/bearer/login`, `/auth/google/native` → 429. El waitlist conserva 10 / hora.
- Google: audiencia = `settings.google_oauth_client_id` (el Web Client ID). `email_verified` obligatorio. Invitación ausente → **400** `auth.invite_required` (es lo que hoy lanza `manager.py:210-214`; la spec decía 403 y se corrige en la Task 7).
- Token del WS: **solo** en el primer frame (`{reference_text, language, token?}`); nunca en URL ni headers.
- i18n backend: toda clave nueva en `i18n/messages.py` con las 6 locales (es, en, de, fr, ja, pt).
- Gates locales (los de `scripts/deploy-prod.sh:86-97`): `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run pytest tests/ -q` (Postgres local; `TEST_DATABASE_URL` si no es el default de `conftest.py:16-19`).
- Commits: un commit por task, mensaje en español, con los trailers `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` y `Claude-Session: https://claude.ai/code/session_01JA3gtwcytg8fPuFv5o6CJx`.
- Rama de trabajo: `android-nativo-spec` (donde vive la spec). El PR sale de ahí.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `backend/src/klara/models/access_token.py` (nuevo) | Modelo `AccessToken` (tabla `access_tokens`). |
| `backend/alembic/versions/20260829_0022_access_tokens.py` (nuevo) | Crea `access_tokens`. |
| `backend/src/klara/auth/bearer.py` (nuevo) | `bearer_backend`, `get_access_token_db`, `get_database_strategy`, `make_database_strategy` (sin DI, para el WS), `StrategyDep`. |
| `backend/src/klara/auth/google_native.py` (nuevo) | `verify_google_id_token(id_token, audience) -> GoogleClaims`; `InvalidGoogleToken`. |
| `backend/src/klara/routers/auth_native.py` (nuevo) | `POST /api/v1/auth/google/native`. |
| `backend/src/klara/ratelimit.py` (nuevo) | `RateLimiter`, `client_ip`, `waitlist_limiter`, `login_limiter`, dependencia `login_rate_limit`. |
| `backend/src/klara/config.py` | `auth_bearer_max_age`. |
| `backend/src/klara/auth/users.py` | Registra `[auth_backend, bearer_backend]`. |
| `backend/src/klara/main.py` | Incluye router bearer y google/native; `dependencies=[Depends(login_rate_limit)]` en los routers de login. |
| `backend/src/klara/pronunciation/ws_auth.py` | `authenticate_ws(websocket, settings, token=None)`. |
| `backend/src/klara/routers/pronunciation.py` | Handshake antes de auth; pasa `token`. |
| `backend/src/klara/routers/waitlist.py` | Usa `klara.ratelimit`. |
| `backend/src/klara/routers/srs.py` + `schemas/srs.py` | `GET /srs/next` + `SrsNextOut`. |
| `backend/src/klara/i18n/messages.py` | `auth.google_native.invalid`. |
| `backend/pyproject.toml` + `uv.lock` | `pyjwt[crypto]` como dependencia directa. |
| `docker-compose.prod.yml`, `backend/.env.example`, `.env.example` | Orígenes del WebView en `CORS_ORIGINS`. |
| `backend/tests/conftest.py` | `access_tokens` en el TRUNCATE. |
| `backend/tests/test_auth_bearer.py`, `test_ratelimit_login.py`, `test_auth_google_native.py`, `test_ws_auth.py`, `test_srs_next.py` (nuevos); `test_waitlist.py` (adaptado) | Contratos. |

---

### Task 1: Tabla `access_tokens` — modelo + migración

**Files:**
- Create: `backend/src/klara/models/access_token.py`
- Create: `backend/alembic/versions/20260829_0022_access_tokens.py`
- Modify: `backend/src/klara/models/__init__.py` (import + `__all__`)
- Modify: `backend/tests/conftest.py:75-84` (lista del TRUNCATE)
- Test: `backend/tests/test_auth_bearer.py`

**Interfaces:**
- Produces: `klara.models.AccessToken` con columnas `token: str` (PK, 43 chars), `created_at: datetime` (tz-aware, default `now_utc`), `user_id: UUID` (FK `users.id` CASCADE). Task 2 y Task 5 la consumen vía `SQLAlchemyAccessTokenDatabase(session, AccessToken)`.

- [ ] **Step 1: Test que falla**

`backend/tests/test_auth_bearer.py`:

```python
import uuid

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_access_token_row_roundtrip(db_session, seed_invite):
    """La tabla existe (migración 0022) y el modelo mapea users.id, no user.id."""
    from klara.models import AccessToken, User

    await seed_invite()  # siembra un admin: nos sirve de dueño del token
    owner = (await db_session.execute(select(User))).scalars().first()
    assert owner is not None

    token = "a" * 43
    db_session.add(AccessToken(token=token, user_id=owner.id))
    await db_session.commit()

    row = await db_session.get(AccessToken, token)
    assert row is not None
    assert row.user_id == owner.id
    assert row.created_at.tzinfo is not None
```

- [ ] **Step 2: Verlo fallar**

Run: `cd backend && uv run pytest tests/test_auth_bearer.py::test_access_token_row_roundtrip -q`
Expected: FAIL — `ImportError: cannot import name 'AccessToken' from 'klara.models'`.

- [ ] **Step 3: Modelo**

`backend/src/klara/models/access_token.py`:

```python
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    """Sesión Bearer del app nativo (spec android §2.1).

    Una fila = una sesión revocable: el logout borra la fila y el token muere
    de verdad — a diferencia del JWT del cookie, que vive 30 días pase lo que pase.
    """

    __tablename__ = "access_tokens"

    # Igual que OAuthAccount: la clase base apunta a "user.id"; la tabla es "users".
    user_id: Mapped[GUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="cascade"), nullable=False
    )
```

En `backend/src/klara/models/__init__.py` agregar `from klara.models.access_token import AccessToken` (orden alfabético: antes de `attempts`) y `"AccessToken",` al principio de `__all__`.

- [ ] **Step 4: Migración**

`backend/alembic/versions/20260829_0022_access_tokens.py`:

```python
"""access_tokens — sesiones Bearer revocables del app nativo (F-A0)

Aditiva. Tabla nueva; cero cambios sobre tablas existentes. El transporte de
cookie sigue intacto: esta tabla solo la usa el backend "bearer-db".

Revision ID: 20260829_0022
Revises: 20260811_0021
Create Date: 2026-08-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260829_0022"
down_revision: str | None = "20260811_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_tokens",
        sa.Column("token", sa.String(length=43), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    # El nombre coincide con el que genera `index=True` de la clase base, así
    # el autogenerate de alembic no ve deriva.
    op.create_index("ix_access_tokens_created_at", "access_tokens", ["created_at"])
    op.create_index("ix_access_tokens_user_id", "access_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_access_tokens_user_id", table_name="access_tokens")
    op.drop_index("ix_access_tokens_created_at", table_name="access_tokens")
    op.drop_table("access_tokens")
```

- [ ] **Step 5: `conftest.py` — limpiar la tabla entre tests**

En `backend/tests/conftest.py:78` (el `TRUNCATE`), agregar `access_tokens, ` justo después de `"TRUNCATE audio_cache, ` — el CASCADE desde `users` ya la vaciaría, pero explícito es más legible que depender de la FK.

- [ ] **Step 6: Verlo pasar**

Run: `cd backend && uv run pytest tests/test_auth_bearer.py -q`
Expected: PASS (1 test). La sesión de pytest corre `alembic upgrade head` al arrancar (`conftest.py:66-71`): si la migración está mal, falla aquí.

- [ ] **Step 7: Commit**

```bash
git add backend/src/klara/models/access_token.py backend/src/klara/models/__init__.py backend/alembic/versions/20260829_0022_access_tokens.py backend/tests/conftest.py backend/tests/test_auth_bearer.py
git commit -m "feat(auth): tabla access_tokens para sesiones Bearer revocables (F-A0)"
```

---

### Task 2: Backend Bearer al lado del cookie

**Files:**
- Create: `backend/src/klara/auth/bearer.py`
- Modify: `backend/src/klara/config.py:138-139` (nuevo `auth_bearer_max_age`)
- Modify: `backend/src/klara/auth/users.py:9-12,20-26`
- Modify: `backend/src/klara/main.py:11,149-157`
- Test: `backend/tests/test_auth_bearer.py`

**Interfaces:**
- Consumes: `klara.models.AccessToken` (Task 1); `klara.auth.db.AuthSessionDep`.
- Produces:
  - `bearer_backend: AuthenticationBackend` (name `"bearer-db"`).
  - `get_database_strategy(access_token_db) -> DatabaseStrategy[User, UUID, AccessToken]` (dependencia FastAPI) y `StrategyDep = Annotated[DatabaseStrategy[...], Depends(get_database_strategy)]` — Task 4 la usa para emitir el token.
  - `make_database_strategy(session: AsyncSession) -> DatabaseStrategy[...]` — sin DI, Task 5 la usa en el WS.
  - Rutas `POST /api/v1/auth/bearer/login` (form `username`, `password` → `{"access_token", "token_type": "bearer"}`) y `POST /api/v1/auth/bearer/logout` (204, requiere `Authorization: Bearer`).
  - `Settings.auth_bearer_max_age: int` (segundos).

- [ ] **Step 1: Tests que fallan**

Añadir a `backend/tests/test_auth_bearer.py`:

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy import update

EMAIL = "bearer@example.com"
PASSWORD = "hunter2hunter2"


async def _register(client, seed_invite, app_settings, email: str = EMAIL) -> None:
    app_settings(INITIAL_OWNER_EMAIL="")
    invite = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Bearer",
            "invite_token": invite,
        },
    )
    assert r.status_code == 201, r.text


async def _bearer_login(client, email: str = EMAIL, password: str = PASSWORD):
    return await client.post(
        "/api/v1/auth/bearer/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


@pytest.mark.asyncio
async def test_bearer_login_returns_token_that_opens_me(client, seed_invite, app_settings):
    await _register(client, seed_invite, app_settings)
    r = await _bearer_login(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) == 43
    assert "set-cookie" not in r.headers  # el transporte Bearer no toca cookies

    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200, me.text
    assert me.json()["display_name"] == "Bearer"


@pytest.mark.asyncio
async def test_bearer_login_bad_password_is_400(client, seed_invite, app_settings):
    await _register(client, seed_invite, app_settings)
    r = await _bearer_login(client, password="wrong-wrong-wrong")
    assert r.status_code == 400
    assert r.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


@pytest.mark.asyncio
async def test_bearer_logout_revokes_token(client, seed_invite, app_settings):
    await _register(client, seed_invite, app_settings)
    token = (await _bearer_login(client)).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    out = await client.post("/api/v1/auth/bearer/logout", headers=auth)
    assert out.status_code == 204, out.text

    me = await client.get("/api/v1/me", headers=auth)
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_bearer_expired_token_is_401(client, seed_invite, app_settings, db_session):
    from klara.config import get_settings
    from klara.models import AccessToken

    await _register(client, seed_invite, app_settings)
    token = (await _bearer_login(client)).json()["access_token"]

    too_old = datetime.now(UTC) - timedelta(seconds=get_settings().auth_bearer_max_age + 60)
    await db_session.execute(
        update(AccessToken).where(AccessToken.token == token).values(created_at=too_old)
    )
    await db_session.commit()

    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_cookie_login_unchanged(client, seed_invite, app_settings):
    """El backend nuevo no altera el de cookie: 204 + Set-Cookie, como siempre."""
    await _register(client, seed_invite, app_settings)
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 204, r.text
    assert "klara_session" in r.headers.get("set-cookie", "")
```

- [ ] **Step 2: Verlos fallar**

Run: `cd backend && uv run pytest tests/test_auth_bearer.py -q`
Expected: los cuatro tests de bearer fallan con 404 en `/api/v1/auth/bearer/login`; `test_cookie_login_unchanged` pasa; `test_bearer_expired_token_is_401` falla además por `Settings` sin `auth_bearer_max_age`.

- [ ] **Step 3: Setting**

En `backend/src/klara/config.py`, después de `auth_cookie_max_age` (línea 139):

```python
    # Sesión Bearer del app nativo (spec android §2.1). Larga porque es
    # revocable desde el servidor: el logout borra la fila de access_tokens.
    auth_bearer_max_age: int = 60 * 60 * 24 * 180  # 180 días
```

- [ ] **Step 4: `auth/bearer.py`**

```python
"""Transporte Bearer + estrategia en base de datos para el app nativo.

Convive con el backend de cookie (backend.py) sin tocarlo: FastAPIUsers recibe
los dos y `current_active_user` acepta cualquiera. Spec android §2.1.
"""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi_users.authentication import AuthenticationBackend, BearerTransport
from fastapi_users.authentication.strategy.db import AccessTokenDatabase, DatabaseStrategy
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from klara.auth.db import AuthSessionDep
from klara.config import get_settings
from klara.models import AccessToken, User

BearerStrategy = DatabaseStrategy[User, UUID, AccessToken]


async def get_access_token_db(
    session: AuthSessionDep,
) -> AsyncGenerator[SQLAlchemyAccessTokenDatabase[AccessToken], None]:
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


def make_database_strategy(session: AsyncSession) -> BearerStrategy:
    """Sin inyección de dependencias: el WebSocket (ws_auth.py) trae su sesión."""
    return DatabaseStrategy(
        SQLAlchemyAccessTokenDatabase(session, AccessToken),
        lifetime_seconds=get_settings().auth_bearer_max_age,
    )


def get_database_strategy(
    access_token_db: Annotated[AccessTokenDatabase[AccessToken], Depends(get_access_token_db)],
) -> BearerStrategy:
    return DatabaseStrategy(access_token_db, lifetime_seconds=get_settings().auth_bearer_max_age)


StrategyDep = Annotated[BearerStrategy, Depends(get_database_strategy)]

bearer_transport = BearerTransport(tokenUrl="api/v1/auth/bearer/login")

bearer_backend = AuthenticationBackend(
    name="bearer-db",
    transport=bearer_transport,
    get_strategy=get_database_strategy,
)
```

- [ ] **Step 5: Registrar los dos backends**

`backend/src/klara/auth/users.py`:

```python
from uuid import UUID

from fastapi_users import FastAPIUsers

from klara.auth.backend import auth_backend
from klara.auth.bearer import bearer_backend
from klara.auth.manager import get_user_manager
from klara.models import User

# Dos transportes, una identidad: cookie para el navegador, Bearer para el app
# nativo (spec android §2.1). Cualquier ruta protegida acepta los dos.
fastapi_users: FastAPIUsers[User, UUID] = FastAPIUsers[User, UUID](
    get_user_manager,
    [auth_backend, bearer_backend],
)
```

y en `__all__` agregar `"bearer_backend",` después de `"auth_backend",`. El resto del archivo (`current_active_user`, `current_admin_user`, comentario) queda igual.

- [ ] **Step 6: Rutas en `main.py`**

En `backend/src/klara/main.py`, línea 11, añadir debajo de `from klara.auth.backend import auth_backend`:

```python
from klara.auth.bearer import bearer_backend
```

Y justo después del `include_router` de `get_auth_router(auth_backend)` (líneas 152-156):

```python
    app.include_router(
        fastapi_users.get_auth_router(bearer_backend),
        prefix=f"{auth_prefix}/bearer",
        tags=["auth"],
    )
```

- [ ] **Step 7: Verlos pasar**

Run: `cd backend && uv run pytest tests/test_auth_bearer.py tests/test_auth_signup.py tests/test_owner_adoption.py -q`
Expected: PASS todos.

- [ ] **Step 8: Commit**

```bash
git add backend/src/klara/auth/bearer.py backend/src/klara/auth/users.py backend/src/klara/config.py backend/src/klara/main.py backend/tests/test_auth_bearer.py
git commit -m "feat(auth): transporte Bearer revocable al lado del cookie (F-A0 §2.1)"
```

---

### Task 3: Rate limit en las rutas de login (reutilizando el limitador del waitlist)

**Files:**
- Create: `backend/src/klara/ratelimit.py`
- Modify: `backend/src/klara/routers/waitlist.py:41-56,72-91` (borrar el limitador local; importar el compartido)
- Modify: `backend/tests/test_waitlist.py:6,49-53,92-103,114-120`
- Modify: `backend/src/klara/main.py:5,149-162`
- Test: `backend/tests/test_ratelimit_login.py`

**Interfaces:**
- Produces: `klara.ratelimit.RateLimiter(window_s, max_per_window)` con `.hit(ip, now=None) -> bool` (True = excedido) y `.reset()`; `client_ip(request) -> str`; instancias `waitlist_limiter` (3600 s / 10) y `login_limiter` (300 s / 10); dependencia `login_rate_limit(request)` que lanza 429 solo en las rutas de login. Task 4 aplica la dependencia al router nuevo.

- [ ] **Step 1: Tests que fallan**

`backend/tests/test_ratelimit_login.py`:

```python
import pytest

BAD = {"username": "nobody@example.com", "password": "definitely-wrong"}
FORM = {"Content-Type": "application/x-www-form-urlencoded"}


@pytest.fixture(autouse=True)
def _reset_login_limiter():
    from klara.ratelimit import login_limiter

    login_limiter.reset()
    yield
    login_limiter.reset()


def _xff(ip: str) -> dict[str, str]:
    # El peer del ASGITransport es 127.0.0.1 (loopback = proxy confiable), así
    # que client_ip toma el último hop del XFF: cada test elige su IP.
    return {**FORM, "X-Forwarded-For": ip}


@pytest.mark.asyncio
async def test_eleventh_login_attempt_is_429(client):
    for _ in range(10):
        r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.5"))
        assert r.status_code == 400  # credenciales malas, pero atendida
    r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.5"))
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_other_ip_is_not_affected(client):
    for _ in range(11):
        await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.5"))
    r = await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.6"))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_bearer_login_shares_the_bucket(client):
    for _ in range(10):
        await client.post("/api/v1/auth/jwt/login", data=BAD, headers=_xff("203.0.113.7"))
    r = await client.post("/api/v1/auth/bearer/login", data=BAD, headers=_xff("203.0.113.7"))
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_logout_is_never_counted(client):
    for _ in range(12):
        r = await client.post("/api/v1/auth/jwt/logout", headers=_xff("203.0.113.8"))
        assert r.status_code == 401  # sin sesión, pero nunca 429


def test_window_resets():
    from klara.ratelimit import RateLimiter

    lim = RateLimiter(window_s=300, max_per_window=10)
    for _ in range(10):
        assert lim.hit("1.2.3.4", now=1000.0) is False
    assert lim.hit("1.2.3.4", now=1000.0) is True
    assert lim.hit("1.2.3.4", now=1000.0 + 301) is False
```

- [ ] **Step 2: Verlos fallar**

Run: `cd backend && uv run pytest tests/test_ratelimit_login.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.ratelimit'`.

- [ ] **Step 3: `klara/ratelimit.py`** (el cuerpo de `client_ip` y del contador es el de `waitlist.py:53-86`, movido tal cual)

```python
"""Rate limit in-memory por IP, compartido por waitlist y login.

ponytail: por proceso (un worker en prod; se resetea al reiniciar) y single-hop
X-Forwarded-For (confía en el último hop si el peer inmediato es el proxy del
host). El dict se purga de ventanas expiradas al pasar de 1024 IPs distintas,
así la rotación de IPv6 no crece sin límite. Si hay N workers, cadena de proxies
o abuso real: slowapi con forwarded-allow-ips.
"""

from __future__ import annotations

import ipaddress
import time

from fastapi import HTTPException, Request, status

_MAX_HITS_ENTRIES = 1024


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    xff = request.headers.get("x-forwarded-for")
    if not xff:
        return peer
    try:
        peer_addr = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not (peer_addr.is_loopback or peer_addr.is_private):
        return peer
    candidate = xff.split(",")[-1].strip()
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer
    return candidate


class RateLimiter:
    def __init__(self, window_s: int, max_per_window: int) -> None:
        self.window_s = window_s
        self.max_per_window = max_per_window
        self._hits: dict[str, tuple[int, float]] = {}

    def reset(self) -> None:
        self._hits.clear()

    def hit(self, ip: str, now: float | None = None) -> bool:
        """Registra una petición; True si con ella se excede el cupo."""
        t = now if now is not None else time.monotonic()
        if len(self._hits) > _MAX_HITS_ENTRIES:
            expired = [k for k, (_, start) in self._hits.items() if t - start > self.window_s]
            for k in expired:
                del self._hits[k]
        count, start = self._hits.get(ip, (0, t))
        if t - start > self.window_s:
            count, start = 0, t
        count += 1
        self._hits[ip] = (count, start)
        return count > self.max_per_window


waitlist_limiter = RateLimiter(window_s=3600, max_per_window=10)
# Spec android §2.5: 10 intentos / 5 min por IP sobre las tres rutas de login.
login_limiter = RateLimiter(window_s=300, max_per_window=10)

_LOGIN_PATHS = ("/auth/jwt/login", "/auth/bearer/login", "/auth/google/native")


def login_rate_limit(request: Request) -> None:
    """Dependencia de router: los routers de auth traen también /logout, y ese
    no cuenta — solo se limita lo que adivina contraseñas o tokens."""
    if not request.url.path.endswith(_LOGIN_PATHS):
        return
    if login_limiter.hit(client_ip(request)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS)
```

- [ ] **Step 4: `waitlist.py` usa el compartido**

En `backend/src/klara/routers/waitlist.py`:
- Borrar el bloque `41-56` (comentario ponytail, `_WINDOW_S`, `_MAX_PER_WINDOW`, `_MAX_HITS_ENTRIES`, `_hits`) y las funciones `_client_ip` (53-70) y `_rate_limited` (72-86).
- Quitar `import ipaddress` y `import time` si ya no se usan en el archivo (comprobar con `uv run ruff check`).
- Añadir `from klara.ratelimit import client_ip, waitlist_limiter`.
- En `join_waitlist`, reemplazar
  ```python
      ip = _client_ip(request)
      if _rate_limited(ip):
  ```
  por
  ```python
      if waitlist_limiter.hit(client_ip(request)):
  ```

- [ ] **Step 5: Adaptar `test_waitlist.py`**

- Línea 6: dejar `from klara.routers import waitlist as waitlist_router` solo si algo más lo usa; añadir `from klara import ratelimit`.
- Fixture `_reset_rate_limit` (49-53): `waitlist_router._hits.clear()` → `ratelimit.waitlist_limiter.reset()` (las dos veces).
- `test_client_ip_ignores_xff_from_non_private_peer` y `test_client_ip_uses_last_xff_hop_from_trusted_peer`: `waitlist_router._client_ip(req)` → `ratelimit.client_ip(req)`.
- `test_rate_limit_window_resets` (114-120): 
  ```python
  def test_rate_limit_window_resets():
      ratelimit.waitlist_limiter.reset()
      for _ in range(10):
          assert ratelimit.waitlist_limiter.hit("1.2.3.4", now=1000.0) is False
      assert ratelimit.waitlist_limiter.hit("1.2.3.4", now=1000.0) is True
      assert ratelimit.waitlist_limiter.hit("1.2.3.4", now=1000.0 + 3601) is False
  ```

- [ ] **Step 6: Aplicar a los routers de login en `main.py`**

- Línea 5: `from fastapi import Depends, FastAPI`.
- Debajo de los imports de `klara.*`: `from klara.ratelimit import login_rate_limit`.
- Reemplazar el comentario `# TODO(security): wire slowapi ...` (149-151) por:
  ```python
      # Spec android §2.5: 10 intentos / 5 min por IP en las rutas de login.
      # Como dependencia de router alcanza también a /logout; la dependencia
      # misma filtra por path y solo cuenta las de login.
      login_guard = [Depends(login_rate_limit)]
  ```
- En los dos `include_router` de auth (`get_auth_router(auth_backend)` y `get_auth_router(bearer_backend)`) añadir `dependencies=login_guard,`.

- [ ] **Step 7: Verlos pasar (y que el waitlist siga igual)**

Run: `cd backend && uv run pytest tests/test_ratelimit_login.py tests/test_waitlist.py tests/test_auth_bearer.py -q && uv run ruff check src tests`
Expected: PASS todos; ruff limpio (sin imports muertos en `waitlist.py`).

- [ ] **Step 8: Commit**

```bash
git add backend/src/klara/ratelimit.py backend/src/klara/routers/waitlist.py backend/src/klara/main.py backend/tests/test_waitlist.py backend/tests/test_ratelimit_login.py
git commit -m "feat(auth): rate limit 10/5min por IP en login, reutilizando el limitador del waitlist (F-A0 §2.5)"
```

---

### Task 4: Google nativo — `POST /api/v1/auth/google/native`

**Files:**
- Create: `backend/src/klara/auth/google_native.py`
- Create: `backend/src/klara/routers/auth_native.py`
- Modify: `backend/src/klara/i18n/messages.py:134` (clave nueva antes de `auth.invite_required`)
- Modify: `backend/src/klara/main.py` (import + include)
- Modify: `backend/pyproject.toml:19-21` (+ `pyjwt[crypto]`) y `backend/uv.lock` (`uv lock`)
- Test: `backend/tests/test_auth_google_native.py`

**Interfaces:**
- Consumes: `StrategyDep` (Task 2), `login_rate_limit` (Task 3), `UserManager.oauth_callback` (`auth/manager.py:172`), `UserManagerDep`, `LocaleDep`, `SettingsDep` (`klara/dependencies.py`).
- Produces: `verify_google_id_token(id_token: str, audience: str) -> GoogleClaims(sub, email, exp)`; `InvalidGoogleToken`; ruta `POST /api/v1/auth/google/native` `{id_token}` → `{access_token, token_type}`; 400 / 503 según §8 de la spec.

- [ ] **Step 1: Tests que fallan**

`backend/tests/test_auth_google_native.py`:

```python
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

AUD = "web-client-id.apps.googleusercontent.com"


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _mint(rsa_key, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": AUD,
        "sub": "g-123",
        "email": "invited@example.com",
        "email_verified": True,
        "iat": now,
        "exp": now + 600,
    }
    claims.update(overrides)
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "test-kid"})


@pytest.fixture
def google_keys(monkeypatch, rsa_key):
    """Sustituye la descarga del JWKS de Google por la clave pública local."""
    from klara.auth import google_native

    monkeypatch.setattr(google_native, "_signing_key", lambda _tok: rsa_key.public_key())


# --- verificación pura -------------------------------------------------------


def test_verify_accepts_valid_token(google_keys, rsa_key):
    from klara.auth.google_native import verify_google_id_token

    claims = verify_google_id_token(_mint(rsa_key), AUD)
    assert claims.sub == "g-123"
    assert claims.email == "invited@example.com"
    assert claims.exp > int(time.time())


@pytest.mark.parametrize(
    "override",
    [
        {"aud": "other-client"},
        {"iss": "https://evil.example"},
        {"exp": int(time.time()) - 5},
        {"email_verified": False},
        {"email": ""},
    ],
)
def test_verify_rejects(google_keys, rsa_key, override):
    from klara.auth.google_native import InvalidGoogleToken, verify_google_id_token

    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token(_mint(rsa_key, **override), AUD)


def test_verify_rejects_garbage(google_keys):
    from klara.auth.google_native import InvalidGoogleToken, verify_google_id_token

    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token("not.a.jwt", AUD)


# --- ruta ----------------------------------------------------------------------


async def _register_invited(client, seed_invite, app_settings, email: str) -> None:
    app_settings(INITIAL_OWNER_EMAIL="", GOOGLE_OAUTH_CLIENT_ID=AUD)
    invite = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "hunter2hunter2",
            "display_name": "Invited",
            "invite_token": invite,
        },
    )
    assert r.status_code == 201, r.text


@pytest.mark.asyncio
async def test_native_links_existing_invited_user(client, seed_invite, app_settings, google_keys, rsa_key):
    await _register_invited(client, seed_invite, app_settings, "invited@example.com")

    r = await client.post("/api/v1/auth/google/native", json={"id_token": _mint(rsa_key)})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == "Invited"

    # Segunda vez: mismo sub → login, no duplica cuenta ni falla.
    r2 = await client.post("/api/v1/auth/google/native", json={"id_token": _mint(rsa_key)})
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_native_unknown_email_requires_invite(client, app_settings, google_keys, rsa_key):
    app_settings(INITIAL_OWNER_EMAIL="", GOOGLE_OAUTH_CLIENT_ID=AUD)
    r = await client.post(
        "/api/v1/auth/google/native",
        json={"id_token": _mint(rsa_key, email="stranger@example.com", sub="g-999")},
    )
    assert r.status_code == 400
    assert "invitaci" in r.json()["detail"]  # auth.invite_required (es)


@pytest.mark.asyncio
async def test_native_invalid_token_is_400(client, app_settings, google_keys, rsa_key):
    app_settings(INITIAL_OWNER_EMAIL="", GOOGLE_OAUTH_CLIENT_ID=AUD)
    r = await client.post(
        "/api/v1/auth/google/native",
        json={"id_token": _mint(rsa_key, aud="other-client")},
    )
    assert r.status_code == 400
    assert "Google" in r.json()["detail"]  # auth.google_native.invalid


@pytest.mark.asyncio
async def test_native_without_client_id_is_503(client, app_settings, google_keys, rsa_key):
    app_settings(GOOGLE_OAUTH_CLIENT_ID=None)
    r = await client.post("/api/v1/auth/google/native", json={"id_token": _mint(rsa_key)})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_native_adopts_legacy_owner(
    client, app_settings, google_keys, rsa_key, legacy_owner_with_story
):
    """Mismo camino que el callback del navegador: el dueño bootstrap adopta la
    fila legacy (email NULL) y sale superuser."""
    app_settings(INITIAL_OWNER_EMAIL="owner@example.com", GOOGLE_OAUTH_CLIENT_ID=AUD)
    r = await client.post(
        "/api/v1/auth/google/native",
        json={"id_token": _mint(rsa_key, email="owner@example.com", sub="g-owner")},
    )
    assert r.status_code == 200, r.text
    me = await client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["is_superuser"] is True
```

- [ ] **Step 2: Verlos fallar**

Run: `cd backend && uv run pytest tests/test_auth_google_native.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'klara.auth.google_native'`.

- [ ] **Step 3: Dependencia explícita**

En `backend/pyproject.toml`, después de `"httpx-oauth>=0.15",`: `"pyjwt[crypto]>=2.9",`. Luego `cd backend && uv lock` (ya está instalado como transitiva de fastapi-users; esto solo lo declara, el lock cambia una línea).

- [ ] **Step 4: `auth/google_native.py`**

```python
"""Verificación del ID token de Google que entrega el Credential Manager del app
nativo (spec android §2.2).

Sin dependencia nueva: pyjwt[crypto] ya viene con fastapi-users. La firma se
comprueba contra el JWKS público de Google; la audiencia es el Web Client ID
(el mismo que usa el flujo del navegador), porque el plugin del app se
inicializa con ese id y Google lo pone en `aud`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})

_jwks_client: PyJWKClient | None = None


class InvalidGoogleToken(Exception):
    """Firma, audiencia, emisor, expiración o email no verificado."""


@dataclass(frozen=True)
class GoogleClaims:
    sub: str
    email: str
    exp: int


def _signing_key(id_token: str) -> Any:
    """Clave pública de Google para este token (cacheada por PyJWKClient).
    Separada para que los tests la sustituyan por una clave local."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True)
    return _jwks_client.get_signing_key_from_jwt(id_token).key


def verify_google_id_token(id_token: str, audience: str) -> GoogleClaims:
    try:
        key = _signing_key(id_token)
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=audience,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as e:
        raise InvalidGoogleToken(str(e)) from e
    # `issuer=` de pyjwt acepta lista solo en versiones recientes; comparar a mano
    # es una línea y no depende de la versión.
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise InvalidGoogleToken("issuer")
    email = claims.get("email")
    if claims.get("email_verified") is not True or not email:
        raise InvalidGoogleToken("email not verified")
    return GoogleClaims(sub=str(claims["sub"]), email=str(email), exp=int(claims["exp"]))
```

- [ ] **Step 5: i18n**

En `backend/src/klara/i18n/messages.py`, antes de `"auth.invite_required": {` (línea 134):

```python
    "auth.google_native.invalid": {
        "es": "No pudimos validar tu cuenta de Google. Inténtalo de nuevo.",
        "en": "We couldn't validate your Google account. Please try again.",
        "de": "Dein Google-Konto konnte nicht bestätigt werden. Bitte versuche es erneut.",
        "fr": "Impossible de valider ton compte Google. Réessaie.",
        "ja": "Google アカウントを確認できませんでした。もう一度お試しください。",
        "pt": "Não conseguimos validar a tua conta Google. Tenta de novo.",
    },
```

- [ ] **Step 6: `routers/auth_native.py`**

```python
"""Google Sign-In del app nativo: ID token → sesión Bearer (spec android §2.2).

Entra por el MISMO UserManager.oauth_callback que el callback del navegador:
ahí viven la regla de invitación y la adopción del dueño legacy. Nunca se crea
el usuario a mano.
"""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from klara.auth import google_native
from klara.auth.bearer import StrategyDep
from klara.dependencies import LocaleDep, SettingsDep, UserManagerDep
from klara.i18n import t

router = APIRouter(prefix="/auth/google", tags=["auth"])


class GoogleNativeIn(BaseModel):
    id_token: str


class BearerOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/native", response_model=BearerOut)
async def google_native_login(
    payload: GoogleNativeIn,
    request: Request,
    settings: SettingsDep,
    locale: LocaleDep,
    user_manager: UserManagerDep,
    strategy: StrategyDep,
) -> BearerOut:
    if not settings.google_oauth_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        claims = google_native.verify_google_id_token(
            payload.id_token, settings.google_oauth_client_id
        )
    except google_native.InvalidGoogleToken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("auth.google_native.invalid", locale),
        ) from None
    # access_token = el propio id_token: la columna de oauth_accounts es NOT NULL
    # y este flujo no tiene access token de Google (decisión deliberada, spec §2.2).
    user = await user_manager.oauth_callback(
        "google",
        payload.id_token,
        claims.sub,
        claims.email,
        expires_at=claims.exp,
        request=request,
        associate_by_email=True,
        is_verified_by_default=True,
    )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=t("auth.google_native.invalid", locale),
        )
    token = await strategy.write_token(user)
    return BearerOut(access_token=token)
```

`"google"` es el `name` del `GoogleOAuth2` de httpx-oauth que usa `auth/oauth_google.py` — el mismo `oauth_name` con el que el callback del navegador guarda la fila, así una cuenta enlazada por web entra por el app y viceversa.

- [ ] **Step 7: Incluir el router**

`backend/src/klara/routers/__init__.py` está vacío a propósito (los routers se importan como submódulos); no se toca. En `backend/src/klara/main.py`: en el bloque `from klara.routers import (...)` añadir `auth_native` (orden alfabético); después del `include_router(taller.router, ...)`:
  ```python
      app.include_router(auth_native.router, prefix="/api/v1", dependencies=login_guard)
  ```

- [ ] **Step 8: Verlos pasar**

Run: `cd backend && uv run pytest tests/test_auth_google_native.py tests/test_owner_adoption.py tests/test_ratelimit_login.py -q`
Expected: PASS. Si `test_native_adopts_legacy_owner` falla, leer `manager.py:284-323` (`_adopt_legacy_if_owner_oauth`) antes de tocar nada: la adopción por OAuth ya existe para el navegador y el endpoint solo la reutiliza.

- [ ] **Step 9: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/klara/auth/google_native.py backend/src/klara/routers/auth_native.py backend/src/klara/i18n/messages.py backend/src/klara/main.py backend/tests/test_auth_google_native.py
git commit -m "feat(auth): Google nativo por ID token → sesión Bearer, mismo oauth_callback (F-A0 §2.2)"
```

---

### Task 5: WebSocket — token en el primer frame

**Files:**
- Modify: `backend/src/klara/pronunciation/ws_auth.py:1-8,28-55`
- Modify: `backend/src/klara/routers/pronunciation.py:270-300`
- Test: `backend/tests/test_ws_auth.py`

**Interfaces:**
- Consumes: `make_database_strategy(session)` (Task 2).
- Produces: `authenticate_ws(websocket, settings, token: str | None = None) -> User | None` — cookie primero; si no hay cookie, `token`. El endpoint `stream` acepta `{"reference_text", "language", "token"?}` como handshake y autentica **después** de leerlo.

- [ ] **Step 1: Tests que fallan**

`backend/tests/test_ws_auth.py`:

```python
import pytest

EMAIL = "ws@example.com"
PASSWORD = "hunter2hunter2"


class FakeWS:
    def __init__(self, cookies: dict[str, str] | None = None, origin: str | None = None):
        self.cookies = cookies or {}
        self.headers = {"origin": origin} if origin else {}
        self.accepted = False
        self.closed_code: int | None = None
        self._handshake: dict | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int) -> None:
        self.closed_code = code

    def queue_handshake(self, msg: dict) -> None:
        self._handshake = msg

    async def receive_json(self) -> dict:
        assert self._handshake is not None
        return self._handshake


async def _register(client, seed_invite, app_settings) -> None:
    app_settings(INITIAL_OWNER_EMAIL="")
    invite = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "display_name": "WS",
            "invite_token": invite,
        },
    )
    assert r.status_code == 201, r.text


async def _cookie(client) -> str:
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 204
    return r.headers["set-cookie"].split(";")[0].split("=", 1)[1]


async def _bearer(client) -> str:
    r = await client.post(
        "/api/v1/auth/bearer/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_cookie_still_authenticates(client, seed_invite, app_settings):
    from klara.config import get_settings
    from klara.pronunciation.ws_auth import authenticate_ws

    await _register(client, seed_invite, app_settings)
    settings = get_settings()
    ws = FakeWS(cookies={settings.auth_cookie_name: await _cookie(client)})
    user = await authenticate_ws(ws, settings)
    assert user is not None and user.email == EMAIL


@pytest.mark.asyncio
async def test_bearer_token_authenticates(client, seed_invite, app_settings):
    from klara.config import get_settings
    from klara.pronunciation.ws_auth import authenticate_ws

    await _register(client, seed_invite, app_settings)
    token = await _bearer(client)
    user = await authenticate_ws(FakeWS(), get_settings(), token=token)
    assert user is not None and user.email == EMAIL


@pytest.mark.asyncio
async def test_revoked_bearer_token_is_rejected(client, seed_invite, app_settings):
    from klara.config import get_settings
    from klara.pronunciation.ws_auth import authenticate_ws

    await _register(client, seed_invite, app_settings)
    token = await _bearer(client)
    out = await client.post(
        "/api/v1/auth/bearer/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert out.status_code == 204
    assert await authenticate_ws(FakeWS(), get_settings(), token=token) is None


@pytest.mark.asyncio
async def test_garbage_or_nothing_is_rejected(client):
    from klara.config import get_settings
    from klara.pronunciation.ws_auth import authenticate_ws

    settings = get_settings()
    assert await authenticate_ws(FakeWS(), settings) is None
    assert await authenticate_ws(FakeWS(), settings, token="x" * 43) is None


@pytest.mark.asyncio
async def test_stream_reads_handshake_before_auth_and_passes_token(client, monkeypatch):
    """Orden nuevo: origin-gate → accept → handshake → auth. Con token malo cierra
    con WS_CLOSE_AUTH; con auth OK y sin Azure cierra con WS_CLOSE_FAILURE."""
    from klara.pronunciation.streaming import WS_CLOSE_AUTH, WS_CLOSE_FAILURE
    from klara.routers import pronunciation as pron

    seen: dict[str, str | None] = {}

    async def fake_auth(websocket, settings, token=None):
        seen["token"] = token
        return None

    monkeypatch.setattr(pron, "authenticate_ws", fake_auth)
    ws = FakeWS(origin="http://localhost:5173")
    ws.queue_handshake({"reference_text": "Hallo", "language": "de", "token": "abc"})
    await pron.stream(ws)
    assert ws.accepted is True
    assert seen["token"] == "abc"
    assert ws.closed_code == WS_CLOSE_AUTH

    class _User:
        id = "00000000-0000-0000-0000-000000000001"
        is_active = True

    async def ok_auth(websocket, settings, token=None):
        return _User()

    monkeypatch.setattr(pron, "authenticate_ws", ok_auth)
    ws2 = FakeWS(origin="http://localhost:5173")
    ws2.queue_handshake({"reference_text": "Hallo", "language": "de"})
    await pron.stream(ws2)  # sin AZURE_SPEECH_KEY en tests → cierre "failure"
    assert ws2.closed_code == WS_CLOSE_FAILURE


@pytest.mark.asyncio
async def test_stream_rejects_non_string_token(client):
    from klara.pronunciation.streaming import WS_CLOSE_FAILURE
    from klara.routers import pronunciation as pron

    ws = FakeWS(origin="http://localhost:5173")
    ws.queue_handshake({"reference_text": "Hallo", "language": "de", "token": 42})
    await pron.stream(ws)
    assert ws.closed_code == WS_CLOSE_FAILURE
```

- [ ] **Step 2: Verlos fallar**

Run: `cd backend && uv run pytest tests/test_ws_auth.py -q`
Expected: `test_bearer_token_authenticates` falla con `TypeError: authenticate_ws() got an unexpected keyword argument 'token'`; `test_stream_reads_handshake_before_auth_and_passes_token` falla en `seen["token"]` (hoy autentica antes del handshake).

- [ ] **Step 3: `ws_auth.py`**

Docstring del módulo: sustituir la primera frase por

```python
"""Autenticación del WebSocket de streaming: cookie (navegador) o token Bearer
del app nativo, leído del primer frame (spec android §2.3).

El navegador manda la cookie httponly sola en el upgrade; el app no tiene
cookie y manda el token dentro del handshake JSON — nunca en la URL (se filtra
a logs) ni en headers (el WebSocket del navegador no permite fijarlos). La
allowlist de Origin es defensa en profundidad encima de las dos.
"""
```

Añadir `from klara.auth.bearer import make_database_strategy` y reescribir `authenticate_ws`:

```python
async def authenticate_ws(
    websocket: WebSocket, settings: Settings, token: str | None = None
) -> User | None:
    """Cookie primero; si no hay, el token Bearer del handshake. None si nada vale.

    Sesión propia vía get_session() (el endpoint WS no tiene DI por petición);
    cada generador de la cadena get_session -> get_user_db -> get_user_manager
    va en contextlib.aclosing() para que su cierre corra antes de retornar.
    """
    cookie = websocket.cookies.get(settings.auth_cookie_name)
    if not cookie and not token:
        return None
    async with contextlib.aclosing(get_session()) as sessions:
        async for session in sessions:
            async with contextlib.aclosing(get_user_db(session)) as user_dbs:
                async for user_db in user_dbs:
                    async with contextlib.aclosing(
                        get_user_manager(user_db, settings, session)
                    ) as managers:
                        async for user_manager in managers:
                            if cookie:
                                user = await auth_backend.get_strategy().read_token(
                                    cookie, user_manager
                                )
                            else:
                                user = await make_database_strategy(session).read_token(
                                    token, user_manager
                                )
                            return user if (user and user.is_active) else None
    return None
```

- [ ] **Step 4: Endpoint — handshake antes de auth**

En `backend/src/klara/routers/pronunciation.py`, el inicio de `stream` (líneas 274-300) queda así (el bloque de caps y el `try/finally` de la sesión no cambian; el handshake sale del `try` y sube):

```python
    if not origin_allowed(websocket, settings):
        await websocket.close(code=WS_CLOSE_AUTH)
        return
    await websocket.accept()  # accept first so the app close code reaches the client
    # Handshake primero: el primer frame trae reference_text, language y — para
    # el app nativo — el token Bearer (spec android §2.3). Se lee ANTES de
    # autenticar porque el token viene dentro; un peer sin credenciales solo
    # nos cuesta este receive con timeout, y el origin-gate ya lo filtró.
    try:
        handshake = await asyncio.wait_for(
            websocket.receive_json(), timeout=settings.pron_stream_send_timeout_s
        )
        reference_text = handshake["reference_text"]
        language = handshake["language"]
        token = handshake.get("token")
        if not (isinstance(reference_text, str) and isinstance(language, str)):
            raise TypeError("handshake fields must be strings")
        if token is not None and not isinstance(token, str):
            raise TypeError("token must be a string")
    except Exception:
        await _safe_close(websocket, WS_CLOSE_FAILURE)
        return
    user = await authenticate_ws(websocket, settings, token=token)
    if user is None:
        await _safe_close(websocket, WS_CLOSE_AUTH)
        return
    if not settings.azure_speech_configured:
        await _safe_close(websocket, WS_CLOSE_FAILURE)  # client falls back to batch
        return
```

y dentro del `try:` que sigue a `_active_per_user[uid] += 1`, **borrar** el bloque de handshake antiguo (el comentario `# Handshake: first client frame...` y su `try/except`), dejando que empiece directamente en `recognizer = _build_stream_recognizer(settings, reference_text, language)`.

- [ ] **Step 5: Verlos pasar (y el resto del streaming)**

Run: `cd backend && uv run pytest tests/test_ws_auth.py tests/test_pronunciation_stream.py tests/test_pronunciation.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/pronunciation/ws_auth.py backend/src/klara/routers/pronunciation.py backend/tests/test_ws_auth.py
git commit -m "feat(pronunciation): el WS acepta el token Bearer en el primer frame (F-A0 §2.3)"
```

---

### Task 6: `GET /api/v1/srs/next`

**Files:**
- Modify: `backend/src/klara/schemas/srs.py` (nuevo `SrsNextOut`)
- Modify: `backend/src/klara/routers/srs.py:1-24,83` (imports + ruta nueva antes de `due_cards`)
- Test: `backend/tests/test_srs_next.py`

**Interfaces:**
- Produces: `GET /api/v1/srs/next` → `{"due_now": int, "next_due_at": datetime | null}` (unión de `user_cards` y `study_cards` no archivadas). Lo consume F-A2 (recordatorio local).

- [ ] **Step 1: Tests que fallan**

`backend/tests/test_srs_next.py`:

```python
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

EMAIL = "next@example.com"
PASSWORD = "hunter2hunter2"


async def _login(client, seed_invite, app_settings) -> dict[str, str]:
    app_settings(INITIAL_OWNER_EMAIL="")
    invite = await seed_invite(email=None)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": EMAIL,
            "password": PASSWORD,
            "display_name": "Next",
            "invite_token": invite,
        },
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 204
    return {"Cookie": r.headers["set-cookie"].split(";")[0]}


async def _user_id(db_session) -> uuid.UUID:
    from klara.models import User

    user = (await db_session.execute(select(User).where(User.email == EMAIL))).scalar_one()
    return user.id


async def _add_user_card(db_session, user_id, next_review_at):
    from klara.models import UserCard, VocabItem
    from klara.models.enums import PartOfSpeech

    vocab = VocabItem(
        id=uuid.uuid4(),
        language="de",
        lemma=f"wort-{uuid.uuid4().hex[:6]}",
        pos=PartOfSpeech.NOUN,
        translations={"es": "palabra"},
        example_target=None,
    )
    db_session.add(vocab)
    await db_session.flush()
    db_session.add(
        UserCard(
            id=uuid.uuid4(), user_id=user_id, vocab_item_id=vocab.id, next_review_at=next_review_at
        )
    )
    await db_session.commit()


async def _add_study_card(db_session, user_id, next_review_at, archived: bool = False):
    from klara.models import StudyCard

    db_session.add(
        StudyCard(
            id=uuid.uuid4(),
            user_id=user_id,
            front="f",
            back="b",
            tags=[],
            batch_id=uuid.uuid4(),
            next_review_at=next_review_at,
            archived_at=datetime.now(UTC) if archived else None,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_next_requires_auth(client):
    assert (await client.get("/api/v1/srs/next")).status_code == 401


@pytest.mark.asyncio
async def test_next_empty(client, seed_invite, app_settings):
    headers = await _login(client, seed_invite, app_settings)
    r = await client.get("/api/v1/srs/next", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"due_now": 0, "next_due_at": None}


@pytest.mark.asyncio
async def test_next_counts_due_and_finds_earliest_future(client, seed_invite, app_settings, db_session):
    headers = await _login(client, seed_invite, app_settings)
    uid = await _user_id(db_session)
    now = datetime.now(UTC)
    in_2h = (now + timedelta(hours=2)).replace(microsecond=0)
    in_1d = (now + timedelta(days=1)).replace(microsecond=0)

    await _add_user_card(db_session, uid, next_review_at=None)  # NULL = vencida (srs.py:95)
    await _add_user_card(db_session, uid, next_review_at=in_1d)
    await _add_study_card(db_session, uid, next_review_at=now - timedelta(minutes=1))  # vencida
    await _add_study_card(db_session, uid, next_review_at=in_2h)
    await _add_study_card(db_session, uid, next_review_at=now + timedelta(minutes=5), archived=True)

    r = await client.get("/api/v1/srs/next", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["due_now"] == 2
    assert datetime.fromisoformat(body["next_due_at"]) == in_2h
```

- [ ] **Step 2: Verlos fallar**

Run: `cd backend && uv run pytest tests/test_srs_next.py -q`
Expected: `test_next_requires_auth` pasa por accidente (404 ≠ 401 → en realidad FALLA con 404); los otros dos fallan con 404.

- [ ] **Step 3: Schema**

En `backend/src/klara/schemas/srs.py`, al final:

```python
class SrsNextOut(BaseModel):
    """Lo que el recordatorio del app necesita (spec android §2.6)."""

    due_now: int
    next_due_at: datetime | None
```

(`datetime` ya está importado en ese archivo para `CardOut.next_review_at`; si no, `from datetime import datetime`.)

- [ ] **Step 4: Ruta**

En `backend/src/klara/routers/srs.py`:
- `from sqlalchemy import func, or_, select`
- `from klara.models import Review, StudyCard, UserCard, VocabItem`
- `SrsNextOut` en el import de `klara.schemas.srs`.
- Antes de `@router.get("/cards/due", ...)`:

```python
@router.get("/next", response_model=SrsNextOut)
async def next_due(db: DBSession, user: CurrentUser) -> SrsNextOut:
    """Cuántas vencen ya y cuándo vence la próxima, sumando la caja de alemán
    (user_cards; NULL cuenta como vencida, igual que /cards/due) y las tarjetas
    del taller no archivadas. Solo lectura; lo consume el recordatorio del app."""
    now = datetime.now(UTC)
    due_de = await db.scalar(
        select(func.count())
        .select_from(UserCard)
        .where(
            UserCard.user_id == user.id,
            or_(UserCard.next_review_at.is_(None), UserCard.next_review_at <= now),
        )
    )
    due_taller = await db.scalar(
        select(func.count())
        .select_from(StudyCard)
        .where(
            StudyCard.user_id == user.id,
            StudyCard.archived_at.is_(None),
            StudyCard.next_review_at <= now,
        )
    )
    next_de = await db.scalar(
        select(func.min(UserCard.next_review_at)).where(
            UserCard.user_id == user.id, UserCard.next_review_at > now
        )
    )
    next_taller = await db.scalar(
        select(func.min(StudyCard.next_review_at)).where(
            StudyCard.user_id == user.id,
            StudyCard.archived_at.is_(None),
            StudyCard.next_review_at > now,
        )
    )
    candidates = [d for d in (next_de, next_taller) if d is not None]
    return SrsNextOut(
        due_now=(due_de or 0) + (due_taller or 0),
        next_due_at=min(candidates) if candidates else None,
    )
```

- [ ] **Step 5: Verlos pasar**

Run: `cd backend && uv run pytest tests/test_srs_next.py tests/test_practice_queue.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/klara/schemas/srs.py backend/src/klara/routers/srs.py backend/tests/test_srs_next.py
git commit -m "feat(srs): GET /srs/next — vencidas ahora y próximo vencimiento, alemán + taller (F-A0 §2.6)"
```

---

### Task 7: Orígenes del WebView, correcciones a la spec y gates completos

**Files:**
- Modify: `docker-compose.prod.yml:38`
- Modify: `backend/.env.example:63`, `.env.example:78`
- Modify: `docs/superpowers/specs/2026-08-29-android-nativo-design.md` (§2.2, §2.4, §8)

- [ ] **Step 1: CORS en prod y en los ejemplos**

`docker-compose.prod.yml:38`:

```yaml
      # Los dos últimos son el origen del WebView del app nativo (Android e iOS).
      # Seguro con allow_credentials: la cookie es SameSite=Strict y localhost no
      # es same-site con sdar.dev; el Bearer exige el token. Spec android §2.4.
      CORS_ORIGINS: "https://klara.sdar.dev,https://localhost,capacitor://localhost"
```

`backend/.env.example:63` y `.env.example:78`: dejar el valor de dev como está y añadir debajo una línea de comentario:

```
# App nativo (Capacitor): en prod se suman https://localhost y capacitor://localhost (ver docker-compose.prod.yml).
```

- [ ] **Step 2: Corregir la spec**

En `docs/superpowers/specs/2026-08-29-android-nativo-design.md`:
- §2.2, viñeta "Errores": `403 \`auth.invite_required\`` → `400 \`auth.invite_required\`` y añadir "(es lo que lanza `manager.py:210-214`)".
- §2.4, última frase: sustituir "El cambio de `CORS_ORIGINS` en la caja es un paso manual del despliegue de F-A0 (el script `deploy-prod.sh` no toca el `.env` de prod, a propósito)." por "`CORS_ORIGINS` de prod vive en `docker-compose.prod.yml:38`, así que el cambio va en el PR y lo aplica el despliegue normal."
- §8, fila "Google sin invitación": `403` → `400`.

- [ ] **Step 3: Gates completos**

Run:
```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && uv run pytest tests/ -q
cd ../frontend && npm run typecheck && npm run i18n:check && npm run test
```
Expected: todo verde. Si `ruff format --check` marca archivos nuevos, `uv run ruff format src tests` y volver a correr.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.prod.yml backend/.env.example .env.example docs/superpowers/specs/2026-08-29-android-nativo-design.md
git commit -m "chore(cors): orígenes del WebView en prod; spec §2.2/§2.4/§8 al día (F-A0 §2.4)"
```

---

### Task 8: PR, despliegue y smoke (lo hace el dueño)

**Files:** ninguno.

- [ ] **Step 1: PR** desde `android-nativo-spec` a `main` con la spec, este plan y los siete commits. Título: `F-A0 — API para clientes nativos (Bearer, Google por ID token, WS por frame, rate limit, /srs/next)`.

- [ ] **Step 2: Despliegue** con `scripts/deploy-prod.sh` (corre los gates otra vez, hace backup, construye, sube). Alembic aplica `20260829_0022` en el arranque del backend según el flujo habitual del script.

- [ ] **Step 3: Smoke en web** (`https://klara.sdar.dev`): login con contraseña, login con Google, grabar una frase con streaming en `/review`, cerrar sesión. Nada debe haber cambiado.

- [ ] **Step 4: Smoke de la API nueva** desde la PC (sustituir credenciales):

```bash
curl -s -X POST https://klara.sdar.dev/api/v1/auth/bearer/login -d "username=<email>&password=<pw>"
# → {"access_token":"...","token_type":"bearer"}
curl -s https://klara.sdar.dev/api/v1/me -H "Authorization: Bearer <token>"      # 200
curl -s https://klara.sdar.dev/api/v1/srs/next -H "Authorization: Bearer <token>" # {"due_now":N,"next_due_at":...}
curl -s -X POST https://klara.sdar.dev/api/v1/auth/bearer/logout -H "Authorization: Bearer <token>" -o /dev/null -w "%{http_code}\n"  # 204
curl -s https://klara.sdar.dev/api/v1/me -H "Authorization: Bearer <token>" -o /dev/null -w "%{http_code}\n"  # 401
```

- [ ] **Step 5: Gate de F-A0 cumplido** → abrir el plan de F-A1 (el cascarón).

---

## Self-review del plan

- **Cobertura de la spec §2:** 2.1 → Tasks 1-2; 2.2 → Task 4; 2.3 → Task 5; 2.4 → Task 7; 2.5 → Task 3; 2.6 → Task 6. §8 (errores 400/503/401/429) cubiertos por los tests de Tasks 2-5. §11 backend: los cinco archivos de test nombrados en la spec existen aquí (`test_ratelimit_login.py` cubre lo que la spec llama así; `test_ws_auth.py` es el nombre real del de WS porque `test_pronunciation_stream.py` no toca la DB).
- **Sin placeholders:** cada step trae el código; las adaptaciones de `test_waitlist.py` y `main.py` van con el texto exacto a sustituir.
- **Consistencia de nombres:** `bearer_backend`, `StrategyDep`, `make_database_strategy`, `login_rate_limit`, `login_guard`, `waitlist_limiter`, `login_limiter`, `client_ip`, `verify_google_id_token`, `InvalidGoogleToken`, `GoogleClaims`, `authenticate_ws(..., token=None)`, `SrsNextOut` — mismos nombres en definición, uso y tests.
- **Riesgos señalados:** la adopción del dueño legacy por Google nativo (Task 4, Step 8) depende de `_adopt_legacy_if_owner_oauth`, que ya existe para el navegador; el test lo cubre y el step dice qué leer si falla.
