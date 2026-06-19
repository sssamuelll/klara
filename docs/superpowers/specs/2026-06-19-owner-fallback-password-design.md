# Owner fallback password — design

- **Date:** 2026-06-19
- **Status:** Approved (design); pending implementation plan
- **Author:** Samuel + Claude

## Problem

The bootstrap owner ("user zero") signs in with Google OAuth and has no
email+password login. The app already ships a "set a fallback password"
feature (an onboarding step and a Settings → Security panel), gated on the
user not yet having a password. That gate is driven by `hashed_password IS
NULL`.

A prior fix for a 500 error (PR #69) made `_adopt_legacy_if_owner_oauth`
seed a random placeholder hash so fastapi-users' `forgot_password` /
`authenticate` would stop crashing on a NULL password. That placeholder
left `hashed_password` non-NULL, which **broke the fallback-password
feature**: the owner now appears to already have a password, so

- `POST /me/password` returns **409 `password_already_set`**
  (`routers/users.py:121`),
- `auth_methods` includes `"password"` (`routers/users.py:37`), so both the
  onboarding step (`Onboarding.tsx:126`) and the Settings panel
  (`Settings.tsx:250,266`) are hidden.

So the owner cannot set a fallback password at all.

## Goals

1. Restore `hashed_password IS NULL` as the truthful "no password yet"
   signal, without re-introducing the 500s.
2. Make setting a fallback password **mandatory** for the owner:
   - a fresh owner cannot finish onboarding without it;
   - the already-onboarded owner (current production state) is forced to
     set it via a one-time blocking gate, without redoing onboarding or
     touching their profile.

## Non-goals

- Internationalizing the onboarding flow (it is currently hardcoded
  Spanish — out of scope here).
- Changing the invite-only signup, the "change password" flow for users who
  already have one, or the Resend email delivery issue (tracked separately).
- Forcing a password on regular invited users (they already have one from
  signup, so they never hit these paths).

## Design

### Part A — Backend: undo the regression (`backend/src/klara/auth/manager.py`)

**A1. Stop seeding a placeholder.** Remove the line added by PR #69 in
`_adopt_legacy_if_owner_oauth`:

```python
legacy.hashed_password = self.password_helper.hash(self.password_helper.generate())
```

OAuth owner adoption again leaves `hashed_password = None`.

**A2. Override `forgot_password`** to no-op on a passwordless account:

```python
async def forgot_password(self, user, request=None):
    if user.hashed_password is None:
        log.info("auth.forgot_password_noop_no_password", user_id=str(user.id))
        return  # OAuth-only: no password to reset; no crash, no email
    await super().forgot_password(user, request)
```

The reset router still returns 202 regardless, so anti-enumeration is
preserved.

**A3. Override `authenticate`** to fail cleanly on a passwordless account.
Replicate fastapi-users' `authenticate` with a NULL guard before the
`verify_and_update` call:

```python
async def authenticate(self, credentials):
    try:
        user = await self.get_by_email(credentials.username)
    except exceptions.UserNotExists:
        self.password_helper.hash(credentials.password)  # timing mitigation
        return None
    if user.hashed_password is None:
        return None  # OAuth-only: no password; clean 400, no crash
    verified, updated = self.password_helper.verify_and_update(
        credentials.password, user.hashed_password
    )
    if not verified:
        return None
    if updated is not None:
        await self.user_db.update(user, {"hashed_password": updated})
    return user
```

**A4. Data backfill (one-off).** Revert the production owner row
(`samueldarioballesteros@gmail.com`) `hashed_password` to `NULL`. This
restores `auth_methods` (no `"password"`), clears the `/me/password` 409,
and makes the gate / Settings panel appear.

> The story-gen fix from PR #69 is unrelated and stays. Only the auth
> placeholder line is reverted.

### Part B — Frontend: make it mandatory

**B1. `onboarding/steps/StepPassword.tsx` — non-skippable.**

- Empty is no longer valid; require length **≥ 8** (matches backend
  `validate_password`) **and** matching confirm before "Siguiente" enables.
- Remove the skip affordance (`onSkip` / "Más tarde").
- Change copy from optional ("¿Una contraseña, por si acaso?", "Si
  quieres…") to required framing ("Crea tu contraseña — la necesitas como
  respaldo por si pierdes el acceso a Google").
- Update the chapter whisper in `onboarding/data.ts` (currently "Puedes
  saltarlo y agregarla después en ajustes") to a required framing.

**B2. `onboarding/Onboarding.tsx` — no structural change.** `StepPassword`
already only appears when `!hasPassword` (`auth_methods` lacks `"password"`).
Now that the step is mandatory, a fresh owner cannot reach `StepDone`
without setting a password.

**B3. Blocking gate for already-onboarded passwordless owner.** Add a guard
in the authenticated app shell (`App.tsx`, alongside the existing
`needs_onboarding` redirect). Condition:

```
onboarding completed (needs_onboarding === false)
AND auth_methods does NOT include "password"
```

In practice only the owner can be in this state. When true, render a
blocking "Set your password" screen (reuse `components/PasswordSetForm`),
non-dismissable. On success, `applyUserResponse` updates `auth_methods` and
the user proceeds to the app. The exact integration point in `App.tsx`'s
routing is confirmed during implementation.

### Data flow

- `GET /me` → `UserOut.auth_methods` is the single source of truth for "has
  password" on the frontend (onboarding gate, Settings panel, new App gate).
- Setting a password (onboarding step or gate) → `POST /me/password` →
  `auth_methods` now includes `"password"` → all gates close.

### Deploy order (important)

1. Deploy the code (Part A + B) so NULL is handled safely everywhere.
2. **Then** run the one-off backfill reverting the owner row to NULL.

If reversed, between the backfill and the deploy the old code would crash
again on `/forgot` and password `/login` for the now-NULL owner row.

## Testing

**Backend**
- `forgot_password` no-ops (no exception, no send) when `hashed_password is None`.
- `authenticate` returns `None` (not a 500) when `hashed_password is None`.
- `POST /me/password` succeeds when `hashed_password is None`; still 409 when set.
- OAuth owner adoption leaves `hashed_password = None`.

**Frontend**
- `StepPassword` cannot advance with empty / <8 / mismatched password; no skip control.
- App gate renders when onboarding is complete and `auth_methods` lacks `"password"`; disappears after a successful set.

## Rollout

- One PR (backend + frontend) → CI → deploy.
- After deploy, run the owner-row NULL backfill (one-off SQL via the backend
  connection, parameterized).
- Verify: owner sees the gate, sets a password, `auth_methods` updates,
  `/forgot` and `/login` no longer 500 for a NULL row, story-gen fix intact.
