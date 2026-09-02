Análisis completo. Todo hecho con herramientas de solo lectura (sin bash, sin ediciones). Método: extracción de selectores de clase de cada hoja y búsqueda de cada clase en los .tsx con patrón de fronteras `(^|[^A-Za-z0-9_-])clase([^A-Za-z0-9_-]|$)` para evitar falsos positivos tipo `card` dentro de `m3-card`.

---

## 1. QUIÉN LO CARGA — ruta de cada hoja al bundle

Todas las hojas entran por import estático. `main.tsx` es el entry global (las 12 hojas que importa van a **todas** las rutas, no solo a sus pantallas):

| Hoja | Ruta de carga |
|---|---|
| `global.css` | `main.tsx:6` → dentro de ella, `@import` de `tokens.css` (línea 6) y `pages.css` (línea 7) — **esas dos entran por global.css**, no por import directo. Además un `@import` de Google Fonts. |
| `native.css` | `main.tsx:7` |
| `onboarding.css` | `main.tsx:8` |
| `sentence-view.css` | `main.tsx:9` |
| `finish.css` | `main.tsx:10` |
| `speak.css` | `main.tsx:11` |
| `path.css` | `main.tsx:12` |
| `mobile3.css` | `main.tsx:13` |
| `mobile4.css` | `main.tsx:14` |
| `perfil-aprendizaje.css` | `main.tsx:15` |
| `auth.css` | `main.tsx:16` |
| `landing.css` | `main.tsx:17` |
| `gender-review.css` | `components/GenderReviewSession.tsx:1` |
| `recall-review.css` | `components/RecallReviewSession.tsx:1` |
| `taller.css` | `routes/Taller.tsx:1` |
| `tokens.css` | `@import` dentro de `global.css:6` |
| `pages.css` | `@import` dentro de `global.css:7` |

No hay `require()` dinámico ni otros imports de CSS fuera de los listados.

## 2–3. USO REAL y PANTALLAS, hoja por hoja

**`pages.css`** — 790 líneas | 122 clases | 77 usadas | **45 muertas**
Muertas: las 23 `home*` (bloque home completo), las 10 `story-end*`, las 11 `story__new*` (+`story__foot`), y `wpop__example-es`. El 45% de la hoja.
Pantallas (10 reales): `routes/Practice.tsx`, `routes/Speak.tsx`, `routes/NewStory.tsx`, `routes/Settings.tsx`, `routes/Module.tsx`, `components/InvitationsPanel.tsx`, `components/OwnerPasswordGate.tsx`, `components/ProtectedRoute.tsx`, `components/WordPopover.tsx`, `components/BreakdownPopover.tsx`. (Otros 14 .tsx la "tocan" solo por `k-mono`, clase definida en global.css.)

**`mobile3.css`** — 201 líneas | 92 clases | 65 usadas | **27 muertas**
Muertas: `m3-saludo, m3-linea, m3-mapa-h1, m3-sheet, m3-art-der, m3-art-die, m3-art-das, m3-carta, m3-turno, m3-corr, m3-lado, m3-rep, m3-repbar, m3-ficha, m3-srs` y las genéricas `art, trad, quien, linea, grab, fila1, miclbl, fin, centro, posw, ej, micgrande`.
Pantallas (13 con uso real): `App.tsx`, `components/EstudiarView.tsx`, `components/Masthead.tsx`, `components/SessTop.tsx`, `components/TabBar.tsx`, `perfil/views.tsx`, `routes/Inicio.tsx`, `routes/Landing.tsx`, `routes/MapaCurso.tsx`, `routes/NuevoPlaceholder.tsx`, `routes/Perfil.tsx`, `routes/Portada.tsx`, `routes/Story.tsx`. ⚠️ De las 65 "usadas", ~11 (`n, l, d, de, es, mal, bien, palabra, hint, hablar, lemma…`) son solo coincidencias de token (variables/i18n), no `className` real.

**`path.css`** — 87 líneas | 25 clases | 9 usadas | **16 muertas**
Muertas: `path__list, path__node, path__title, path__num, path__body, path__check, path__meta, path__cta, path__empty, path__bar, path__bar-fast, path__bar-slow, path__node--locked, path__node--current, path__node--completed, mod__list`. Además `path` (contada usada) es falso positivo (props `<Route path>` / SVG `<path>`): uso real = **8 clases**.
Pantallas: `routes/Module.tsx` (único consumidor real, clases `mod__*` + `path__kicker`).

**`recall-review.css`** — 351 líneas | 60 clases | 49 usadas | **11 muertas**
Muertas: `rr-prog__slash, rr-prog__track, rr-prog__pip, rr-ficha__folio, rr-ficha__front-folio, rr-ficha__pos, rr-ficha__back-folio, rr-ficha__eg-tx, rr-ficha__src, rr-flip__hint, rr-rate__key`.
Pantallas: `components/RecallReviewSession.tsx` (único).

**`mobile4.css`** — 59 líneas | 26 clases | 20 usadas | **6 muertas**
Muertas: `m4-input, m4-chips, m4-o, m4-upload, m4-pensando, m4-modo`.
Pantallas (9): `components/TabBar.tsx`, `components/SessTop.tsx`, `perfil/views.tsx`, `routes/Inicio.tsx`, `routes/MapaCurso.tsx`, `routes/NuevoPlaceholder.tsx`, `routes/Perfil.tsx`, `routes/Portada.tsx`, `routes/NewStory.tsx`.

**`global.css`** — 422 líneas | 26 clases | 24 usadas | **2 muertas**
Muertas: `k-rule`, `k-btn--accent`.
Pantallas (41): `App.tsx`, `components/BreakdownPopover.tsx`, `EstudiarView.tsx`, `GenderReviewSession.tsx`, `InvitationsPanel.tsx`, `KlaraMark.tsx`, `Masthead.tsx`, `OwnerPasswordGate.tsx`, `PasswordSetForm.tsx`, `ProtectedRoute.tsx`, `RecallReviewSession.tsx`, `StoryFinish.tsx`, `WordPopover.tsx`, `onboarding/Onboarding.tsx`, `onboarding/primitives/ObField.tsx`, `ObInlineSelect.tsx`, `ObNav.tsx`, `ObPrompt.tsx`, `onboarding/steps/StepContext.tsx`, `StepDone.tsx`, `StepLanguages.tsx`, `StepLevel.tsx`, `StepName.tsx`, `StepPassword.tsx`, `StepWelcome.tsx`, `perfil/views.tsx`, `routes/ForgotPassword.tsx`, `Inicio.tsx`, `Landing.tsx`, `Login.tsx`, `Module.tsx`, `NewStory.tsx`, `Perfil.tsx`, `Practice.tsx`, `ResetPassword.tsx`, `Settings.tsx`, `Signup.tsx`, `Speak.tsx`, `Story.tsx`, `Taller.tsx`, `VerifyEmail.tsx`.

**`speak.css`** — 277 líneas | 53 clases | 51 usadas | **2 muertas**
Muertas: `kac-tri--lg`, `kac-feedback__btn--strong`.
Pantallas: `routes/Speak.tsx` (único).

**`perfil-aprendizaje.css`** — 110 líneas | 50 clases | 48 usadas | **2 muertas**
Muertas: `ob5-fila`, `est` (bloque autocontenido de las líneas 92–97; `routes/Perfil.tsx` renderiza sus filas con `m3-rowbtn`/`estado`, no con `ob5-fila`).
Pantallas: `perfil/views.tsx` (consumidor principal, 46 de 50 clases).

**Cero muertas:**
- `sentence-view.css` — 576 líneas | 57 clases | 57 usadas → `components/SentenceView.tsx`
- `finish.css` — 1021 líneas | 108 clases | 108 usadas → `components/StoryFinish.tsx`, `components/GenderPicker.tsx`, `components/GenderReviewSession.tsx`
- `onboarding.css` — 718 líneas | 78 clases | 78 usadas → `onboarding/Onboarding.tsx` + los 11 archivos de `onboarding/` (primitives + steps)
- `taller.css` — 309 líneas | 29 clases | 29 usadas → `routes/Taller.tsx` (verificado leyéndolo: las 29 son `className` reales)
- `auth.css` — 76 líneas | 8 clases | 8 usadas → `App.tsx`, `routes/ForgotPassword.tsx`, `Login.tsx`, `ResetPassword.tsx`, `Signup.tsx`, `VerifyEmail.tsx`, `routes/Landing.tsx`
- `landing.css` — 128 líneas | 12 clases | 12 usadas → `routes/Landing.tsx`, `App.tsx`
- `gender-review.css` — 58 líneas | 8 clases | 8 usadas → `components/GenderReviewSession.tsx`
- `native.css` — 14 líneas | 2 clases | 2 usadas → `components/NativeChrome.tsx` (clase `native`; `k-btn` la comparte con global.css)
- `tokens.css` — 117 líneas | 0 clases | 0 | 0 (solo `:root` y variables `--*`)

## Tabla resumen (ordenada por clases muertas descendente)

| hoja | lineas | clases | usadas | muertas | tsx que la usan |
|---|---|---|---|---|---|
| pages.css | 790 | 122 | 77 | **45** | 10 (Practice, Speak, NewStory, Settings, Module, InvitationsPanel, OwnerPasswordGate, ProtectedRoute, WordPopover, BreakdownPopover) |
| mobile3.css | 201 | 92 | 65 | **27** | 13 (App, EstudiarView, Masthead, SessTop, TabBar, perfil/views, Inicio, Landing, MapaCurso, NuevoPlaceholder, Perfil, Portada, Story) |
| path.css | 87 | 25 | 9* | **16** | 1 (routes/Module.tsx) |
| recall-review.css | 351 | 60 | 49 | **11** | 1 (components/RecallReviewSession.tsx) |
| mobile4.css | 59 | 26 | 20 | **6** | 9 (TabBar, SessTop, perfil/views, Inicio, MapaCurso, NuevoPlaceholder, Perfil, Portada, NewStory) |
| global.css | 422 | 26 | 24 | **2** | 41 (todo el árbol de pantallas) |
| speak.css | 277 | 53 | 51 | **2** | 1 (routes/Speak.tsx) |
| perfil-aprendizaje.css | 110 | 50 | 48 | **2** | 1 (perfil/views.tsx) |
| sentence-view.css | 576 | 57 | 57 | 0 | 1 (components/SentenceView.tsx) |
| finish.css | 1021 | 108 | 108 | 0 | 3 (StoryFinish, GenderPicker, GenderReviewSession) |
| onboarding.css | 718 | 78 | 78 | 0 | 12 (todo onboarding/) |
| taller.css | 309 | 29 | 29 | 0 | 1 (routes/Taller.tsx) |
| auth.css | 76 | 8 | 8 | 0 | 7 (App + 6 rutas auth) |
| landing.css | 128 | 12 | 12 | 0 | 2 (Landing, App) |
| gender-review.css | 58 | 8 | 8 | 0 | 1 (GenderReviewSession) |
| native.css | 14 | 2 | 2 | 0 | 1 (NativeChrome) |
| tokens.css | 117 | 0 | 0 | 0 | — (sin clases; capa de variables) |
| **TOTAL** | **5294** | **756** | **636** | **111** | |

\* de las 9, `path` es falso positivo (token de ruta/SVG); uso real 8.

## GENERACIONES

- **Sistema móvil actual (prefijos `m3-`, `m4-`)**: `mobile3.css` (41 clases `m3-`), `mobile4.css` (15 clases `m4-` + hereda `m3-tabbar`/`m3-hero`). `perfil-aprendizaje.css` **no** pertenece aquí por prefijo: usa `ob5-*` (diseño "Onboarding v5"), aunque su cabecera declara depender de mobile3.css — es por-función.
- **Sistema de escritorio antiguo (`k-masthead`, `k-page`, `kapp`, `kframe` y `pages.css`)**: `global.css` (define `kapp`, `kframe`, `k-masthead` y sus `__star/__theme/__star-icon/__star-label`, `k-page`, `lockup`/`wordmark`/`edition`, más la familia `k-btn/k-link/k-level/k-chip/k-hairline/k-error/k-spinner/k-mono/k-serif`) y `pages.css` (bloques `home*`, `snew*`, `story*`, `wpop*`, `kp-*`, `ph*`). `native.css` es un parche de esa shell (`html.native` re-estilando `k-btn`), no un sistema propio.
- **Por-función** (familias propias de su pantalla): `auth.css` (`auth-*`), `landing.css` (`landing__*`), `onboarding.css` (`ob-*`), `taller.css` (nombres planos bajo `.taller`), `finish.css` (`fin-*`/`qcard*`/`quiz-hero*`), `speak.css` (`kc-*`/`kac-*`), `sentence-view.css` (`k-chapter`/`k-prog`/`k-feedback`/`k-wave`/`k-stepnav`…), `perfil-aprendizaje.css` (`ob5-*`), `recall-review.css` (`rr-*`), `gender-review.css` (`gr-*`). `path.css` también es por-función (`path__*`/`mod__*`), de la era del escritorio antiguo, pero hoy solo lo consume `routes/Module.tsx`.
- `tokens.css` es la capa base de tokens (variables, sin clases); no es una generación de UI.

**HUERFANA:** ninguna hoja está huérfana en su totalidad — las 16 hojas con clases tienen al menos un .tsx que las usa. Lo huérfano son **bloques dentro de hojas vivas**: el bloque `home*` completo de `pages.css` (la home real usa `m3-*`/`m4-*`), los bloques `story-end*` y `story__new*` de `pages.css` (sustituidos por `fin-*`/`qcard*`), la mitad de `path.css`, y los bloques muertos listados de `mobile3`/`mobile4`/`recall-review` (folios y pips que el componente no renderiza).