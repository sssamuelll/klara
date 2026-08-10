# Puerta de entrada v4 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Landing editorial con waitlist + funnel auth completo re-vestido al design system v4 + onboarding armonizado, según `docs/superpowers/specs/2026-08-10-puerta-entrada-v4-design.md`.

**Architecture:** Las 5 rutas auth salen del `LegacyShell` a un `AuthShell` nuevo (patrón `m3-app` sin TabBar, el de `/estudiar/:id`). La raíz `/` gana un `RootGate`: sin sesión → `Landing`; con sesión → Inicio como hoy. Único cambio de dominio: tabla `waitlist_signups` + router `waitlist.py` (público idempotente + admin). Onboarding: solo CSS.

**Tech Stack:** React+TS+Vite (vitest solo `src/**/*.test.ts`), FastAPI+SQLAlchemy async+Alembic, pytest-asyncio con cookie auth.

## Global Constraints

- Mobile-first 430px / `100dvh`; desktop hereda frame centrado (`border-inline` ≥520px).
- Identidad: serif editorial (`--font-serif`), papel/tinta, UN acento bermellón, hairlines 1px. Sin gradientes, sin gamification, sin hype. Copy sin exclamaciones ni emoji, sentence case.
- i18n: NI UN string duro. Claves nuevas en `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json` en el mismo PR; es es master. ja: puntuación japonesa (。) y sin espacio en "Klaraが". Gate: `npm run i18n:check`.
- A11y en todo lo nuevo: `label htmlFor` + `id` en inputs, `role="alert"` en errores, focus visible, botones reales.
- **Archivos sensibles (regla saver): todo lo de backend auth/admin (`routers/waitlist.py`, `main.py`, conftest) lo escribe Claude, no un delegado.**
- Gates por tarea (Actions OFF; el remoto rojo es esperado):
  - Backend (desde `backend/`): `uv run pytest tests/ -v` · `uv run ruff check src tests` · `uv run ruff format --check src tests`
  - Frontend (desde `frontend/`): `npm run typecheck` · `npm test` · `npm run i18n:check` · `npm run build`
- Un PR por bloque (6 PRs). Samuel mergea — no hay self-merge. Rama por PR, `gh pr create`, body termina con `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

---

## PR1 — AuthShell + Login (`feat/pe-authshell-login`)

### Task 1: `auth.css` + `AuthShell` + mover rutas

**Files:**
- Create: `frontend/src/styles/auth.css`
- Modify: `frontend/src/main.tsx:14` (import nuevo)
- Modify: `frontend/src/App.tsx` (AuthShell + grupo de rutas; LegacyShell L30-47, grupo legacy L131-193)

**Interfaces:**
- Produces: clases `.auth-page`, `.auth-title`, `.auth-sub`, `.auth-form`, `.auth-label`, `.auth-input`, `.auth-actions`, `.auth-links` — las consumen Tasks 2-4. Componente `AuthShell` (layout con `<Outlet/>`).

- [ ] **Step 1: Crear `frontend/src/styles/auth.css`**

```css
/* Puerta de entrada v4 — pantallas auth (AuthShell). Solo tokens de tokens.css. */

.auth-page {
  overflow-y: auto;
  gap: var(--space-4);
}

.auth-title {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  font-size: var(--t-h2);
  line-height: var(--lh-tight);
  letter-spacing: var(--tracking-tight);
  margin: var(--space-5) 0 var(--space-3);
  color: var(--ink);
}

.auth-sub {
  font-family: var(--font-serif);
  font-size: var(--t-body);
  line-height: var(--lh-read);
  color: var(--ink-2);
  margin: 0 0 var(--space-3);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.auth-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: var(--tracking-mark);
  text-transform: uppercase;
  color: var(--ink-3);
}

.auth-input {
  width: 100%;
  font-family: var(--font-serif);
  font-size: var(--t-read);
  line-height: 1.4;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--rule);
  border-radius: 0;
  padding: 10px 0;
  color: var(--ink);
}

.auth-input:focus-visible {
  outline: none;
  border-bottom-color: var(--ink);
}

.auth-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: var(--space-4);
}

.auth-links {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: var(--tracking-mark);
  text-transform: uppercase;
  margin-top: var(--space-4);
}

.auth-links a { color: var(--ink-3); }
.auth-links a:hover { color: var(--ink); }
```

- [ ] **Step 2: Importar la hoja en `frontend/src/main.tsx`** — añadir tras la línea 14 (`perfil-aprendizaje.css`):

```ts
import "./styles/auth.css";
```

- [ ] **Step 3: `AuthShell` en `App.tsx`** — junto a `V4Shell` (L49-56):

```tsx
function AuthShell() {
  return (
    <div className="m3-app">
      <div className="m3-page auth-page">
        <header className="m3-top">
          <span className="marca">
            <span className="wordmark">Klara</span>
          </span>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Mover las 5 rutas** — sacar `/login`, `/signup`, `/forgot`, `/reset`, `/verify` del grupo `<Route element={<LegacyShell />}>` (L131-193) a un grupo nuevo:

```tsx
<Route element={<AuthShell />}>
  <Route path="/login" element={<Login />} />
  <Route path="/signup" element={<Signup />} />
  <Route path="/forgot" element={<ForgotPassword />} />
  <Route path="/reset" element={<ResetPassword />} />
  <Route path="/verify" element={<VerifyEmail />} />
</Route>
```

(Los elementos son los mismos que ya están; solo cambia el shell. `/onboarding` y `/settings` NO se mueven.)

- [ ] **Step 5: Gates frontend** — `npm run typecheck && npm test && npm run i18n:check && npm run build`. Expected: verde (las pantallas aún usan clases `snew__*` viejas dentro del shell nuevo; se ven raras — Task 2 las viste).

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat(pe): AuthShell v4 + rutas auth fuera del LegacyShell"`

### Task 2: Login re-vestido + copy

**Files:**
- Modify: `frontend/src/routes/Login.tsx:54-111` (el JSX; la lógica L1-52 NO se toca — el gate iOS-standalone L22-23 y su comentario se conservan)
- Modify: `frontend/src/locales/es/common.json:633-645` (bloque `auth.login`) + mismas claves en en/de/fr/ja/pt

**Interfaces:**
- Consumes: clases `auth-*` de Task 1.

- [ ] **Step 1: Reemplazar el JSX de Login** (return completo):

```tsx
  return (
    <main>
      <h1 className="auth-title">{t("auth.login.title")}</h1>

      {error && <div className="k-error" role="alert">{error}</div>}

      <form className="auth-form" onSubmit={onSubmit}>
        <div>
          <label className="auth-label" htmlFor="login-email">
            {t("auth.login.emailLabel")}
          </label>
          <input
            id="login-email"
            className="auth-input"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
          />
        </div>

        <div>
          <label className="auth-label" htmlFor="login-password">
            {t("auth.login.passwordLabel")}
          </label>
          <input
            id="login-password"
            className="auth-input"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
          />
        </div>

        <div className="auth-actions">
          <button type="submit" className="k-btn" disabled={submitting}>
            {t("auth.login.submit")}
          </button>
          {!iosStandalone && (
            <button
              type="button"
              className="k-btn k-btn--ghost"
              onClick={onGoogle}
              disabled={submitting}
            >
              {t("auth.login.googleBtn")}
            </button>
          )}
        </div>
      </form>

      <p className="auth-links">
        <Link to="/forgot">{t("auth.login.forgotLink")}</Link>
      </p>
    </main>
  );
```

- [ ] **Step 2: Copy es** — en `es/common.json` cambiar `auth.login.title` de `"Entrar a Klara"` a `"Entrar."` (el wordmark ya vive en el AuthShell). Las demás claves de `auth.login` quedan igual.

- [ ] **Step 3: Locales** — replicar el cambio de `title` en en (`"Sign in."`), de (`"Anmelden."`), fr (`"Se connecter."`), pt (`"Entrar."`), ja (`"ログイン。"` — punto japonés).

- [ ] **Step 4: Gates frontend** (los 4 comandos). Expected: verde.

- [ ] **Step 5: Commit + PR** —

```bash
git add -A && git commit -m "feat(pe): Login re-vestido al v4"
gh pr create --title "F-PE.1 — AuthShell v4 + Login" --body "Rutas auth fuera del LegacyShell (adiós edition tag visible) + Login en formato v4. Spec: docs/superpowers/specs/2026-08-10-puerta-entrada-v4-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

**Gate de PR:** review visual Iris Tane + `/code-review` normal. Samuel mergea.

---

## PR2 — Signup + Verify (`feat/pe-signup-verify`, desde main tras merge de PR1)

### Task 3: Signup con cabecera de invitación + Verify

**Files:**
- Modify: `frontend/src/routes/Signup.tsx` (los 4 returns JSX L93-193; lógica L1-90 intacta)
- Modify: `frontend/src/routes/VerifyEmail.tsx:30-57` (JSX)
- Modify: locales ×6: bloque `auth.signup` gana `invitedTitle` y `invitedSub`

**Interfaces:**
- Consumes: clases `auth-*` (Task 1).

- [ ] **Step 1: Claves nuevas en `es/common.json`** dentro de `auth.signup`:

```json
      "invitedTitle": "Te invitaron a Klara.",
      "invitedSub": "Crea tu cuenta y entra a la biblioteca.",
```

Traducir a en/de/fr/pt/ja en el mismo paso (en: `"You're invited to Klara." / "Create your account and step into the library."`; ja con 。).

- [ ] **Step 2: Reskin de los 4 returns de Signup** con el mismo patrón de Task 2 Step 1: `<main>` + `.auth-title`/`.auth-sub`/`.auth-form`/`.auth-label`+`htmlFor`/`.auth-input`/`.auth-actions`/`.auth-links`, cero `style={{...}}`. El return principal (L131-193) usa como título `t("auth.signup.invitedTitle")` y debajo `<p className="auth-sub">{t("auth.signup.invitedSub")}</p>`; ids: `signup-email`, `signup-password`, `signup-confirm`. Los returns de gate sin token (L93-107), loading (L109-115) y error de invitación (L117-129) conservan sus claves actuales (`inviteOnly.*`, `common.loading`) con las clases nuevas.

- [ ] **Step 3: Reskin de VerifyEmail** — mismo patrón; título `auth.verify.title` en `.auth-title`, párrafos en `.auth-sub`, link de vuelta en `.auth-links`. Sin claves nuevas.

- [ ] **Step 4: Gates frontend.** Expected: verde. Smoke manual: `/signup` sin token muestra el gate; `/signup?invite=x` inválido muestra `k-error`.

- [ ] **Step 5: Commit + PR** — `feat(pe): Signup con cabecera de invitación + Verify al v4` · PR `F-PE.2 — Signup + Verify`.

---

## PR3 — Forgot + Reset (`feat/pe-forgot-reset`)

### Task 4: reskin + los dos arreglos de Reset

**Files:**
- Modify: `frontend/src/routes/ForgotPassword.tsx` (JSX completo)
- Modify: `frontend/src/routes/ResetPassword.tsx` (JSX + `onSubmit` L26-28 + estado `done` L36-47)
- Modify: locales ×6: `auth.reset` gana `forgotBody`, `goLogin`, `error.missingToken`; cambian `forgotTitle` y `success`

**Interfaces:**
- Consumes: clases `auth-*` (Task 1).

- [ ] **Step 1: Copy es** — en `auth.reset`:

```json
      "forgotTitle": "¿Olvidaste tu contraseña?",
      "forgotBody": "Escribe tu correo y te mando un enlace para crear una nueva.",
      "success": "Contraseña nueva guardada. Entra con ella.",
      "goLogin": "Ir a entrar",
      "error": { "missingToken": "El enlace está incompleto. Abre otra vez el enlace del correo." }
```

(Conservar las claves hermanas existentes del bloque; traducir lo nuevo/cambiado a las 5 locales.)

- [ ] **Step 2: ForgotPassword** — reskin de ambos returns al patrón auth-*; añadir `<p className="auth-sub">{t("auth.reset.forgotBody")}</p>` bajo el título del form; id `forgot-email`.

- [ ] **Step 3: Reset — quitar el timeout** (L26-28):

```tsx
      await api.resetPassword(token, password);
      setDone(true);
```

(Se borra la línea `setTimeout(...)` y el import de `useNavigate` si queda sin uso.)

- [ ] **Step 4: Reset — estado `done` con salida explícita:**

```tsx
  if (done) {
    return (
      <main>
        <h1 className="auth-title">{t("auth.reset.resetTitle")}</h1>
        <p className="auth-sub">{t("auth.reset.success")}</p>
        <div className="auth-actions">
          <Link className="k-btn" to="/login">{t("auth.reset.goLogin")}</Link>
        </div>
      </main>
    );
  }
```

- [ ] **Step 5: Reset — token ausente claro:** encima del form, si `!token`:

```tsx
      {!token && (
        <div className="k-error" role="alert">{t("auth.reset.error.missingToken")}</div>
      )}
```

(Los `disabled={submitting || !token}` existentes se conservan.) Reskin del form al patrón auth-* con ids `reset-password`, `reset-confirm`.

- [ ] **Step 6: Gates frontend → Commit + PR** — `feat(pe): Forgot/Reset al v4 + salida explícita del reset` · PR `F-PE.3 — Forgot + Reset`.

---

## PR4 — Waitlist backend + panel admin (`feat/pe-waitlist-api`) — **lo escribe Claude (archivo sensible)**

### Task 5: modelo + migración

**Files:**
- Create: `backend/src/klara/models/waitlist.py`
- Modify: `backend/src/klara/models/__init__.py` (export, espejo de cómo se exporta `Invitation`)
- Create: `backend/alembic/versions/20260810_0020_waitlist_signups.py`
- Modify: `backend/tests/conftest.py` (añadir `waitlist_signups` al TRUNCATE de `_clean_tables`, L62-85)

**Interfaces:**
- Produces: `WaitlistSignup(id, email, locale, created_at, invited_at)` — lo consumen Tasks 6-7.

- [ ] **Step 1: `models/waitlist.py`** (espejo de `models/invitation.py`):

```python
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from klara.models.base import Base, created_ts, uuid_pk


class WaitlistSignup(Base):
    __tablename__ = "waitlist_signups"

    id: Mapped[uuid_pk]
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[created_ts]
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Export en `models/__init__.py`** igual que `Invitation`.

- [ ] **Step 3: Migración `20260810_0020_waitlist_signups.py`** — docstring una línea, `revision = "20260810_0020"`, `down_revision = "20260809_0019"`. Para las columnas `id`/`created_at`, **copiar verbatim las definiciones de columna de `20260809_0019_learner_profile.py`** (mismos server defaults); añadir `email` (String(320) not null), `locale` (String(8) null), `invited_at` (DateTime tz null) y el índice único:

```python
    op.create_index("ix_waitlist_signups_email", "waitlist_signups", ["email"], unique=True)
```

`downgrade()`: drop index + drop table.

- [ ] **Step 4: Roundtrip local** — `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`. Expected: sin errores.

- [ ] **Step 5: conftest** — añadir `waitlist_signups` a la lista TRUNCATE de `_clean_tables`.

- [ ] **Step 6: Gates backend → Commit** — `feat(pe): tabla waitlist_signups`.

### Task 6: `POST /waitlist` (TDD)

**Files:**
- Create: `backend/tests/test_waitlist.py`
- Create: `backend/src/klara/routers/waitlist.py`
- Modify: `backend/src/klara/main.py:221-231` (include_router)

**Interfaces:**
- Consumes: `WaitlistSignup` (Task 5); `AuthSessionDep` — **copiar el import/definición de `routers/invitations.py:1-18`**.
- Produces: `POST /api/v1/waitlist` body `{email, locale?}` → 200 `{"ok": true}` siempre (válido, nuevo o repetido); 422 email inválido; 429 rate limit. Función `_rate_limited(ip)` y dict `_hits` (Task 7 los testea; el panel de Task 8 no los usa).

- [ ] **Step 1: Tests que fallan** (`test_waitlist.py`):

```python
import pytest
from sqlalchemy import select

from klara.models.waitlist import WaitlistSignup
from klara.routers import waitlist as waitlist_router


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    waitlist_router._hits.clear()
    yield
    waitlist_router._hits.clear()


@pytest.mark.asyncio
async def test_signup_creates_row_lowercased(client, db_session):
    r = await client.post("/api/v1/waitlist", json={"email": "Ana@Example.com", "locale": "es"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    row = await db_session.scalar(select(WaitlistSignup))
    assert row is not None
    assert row.email == "ana@example.com"
    assert row.locale == "es"
    assert row.invited_at is None


@pytest.mark.asyncio
async def test_signup_idempotent_same_response_no_enumeration(client, db_session):
    r1 = await client.post("/api/v1/waitlist", json={"email": "ana@example.com"})
    r2 = await client.post("/api/v1/waitlist", json={"email": "ANA@example.com"})
    assert (r1.status_code, r1.json()) == (r2.status_code, r2.json())
    rows = (await db_session.scalars(select(WaitlistSignup))).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_signup_invalid_email_422(client):
    r = await client.post("/api/v1/waitlist", json={"email": "no-es-un-correo"})
    assert r.status_code == 422
```

- [ ] **Step 2: Correr y verlos fallar** — `uv run pytest tests/test_waitlist.py -v`. Expected: FAIL (404, router no existe).

- [ ] **Step 3: `routers/waitlist.py`:**

```python
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from klara.auth.users import current_admin_user
from klara.models.user import User
from klara.models.waitlist import WaitlistSignup
# + AuthSessionDep: mismo import/definición que routers/invitations.py

router = APIRouter()

AdminUser = Annotated[User, Depends(current_admin_user)]


class WaitlistIn(BaseModel):
    email: EmailStr
    locale: str | None = Field(default=None, max_length=8)


class WaitlistOut(BaseModel):
    ok: bool = True


# ponytail: rate limit in-memory por proceso (un worker en prod; se resetea al
# reiniciar). Si hay N workers o abuso real: slowapi, ver TODO de main.py:147.
_WINDOW_S = 3600
_MAX_PER_WINDOW = 10
_hits: dict[str, tuple[int, float]] = {}


def _rate_limited(ip: str, now: float | None = None) -> bool:
    t = now if now is not None else time.monotonic()
    count, start = _hits.get(ip, (0, t))
    if t - start > _WINDOW_S:
        count, start = 0, t
    count += 1
    _hits[ip] = (count, start)
    return count > _MAX_PER_WINDOW


@router.post("/waitlist", response_model=WaitlistOut)
async def join_waitlist(
    payload: WaitlistIn, request: Request, session: AuthSessionDep
) -> WaitlistOut:
    ip = request.client.host if request.client else "unknown"
    if _rate_limited(ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS)
    email = payload.email.strip().lower()
    existing = await session.scalar(
        select(WaitlistSignup).where(WaitlistSignup.email == email)
    )
    if existing is None:
        session.add(WaitlistSignup(email=email, locale=payload.locale))
        try:
            await session.commit()
        except IntegrityError:
            # Carrera entre dos POST del mismo correo: el segundo pierde y da igual.
            await session.rollback()
    # Respuesta idéntica exista o no: sin enumeración de correos.
    return WaitlistOut()
```

- [ ] **Step 4: Registrar en `main.py`** — junto al bloque L221-231:

```python
app.include_router(waitlist.router, prefix="/api/v1", tags=["waitlist"])
```

(+ import del módulo arriba, espejo de `invitations`.)

- [ ] **Step 5: Verde** — `uv run pytest tests/test_waitlist.py -v`. Expected: 3 PASS.

- [ ] **Step 6: Suite completa + ruff → Commit** — `feat(pe): POST /waitlist idempotente sin enumeración`.

### Task 7: rate limit (TDD)

**Files:**
- Modify: `backend/tests/test_waitlist.py`

- [ ] **Step 1: Test que falla** (falla si `_rate_limited` no corta):

```python
@pytest.mark.asyncio
async def test_rate_limit_429_after_10(client):
    for i in range(10):
        r = await client.post("/api/v1/waitlist", json={"email": f"p{i}@example.com"})
        assert r.status_code == 200
    r11 = await client.post("/api/v1/waitlist", json={"email": "p11@example.com"})
    assert r11.status_code == 429


def test_rate_limit_window_resets():
    waitlist_router._hits.clear()
    for _ in range(10):
        assert waitlist_router._rate_limited("1.2.3.4", now=1000.0) is False
    assert waitlist_router._rate_limited("1.2.3.4", now=1000.0) is True
    assert waitlist_router._rate_limited("1.2.3.4", now=1000.0 + 3601) is False
```

- [ ] **Step 2: Correr** — si Task 6 se implementó completa, ambos PASAN ya (el límite vive en el código de Task 6); si algo falla, arreglar en `waitlist.py`, no en el test.

- [ ] **Step 3: Commit** — `test(pe): rate limit del waitlist`.

### Task 8: admin (listar + marcar invitado) + panel

**Files:**
- Modify: `backend/src/klara/routers/waitlist.py`
- Modify: `backend/tests/test_waitlist.py`
- Modify: `frontend/src/api/client.ts` (3 funciones nuevas)
- Modify: `frontend/src/components/InvitationsPanel.tsx`
- Modify: locales ×6 (bloque `settings.waitlist` nuevo)

**Interfaces:**
- Produces: `GET /api/v1/admin/waitlist` → `[{id, email, locale, created_at, invited_at}]`; `POST /api/v1/admin/waitlist/{id}/invited` → fila actualizada. Frontend: `api.listWaitlist()`, `api.markWaitlistInvited(id)`.

- [ ] **Step 1: Tests que fallan** — añadir a `test_waitlist.py` (copiar los helpers de cookie `_login_cookie`/`_register_owner` verbatim de `tests/test_invitations.py:7-45`):

```python
@pytest.mark.asyncio
async def test_admin_waitlist_requires_admin(client):
    r = await client.get("/api/v1/admin/waitlist")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_admin_lists_and_marks_invited(client, app_settings, db_session):
    cookie = await _register_owner(client, app_settings, db_session)
    await client.post("/api/v1/waitlist", json={"email": "fan@example.com", "locale": "de"})

    r = await client.get("/api/v1/admin/waitlist", headers={"Cookie": cookie})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1 and rows[0]["email"] == "fan@example.com"
    assert rows[0]["invited_at"] is None

    r2 = await client.post(
        f"/api/v1/admin/waitlist/{rows[0]['id']}/invited", headers={"Cookie": cookie}
    )
    assert r2.status_code == 200
    assert r2.json()["invited_at"] is not None
```

- [ ] **Step 2: FAIL → implementar en `waitlist.py`:**

```python
from datetime import datetime, timezone
from uuid import UUID


class WaitlistRowOut(BaseModel):
    id: UUID
    email: EmailStr
    locale: str | None
    created_at: datetime
    invited_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/admin/waitlist", response_model=list[WaitlistRowOut])
async def list_waitlist(session: AuthSessionDep, admin: AdminUser) -> list[WaitlistRowOut]:
    rows = await session.scalars(
        select(WaitlistSignup).order_by(WaitlistSignup.created_at.desc())
    )
    return [WaitlistRowOut.model_validate(r) for r in rows]


@router.post("/admin/waitlist/{signup_id}/invited", response_model=WaitlistRowOut)
async def mark_invited(
    signup_id: UUID, session: AuthSessionDep, admin: AdminUser
) -> WaitlistRowOut:
    row = await session.get(WaitlistSignup, signup_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    row.invited_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    return WaitlistRowOut.model_validate(row)
```

- [ ] **Step 3: Verde + suite completa + ruff → Commit** — `feat(pe): admin waitlist (listar + marcar invitado)`.

- [ ] **Step 4: API client frontend** — leer `frontend/src/api/client.ts` alrededor de `listInvitations`/`createInvitation` y añadir con el MISMO helper interno:

```ts
listWaitlist: () => /* GET */ "/admin/waitlist",
markWaitlistInvited: (id: string) => /* POST */ `/admin/waitlist/${id}/invited`,
joinWaitlist: (email: string, locale: string) => /* POST */ "/waitlist" /* body {email, locale} */,
```

(Los tipos: `WaitlistRow { id: string; email: string; locale: string | null; created_at: string; invited_at: string | null }`.)

- [ ] **Step 5: Sección Waitlist en `InvitationsPanel.tsx`** — debajo de la lista de invitaciones, misma estética del panel: título `k-mono` `t("settings.waitlist.title")`, lista de filas email + fecha + botón `.k-btn.k-btn--ghost`. El botón "Invitar" hace el dos-pasos que reusa el flujo probado:

```tsx
async function onInviteFromWaitlist(row: WaitlistRow) {
  await api.createInvitation({ email: row.email, note: "waitlist" });
  await api.markWaitlistInvited(row.id);
  await reloadAll(); // recarga invitaciones + waitlist
}
```

Filas con `invited_at` muestran `t("settings.waitlist.invited")` en vez del botón.

- [ ] **Step 6: Claves es** (`settings.waitlist`): `"title": "Lista de espera"`, `"empty": "Nadie esperando todavía."`, `"invite": "Invitar"`, `"invited": "Invitado"` + 5 locales.

- [ ] **Step 7: Gates frontend + backend → Commit + PR** — `feat(pe): waitlist en el panel de invitaciones` · PR `F-PE.4 — Waitlist (API + panel)`.

---

## PR5 — Landing (`feat/pe-landing`)

### Task 9: Landing + RootGate

**Files:**
- Create: `frontend/src/routes/Landing.tsx`
- Create: `frontend/src/styles/landing.css` (+ import en `main.tsx`)
- Modify: `frontend/src/App.tsx` (V4Frame + RootGate; el `/` sale del grupo V4Shell)
- Modify: locales ×6 (bloques `landing.*` y `waitlist.*`)

**Interfaces:**
- Consumes: `api.joinWaitlist` (Task 8), copy master de la spec §2.
- Produces: ruta pública `/` sin sesión.

- [ ] **Step 1: Claves es** — bloques nuevos en `es/common.json` (copy master de la spec, verbatim):

```json
  "landing": {
    "hero": {
      "tagline": "Tu biblioteca de estudio.",
      "support": "Lees, hablas, repasas. Cada curso se arma a la forma en que aprendes tú.",
      "ctaPrimary": "Avísame cuando abra",
      "ctaLogin": "¿Ya tienes cuenta? Entrar"
    },
    "que": {
      "leer": { "title": "Leer", "body": "Historias cortas en el idioma que estudias. Cada palabra se abre con un toque: significado, género, contexto." },
      "hablar": { "title": "Hablar", "body": "Conversas y Klara te corrige el sonido exacto que falló. Lo que dijiste ayer lo recuerda hoy." },
      "repasar": { "title": "Repasar", "body": "Fichas que vuelven justo antes del olvido. Sin rachas, sin corazones, sin culpa." }
    },
    "footer": { "contact": "Escríbeme", "copyright": "Klara" }
  },
  "waitlist": {
    "title": "Por ahora, por invitación.",
    "body": "Klara está en pruebas con un grupo pequeño. Deja tu correo y te escribo cuando abra.",
    "placeholder": "tu@correo.com",
    "submit": "Avísame cuando abra",
    "privacyNote": "Tu correo sirve para avisarte del lanzamiento y nada más. Pide borrarlo cuando quieras.",
    "success": "Anotado. Te escribo cuando Klara abra.",
    "error": {
      "invalid": "Ese correo no parece completo. Revísalo.",
      "network": "No se pudo guardar. Intenta otra vez en un momento."
    }
  },
```

+ 5 locales (ja: 。, "Klaraが" sin espacio).

- [ ] **Step 2: `landing.css`:**

```css
/* Puerta de entrada v4 — landing pública. Scrollea (no vive en .m3-app). */

.landing {
  min-height: 100dvh;
  max-width: 430px;
  margin: 0 auto;
  background: var(--paper);
  color: var(--ink);
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
  padding: 16px 22px 40px;
  padding-top: calc(16px + env(safe-area-inset-top));
}

@media (min-width: 520px) {
  .landing { border-inline: 1px solid var(--rule); }
}

.landing__tagline {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  font-size: var(--t-h1);
  line-height: var(--lh-tight);
  letter-spacing: var(--tracking-display);
  margin: var(--space-6) 0 var(--space-3);
}

.landing__support {
  font-family: var(--font-serif);
  font-size: var(--t-read);
  line-height: var(--lh-read);
  color: var(--ink-2);
  margin: 0 0 var(--space-4);
}

.landing__bloque {
  border-top: 1px solid var(--rule);
  padding-top: var(--space-3);
}

.landing__bloque h2 {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 500;
  font-size: var(--t-h3);
  margin: 0 0 var(--space-2);
}

.landing__bloque p {
  font-family: var(--font-serif);
  font-size: var(--t-body);
  line-height: var(--lh-read);
  color: var(--ink-2);
  margin: 0;
}

.landing__wl { border-top: 1px solid var(--rule); padding-top: var(--space-4); }

.landing__wl-note {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--ink-3);
  margin-top: var(--space-2);
}

.landing__footer {
  border-top: 1px solid var(--rule);
  padding-top: var(--space-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: var(--tracking-mark);
  text-transform: uppercase;
  color: var(--ink-4);
  display: flex;
  justify-content: space-between;
}
```

- [ ] **Step 3: `Landing.tsx`:**

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

type WlState = "idle" | "sending" | "ok" | "error";

export default function Landing() {
  const { t, i18n } = useTranslation();
  const [email, setEmail] = useState("");
  const [state, setState] = useState<WlState>("idle");

  async function onJoin(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    try {
      await api.joinWaitlist(email.trim().toLowerCase(), i18n.language);
      setState("ok");
    } catch {
      setState("error");
    }
  }

  return (
    <div className="landing">
      <header className="m3-top">
        <span className="marca">
          <span className="wordmark">Klara</span>
        </span>
        <Link to="/login">{t("landing.hero.ctaLogin")}</Link>
      </header>

      <section>
        <h1 className="landing__tagline">{t("landing.hero.tagline")}</h1>
        <p className="landing__support">{t("landing.hero.support")}</p>
        <a className="k-btn" href="#waitlist">{t("landing.hero.ctaPrimary")}</a>
      </section>

      <section aria-label={t("landing.que.leer.title")}>
        {(["leer", "hablar", "repasar"] as const).map((k) => (
          <div className="landing__bloque" key={k}>
            <h2>{t(`landing.que.${k}.title`)}</h2>
            <p>{t(`landing.que.${k}.body`)}</p>
          </div>
        ))}
      </section>

      <section id="waitlist" className="landing__wl">
        <h2 className="auth-title">{t("waitlist.title")}</h2>
        <p className="landing__support">{t("waitlist.body")}</p>
        {state === "ok" ? (
          <p className="auth-sub" role="status">{t("waitlist.success")}</p>
        ) : (
          <form className="auth-form" onSubmit={onJoin}>
            <div>
              <label className="auth-label" htmlFor="wl-email">{t("waitlist.placeholder")}</label>
              <input
                id="wl-email"
                className="auth-input"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={state === "sending"}
              />
            </div>
            {state === "error" && (
              <div className="k-error" role="alert">{t("waitlist.error.network")}</div>
            )}
            <div className="auth-actions">
              <button type="submit" className="k-btn" disabled={state === "sending"}>
                {t("waitlist.submit")}
              </button>
            </div>
          </form>
        )}
        <p className="landing__wl-note">{t("waitlist.privacyNote")}</p>
      </section>

      <footer className="landing__footer">
        <span>{t("landing.footer.copyright")}</span>
        <a href="mailto:samueldarioballesteros@gmail.com">{t("landing.footer.contact")}</a>
      </footer>
    </div>
  );
}
```

(Nota: el error `waitlist.error.invalid` lo cubre la validación nativa `type="email" required` del navegador — la clave queda para el caso de un 422 del server que la esquive.)

- [ ] **Step 4: RootGate en `App.tsx`** — extraer `V4Frame` y sacar `/` del grupo V4Shell:

```tsx
function V4Frame({ children }: { children: ReactNode }) {
  return (
    <div className="m3-app">
      {children}
      <TabBar />
    </div>
  );
}

function V4Shell() {
  return (
    <V4Frame>
      <Outlet />
    </V4Frame>
  );
}

function RootGate() {
  const { user, loading } = useAuth();
  if (loading) return <div className="landing" />;
  if (!user) return <Landing />;
  return (
    <V4Frame>
      <ProtectedRoute>
        <Inicio />
      </ProtectedRoute>
    </V4Frame>
  );
}
```

Ruta: `<Route path="/" element={<RootGate />} />` fuera de los shells; borrar el index `/` del grupo V4Shell. (`ProtectedRoute` sigue manejando `needs_onboarding` y el owner-gate; el redirect a `/login` de ese componente nunca se alcanza aquí porque `user` ya existe.)

- [ ] **Step 5: Gates frontend.** Smoke manual: sin sesión `/` muestra landing y `Entrar` lleva a `/login`; con sesión `/` muestra Inicio con TabBar; submit del waitlist → "Anotado."

- [ ] **Step 6: Commit + PR** — `feat(pe): landing pública con waitlist` · PR `F-PE.5 — Landing`.

---

## PR6 — Onboarding armonizado (`feat/pe-onboarding-v4`)

### Task 10: pase de tokens a `onboarding.css`

**Files:**
- Modify: `frontend/src/styles/onboarding.css` (SOLO este archivo — el diff del PR debe ser 100% CSS)

- [ ] **Step 1: Inventario** — leer `onboarding.css` completo y listar todo valor duro (hex, px de fuente, families) que NO use `var(--...)`.

- [ ] **Step 2: Sustitución por tokens** — mapa: colores papel→`var(--paper*)`, tintas→`var(--ink*)`, rojos→`var(--accent*)`, bordes→`var(--rule)`; fuentes→`var(--font-serif|sans|mono)`; tamaños a la escala `--t-*` (los mono chicos: 10px etiquetas / 12px contenido, el corte de Iris); radios→`--r-*`; espaciados evidentes→`--space-*`. Donde el valor no tenga token equivalente exacto, conservarlo y anotar `/* sin token: <razón> */`.

- [ ] **Step 3: Verificación de paridad** — `npm run build` + pasada visual de los 7 pasos del onboarding en dev (Welcome→Nombre→Idiomas→Nivel→Contexto→Contraseña→Done). El comportamiento no cambia: `git diff --stat` muestra únicamente `onboarding.css`.

- [ ] **Step 4: Checklist de señales (constraint F2):** el draft de localStorage `klara:onboarding:draft` y el POST final no se tocan — verificado por el diff CSS-only.

- [ ] **Step 5: Gates frontend → Commit + PR** — `feat(pe): onboarding sobre tokens v4` · PR `F-PE.6 — Onboarding armonizado`.

---

## Cierre de fase

- [ ] **Smoke en el iPhone real de Samuel** (gate final): PWA instalada → landing → link de invitación → signup → onboarding completo. Verificar: 100dvh con teclado abierto, safe-areas, mic intacto (#103), Google OAuth oculto en standalone.
- [ ] Review visual **Iris Tane** por pantalla (gate de merge de cada PR).
- [ ] Deploy: `scripts/deploy-prod.sh` (recordar: la migración 0020 corre en el ensamblado; verificar `alembic upgrade head` en el box).

## Self-review del plan

- Cobertura vs spec: §1 rutas→T1+T9 · §2 landing+copy→T9 · §3 waitlist→T5-T8 · §4 cinco pantallas→T2-T4 · §5 onboarding→T10 · §6 i18n→en cada task · §7 PRs/gates→estructura + cierre. ✓
- Sin placeholders: cada paso con código o instrucción de espejo con path exacto (`AuthSessionDep`, columnas de 0019, helper de client.ts). ✓
- Consistencia de tipos: `WaitlistSignup`/`WaitlistRowOut`/`WaitlistRow` alineados (id/email/locale/created_at/invited_at); `_hits`/`_rate_limited` idénticos en T6/T7. ✓
