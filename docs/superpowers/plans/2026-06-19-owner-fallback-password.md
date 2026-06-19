# Owner Fallback Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore `hashed_password IS NULL` as the truthful "no password yet" signal (without re-introducing the 500s) and force the OAuth owner to set a fallback password — mandatory in onboarding for a fresh owner, and via a one-time blocking gate for the already-onboarded owner.

**Architecture:** Backend stops seeding a placeholder hash on OAuth owner adoption and instead null-guards fastapi-users' `forgot_password` (no-op) and `authenticate` (returns None). Frontend makes the existing onboarding `StepPassword` non-skippable and adds an `OwnerPasswordGate` rendered by `ProtectedRoute` when an onboarded owner has no password. A one-off post-deploy SQL reverts the production owner row to NULL.

**Tech Stack:** Python 3.12, FastAPI, fastapi-users 15.0.5, SQLAlchemy (async), pytest; React 18 + TypeScript + Vite + react-i18next (no frontend unit-test runner — verify with `tsc`/build/i18n check).

## Global Constraints

- Minimum password length is **8** (backend `UserManager.validate_password`; frontend forms must match).
- `/forgot-password` MUST keep returning 202 regardless of account existence (anti-enumeration). The null no-op preserves this.
- i18n parity is enforced by `npm run i18n:check`: any new key must exist in ALL six locales (`es, en, fr, de, pt, ja`).
- Owner email (for the one-off backfill): `samueldarioballesteros@gmail.com`.
- The story-gen changes from PR #69 are unrelated and must remain untouched.
- Deploy = squash-merge to `main` → CI → SSH deploy. The one-off SQL runs AFTER the deploy.
- fastapi-users version is 15.0.5; the `authenticate` override below mirrors that version's body exactly plus a null guard.

## File Structure

- `backend/src/klara/auth/manager.py` — remove the OAuth-adoption placeholder line; add `forgot_password` + `authenticate` overrides. (One responsibility: the owner/auth UserManager.)
- `backend/tests/test_auth_null_password.py` (new) — regression tests for null-password accounts.
- `frontend/src/onboarding/steps/StepPassword.tsx` — make the step mandatory.
- `frontend/src/onboarding/data.ts` — update the step-5 whisper copy.
- `frontend/src/components/OwnerPasswordGate.tsx` (new) — blocking gate screen reusing `PasswordSetForm`.
- `frontend/src/components/ProtectedRoute.tsx` — render the gate for an onboarded owner without a password.
- `frontend/src/locales/{es,en,fr,de,pt,ja}/common.json` — add `settings.security.gateHint`.

---

### Task 1: Backend — null-safe auth + drop the placeholder

**Files:**
- Modify: `backend/src/klara/auth/manager.py` (remove placeholder in `_adopt_legacy_if_owner_oauth`; add `forgot_password` and `authenticate` overrides in the `# --- overrides ---` section)
- Test: `backend/tests/test_auth_null_password.py` (create)

**Interfaces:**
- Consumes: `UserManager` (existing), fixtures `client`, `db_session`, `app_settings`, `captured_emails` (from `backend/tests/conftest.py`), `User` model.
- Produces: `UserManager.forgot_password(user, request=None)` no-ops when `user.hashed_password is None`; `UserManager.authenticate(credentials)` returns `None` when the matched user has `hashed_password is None`; `_adopt_legacy_if_owner_oauth` leaves `hashed_password` as `None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth_null_password.py`:

```python
import uuid

import pytest
from sqlalchemy import select


async def _seed_passwordless_user(db_session, email: str):
    """An OAuth-only user: email set, verified, active, hashed_password NULL."""
    from klara.models.enums import CEFRLevel
    from klara.models import User

    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=None,
        is_active=True,
        is_verified=True,
        is_superuser=True,
        display_name="Owner",
        level=CEFRLevel.A0,
        native_language="es",
        target_language="de",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_forgot_password_null_is_silent(
    client, app_settings, captured_emails, db_session
):
    app_settings(INITIAL_OWNER_EMAIL="")
    await _seed_passwordless_user(db_session, "owner@example.com")

    r = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "owner@example.com"}
    )
    # No crash (was 500 before the fix), still 202, and no reset email sent.
    assert r.status_code in (200, 202), r.text
    assert not [e for e in captured_emails if e["kind"] == "reset"]


@pytest.mark.asyncio
async def test_login_null_password_returns_400(client, app_settings, db_session):
    app_settings(INITIAL_OWNER_EMAIL="")
    await _seed_passwordless_user(db_session, "owner@example.com")

    r = await client.post(
        "/api/v1/auth/jwt/login",
        data={"username": "owner@example.com", "password": "anything12345"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # Clean bad-credentials, not a 500 from hashing None.
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_oauth_owner_adoption_leaves_password_null(
    client, app_settings, legacy_owner_with_story, db_session
):
    """Adopting the legacy owner via OAuth must NOT set a password hash."""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    from klara.auth.email import EmailService
    from klara.auth.manager import UserManager
    from klara.config import get_settings
    from klara.models import OAuthAccount, User

    app_settings(INITIAL_OWNER_EMAIL="owner@example.com")
    settings = get_settings()
    user_db = SQLAlchemyUserDatabase(db_session, User, OAuthAccount)
    manager = UserManager(user_db, settings, db_session, EmailService(settings))

    adopted = await manager.oauth_callback(
        "google", "access-tok", "google-acct-123", "owner@example.com",
        None, None, None,
    )

    assert str(adopted.id) == legacy_owner_with_story["user_id"]
    refreshed = (
        await db_session.execute(select(User).where(User.id == adopted.id))
    ).scalar_one()
    assert refreshed.email == "owner@example.com"
    assert refreshed.hashed_password is None  # ← the regression guard
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_auth_null_password.py -v`
Expected: all three FAIL — `test_forgot_password_null_is_silent` and `test_login_null_password_returns_400` error with a 500 (`TypeError: ... must be str or bytes`); `test_oauth_owner_adoption_leaves_password_null` fails on `assert refreshed.hashed_password is None` (it is the placeholder).

- [ ] **Step 3: Remove the placeholder line**

In `backend/src/klara/auth/manager.py`, inside `_adopt_legacy_if_owner_oauth`, delete the PR #69 block (the comment + assignment immediately after `legacy.is_superuser = True  # the owner is the admin`):

```python
        # OAuth adoption sets no password. Mirror fastapi-users' base
        # oauth_callback (which seeds a random, unusable hash) so that
        # hashed_password is never NULL: a NULL crashes forgot_password
        # (hash(None)) and authenticate (verify_and_update(..., None)) with
        # "TypeError: ... must be str or bytes", surfacing as a 500.
        legacy.hashed_password = self.password_helper.hash(self.password_helper.generate())
```

So the lines become exactly:

```python
        legacy.is_superuser = True  # the owner is the admin

        await self.session.commit()
```

- [ ] **Step 4: Add the overrides**

In the same file, add an import at the top with the other `fastapi` imports:

```python
from fastapi.security import OAuth2PasswordRequestForm
```

Then add these two methods to `UserManager`, in the `# --- overrides ---` section (e.g. right after `validate_password`):

```python
    async def forgot_password(self, user: User, request: Request | None = None) -> None:
        # OAuth-only accounts have no password to reset. Upstream hashes
        # user.hashed_password to fingerprint the token, which raises on NULL.
        # No-op (the router still returns 202, preserving anti-enumeration).
        if user.hashed_password is None:
            log.info("auth.forgot_password_noop_no_password", user_id=str(user.id))
            return
        await super().forgot_password(user, request)

    async def authenticate(self, credentials: OAuth2PasswordRequestForm) -> "User | None":
        # Mirrors fastapi-users 15.0.5 BaseUserManager.authenticate, with a
        # NULL guard: verify_and_update(..., None) raises on OAuth-only rows.
        try:
            user = await self.get_by_email(credentials.username)
        except exceptions.UserNotExists:
            self.password_helper.hash(credentials.password)  # timing mitigation
            return None
        if user.hashed_password is None:
            return None
        verified, updated_password_hash = self.password_helper.verify_and_update(
            credentials.password, user.hashed_password
        )
        if not verified:
            return None
        if updated_password_hash is not None:
            await self.user_db.update(user, {"hashed_password": updated_password_hash})
        return user
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_auth_null_password.py tests/test_owner_adoption.py tests/test_auth_verify_reset.py -v`
Expected: all PASS (new tests green; existing owner-adoption and reset tests still green).

- [ ] **Step 6: Lint + commit**

```bash
cd backend && uv run ruff check src/klara/auth/manager.py tests/test_auth_null_password.py
git add backend/src/klara/auth/manager.py backend/tests/test_auth_null_password.py
git commit -m "fix(auth): null-safe forgot/authenticate, drop OAuth placeholder hash"
```

---

### Task 2: Frontend — make the onboarding password step mandatory

**Files:**
- Modify: `frontend/src/onboarding/steps/StepPassword.tsx`
- Modify: `frontend/src/onboarding/data.ts:127` (the step-5 whisper)

**Interfaces:**
- Consumes: `api.setPassword` (existing), `ObNav` (skip controls are optional — omit them to remove the skip).
- Produces: a `StepPassword` whose "Continuar" stays disabled until password length ≥ 8 and confirm matches, with no skip path.

- [ ] **Step 1: Make the step non-skippable**

In `frontend/src/onboarding/steps/StepPassword.tsx`:

Replace the validity rule (was: empty OR ≥6+match):

```tsx
  // Mandatory: must be >= 8 and match (no skip).
  const valid = data.password.length >= 8 && data.password === data.passwordConfirm;
```

Replace `commit` (drop the empty-as-skip branch):

```tsx
  async function commit() {
    if (!valid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await api.setPassword(data.password);
      applyUserResponse(updated);
      next();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Algo no salió bien.");
    } finally {
      setSubmitting(false);
    }
  }
```

Update the prompt copy:

```tsx
      <ObPrompt sub="Entraste con Google. Crea una contraseña como respaldo, por si pierdes el acceso a Google.">
        Crea tu contraseña
      </ObPrompt>
```

Remove the skip props from `ObNav` (delete the `onSkip` and `skipLabel` lines) so it reads:

```tsx
      <ObNav
        onNext={() => void commit()}
        onPrev={prev}
        canNext={valid}
        submitting={submitting}
      />
```

- [ ] **Step 2: Update the whisper copy**

In `frontend/src/onboarding/data.ts`, change the step-5 whisper (line 127):

```ts
  5: () => "La necesitas como respaldo: con ella entras también por email.",
```

- [ ] **Step 3: Typecheck and build**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: both succeed, no TypeScript errors.

- [ ] **Step 4: Manual check (note for the reviewer)**

There is no frontend unit-test runner. Verify by inspection that: `valid` is false for empty/short/mismatched input (so "Continuar" is disabled), and no "Más tarde" control renders. Real-flow verification happens in Task 4.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/onboarding/steps/StepPassword.tsx frontend/src/onboarding/data.ts
git commit -m "feat(onboarding): make the fallback-password step mandatory"
```

---

### Task 3: Frontend — owner password gate for already-onboarded owners

**Files:**
- Create: `frontend/src/components/OwnerPasswordGate.tsx`
- Modify: `frontend/src/components/ProtectedRoute.tsx`
- Modify: `frontend/src/locales/{es,en,fr,de,pt,ja}/common.json` (add `settings.security.gateHint`)

**Interfaces:**
- Consumes: `PasswordSetForm` (default export), `useTranslation`, `user.is_superuser`, `user.needs_onboarding`, `user.auth_methods` (all on `UserOut`).
- Produces: `OwnerPasswordGate` (default export, no props); `ProtectedRoute` renders it instead of `children` when `!needs_onboarding && is_superuser && !auth_methods.includes("password")`.

- [ ] **Step 1: Add the `gateHint` i18n key to all six locales**

In each `frontend/src/locales/<lang>/common.json`, inside `settings.security` (next to `title`/`hint`/`savedToast`), add `gateHint`:

- `es`: `"gateHint": "Eres el owner. Crea una contraseña de respaldo para no depender solo de Google.",`
- `en`: `"gateHint": "You're the owner. Set a backup password so you don't depend on Google alone.",`
- `fr`: `"gateHint": "Tu es le propriétaire du compte. Crée un mot de passe de secours pour ne pas dépendre seulement de Google.",`
- `de`: `"gateHint": "Du bist der Eigentümer. Lege ein Backup-Passwort an, damit du nicht nur von Google abhängst.",`
- `pt`: `"gateHint": "És o proprietário. Cria uma palavra-passe de reserva para não depender só do Google.",`
- `ja`: `"gateHint": "あなたはオーナーです。Googleだけに頼らないよう、予備のパスワードを設定してください。",`

(Place it before `"savedToast"` so the trailing comma stays valid.)

- [ ] **Step 2: Create the gate component**

Create `frontend/src/components/OwnerPasswordGate.tsx`:

```tsx
import { useTranslation } from "react-i18next";
import PasswordSetForm from "./PasswordSetForm";

// Blocking screen for an onboarded owner who has no password yet. Reuses
// PasswordSetForm; on success, applyUserResponse updates auth_methods, which
// re-renders ProtectedRoute and lets the user through.
export default function OwnerPasswordGate() {
  const { t } = useTranslation();
  return (
    <main className="k-page snew">
      <div className="snew__head">
        <span className="k-mono">{t("settings.security.kicker")}</span>
        <h1 className="snew__title">{t("settings.security.title")}</h1>
      </div>
      <p className="snew__sub" style={{ marginTop: "0.5rem" }}>
        {t("settings.security.gateHint")}
      </p>
      <div style={{ marginTop: "1.5rem" }}>
        <PasswordSetForm />
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Wire the gate into `ProtectedRoute`**

In `frontend/src/components/ProtectedRoute.tsx`, add the import:

```tsx
import OwnerPasswordGate from "./OwnerPasswordGate";
```

Then add the gate check after the existing onboarding redirects (after the `!user.needs_onboarding && location.pathname === "/onboarding"` block, before `return <>{children}</>`):

```tsx
  if (
    !user.needs_onboarding &&
    user.is_superuser &&
    !user.auth_methods.includes("password")
  ) {
    return <OwnerPasswordGate />;
  }
```

- [ ] **Step 4: Typecheck, build, i18n check**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run build`
Expected: all succeed (i18n:check confirms `gateHint` exists in all six locales).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/OwnerPasswordGate.tsx frontend/src/components/ProtectedRoute.tsx frontend/src/locales
git commit -m "feat(auth): blocking owner password gate for onboarded owners"
```

---

### Task 4: Ship and backfill

**Files:** none (deployment runbook).

- [ ] **Step 1: Open the PR and let CI run**

```bash
git push -u origin feat/owner-fallback-password
gh pr create --base main --head feat/owner-fallback-password \
  --title "feat(auth): mandatory fallback password for the OAuth owner" \
  --body-file docs/superpowers/specs/2026-06-19-owner-fallback-password-design.md
```
Expected: `backend / pytest`, `backend / ruff`, `backend / migration roundtrip`, `frontend / typecheck + build + i18n`, build smokes, CodeQL all PASS.

- [ ] **Step 2: Merge (squash) — deploys to prod**

```bash
gh pr merge <PR#> --squash --delete-branch
```
Then watch `gh run watch` on the new Build & Deploy run; expect `deploy` + `Wait for health` to succeed.

- [ ] **Step 3: One-off backfill — revert the owner row to NULL (AFTER deploy)**

Run on the server (parameterized, no shell/SQL quoting of the value needed — it is a constant NULL):

```bash
ssh atrium-aws "docker exec klara_postgres psql -U klara -d klara -c \
  \"UPDATE users SET hashed_password = NULL WHERE email = 'samueldarioballesteros@gmail.com';\""
```
This is safe because this row holds the PR #69 placeholder (an unguessable value the owner never chose), not a user-set password. Expected: `UPDATE 1`.

- [ ] **Step 4: Verify**

```bash
ssh atrium-aws '
echo -n "forgot -> "; curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Content-Type: application/json" \
  -d "{\"email\":\"samueldarioballesteros@gmail.com\"}" http://127.0.0.1:8210/api/v1/auth/forgot-password
echo -n "login(bad) -> "; curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data "username=samueldarioballesteros@gmail.com&password=xx" http://127.0.0.1:8210/api/v1/auth/jwt/login
docker exec klara_postgres psql -U klara -d klara -t -c \
  "SELECT (hashed_password IS NULL) FROM users WHERE email='\''samueldarioballesteros@gmail.com'\'';"
'
```
Expected: `forgot -> 202`, `login(bad) -> 400`, password-null = `t`. Then in the browser, log in with Google → the owner gate appears → set a password ≥8 → gate disappears and the app loads; the Settings → Security panel no longer offers "set password" (now `auth_methods` includes `"password"`).

---

## Self-Review

**Spec coverage:**
- A1 (remove placeholder) → Task 1 Step 3. A2 (`forgot_password`) → Task 1 Step 4. A3 (`authenticate`) → Task 1 Step 4. A4 (backfill owner row) → Task 4 Step 3.
- B1 (StepPassword mandatory ≥8, no skip, copy) → Task 2. B2 (Onboarding.tsx no change) → noted, no task needed. B3 (gate) → Task 3.
- Deploy order (code first, then SQL) → Task 4 Steps 2–3. Testing → Task 1 tests + Task 4 Step 4 manual flow.

**Placeholder scan:** No "TBD"/"add validation"-style gaps; every code step shows real code. The only non-code verification (frontend) is explicit about why (no test runner) and gives concrete inspection criteria + a real-flow check in Task 4.

**Type consistency:** `forgot_password(user, request=None)`, `authenticate(credentials)`, `setPassword(password) -> User`, `auth_methods`, `needs_onboarding`, `is_superuser` are used consistently across tasks and match the existing `UserOut` / `api.client` / `UserManager` signatures verified in the codebase.
