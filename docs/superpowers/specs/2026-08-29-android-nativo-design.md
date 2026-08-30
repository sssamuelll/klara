# Klara en el teléfono — app Android nativa (diseño)

Spec del "gran salto" decidido el 2026-08-29: la PWA instalada (PR #103) no resultó
"realmente funcional" en el teléfono y el proyecto quedó abandonado varios días. Las
cuatro fallas nombradas por el dueño — *se siente como una web · no me llama de vuelta ·
micrófono/audio fallan · no puedo meterle texto rápido* — son exactamente las cuatro
cosas que un cascarón nativo puede dar y una PWA no. Android primero (hay dispositivo
para depurar desde esta PC); iOS después, con el mismo cascarón, cuando el dueño esté
frente a su Mac. **Nada Android-only en los cimientos.**

**Estado: v1, aprobada en chat (diseño en seis secciones), pendiente de revisión del
dueño sobre el texto.** Anexo A trae los hechos de investigación ya refutados
adversarialmente (61 agentes, 30 fuentes); Anexo B, las costuras del código en HEAD
con archivo:línea, verificadas a mano.

## Goal

Que Klara viva en el teléfono del dueño como app instalada desde `adb`, con login de
Google nativo, grabación de pronunciación con streaming, TTS, recordatorio real cuando
vence un repaso, y "compartir → tarjetas" desde cualquier app — sin bifurcar el
frontend ni tocar el dominio de alemán. Play viene después; iOS viene después; los dos
sobre esta misma base.

## 0. Forma: qué es y qué no

**Es Capacitor 8 envolviendo el mismo React 18 + Vite.** Un solo frontend, dos builds
(web como hoy; nativo sin service worker y con API absoluta). El proyecto Android vive
en `frontend/android/`, commiteado.

- **No es TWA.** Una TWA es *exactamente* el Chrome que hoy corre la PWA, con un ícono
  en Play. Si la PWA falló, la TWA falla igual, y es Android-only por diseño: no lleva
  al iPhone.
- **No es un rewrite en Kotlin.** Bifurcaría la UI en dos códigos a mitad del rediseño
  v4, para un solo desarrollador. Y el trabajo de API de la §2 es el mismo para
  cualquier cliente nativo: si algún día hay un cliente Kotlin de verdad, esa API ya
  está; no se pierde nada por diferirlo.
- **Honestidad sobre "se siente web":** el scroll y el render siguen siendo Chromium.
  Lo que cambia es todo lo demás — arranque con splash, barra de estado del color del
  tema, teclado que no rompe el layout, botón atrás que hace lo correcto, vibración al
  calificar, sin barra de navegador, sin service worker peleando con el bundle.

Nombre del paquete: **`dev.sdar.klara`** (inverso de `klara.sdar.dev`). Nombre visible:
**Klara**.

## 1. Repo y builds

```
frontend/
  capacitor.config.ts        # appId, appName, webDir: "dist", plugins
  android/                   # generado por `cap add android`, COMMITEADO
  src/lib/native.ts          # isNative(), token, haptics, pause — la única puerta a Capacitor
  package.json               # + build:native, cap:sync, android:run
```

| Script | Qué hace |
|---|---|
| `npm run build` | Como hoy (web, PWA). |
| `npm run build:native` | `tsc -b && vite build --mode native` — lee `frontend/.env.native` (`VITE_NATIVE=1`, `VITE_API_BASE=https://klara.sdar.dev/api/v1`). Sin SW, API absoluta. **Corregido en F-A1:** las variables NO van en la línea de comando, porque `VAR=x cmd` no es sintaxis válida en Windows; y el nombre es `VITE_API_BASE`, NO `VITE_API_BASE_URL` — esa última ya existe en `vite.config.ts:6` como target del proxy de desarrollo, con forma de origen y sin `/api/v1`. |
| `npm run cap:sync` | `build:native` + `npx cap sync android`. |
| `npm run android:run` | `npx cap run android -l --external` — live reload contra el Vite de la PC (`host: true`, puerto 5273, ya configurado). |

**Dev con live reload no toca nada de red:** el WebView carga `http://<ip-pc>:5273`,
el proxy `/api` de `vite.config.ts:65-70` reenvía HTTP y WS al backend, y el código
relativo sigue funcionando. El token Bearer (§3) se usa igual en dev, así el camino
nativo se prueba a diario, no solo en el build de producción.

`vite-plugin-pwa` recibe `disable: !!process.env.VITE_NATIVE`. Un service worker
dentro del WebView es inútil (el bundle ya es local) y el soporte de SW en Android
System WebView es poco fiable — se apaga en el build nativo, se conserva en web.

Toolchain ya presente en la PC del dueño: Android SDK (platform-tools, build-tools,
cmdline-tools), JDK 21, Node 24. Capacitor 8: `minSdk 24`, `compileSdk`/`targetSdk 36`
— que es lo que Play exige para apps nuevas desde el 2026-08-31.

## 2. API para clientes que no son un navegador (F-A0, backend)

Hoy la auth es **solo cookie** (`auth/backend.py:7-13`: host-only, `SameSite=Strict`,
JWT de 30 días sin refresh, `users.py:11` registra un único backend). Desde un WebView
con origen `https://localhost` esa cookie no viaja nunca. Se agrega un segundo
transporte **al lado**, sin tocar el primero; el web no se entera.

### 2.1 Bearer revocable

- `BearerTransport(tokenUrl="api/v1/auth/bearer/login")` + **`DatabaseStrategy`**
  (`fastapi_users.authentication.strategy.db`, ya instalada) con
  `lifetime_seconds = 180 días`.
- Tabla nueva `access_tokens` (`SQLAlchemyBaseAccessTokenTableUUID`: `token` PK,
  `user_id` FK CASCADE, `created_at`). Migración `20260829_0022_access_tokens.py`,
  `down_revision = "20260811_0021"`. Aditiva.
- `FastAPIUsers(get_user_manager, [auth_backend, bearer_backend])`: `current_active_user`
  acepta cualquiera de los dos sin cambiar una sola ruta.
- Rutas nuevas: `POST /api/v1/auth/bearer/login` (form `username`/`password`, devuelve
  `{access_token, token_type}`) y `POST /api/v1/auth/bearer/logout` (borra la fila →
  **el logout revoca de verdad**, cosa que el JWT de cookie no hace hoy).
- Sin rotación. `# ponytail: token de 180 días revocable; rotación cuando haya más de un usuario por dispositivo.`

### 2.2 Google nativo — `POST /api/v1/auth/google/native`

Google devuelve 403 `disallowed_useragent` a cualquier WebView embebido (es la razón
por la que `Login.tsx:18-23` esconde el botón en el iPhone). La solución correcta no es
un Custom Tab (salto al navegador, "se siente web") sino el Credential Manager del SO:
selector de cuenta en hoja inferior, sin salir del app.

- Cuerpo: `{"id_token": "<JWT de Google>"}`. Respuesta: la misma que `bearer/login`.
- Verificación **sin dependencia nueva**: `pyjwt[crypto]` ya está en `uv.lock`.
  `PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", cache_keys=True)`,
  `jwt.decode(..., algorithms=["RS256"], audience=settings.google_oauth_client_id,
  issuer={"https://accounts.google.com", "accounts.google.com"})`. Además
  `email_verified is True` o 400.
- Luego llama al **mismo** `UserManager.oauth_callback` (`manager.py:172`) con
  `oauth_name="google"`, `account_id=sub`, `account_email=email`, `expires_at=exp`,
  `associate_by_email=True`, `is_verified_by_default=True`. Así la regla de invitación
  (`manager.py:190-213`) y la adopción del dueño legacy se aplican solas; **nunca se
  crea el usuario a mano**.
- `OAuthAccount.access_token` es NOT NULL en la tabla base de fastapi-users; se guarda
  el propio `id_token` (decisión deliberada, documentada en el código: no hay access
  token en este flujo y el campo no se lee en ningún sitio).
- Errores: 400 `auth.google_native.invalid` (firma/aud/iss/exp/email no verificado),
  400 `auth.invite_required` (viene del manager) (es lo que lanza `manager.py:210-214`), 429 (§2.5).
- Google Cloud (lo hace el dueño, fuera del repo): en el mismo proyecto OAuth, un
  cliente tipo **Android** con paquete `dev.sdar.klara` + SHA-1 del keystore de debug
  (`~/.android/debug.keystore`; el de release se suma en F-A4). El plugin se
  inicializa con `webClientId` = el **Web Client ID que ya existe** — es la audiencia
  del ID token y por eso el backend reutiliza `google_oauth_client_id`.

### 2.3 WebSocket de pronunciación: token en el primer frame

`ws_auth.py` decidió con razón que el token no va en la URL (se filtra a logs). El
cliente ya manda un primer frame JSON `{reference_text, language}`
(`streamClient.ts:106`, consumido en `pronunciation.py:295`). Se le agrega `token`
opcional:

1. Origin-gate (sin cambios, la allowlist crece — §2.4) → `accept()`.
2. Recibir el handshake (el `wait_for` con `pron_stream_send_timeout_s` ya existe).
3. Autenticar: cookie si viene; si no, `token` del handshake contra la estrategia
   Bearer (`read_token`). Ninguno → `WS_CLOSE_AUTH`, como hoy.
4. Caps y sesión, sin cambios.

El orden cambia (hoy autentica antes del handshake): es el único movimiento de código
en el endpoint. `test_pronunciation_stream.py` ya cubre el handshake; se extiende.

### 2.4 Origen del WebView en CORS y en el origin-gate

`CORS_ORIGINS` (prod: `docker-compose.prod.yml:38`) suma `https://localhost` (Android)
y `capacitor://localhost` (iOS, desde ya, para no volver). `origin_allowed` lee la
misma lista (`ws_auth.py:23-25`), así que el WS queda cubierto con el mismo cambio.

Por qué es seguro con `allow_credentials=True`: la cookie es `SameSite=Strict` y
`localhost` no es *same-site* con `sdar.dev`, así que una página maliciosa servida en
`https://localhost` no puede montar la cookie del usuario; el Bearer exige el token,
que solo tiene el app. `CORS_ORIGINS` de prod vive en `docker-compose.prod.yml:38`, así
que el cambio va en el PR y lo aplica el despliegue normal.

### 2.5 Rate limit en login — cerrar el `TODO(security)` de `main.py:149`

Se reutiliza el limitador in-memory por IP que ya existe en `routers/waitlist.py:41-91`
(`_client_ip` respeta `X-Forwarded-For`, verificado en la puerta de entrada v4):
se mueve a `klara/ratelimit.py` y se aplica como dependencia a `/auth/jwt/login`,
`/auth/bearer/login` y `/auth/google/native`: **10 intentos fallidos / 5 min por IP →
429** con `Retry-After: 300` y detail i18n `auth.too_many_attempts`. Un login exitoso
limpia el contador de esa IP (`UserManager.on_after_login`, que fastapi-users llama
desde las tres rutas y la de OAuth del navegador) — si contara también los exitosos, el
gate de F-A1 (login/logout repetidos desde el mismo wifi) lo dispararía. Sin
dependencia nueva (`slowapi` no hace falta). El mapeo del 429 a un mensaje propio en
`Login.tsx` va en F-A1 (hoy el web muestra el genérico de credenciales para todo error).

### 2.6 `GET /api/v1/srs/next` — lo que el recordatorio necesita saber

`{ "due_now": int, "next_due_at": datetime | null }`, unión de `user_cards`
(`next_review_at` NULL cuenta como vencida, `routers/srs.py:95`) y `study_cards`
(`next_review_at` NOT NULL). Solo lectura, una consulta por tabla. Es el único
endpoint nuevo que no es de auth; existe porque las listas de vencidas actuales
(`/srs/cards/due`, `/taller/cards/due`) no dicen *cuándo* vence la próxima.

**F-A0 se despliega solo y no cambia nada visible en web.** Este PR **no se delega**
(archivos de auth).

## 3. Frontend: las costuras de mismo origen (F-A1)

Todo el frontend es "mismo origen relativo". Son tres líneas y se resuelven con una
función:

| Costura | Hoy | Después |
|---|---|---|
| `client.ts:44` | `const API_BASE = "/api/v1"` | `apiBase()` → `VITE_API_BASE` si está definida, si no `/api/v1` |
| `streamClient.ts:47` | `deriveWsUrl(window.location)` | deriva de `apiBase()` (`https:`→`wss:`); si es relativa, como hoy |
| `tts.ts:35`, `waveform.ts:22` | `` `/api/v1/tts?...` `` | `` `${apiBase()}/tts?...` `` |

**Capa de auth** — `src/lib/native.ts` es la única puerta a Capacitor; el resto del
código no importa `@capacitor/*`:

- `isNative()` = `Capacitor.isNativePlatform()`. En nativo el login va a
  `/auth/bearer/login`, el logout a `/auth/bearer/logout` + borrar token, y `request()`
  (`client.ts:100`) agrega `Authorization: Bearer` cuando hay token. En web, nada cambia.
- Google: `@capgo/capacitor-social-login` → `idToken` → `POST /auth/google/native` →
  guardar token. El botón de Google **aparece** en nativo (hoy se esconde en iOS
  standalone; esa condición queda solo para la PWA de iOS).
- Token en **`@capacitor/preferences`** (SharedPreferences privadas del app) con
  `android:allowBackup="false"` para que no viaje a la copia de seguridad de Google.
  Razón para no usar Keystore: Google retiró `EncryptedSharedPreferences` en 2024 con
  la guía de que el sandbox del app basta para este caso; y el token es revocable
  (§2.1), así que una fuga se mata desde el servidor. Decisión del dueño si prefiere un
  plugin de Keystore; el cambio queda encapsulado en `native.ts`.
- 401 → borrar token → `unauthorizedListeners` (`client.ts:111`) → login, como hoy.

**TTS bajo Bearer.** Un `<audio src>` no puede mandar headers. En nativo `speak()`
hace `fetch` con el header → `URL.createObjectURL(blob)` → el mismo elemento
desbloqueado de `tts.ts:142`; se revoca el blob anterior en cada `speak`. `waveform.ts`
ya usa `fetch`, solo suma el header y comparte la caché HTTP (misma URL). La caché
`immutable` de un año del backend sigue aplicando: el navegador cachea respuestas a
peticiones con `Authorization` cuando la respuesta trae `max-age`.

**`speechSynthesis` no existe en el WebView de Android.** El fallback de `tts.ts:250`
falla en silencio y `onDone("error")` sigue su camino; no se agrega nada.

## 4. El cascarón (F-A1, `frontend/android/` + plugins oficiales)

`capacitor.config.ts`:

```ts
{ appId: "dev.sdar.klara", appName: "Klara", webDir: "dist",
  android: { allowMixedContent: false, adjustMarginsForEdgeToEdge: "auto" },
  plugins: { SplashScreen: { launchAutoHide: false, backgroundColor: "#F4EFE6" },
             Keyboard: { resize: "native" } } }
```

`adjustMarginsForEdgeToEdge: "auto"` importa: con `targetSdk 35+` Android impone
edge-to-edge y el WebView quedaría debajo de la barra de estado. El CSS de safe-area
que ya existe (`index.html:6` `viewport-fit=cover`, `global.css:103`) se queda como
está. **Verificar en dispositivo real en el gate de F-A1.**

| Falla del dueño | Respuesta | Plugin |
|---|---|---|
| Se siente web | Splash con el ícono sobre `#F4EFE6`, `SplashScreen.hide()` tras el primer render del shell. | `@capacitor/splash-screen` |
| | Barra de estado del color del tema; sigue a `klara.theme` (`preferences.ts`) en vivo. | `@capacitor/status-bar` |
| | Teclado en `resize: "native"` — arregla "teclado abierto rompe el layout" del smoke del iPhone. | `@capacitor/keyboard` |
| | Botón atrás: `canGoBack` → `history.back()`; en raíz → `App.exitApp()`. | `@capacitor/app` |
| | Vibración ligera al calificar un repaso (fichas y taller); `tap()` es no-op en web. | `@capacitor/haptics` |
| | `overscroll-behavior: none`, `-webkit-tap-highlight-color: transparent`, `user-select: none` en controles — solo bajo `html.native`. | CSS |
| Mic/audio fallan | Manifest: `RECORD_AUDIO` **y** `MODIFY_AUDIO_SETTINGS` (sin el segundo, `getUserMedia` da `NotAllowedError` aunque el usuario acepte). El bridge de Capacitor concede el permiso del WebView solo. | manifest |
| | `App` `pause` → cerrar WS + worklet + `MediaRecorder` limpio (Android corta el mic en segundo plano desde 9; hoy quedaría colgado). Seams: `useSentencePractice.ts`, `pronunciation.ts`. | `@capacitor/app` |
| | `AudioContext({sampleRate: 16000})` de `pcmCapture.ts:35` ya es lo correcto: el constraint de `getUserMedia` no es fiable en Android, el contexto sí. Sin cambios. | — |

Manifest además: `INTERNET` (default), `POST_NOTIFICATIONS` (§5),
`android:allowBackup="false"`, intent-filter `ACTION_SEND` `text/plain` en
`MainActivity` (§6). Firma: keystore de debug para el dogfood por `adb`; el de release
nace en F-A4.

## 5. Que te llame de vuelta (F-A2)

Recordatorio **local**, sin servidor: `@capacitor/local-notifications`.

- Cuándo se (re)agenda: al abrir/reanudar el app y tras cada `POST .../review`. Se
  cancela la notificación `id=1` y, si `GET /srs/next` da `next_due_at` en el futuro,
  se agenda una sola a esa hora con `allowWhileIdle: true`. Si `due_now > 0` no hace
  falta avisar: ya está abierto.
- Sin alarma exacta: el drift de hasta 1 h de Android 12+ es aceptable para un
  recordatorio de repaso, y evita el permiso `SCHEDULE_EXACT_ALARM` y su revisión en Play.
- Permiso `POST_NOTIFICATIONS` (Android 13+) se pide **al terminar la primera sesión de
  repaso**, no al arrancar: es el momento en que el usuario entiende para qué.
  Denegado → no se agenda, sin insistir.
- Tap en la notificación (`localNotificationActionPerformed`) → `/repaso`.
- Copia: `notif.repaso.title` / `notif.repaso.body` (con `{{count}}`), en las 6 locales.

Push desde el servidor (FCM, tabla `device_tokens`, `firebase-admin`) queda fuera: hoy
el servidor no tiene nada que iniciar por su cuenta. Si aparece esa razón, es un PR
propio y la tabla va por dispositivo, nunca un campo en `users`.

## 6. Texto rápido: compartir → tarjetas (F-A2)

- `@capgo/capacitor-share-target` **≥ 8.0.46** (el bug de doble disparo en cold start
  se arregló el 2026-08-13). Listener registrado antes del primer render y consulta del
  último share para el arranque en frío. El campo `url` llega vacío desde apps nativas
  de Android: la URL, si la hay, viene en `text` o `title` — se concatena.
- El texto entra al borrador que ya existe (`tallerDraft.ts`) y se navega a
  **`/taller/entrada`**: pantalla móvil (≤1023 px) con el textarea precargado, campo de
  etiquetas y "Crear tarjetas" → `POST /taller/cards/bulk` con la **misma regla de
  parseo del cliente** (spec taller §3). El banco de trabajo ≥1024 px
  (`taller.css:24`) no cambia.
- Compartir sin sesión → login (Google nativo) → `/taller/entrada` con el borrador
  intacto. Usuario fuera de `TALLER_USER_IDS` → 403 → mensaje `taller.entrada.noAccess`.
- Nombres: sigue la casa del taller (**tarjeta · etiqueta · repaso**). "entrada" es la
  puerta por donde el texto entra al taller; pase solace-wren en el plan si hace falta
  otro sustantivo.

## 7. i18n

Cero strings duros. Claves nuevas en las 6 locales en el mismo PR, con
`npm run i18n:check` como gate: `auth.google_native.*`, `notif.repaso.*`,
`taller.entrada.*`, `native.back.*` si hace falta copia. Backend: `auth.google_native.invalid`
en `i18n/messages.py`.

## 8. Estados de fallo

| Situación | Qué pasa |
|---|---|
| Sin red | Los estados de error existentes; no hay modo offline (fuera de scope). |
| Token revocado o vencido | 401 → borrar token → login. |
| ID token de Google inválido | 400 → `auth.login.error.googleFailed` (clave existente). Si lo que falló fue bajar el JWKS de Google, el backend deja un `warning` `google_native.jwks_unavailable`; la respuesta sigue siendo 400. |
| Demasiados intentos de login | 429 con `Retry-After: 300` y `auth.too_many_attempts`; un login exitoso limpia el contador de esa IP. |
| Google sin invitación | 400 → `auth.invite_required` (existente). |
| SHA-1 no registrado en Google Cloud | El plugin falla sin ID token: mensaje `googleFailed` + log. Es el fallo #1 de configuración; va en el checklist del plan. |
| Mic denegado | `NotAllowedError` por el camino existente de `pronunciation.ts`. |
| App a segundo plano grabando | `pause` cierra todo; la toma se pierde limpia, sin sesión colgada en el servidor. |
| Notificaciones denegadas | No se agenda; nada más. |
| Share con app cerrada | Cold start → borrador → `/taller/entrada`. |
| Share sin acceso al taller | 403 → `taller.entrada.noAccess`. |
| WS de streaming rechazado (origen o token) | `WS_CLOSE_AUTH` → fallback a batch, como hoy. |

## 9. Fuera de scope (explícito)

- **iOS** — mismo cascarón (`cap add ios`), cuando el dueño esté frente al Mac. Nada de
  esta spec es Android-only salvo el manifest; `capacitor://localhost` ya queda en CORS.
- **TTS con pantalla bloqueada / controles en lock screen** — el WebView de Android no
  implementa Media Session; es **F-A3** con reproductor nativo (`@capgo/native-audio`
  soporta streaming) y es una regresión conocida frente a la PWA en Chrome hasta entonces.
- **Push desde servidor (FCM).**
- **Deep links para verificar correo / reset** — se completan en web; el registro es
  por invitación.
- **Offline.**
- **Rotación de tokens Bearer.**
- **Play producción** — F-A4 es la pista de prueba **interna** (hasta 100 testers, sin el
  gate de 12 testers/14 días de las cuentas personales). Requiere cuenta ($25) y
  keystore de release.
- **TWA.**

## 10. Fases y gates

| Fase | Contenido | Gate |
|---|---|---|
| **F-A0** API nativa | §2 completa: migración, bearer, google/native, WS por frame, CORS, rate limit, `/srs/next`. Backend + tests. | `pytest` verde; `CORS_ORIGINS` actualizado en prod; el web sigue igual (smoke manual de login/Google/streaming en `klara.sdar.dev`). |
| **F-A1** El cascarón | §1, §3, §4. | `adb install` en el Android del dueño → login con Google → grabar una frase **con streaming** → oír TTS → cerrar sesión y comprobar que el token murió (401 en `/users/me` con el token viejo). Edge-to-edge y teclado verificados a ojo. |
| **F-A2** Que te llame y que le mandes texto | §5, §6. | Vencer un repaso con el app cerrada → notificación real → tap → `/repaso`. Compartir un párrafo desde Chrome → verlo como tarjetas en `/taller`. |
| **F-A3** Audio en segundo plano | Reproductor nativo + Media Session. | Historia sonando con la pantalla bloqueada, controles en lock screen. |
| **F-A4** Play interna | Cuenta, keystore de release, SHA-1 de release en Google Cloud, Data Safety, política de privacidad. | Instalación desde la pista interna en un segundo dispositivo. |

Cada fase es un PR (o dos, como F0 del taller). Ninguna toca el dominio de alemán.

## 11. Tests

Los tests los escribe Claude antes de delegar (TDD); auth no se delega.

**Backend (`backend/tests/`)**
- `test_auth_bearer.py`: login devuelve token; el token abre `/users/me`; logout lo
  revoca (401 después); el login por cookie sigue igual; token vencido → 401.
- `test_auth_google_native.py`: `PyJWKClient` mockeado; token válido con usuario
  existente → enlaza y devuelve bearer; aud incorrecto / `email_verified=False` / iss
  raro → 400; correo sin invitación ni usuario → 403; adopción del dueño legacy.
- `test_pronunciation_stream.py`: handshake con `token` válido → sesión; token inválido
  → `WS_CLOSE_AUTH`; origen fuera de la lista → cierre antes del accept, como hoy;
  cookie sigue funcionando.
- `test_ratelimit_login.py`: el 11.º intento en 5 min → 429; IP distinta no se ve
  afectada; `X-Forwarded-For` respetado.
- `test_srs_next.py`: unión de las dos tablas; `next_review_at` NULL cuenta como
  vencida; sin tarjetas → `{0, null}`.

**Frontend (`vitest`)**
- `apiBase()` con y sin `VITE_API_BASE`; `deriveWsUrl` desde base absoluta y relativa.
- `openScoreStream` incluye `token` en el handshake solo cuando se le pasa.
- `speak()` en nativo usa `fetch` + blob y revoca el anterior (con `fetch` mockeado).
- `native.ts` en web: `isNative()` false, `tap()` y token son no-op.

**En dispositivo (manual, es el gate de cada fase)** — checklist en el plan, al estilo
de `2026-07-31-fase1-smoke-iphone.md`. Sin CI para Android (Actions apagadas a propósito).

## 12. Decisiones del dueño (cerradas 2026-08-29)

1. **Google Cloud:** el dueño crea el cliente OAuth tipo Android (paquete `dev.sdar.klara`
   + SHA-1 del keystore de debug) en la consola; el plan de F-A1 trae el comando para
   sacar el SHA-1. Es lo primero de F-A1 y no depende del código.
2. **`dev.sdar.klara`** confirmado como id de paquete.
3. **Token en `@capacitor/preferences`** con `allowBackup=false` (§3): aceptado.

## Anexo A — Hechos verificados (2026-08-29; refutación adversarial, fuentes)

- WebView de Capacitor Android = origen `https://localhost`; `server.hostname` bajo el
  mismo eTLD+1 lo vuelve same-site pero es **Android-only** (`iosScheme` fijo en
  `capacitor`). Por eso esta spec va por Bearer. — capacitorjs.com/docs/config
- `CapacitorHttp` ignora `SameSite` por construcción (`CapacitorCookieManager` →
  `android.webkit.CookieManager`); **WebSocket nunca pasa por CapacitorHttp** — el
  origin-gate del WS se arregla aparte siempre. — github.com/ionic-team/capacitor (CapacitorCookieManager.java)
- Google bloquea OAuth en WebView embebido (`disallowed_useragent`); Credential Manager
  devuelve un ID token cuya audiencia es el **Web** Client ID. — developer.android.com/identity/sign-in/credential-manager-siwg-implementation, developers.google.com/identity/sign-in/android/backend-auth
- `@capgo/capacitor-social-login` mantenido (Capacitor 8); exige `webClientId` de tipo Web. — github.com/Cap-go/capacitor-social-login
- Mic: sin plugin en Android e iOS (Capacitor ≥3.5); `onPermissionRequest` lo concede el
  bridge; hacen falta `RECORD_AUDIO` **y** `MODIFY_AUDIO_SETTINGS`; se corta en segundo
  plano (Android 9+). — github.com/ionic-team/capacitor/pull/5196, developer.android.com/about/versions/pie/android-9.0-changes-all
- `sampleRate` como constraint de `getUserMedia` no es fiable en Android; el
  `AudioContext({sampleRate})` sí. AudioWorklet desde Chrome 66.
- **Android WebView no implementa Media Session API** (ago-2026); `@jofr/capacitor-media-session`
  sin actividad desde 2024; `@capgo/native-audio` soporta streaming. — caniwebview.com/features/web-feature-media-session
- Recordatorios sin servidor solo con `@capacitor/local-notifications`; sin alarma
  exacta el drift es ≤1 h (Android 12+). Web Push en PWA/TWA Android sí despierta el SW
  con la app cerrada (la limitación "navegador abierto" es de escritorio). — capacitorjs.com/docs/apis/local-notifications, developer.android.com/develop/background-work/services/alarms
- `@capgo/capacitor-share-target` ≥8.0.46 (fix doble disparo cold start, 2026-08-13);
  `url` vacío desde apps nativas. — github.com/Cap-go/capacitor-share-target/pull/39
- Capacitor 8.5: `minSdk 24`, `compileSdk`/`targetSdk 36`; 8.5 adoptó UIScene en iOS.
- **Play:** cuenta personal nueva = $25 + 12 testers opt-in 14 días continuos antes de
  producción; pista interna hasta 100 testers sin ese gate; **target API 36 obligatorio
  para apps nuevas desde 2026-08-31**; `adb install` exento del "Android Developer
  Verification" (2026-09-30, 4 países). — support.google.com/googleplay/android-developer/answer/14151465, .../answer/11926878, developer.android.com/developer-verification/guides/faq
- TWA = Chrome vía Custom Tabs sobre el dominio real: hereda cookie/CORS/OAuth sin
  cambios, pero no tiene bridge JS↔nativo ni notificaciones locales agendadas, y es
  Android-only. — developer.chrome.com/docs/android/trusted-web-activity

## Anexo B — Costuras en HEAD (verificadas a mano)

| Qué | Dónde |
|---|---|
| Único transporte: cookie host-only, `SameSite=Strict`, JWT 30 d sin refresh | `backend/src/klara/auth/backend.py:7-19` |
| Un solo backend registrado | `backend/src/klara/auth/users.py:9-12` |
| `TODO(security)` rate limit en login | `backend/src/klara/main.py:149-151` |
| OAuth Google: router + `redirect_url` al backend; 204→302 `/` | `main.py:111-126`, `main.py:176-186` |
| Regla de invitación en OAuth | `backend/src/klara/auth/manager.py:172-216` |
| CORS desde `CORS_ORIGINS`; `allow_credentials=True` | `main.py:137-143`, `config.py:135,196-197` |
| WS: origin-gate + cookie; token-en-URL rechazado a propósito | `pronunciation/ws_auth.py:23-55`; endpoint `routers/pronunciation.py:270-300` |
| Limitador in-memory por IP reutilizable | `routers/waitlist.py:41-91` |
| `API_BASE` relativo; `request()` con `credentials: "include"` | `frontend/src/api/client.ts:44,100-130` |
| Login form-encoded a `/auth/jwt/login`; logout | `client.ts:151-152,175` |
| WS desde `window.location`; primer frame `{reference_text, language}` | `frontend/src/lib/streamClient.ts:46-49,103-108` |
| TTS `<audio>` reutilizado con `src` relativo; `speechSynthesis` fallback | `frontend/src/lib/tts.ts:35,111-118,142-145,250` |
| Segundo fetch al TTS (forma de onda) | `frontend/src/lib/waveform.ts:22,43` |
| Captura 16 kHz + worklet | `frontend/src/lib/pcmCapture.ts:35-62` |
| Botón de Google oculto en iOS standalone | `frontend/src/routes/Login.tsx:18-23,48` |
| PWA: `VitePWA` autoUpdate, denylist `/api/` | `frontend/vite.config.ts:13-57` |
| Dev proxy `/api` con WS | `vite.config.ts:65-70` |
| Taller: endpoints y gate ≥1024 px | `backend/src/klara/routers/taller.py:51-227`, `frontend/src/styles/taller.css:24` |
| Vencidas: alemán y taller | `client.ts:243,524`; `routers/srs.py:83-95` |
| Última migración | `backend/alembic/versions/20260811_0021_study_cards.py` |
| Prod: origen único `klara.sdar.dev`, CORS en compose | `docker-compose.prod.yml:38-55` |

## Self-review

- **Placeholders:** ninguno; los nombres de plugin, versiones mínimas, rutas, códigos de
  error y claves i18n están fijados. Lo único que depende del dueño está en §12.
- **Consistencia:** §2.4 mete `capacitor://localhost` en CORS aunque iOS esté fuera de
  scope — es deliberado (§0 "nada Android-only en los cimientos") y se dice en §9. §3
  guarda el token en Preferences y §12.3 lo deja abierto al dueño: la decisión por
  defecto está tomada, el veto es suyo.
- **Alcance:** F-A0 y F-A1 son un plan cada uno; F-A2 puede ir en el mismo plan que
  F-A1 si el gate de F-A1 pasa rápido. F-A3/F-A4 no tienen spec propia todavía.
- **Ambigüedad resuelta:** "nativo" = cascarón Capacitor, no Kotlin (§0); el
  recordatorio es uno solo y local (§5); la entrada móvil del taller reutiliza parser
  y endpoints, no crea otro camino de escritura (§6).
