# Puerta de entrada v4 — landing + auth + primer arranque

**Fecha:** 2026-08-10 · **Estado:** aprobado en diseño, pendiente review de spec
**Corre en paralelo a F2** (no depende del dominio Course; única migración: `waitlist_signups`, aislada del dominio).

## Goal

Que la primera impresión de un invitado (y de cualquier curioso que llegue al dominio) sea la de un producto que va a mercado: landing editorial con waitlist, funnel de auth completo re-vestido al design system v4, y primer arranque (onboarding) armonizado. Hoy las 5 pantallas auth viven en el LegacyShell con el Masthead que muestra el tag de edición interno ("F2.1") a los testers.

**Decisiones de Samuel (2026-08-10):** alcance = "todos los juguetes" (landing + 5 pantallas auth + pase visual al onboarding); CTA de landing para visitantes sin invitación = **waitlist con email**.

## 1. Arquitectura de rutas

- `/` sin sesión → **Landing** (hoy `ProtectedRoute` redirige a `/login`). Con sesión → Inicio (biblioteca), sin cambio.
- Las 5 rutas auth (`/login`, `/signup`, `/forgot`, `/reset`, `/verify`) salen del LegacyShell y entran a un **AuthShell v4**: patrón `m3-app` **sin TabBar** (el que F2.1 aplicó a `/estudiar/:id`), cabecera `m3-top` con wordmark serif — sin edition tag.
- El Masthead legacy deja de ser visible para usuarios no autenticados.
- La landing es una ruta del SPA (misma PWA, i18n de las 6 locales, cero infra nueva). SEO/prerender fuera de scope mientras el registro sea por invitación.
- El guard actual (`ProtectedRoute` → `/login` con `location.state.from`) se conserva; solo cambia el destino de la raíz no autenticada.

## 2. Landing (una página, cuatro secciones)

Identidad constitucional (DESIGN.md + plan v4): serif editorial, papel/tinta, hairlines 1px, UN acento bermellón, sin gradientes/glow, sin gamification, sin hype. Frame 430px mobile-first; desktop hereda el frame centrado.

1. **Hero:** wordmark "Klara" serif grande + tagline + CTA primario (ancla a waitlist) + secundario "¿Ya tienes cuenta? Entrar".
2. **Qué es:** tres bloques serif (Leer / Hablar / Repasar) con lo que la app hace de verdad. Sin screenshots inventados.
3. **Waitlist:** input email + botón + nota de propósito (GDPR: se recogen correos en la UE; la nota no es opcional).
4. **Footer:** contacto + copyright. Sin página legal completa por ahora (pregunta abierta №1).

### Copy master (es) — pase solace-wren 2026-08-10

| Clave | Copy | Notas |
|---|---|---|
| `landing.hero.tagline` | Tu biblioteca de estudio. | 25 chars; dirección ya aprobada (manifest) |
| `landing.hero.support` | Lees, hablas, repasas. Cada curso se arma a la forma en que aprendes tú. | tríada orgánica del producto |
| `landing.hero.ctaPrimary` | Avísame cuando abra | 19 chars; ancla a §waitlist |
| `landing.hero.ctaLogin` | ¿Ya tienes cuenta? Entrar | link secundario |
| `landing.que.leer.title` / `.body` | Leer / Historias cortas en el idioma que estudias. Cada palabra se abre con un toque: significado, género, contexto. | |
| `landing.que.hablar.title` / `.body` | Hablar / Conversas y Klara te corrige el sonido exacto que falló. Lo que dijiste ayer lo recuerda hoy. | fonema-nivel (#42) + memoria (wins) |
| `landing.que.repasar.title` / `.body` | Repasar / Fichas que vuelven justo antes del olvido. Sin rachas, sin corazones, sin culpa. | anti-Duolingo constitucional |
| `waitlist.title` | Por ahora, por invitación. | 26 chars |
| `waitlist.body` | Klara está en pruebas con un grupo pequeño. Deja tu correo y te escribo cuando abra. | voz de Klara, 1ª persona |
| `waitlist.placeholder` | tu@correo.com | |
| `waitlist.submit` | Avísame cuando abra | botón nombra el resultado |
| `waitlist.privacyNote` | Tu correo sirve para avisarte del lanzamiento y nada más. Pide borrarlo cuando quieras. | nota de propósito GDPR |
| `waitlist.success` | Anotado. Te escribo cuando Klara abra. | misma respuesta si el email ya estaba (sin enumeración) |
| `waitlist.error.invalid` | Ese correo no parece completo. Revísalo. | qué pasó → qué hacer |
| `waitlist.error.network` | No se pudo guardar. Intenta otra vez en un momento. | |
| `auth.signup.invitedTitle` | Te invitaron a Klara. | 21 chars; cabecera de marca del signup |
| `auth.signup.invitedSub` | Crea tu cuenta y entra a la biblioteca. | |
| `auth.login.title` / `.submit` | Entrar. / Entrar | |
| `auth.login.googleBtn` | Continuar con Google | |
| `auth.forgot.title` / `.body` | ¿Olvidaste tu contraseña? / Escribe tu correo y te mando un enlace para crear una nueva. | |
| `auth.reset.success` / `.goLogin` | Contraseña nueva guardada. Entra con ella. / Ir a entrar | reemplaza el `setTimeout(1500)` |

Master en es; las 6 locales (es/en/de/fr/ja/pt) pobladas en el mismo PR (constraint global v4). Reglas de copy: sin signos de exclamación, sin emoji, sentence case, sin hype.

## 3. Waitlist (único cambio de dominio)

- **Tabla `waitlist_signups`:** `id`, `email` (unique, almacenado lowercase), `locale` (VARCHAR 8), `created_at`, `invited_at NULL`. Migración Alembic con downgrade.
- **`POST /api/v1/waitlist`** público: body `{email, locale}`, validación `EmailStr`, normalización lowercase/trim. **Idempotente y sin enumeración:** email nuevo y email repetido devuelven la misma respuesta 200 `{ok: true}`. Rate-limit básico por IP (contador in-memory simple; sin dependencia nueva).
- **Admin:** `GET /api/v1/admin/waitlist` (solo admin) → lista con estado. En `InvitationsPanel`, sección "Waitlist": filas con email + fecha + botón **Invitar** que llama al `invitations.create(email)` existente y estampa `invited_at`. Cierra el pipeline curioso → invitado → tester.
- **Tests backend:** validación de email, idempotencia/no-enumeración, rate-limit, admin-only del listado, invitar-desde-waitlist estampa `invited_at`.
- Archivo sensible por regla saver ("decide autenticación"): los cambios de backend auth/admin los escribe Claude, no un delegado.

## 4. Pantallas auth re-vestidas (5)

Formato v4 para todas: hoja nueva `frontend/src/styles/auth.css` construida sobre `tokens.css` (inputs con la estética serif de `snew__input` pero tokenizados), **cero estilos inline**, estados de error/loading existentes conservados.

- **Login:** mismo comportamiento (email+password, Google OAuth con su gate iOS-standalone intacto, link forgot). Solo piel + copy.
- **Signup:** cabecera "Te invitaron a Klara." + email prefillado (ya funciona); los 4 estados de error de invitación (inválida/expirada/usada/revocada) se conservan con su copy actual.
- **Verify:** re-vestida, sin cambio de lógica.
- **Forgot:** re-vestida + copy nuevo.
- **Reset:** re-vestida + **dos arreglos**: (a) el `setTimeout(1500)` se reemplaza por estado de éxito explícito con botón "Ir a entrar"; (b) token inválido se muestra como error claro al submit (sin endpoint nuevo de pre-validación — no lo amerita).

A11y de entrada en todo lo nuevo (labels asociados, `role="alert"` en errores — ya existe en Login —, focus visible, botones reales, `aria-hidden` en glifos decorativos): la cola a11y de F2 aplica por defecto a pantalla nueva.

## 5. Onboarding armonizado

Pase de CSS/tokens sobre los primitives `Ob*` (`ObPrompt`, `ObField`, `ObInlineSelect`, `ObNav`): serif, spacing v4, acento bermellón. **Sin tocar lógica, pasos ni draft de localStorage.** El flujo Welcome→Nombre→Idiomas→Nivel→Contexto→Contraseña→Done queda idéntico en comportamiento. Checklist del PR: ninguna señal persistida se pierde (constraint F2 del plan maestro).

## 6. i18n

Claves nuevas `landing.*` y `waitlist.*` + retoques `auth.*` en las 6 locales, mismo PR que la pantalla que las usa; `frontend/scripts/check-i18n.mjs` en verde como gate. Backend waitlist: mensajes de usuario vía `i18n/messages.py` si aplica (la respuesta es `{ok:true}`, no debería necesitar).

## 7. Ejecución (una pantalla por PR, patrón F2)

1. **PR1 — AuthShell + Login:** shell v4 sin TabBar + `auth.css` + Login re-vestido. Saca las rutas auth del LegacyShell.
2. **PR2 — Signup + Verify** (cabecera de invitación).
3. **PR3 — Forgot + Reset** (incluye los dos arreglos de Reset).
4. **PR4 — Waitlist backend** (migración + endpoint + admin + tests).
5. **PR5 — Landing** (consume el endpoint de PR4).
6. **PR6 — Onboarding armonizado.**

**Gates por PR:** `gates-locales` (Actions OFF; checks rojos del remoto son lo esperado), `check-i18n.mjs`, review visual **Iris Tane**, `/code-review` normal. **Gate final de la fase:** smoke en el iPhone real de Samuel — landing → link de invitación → signup → onboarding completo en PWA instalada (el mic de #103 y el 100dvh son historia sensible).

## 8. Fuera de scope (explícito)

- Página legal completa (privacidad/términos) — contenido legal no se inventa; pregunta abierta №1 para Samuel.
- SEO/prerender/SSG de la landing.
- Signup público sin invitación, billing/suscripción (D-B del plan maestro).
- Doble opt-in del waitlist (la nota de propósito + borrado a pedido cubre el caso actual; se revisa si el volumen crece).
- Rediseño funcional del onboarding (D-J/F1.5 siguen siendo dueños de ese flujo).

## Preguntas abiertas

1. ¿Página de privacidad mínima ahora o al abrir el registro público? (El waitlist ya recoge correos en la UE; la nota de propósito cubre lo esencial, una página formal sería lo correcto antes del lanzamiento.)
2. ¿El dominio raíz de prod debe servir la landing también para usuarios con sesión expirada que tenían la PWA instalada? (Default: sí, la landing muestra "¿Ya tienes cuenta? Entrar" — cero fricción extra.)

## Self-review

- Sin placeholders ni TBD (el copy master está completo; lo único diferido es contenido legal, declarado fuera de scope). ✓
- Consistencia: AuthShell reutiliza el patrón F2.1; waitlist no toca el dominio Course; onboarding solo CSS. ✓
- Scope: 6 PRs chicos, un plan de implementación único. ✓
- Ambigüedad: respuesta idempotente del waitlist definida; rate-limit definido como in-memory sin dependencia nueva; archivos sensibles (auth backend) reservados a Claude. ✓
