# F-A1 — El cascarón Capacitor (Android) — Plan de implementación

> **Para trabajadores agénticos:** SUB-SKILL REQUERIDA: usa
> `superpowers:subagent-driven-development` (recomendado) o
> `superpowers:executing-plans` para ejecutar tarea por tarea. Los pasos usan
> checkbox (`- [ ]`) para seguimiento.

**Goal:** Que Klara arranque como app Android instalada por `adb`, con sesión
Bearer, Google nativo, streaming de pronunciación y TTS funcionando dentro del
WebView de Capacitor — sin cambiar nada del comportamiento web.

**Architecture:** El React actual no se toca en su lógica: se le quitan las seis
suposiciones de mismo-origen (una función `apiBase()`), se le añade una única
puerta a Capacitor (`src/lib/native.ts`) y el resto del código sigue sin importar
`@capacitor/*`. El cascarón (`frontend/android/`) se genera con `cap add android`
y se commitea. En web, cada rama nativa es un no-op.

**Tech Stack:** Capacitor 8.5.0 (core/cli/android), React 18.3.1, Vite 5.4.21,
vite-plugin-pwa 1.3.0, vitest 3.2.6, TypeScript 5.9.3, JDK 21, Android SDK 36.

**Spec:** `docs/superpowers/specs/2026-08-29-android-nativo-design.md` — §1 (repo
y builds), §3 (las costuras del frontend), §4 (el cascarón), §10 (gate de F-A1),
§11 (tests). El plan discute con la spec; ambos viajan juntos.

**Depende de:** F-A0, ya en producción (`sha-14121b9`). Los endpoints
`/auth/bearer/login`, `/auth/bearer/logout`, `/auth/google/native`, `/srs/next` y
el token en el primer frame del WS ya existen y están verificados contra prod.

---

## Global Constraints

- **Rama:** `android-f-a1-cascaron`, sacada de `main` en `14121b9` o posterior.
- **Capacitor 8.5.0** exacto para `@capacitor/core`, `@capacitor/cli` y
  `@capacitor/android`. Plugins verificados en npm el 2026-08-30:
  `@capacitor/preferences@8.0.1`, `@capacitor/splash-screen@8.0.2`,
  `@capacitor/status-bar@8.0.3`, `@capacitor/keyboard@8.0.5`,
  `@capacitor/app@8.1.1`, `@capacitor/haptics@8.0.2`,
  `@capgo/capacitor-social-login@8.5.0`.
- **`appId` = `dev.sdar.klara`**, `appName` = `Klara`, `webDir` = `dist`.
- **`minSdk 24`, `compileSdk 36`, `targetSdk 36`.** El SDK 36 y build-tools
  36.1.0 ya están instalados en la PC del dueño.
- **La variable de entorno del cliente es `VITE_API_BASE`, NO
  `VITE_API_BASE_URL`.** Desviación deliberada de la spec §1: `VITE_API_BASE_URL`
  ya existe en `frontend/vite.config.ts:6` como *target del proxy de desarrollo* y
  su forma es un origen (`http://localhost:8000`), sin `/api/v1`. Reusar ese
  nombre para una base completa rompería el proxy de `npm run dev`. `VITE_API_BASE`
  es nuevo y no colisiona con nada.
- **Auth no se delega** a motores fuera de Claude (reasonix/kimi/codex). Los
  archivos `src/lib/native.ts`, `src/api/client.ts` y `src/routes/Login.tsx` son
  código de autenticación.
- **Aditivo:** ninguna rama nativa puede cambiar el comportamiento web. Toda
  bifurcación pasa por `isNative()`, que en web es `false`.
- **i18n:** cada cadena nueva visible va en los seis locales
  (`frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`). `npm run i18n:check`
  verifica la paridad y es un gate.
- **Gates por tarea:** `cd frontend && npm run typecheck && npm run i18n:check && npm run test`.
  El backend no se toca en toda esta fase.
- **Commits en español**, con estos dos trailers exactos:
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01JA3gtwcytg8fPuFv5o6CJx
  ```
- **`frontend/android/` se commitea** entero (es fuente, no artefacto).

---

## Prerequisitos del dueño (antes de la Tarea 10)

Estos no son código y no los hace el ejecutor:

1. **Cliente OAuth Android en Google Cloud** — HECHO (2026-08-30): paquete
   `dev.sdar.klara`, SHA-1 `DB:ED:BB:A6:6A:11:03:E1:F3:C5:1A:CC:07:FF:E9:2A:2A:57:8A:18`,
   proyecto `gen-lang-client-0086982971` (número 904183028633).
2. **`ANDROID_HOME`** — hoy está sin definir y `adb` no está en el PATH. Gradle lo
   necesita. El ejecutor lo resuelve por repo en la Tarea 7 (`local.properties`),
   pero para `adb` a mano:
   ```bash
   export ANDROID_HOME="$HOME/AppData/Local/Android/Sdk"
   export PATH="$ANDROID_HOME/platform-tools:$PATH"
   ```
3. **El teléfono conectado** con depuración USB activa. Verificado el 2026-08-30:
   `adb devices` sale vacío. Sin dispositivo no hay gate de F-A1.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `frontend/src/lib/apiBase.ts` | **Crear.** `apiBase()` y `deriveWsUrl()`. Cero dependencias de Capacitor: solo lee `import.meta.env`. |
| `frontend/src/lib/native.ts` | **Crear.** La única puerta a `@capacitor/*`: `isNative()`, token, `tap()`. Nadie más importa Capacitor. |
| `frontend/src/api/client.ts` | Modificar: base por `apiBase()`, header Bearer, login/logout nativos, `googleNative()`. |
| `frontend/src/lib/streamClient.ts` | Modificar: URL desde `apiBase()`, `token` en el handshake. |
| `frontend/src/lib/tts.ts` | Modificar: en nativo, `fetch` + blob en vez de `<audio src>`. |
| `frontend/src/lib/waveform.ts` | Modificar: URL desde `apiBase()` + header. |
| `frontend/src/routes/Login.tsx` | Modificar: Google nativo cuando `isNative()`. |
| `frontend/src/routes/Signup.tsx` | Modificar: la consulta de invitación usa `apiBase()`. |
| `frontend/src/components/NativeChrome.tsx` | **Crear.** Splash, barra de estado, botón atrás. Un solo sitio para los efectos del cascarón. |
| `frontend/src/styles/native.css` | **Crear.** Los tres ajustes de CSS bajo `html.native`. |
| `frontend/capacitor.config.ts` | **Crear.** |
| `frontend/android/` | **Crear** con `cap add android`, commiteado. |

---

### Task 1: `apiBase()` y las seis costuras de mismo-origen

Hoy hay **seis** sitios que asumen mismo origen, no tres como decía la spec §3.
Los dos que faltaban los encontró el inventario del 2026-08-30:
`Signup.tsx:33` (consulta de invitación) y `Login.tsx:42` (Google authorize).

**Files:**
- Create: `frontend/src/lib/apiBase.ts`
- Create: `frontend/src/lib/apiBase.test.ts`
- Modify: `frontend/src/api/client.ts:44` (`API_BASE`)
- Modify: `frontend/src/lib/streamClient.ts:41-62` (`STREAM_PATH`, `deriveWsUrl`)
- Modify: `frontend/src/lib/tts.ts:34-39` (`ttsUrl`)
- Modify: `frontend/src/lib/waveform.ts:18-23` (`urlFor`)
- Modify: `frontend/src/routes/Login.tsx:42`
- Modify: `frontend/src/routes/Signup.tsx:33`
- Modify: `frontend/src/lib/streamClient.test.ts:35-44` (firma nueva)

**Interfaces:**
- Consume: nada de tareas anteriores.
- Produce:
  - `apiBase(): string` — `"/api/v1"` en web, o el valor absoluto de
    `VITE_API_BASE` (sin barra final) en el build nativo.
  - `deriveWsUrl(base?: string, loc?: { protocol: string; host: string }): string`
  - `STREAM_SUBPATH: string` — `"/pronunciation/stream"`

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/lib/apiBase.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiBase, deriveWsUrl } from "./apiBase";

afterEach(() => vi.unstubAllEnvs());

describe("apiBase", () => {
  it("es relativa cuando VITE_API_BASE no está definida", () => {
    vi.stubEnv("VITE_API_BASE", "");
    expect(apiBase()).toBe("/api/v1");
  });

  it("usa VITE_API_BASE cuando está definida", () => {
    vi.stubEnv("VITE_API_BASE", "https://klara.sdar.dev/api/v1");
    expect(apiBase()).toBe("https://klara.sdar.dev/api/v1");
  });

  it("le quita la barra final", () => {
    vi.stubEnv("VITE_API_BASE", "https://klara.sdar.dev/api/v1/");
    expect(apiBase()).toBe("https://klara.sdar.dev/api/v1");
  });
});

describe("deriveWsUrl", () => {
  it("usa wss en https y ws en http cuando la base es relativa", () => {
    expect(deriveWsUrl("/api/v1", { protocol: "https:", host: "klara.example" })).toBe(
      "wss://klara.example/api/v1/pronunciation/stream",
    );
    expect(deriveWsUrl("/api/v1", { protocol: "http:", host: "localhost:5273" })).toBe(
      "ws://localhost:5273/api/v1/pronunciation/stream",
    );
  });

  it("deriva de la base absoluta e ignora la ubicación", () => {
    expect(
      deriveWsUrl("https://klara.sdar.dev/api/v1", {
        protocol: "http:",
        host: "localhost:5273",
      }),
    ).toBe("wss://klara.sdar.dev/api/v1/pronunciation/stream");
  });

  it("usa ws: cuando la base absoluta es http", () => {
    expect(
      deriveWsUrl("http://192.168.1.10:8000/api/v1", { protocol: "http:", host: "x" }),
    ).toBe("ws://192.168.1.10:8000/api/v1/pronunciation/stream");
  });
});
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `cd frontend && npx vitest run src/lib/apiBase.test.ts`
Expected: FAIL — `Failed to resolve import "./apiBase"`.

- [ ] **Step 3: Implementar `apiBase.ts`**

Crear `frontend/src/lib/apiBase.ts`:

```ts
/** Streaming subpath, relative to the API base. */
export const STREAM_SUBPATH = "/pronunciation/stream";

/**
 * Base of the API. Relative (same-origin) on the web, absolute in the native
 * build, where the WebView origin is https://localhost and there is no proxy.
 *
 * NOTE: the env var is VITE_API_BASE, not VITE_API_BASE_URL — the latter is the
 * Vite dev-proxy target (an origin, no /api/v1) and reusing it breaks `npm run dev`.
 */
export function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE as string | undefined;
  if (!configured) return "/api/v1";
  return configured.replace(/\/+$/, "");
}

export function deriveWsUrl(
  base: string = apiBase(),
  loc: { protocol: string; host: string } = window.location,
): string {
  if (/^https?:\/\//i.test(base)) {
    return base.replace(/^http/i, "ws") + STREAM_SUBPATH;
  }
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${loc.host}${base}${STREAM_SUBPATH}`;
}
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run: `cd frontend && npx vitest run src/lib/apiBase.test.ts`
Expected: PASS, 6 tests.

- [ ] **Step 5: Mover `deriveWsUrl` fuera de `streamClient.ts`**

En `frontend/src/lib/streamClient.ts`, borrar el bloque de las líneas 41-49
(`STREAM_PATH` y la vieja `deriveWsUrl`) y reexportar desde el módulo nuevo para
no romper importadores:

```ts
import { apiBase, deriveWsUrl } from "./apiBase";

export { deriveWsUrl };
/** Full path of the stream, kept for callers that still reference it. */
export const STREAM_PATH = "/api/v1/pronunciation/stream";
```

Y en la línea 60, cambiar:

```ts
const url = opts.url ?? deriveWsUrl(window.location);
```

por:

```ts
const url = opts.url ?? deriveWsUrl(apiBase(), window.location);
```

- [ ] **Step 6: Actualizar el test viejo de `deriveWsUrl`**

En `frontend/src/lib/streamClient.test.ts`, reemplazar el bloque de las líneas
35-44 por su versión con la firma nueva (los casos completos ya viven en
`apiBase.test.ts`; aquí solo queda la garantía de que la reexportación funciona):

```ts
describe("deriveWsUrl", () => {
  it("se reexporta y sigue derivando del mismo origen", () => {
    expect(deriveWsUrl("/api/v1", { protocol: "https:", host: "klara.example" })).toBe(
      "wss://klara.example/api/v1/pronunciation/stream",
    );
  });
});
```

- [ ] **Step 7: Cambiar las cinco costuras restantes**

`frontend/src/api/client.ts:44` — borrar la constante `API_BASE` y añadir:

```ts
import { apiBase } from "../lib/apiBase";
```

Después, en los **seis** `fetch` del archivo (líneas 101, 152, 336, 430, 475 y 546
antes del cambio), reemplazar cada `` `${API_BASE}` `` por `` `${apiBase()}` ``.
No puede quedar ninguna referencia a `API_BASE`; verifícalo con
`grep -n "API_BASE" src/api/client.ts` (debe salir vacío).

`frontend/src/lib/tts.ts:34`:

```ts
import { apiBase } from "./apiBase";

function ttsUrl(text: string, lang?: string, mode?: TTSMode): string {
  let url = `${apiBase()}/tts?text=${encodeURIComponent(text)}`;
  if (lang) url += `&lang=${encodeURIComponent(lang)}`;
  url += `&mode=${mode ?? "narration"}`;
  return url;
}
```

`frontend/src/lib/waveform.ts:18`:

```ts
import { apiBase } from "./apiBase";

function urlFor(text: string, lang?: string): string {
  let url = `${apiBase()}/tts?text=${encodeURIComponent(text)}`;
  if (lang) url += `&lang=${encodeURIComponent(lang)}`;
  url += "&mode=narration";
  return url;
}
```

`frontend/src/routes/Login.tsx:42` — dentro de `onGoogle()`:

```ts
const resp = await fetch(`${apiBase()}/auth/google/authorize`, {
  credentials: "include",
});
```

`frontend/src/routes/Signup.tsx:33`:

```ts
const r = await fetch(`${apiBase()}/invitations/${inviteToken}`);
```

En ambos archivos añadir `import { apiBase } from "../lib/apiBase";`.

- [ ] **Step 8: Verificar que no queda ninguna costura**

Run:
```bash
cd frontend && grep -rn '"/api/v1\|`/api/v1' src --include=*.ts --include=*.tsx \
  | grep -v ".test.ts" | grep -v "apiBase.ts" | grep -v "STREAM_PATH"
```
Expected: sin resultados.

- [ ] **Step 9: Gates y commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run test`
Expected: todo verde.

```bash
git add frontend/src/lib/apiBase.ts frontend/src/lib/apiBase.test.ts \
  frontend/src/lib/streamClient.ts frontend/src/lib/streamClient.test.ts \
  frontend/src/api/client.ts frontend/src/lib/tts.ts frontend/src/lib/waveform.ts \
  frontend/src/routes/Login.tsx frontend/src/routes/Signup.tsx
git commit -m "feat(native): apiBase() — las seis costuras de mismo origen (F-A1 §3)"
```

---

### Task 2: `native.ts` — la única puerta a Capacitor

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json` (dependencias)
- Create: `frontend/src/lib/native.ts`
- Create: `frontend/src/lib/native.test.ts`

**Interfaces:**
- Consume: nada de tareas anteriores.
- Produce:
  - `isNative(): boolean`
  - `getToken(): Promise<string | null>`
  - `setToken(token: string): Promise<void>`
  - `clearToken(): Promise<void>`
  - `authHeaders(): Promise<Record<string, string>>` — `{}` en web o sin token
  - `tap(): void` — háptico ligero, no-op en web

- [ ] **Step 1: Instalar las dependencias**

Run:
```bash
cd frontend
npm install --save-exact \
  @capacitor/core@8.5.0 @capacitor/preferences@8.0.1 @capacitor/haptics@8.0.2 \
  @capacitor/app@8.1.1 @capacitor/splash-screen@8.0.2 @capacitor/status-bar@8.0.3 \
  @capacitor/keyboard@8.0.5 @capgo/capacitor-social-login@8.5.0
npm install --save-exact --save-dev @capacitor/cli@8.5.0 @capacitor/android@8.5.0
```

- [ ] **Step 2: Escribir el test que falla**

Crear `frontend/src/lib/native.test.ts`. En vitest no hay plataforma nativa, así
que `Capacitor.isNativePlatform()` devuelve `false` de verdad — el test cubre el
camino web, que es el que no puede romperse:

```ts
import { describe, expect, it } from "vitest";
import { authHeaders, clearToken, getToken, isNative, setToken, tap } from "./native";

describe("native.ts en web", () => {
  it("isNative() es false", () => {
    expect(isNative()).toBe(false);
  });

  it("tap() no lanza y no devuelve nada", () => {
    expect(tap()).toBeUndefined();
  });

  it("el token es null y guardarlo es un no-op", async () => {
    await setToken("no-deberia-guardarse");
    expect(await getToken()).toBeNull();
    await clearToken();
    expect(await getToken()).toBeNull();
  });

  it("authHeaders() está vacío", async () => {
    expect(await authHeaders()).toEqual({});
  });
});
```

- [ ] **Step 3: Correr el test para verificar que falla**

Run: `cd frontend && npx vitest run src/lib/native.test.ts`
Expected: FAIL — `Failed to resolve import "./native"`.

- [ ] **Step 4: Implementar `native.ts`**

Crear `frontend/src/lib/native.ts`:

```ts
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";
import { Haptics, ImpactStyle } from "@capacitor/haptics";

const TOKEN_KEY = "klara.bearer";

/** The only place in the app allowed to ask whether we are inside the shell. */
export function isNative(): boolean {
  return Capacitor.isNativePlatform();
}

/**
 * Bearer token, in the app's private SharedPreferences (spec §3). Not Keystore:
 * Google retired EncryptedSharedPreferences in 2024, and the token is revocable
 * server-side, so a leak is killed from the box.
 */
export async function getToken(): Promise<string | null> {
  if (!isNative()) return null;
  const { value } = await Preferences.get({ key: TOKEN_KEY });
  return value ?? null;
}

export async function setToken(token: string): Promise<void> {
  if (!isNative()) return;
  await Preferences.set({ key: TOKEN_KEY, value: token });
}

export async function clearToken(): Promise<void> {
  if (!isNative()) return;
  await Preferences.remove({ key: TOKEN_KEY });
}

export async function authHeaders(): Promise<Record<string, string>> {
  const token = await getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Light tap when grading a review. No-op on the web. */
export function tap(): void {
  if (!isNative()) return;
  void Haptics.impact({ style: ImpactStyle.Light }).catch(() => undefined);
}
```

- [ ] **Step 5: Correr el test para verificar que pasa**

Run: `cd frontend && npx vitest run src/lib/native.test.ts`
Expected: PASS, 4 tests.

- [ ] **Step 6: Gates y commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run test`

```bash
git add frontend/package.json frontend/package-lock.json \
  frontend/src/lib/native.ts frontend/src/lib/native.test.ts
git commit -m "feat(native): native.ts — la única puerta a Capacitor (F-A1 §3)"
```

---

### Task 3: Bearer en el cliente HTTP, login y logout nativos

**Files:**
- Modify: `frontend/src/api/client.ts` (`request`, `login`, `logout`, los 4 `fetch` directos)
- Create: `frontend/src/api/client.bearer.test.ts`

**Interfaces:**
- Consume: `apiBase()` (Tarea 1); `isNative`, `authHeaders`, `setToken`,
  `clearToken` (Tarea 2).
- Produce:
  - `api.login(email, password)` — en nativo pega a `/auth/bearer/login` y guarda el token
  - `api.logout()` — en nativo pega a `/auth/bearer/logout` y lo borra
  - `api.googleNative(idToken: string): Promise<string>` — devuelve el access_token

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/api/client.bearer.test.ts`. El camino web es el que hay que
blindar: no puede aparecer un header `Authorization` ni cambiar la ruta.

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

function mockFetch(status = 200, body = "{}") {
  const spy = vi.fn(
    async (_url: string, _init?: RequestInit) =>
      new Response(body, {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => vi.unstubAllGlobals());

describe("transporte en web", () => {
  it("el login va a /auth/jwt/login y no manda Authorization", async () => {
    const spy = mockFetch();
    await api.login("a@b.com", "secreta");
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/v1/auth/jwt/login");
    expect((init?.headers as Record<string, string>).Authorization).toBeUndefined();
    expect(init?.credentials).toBe("include");
  });

  it("el logout va a /auth/jwt/logout", async () => {
    const spy = mockFetch(204, "");
    await api.logout();
    expect(spy.mock.calls[0][0]).toBe("/api/v1/auth/jwt/logout");
  });

  it("request() no añade Authorization cuando no hay token", async () => {
    const spy = mockFetch(200, '{"id":"u1"}');
    await api.getMe();
    const [, init] = spy.mock.calls[0];
    expect((init?.headers as Record<string, string>).Authorization).toBeUndefined();
  });
});

describe("googleNative", () => {
  it("manda el id_token al endpoint nativo y devuelve el access_token", async () => {
    const spy = mockFetch(200, '{"access_token":"tok-1","token_type":"bearer"}');
    const out = await api.googleNative("id-token-de-google");
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/v1/auth/google/native");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ id_token: "id-token-de-google" });
    expect(out).toBe("tok-1");
  });
});
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `cd frontend && npx vitest run src/api/client.bearer.test.ts`
Expected: FAIL — `api.googleNative is not a function`.

- [ ] **Step 3: Añadir el header y arreglar el orden del spread en `request()`**

En `frontend/src/api/client.ts`, el `request()` de la línea 100. Hoy `...init` va
**después** de `headers`, así que un `init.headers` reemplazaría el objeto entero
—incluido el `Authorization`—. Hoy ningún llamador manda `headers` en `init`
(verificado el 2026-08-30), pero dejarlo así convierte el header de auth en un
accidente esperando. Se invierte el orden:

```ts
import { authHeaders, clearToken, isNative, setToken } from "../lib/native";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${apiBase()}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      "Accept-Language": i18n.language || "es",
      ...(await authHeaders()),
      ...(init?.headers ?? {}),
    },
  });
```

El resto de la función (el 401, el `ApiError`, el 204) queda **exactamente** igual.

- [ ] **Step 4: Añadir el header a los cuatro `fetch` directos**

Los `fetch` de las líneas 336 (`/pronunciation/score`), 430
(`/stories/{id}/quiz/resolve-mc`), 475 (`/speak/turn`) y 546 (`/taller/export`)
no pasan por `request()`. Los tres primeros mandan `FormData` y ya llevan un
objeto `headers` con `Accept-Language`; ahí se añade el spread:

```ts
headers: { "Accept-Language": i18n.language || "es", ...(await authHeaders()) },
```

El cuarto (`/taller/export`, línea 546) hoy no tiene `headers`; se le añade:

```ts
const resp = await fetch(`${apiBase()}/taller/export`, {
  credentials: "include",
  headers: await authHeaders(),
});
```

**No** le pongas `Content-Type` a los que mandan `FormData`: el navegador tiene
que poner el `boundary` él mismo.

- [ ] **Step 5: Bifurcar login y logout**

Reemplazar `login` (línea 150) por:

```ts
login: async (email: string, password: string): Promise<void> => {
  const body = new URLSearchParams({ username: email, password });
  const path = isNative() ? "/auth/bearer/login" : "/auth/jwt/login";
  const resp = await fetch(`${apiBase()}${path}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "Accept-Language": i18n.language || "es",
    },
    body: body.toString(),
  });
  // ↓ conserva TAL CUAL el manejo de error que ya tenía el login original
  //   (líneas 160-172): es el que las pantallas de login interpretan hoy.
  if (isNative() && resp.ok) {
    const data = (await resp.json()) as { access_token: string };
    await setToken(data.access_token);
  }
},
```

> **Importante:** no reescribas el bloque de error. Lee las líneas 160-172
> actuales y déjalas idénticas; lo único que se añade es la línea del `path` y el
> bloque `if (isNative() && resp.ok)` al final. Si el original ya consume
> `resp.json()`, encadena en vez de leer el body dos veces (un `Response` solo se
> puede leer una vez).

Reemplazar `logout` (línea 174) por:

```ts
logout: async (): Promise<void> => {
  const path = isNative() ? "/auth/bearer/logout" : "/auth/jwt/logout";
  try {
    await request<void>(path, { method: "POST" });
  } finally {
    await clearToken();
  }
},
```

El `finally` importa: si el logout falla por red, el token local igual se borra.
La sesión del servidor queda viva hasta que expire, pero el teléfono ya no la
tiene — que es el fallo seguro correcto.

- [ ] **Step 6: Añadir `googleNative`**

Junto a `logout`, en el objeto `api`:

```ts
googleNative: async (idToken: string): Promise<string> => {
  const data = await request<{ access_token: string }>("/auth/google/native", {
    method: "POST",
    body: JSON.stringify({ id_token: idToken }),
  });
  return data.access_token;
},
```

- [ ] **Step 7: Correr los tests**

Run: `cd frontend && npx vitest run src/api/`
Expected: PASS — el nuevo y `client.reviewCard.test.ts` sin tocar.

- [ ] **Step 8: Gates y commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run test`

```bash
git add frontend/src/api/client.ts frontend/src/api/client.bearer.test.ts
git commit -m "feat(native): Bearer en el cliente, login y logout nativos (F-A1 §3)"
```

---

### Task 4: Google nativo en la pantalla de login

Hoy `Login.tsx:97` esconde el botón solo si `navigator.standalone === true`. En
Capacitor eso es `false`, así que el botón aparecería y dispararía el flujo web
—que Google **bloquea** dentro de un WebView con `disallowed_useragent`—. No
basta con mostrarlo: hay que cambiar lo que hace.

**Files:**
- Create: `frontend/src/lib/googleNative.ts`
- Modify: `frontend/src/routes/Login.tsx:22, 39-52, 97`
- Modify: `frontend/src/lib/auth.ts` (exponer `refreshUser` si aún no existe)
- Modify: `frontend/src/locales/{es,en,de,fr,ja,pt}/common.json`
- Modify: `frontend/.env.example`

**Interfaces:**
- Consume: `isNative`, `setToken` (Tarea 2); `api.googleNative` (Tarea 3).
- Produce: `signInWithGoogleNative(): Promise<void>` — deja el token guardado o lanza.

- [ ] **Step 1: Implementar el envoltorio del plugin**

Crear `frontend/src/lib/googleNative.ts`. El `webClientId` es el **Web** client
id, no el de Android: el ID token que devuelve Credential Manager lleva ese
`aud`, y es el que `/auth/google/native` valida (spec §2.2). El cliente Android
existe solo para que Google autorice a esta app firmada con esta llave; nunca
aparece en el código.

```ts
import { SocialLogin } from "@capgo/capacitor-social-login";
import { api } from "../api/client";
import { setToken } from "./native";

const WEB_CLIENT_ID = import.meta.env.VITE_GOOGLE_WEB_CLIENT_ID as string | undefined;

export class GoogleNotConfigured extends Error {}

let initialized = false;

async function ensureInit(): Promise<void> {
  if (initialized) return;
  if (!WEB_CLIENT_ID) throw new GoogleNotConfigured("VITE_GOOGLE_WEB_CLIENT_ID no está definida");
  await SocialLogin.initialize({ google: { webClientId: WEB_CLIENT_ID } });
  initialized = true;
}

/** Credential Manager → ID token → our endpoint → stored bearer. */
export async function signInWithGoogleNative(): Promise<void> {
  await ensureInit();
  const res = await SocialLogin.login({ provider: "google", options: {} });
  const idToken = (res.result as { idToken?: string } | undefined)?.idToken;
  if (!idToken) throw new Error("Google no devolvió idToken");
  const token = await api.googleNative(idToken);
  await setToken(token);
}
```

> El ejecutor debe confirmar la forma exacta de `SocialLogin.login()` y de su
> respuesta contra la versión 8.5.0 instalada, en
> `node_modules/@capgo/capacitor-social-login/dist/esm/definitions.d.ts`, y
> ajustar el acceso a `idToken` si el tipo difiere. **No adivines la forma**: si
> no calza, dilo en el reporte de la tarea en vez de forzar un cast.

- [ ] **Step 2: Bifurcar el handler en `Login.tsx`**

Reemplazar `onGoogle` (línea 39):

```ts
async function onGoogle() {
  setError(null);
  try {
    if (isNative()) {
      await signInWithGoogleNative();
      await refreshUser();
      navigate(from, { replace: true });
      return;
    }
    const resp = await fetch(`${apiBase()}/auth/google/authorize`, {
      credentials: "include",
    });
    if (!resp.ok) throw new Error(`http ${resp.status}`);
    const data = (await resp.json()) as { authorization_url?: string };
    if (!data.authorization_url) throw new Error("no authorization_url");
    window.location.href = data.authorization_url;
  } catch (err) {
    setError(
      err instanceof GoogleNotConfigured
        ? t("auth.login.error.googleNativeUnavailable")
        : t("auth.login.error.googleFailed"),
    );
  }
}
```

`refreshUser` sale del contexto de auth. Si `useAuth()` no lo expone, añádelo en
`frontend/src/lib/auth.ts` reutilizando el `fetchMe` que ya existe ahí (línea 61)
— no dupliques la lógica de lectura del usuario.

- [ ] **Step 3: Mostrar el botón en nativo**

Línea 22, ampliar la condición para que solo esconda en la PWA de iOS:

```ts
const iosStandalone =
  (navigator as Navigator & { standalone?: boolean }).standalone === true;
const hideGoogle = iosStandalone && !isNative();
```

Línea 97:

```tsx
{!hideGoogle && (
```

- [ ] **Step 4: Añadir la cadena de error del camino nativo**

En los seis `frontend/src/locales/*/common.json`, junto a
`auth.login.error.googleFailed` (línea 649 en cada uno), añadir la clave
`googleNativeUnavailable`:

| Locale | Valor |
|---|---|
| es | `"El inicio de sesión con Google no está disponible en esta versión del app."` |
| en | `"Google sign-in isn't available in this version of the app."` |
| de | `"Die Google-Anmeldung ist in dieser App-Version nicht verfügbar."` |
| fr | `"La connexion Google n'est pas disponible dans cette version de l'application."` |
| ja | `"このバージョンのアプリでは Google ログインを利用できません。"` |
| pt | `"O login com Google não está disponível nesta versão do app."` |

- [ ] **Step 5: Documentar la variable**

En `frontend/.env.example`, añadir con su explicación:

```
# Client ID *Web* del proyecto de Google Cloud (NO el de Android). El ID token
# que devuelve Credential Manager en el teléfono lleva este valor como `aud`, y
# es el que valida POST /api/v1/auth/google/native. Solo hace falta para el
# build nativo; ponlo en frontend/.env.native.local, que está en .gitignore.
VITE_GOOGLE_WEB_CLIENT_ID=
```

- [ ] **Step 6: Gates y commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run test`
Expected: `i18n:check` verde (la clave nueva está en los seis locales).

```bash
git add frontend/src/lib/googleNative.ts frontend/src/routes/Login.tsx \
  frontend/src/lib/auth.ts frontend/src/locales frontend/.env.example
git commit -m "feat(native): Google por Credential Manager en la pantalla de login (F-A1 §3)"
```

---

### Task 5: TTS y waveform bajo Bearer

Un `<audio src>` no puede mandar headers. En nativo `speak()` baja el audio con
`fetch`, lo vuelve blob y se lo da al mismo elemento desbloqueado de `tts.ts:102`.

**Files:**
- Modify: `frontend/src/lib/tts.ts:34, 102-110, 141-150`
- Modify: `frontend/src/lib/waveform.ts:42`
- Create: `frontend/src/lib/tts.native.test.ts`

**Interfaces:**
- Consume: `apiBase()` (Tarea 1); `isNative`, `authHeaders` (Tarea 2).
- Produce: `ttsSourceForTest` (costura de test); `speak()` mantiene su firma.

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/lib/tts.native.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { ttsSourceForTest } from "./tts";

afterEach(() => vi.unstubAllGlobals());

describe("origen del audio de TTS", () => {
  it("en web devuelve la URL directa y no hace fetch", async () => {
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    const src = await ttsSourceForTest("Hallo", "de", "narration");
    expect(src).toBe("/api/v1/tts?text=Hallo&lang=de&mode=narration");
    expect(spy).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `cd frontend && npx vitest run src/lib/tts.native.test.ts`
Expected: FAIL — `ttsSourceForTest` no está exportado.

- [ ] **Step 3: Implementar el origen del audio**

En `frontend/src/lib/tts.ts`, justo después de `ttsUrl`:

```ts
import { authHeaders, isNative } from "./native";

let lastBlobUrl: string | null = null;

/**
 * Where the <audio> element should point. On the web that's the plain URL and
 * the cookie rides along; in the shell the token can't ride on <audio src>, so
 * we fetch with the header and hand over a blob. The previous blob is revoked
 * on every call — otherwise every played sentence leaks a few hundred KB.
 */
async function ttsSource(text: string, lang?: string, mode?: TTSMode): Promise<string> {
  const url = ttsUrl(text, lang, mode);
  if (!isNative()) return url;
  const resp = await fetch(url, { headers: await authHeaders() });
  if (!resp.ok) throw new Error(`tts fetch failed: ${resp.status}`);
  const blob = await resp.blob();
  if (lastBlobUrl) URL.revokeObjectURL(lastBlobUrl);
  lastBlobUrl = URL.createObjectURL(blob);
  return lastBlobUrl;
}

/** Test seam — do not use in app code. */
export const ttsSourceForTest = ttsSource;
```

En la línea 145, la asignación `a.src = ttsUrl(text, language, opts?.mode);` pasa
a ser asíncrona. `speak()` es síncrona y debe seguirlo siendo, así que solo se
difiere esa asignación:

```ts
a.preload = "auto";
void ttsSource(text, language, opts?.mode)
  .then((src) => {
    if (gen !== generation) return;
    a.src = src;
    a.load();
  })
  .catch(() => tryFallback());
```

> **Antes de editar, lee las líneas 141-215 completas.** Hoy `a.src` se asigna
> *antes* de registrar los listeners de `error` y `canplay` (líneas 181 y
> siguientes). La asignación diferida tiene que quedar **después** de que esos
> listeners existan, o el evento se pierde y el audio nunca arranca. Mueve la
> llamada a `ttsSource(...)` al final del bloque de configuración, no donde
> estaba `a.src`.

- [ ] **Step 4: Añadir el header al waveform**

`frontend/src/lib/waveform.ts:42`:

```ts
const resp = await fetch(urlFor(text, lang), { headers: await authHeaders() });
```

Con `import { authHeaders } from "./native";` arriba. La caché `immutable` del
backend sigue aplicando: el navegador cachea respuestas a peticiones con
`Authorization` cuando la respuesta trae `max-age`, así que TTS y waveform siguen
compartiendo la misma entrada de caché para la misma URL.

- [ ] **Step 5: Correr los tests**

Run: `cd frontend && npx vitest run src/lib/`
Expected: PASS, incluidos los 12 archivos de test que ya existían.

- [ ] **Step 6: Gates y commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run test`

```bash
git add frontend/src/lib/tts.ts frontend/src/lib/tts.native.test.ts frontend/src/lib/waveform.ts
git commit -m "feat(native): TTS por fetch+blob y waveform con Bearer (F-A1 §3)"
```

---

### Task 6: El token en el handshake del WebSocket

**Files:**
- Modify: `frontend/src/lib/streamClient.ts` (tipo de opciones y `onopen`, línea 102)
- Modify: `frontend/src/lib/useSentencePractice.ts:342-346`
- Modify: `frontend/src/lib/streamClient.test.ts`

**Interfaces:**
- Consume: `getToken` (Tarea 2).
- Produce: `openScoreStream({ ..., token?: string })` — manda `token` en el primer
  frame **solo** cuando se le pasa.

- [ ] **Step 1: Escribir el test que falla**

Añadir a `frontend/src/lib/streamClient.test.ts`:

```ts
it("incluye token en el handshake solo cuando se le pasa", () => {
  make({ token: "tok-abc" });
  ws.open();
  expect(JSON.parse(ws.sent[0] as string)).toEqual({
    reference_text: "Hallo Welt",
    language: "de",
    token: "tok-abc",
  });
});

it("no incluye la clave token cuando no se le pasa", () => {
  make();
  ws.open();
  expect(Object.keys(JSON.parse(ws.sent[0] as string))).toEqual([
    "reference_text",
    "language",
  ]);
});
```

> El helper `make()` del archivo hay que ampliarlo para aceptar opciones extra y
> reenviarlas a `openScoreStream`. Léelo antes de escribir el test y respeta su
> forma actual — no lo reescribas.

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `cd frontend && npx vitest run src/lib/streamClient.test.ts`
Expected: FAIL — el handshake no trae `token`.

- [ ] **Step 3: Implementar**

Añadir `token?: string` al tipo de opciones de `openScoreStream`, y en `onopen`
(línea 102):

```ts
ws.onopen = () => {
  if (settled) return;
  // Handshake MUST be the first frame (backend reads it before the session).
  // The token goes here and never in the URL: query strings land in access logs.
  ws.send(
    JSON.stringify({
      reference_text: opts.referenceText,
      language: opts.language,
      ...(opts.token ? { token: opts.token } : {}),
    }),
  );
  for (const buf of pending) sendBinary(buf);
  pending.length = 0;
};
```

- [ ] **Step 4: Pasarle el token desde el hook**

En `frontend/src/lib/useSentencePractice.ts:342`, la llamada a `openScoreStream`
ya está dentro de un bloque `async`, así que puede esperar el token:

```ts
const aligner = createAligner(current.target);
const stream = openScoreStream({
  referenceText: current.target,
  language: targetLanguage,
  token: (await getToken()) ?? undefined,
  onWord: (w) => {
```

Con `import { getToken } from "./native";` arriba. En web `getToken()` devuelve
`null`, la clave no viaja y el WS sigue autenticando por cookie, igual que hoy.

- [ ] **Step 5: Correr los tests**

Run: `cd frontend && npx vitest run src/lib/streamClient.test.ts`
Expected: PASS, incluidos los que ya existían.

- [ ] **Step 6: Gates y commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run test`

```bash
git add frontend/src/lib/streamClient.ts frontend/src/lib/streamClient.test.ts \
  frontend/src/lib/useSentencePractice.ts
git commit -m "feat(native): token en el primer frame del WS de pronunciación (F-A1 §3)"
```

---

### Task 7: El proyecto Capacitor — config, scripts, `android/`, manifest

**Files:**
- Create: `frontend/capacitor.config.ts`
- Create: `frontend/android/` (generado y commiteado)
- Create: `frontend/.gitignore`
- Modify: `frontend/package.json` (scripts)
- Modify: `frontend/vite.config.ts` (apagar el SW en nativo)
- Modify: `frontend/android/app/src/main/AndroidManifest.xml`
- Modify: `frontend/android/variables.gradle`

**Interfaces:**
- Consume: las dependencias de la Tarea 2.
- Produce: `npm run build:native`, `npm run cap:sync`, `npm run android:run`.

- [ ] **Step 1: Apagar el service worker en el build nativo**

En `frontend/vite.config.ts`, dentro de la llamada a `VitePWA({...})`, como
primera opción:

```ts
VitePWA({
  disable: !!env.VITE_NATIVE,
  registerType: "autoUpdate",
```

Un SW dentro del WebView es inútil —el bundle ya es local— y el soporte en
Android System WebView es poco fiable. En web no cambia nada: `VITE_NATIVE` solo
lo define `build:native`.

- [ ] **Step 2: Crear `capacitor.config.ts`**

```ts
import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "dev.sdar.klara",
  appName: "Klara",
  webDir: "dist",
  android: {
    allowMixedContent: false,
    // targetSdk 35+ forces edge-to-edge; without this the WebView sits under
    // the status bar. The safe-area CSS in global.css handles the rest.
    adjustMarginsForEdgeToEdge: "auto",
  },
  plugins: {
    SplashScreen: { launchAutoHide: false, backgroundColor: "#F4EFE6" },
    Keyboard: { resize: "native" },
  },
};

export default config;
```

- [ ] **Step 3: Añadir los scripts**

En `frontend/package.json`, dentro de `scripts`:

```json
"build:native": "tsc -b && vite build --mode native",
"cap:sync": "npm run build:native && npx cap sync android",
"android:run": "npx cap run android -l --external"
```

Las variables van en un archivo de modo, no en la línea de comando. Crear
`frontend/.env.native` (**se commitea**, no tiene secretos):

```
VITE_NATIVE=1
VITE_API_BASE=https://klara.sdar.dev/api/v1
```

> Así se evita `cross-env`: `VAR=x cmd` no es sintaxis válida en cmd ni en
> PowerShell, y el dueño trabaja en Windows. Vite ya carga `.env.native` (y
> `.env.native.local`) cuando corre con `--mode native`, y el `loadEnv(mode, ...)`
> que `vite.config.ts:5` ya hace las recoge — así que `env.VITE_NATIVE` funciona
> para el `disable` del PWA sin tocar nada más. Cero dependencias nuevas.
>
> El client id de Google va en `frontend/.env.native.local`, que está en
> `.gitignore` y Vite también carga en ese modo:
> `VITE_GOOGLE_WEB_CLIENT_ID=<el client id Web del proyecto 904183028633>`.
>
> `android:run` **no** usa `--mode native` a propósito: en live reload el WebView
> carga el Vite de la PC y el proxy `/api` de `vite.config.ts:65` reenvía HTTP y
> WS al backend, así que la base relativa es la correcta y el SW debe seguir
> apagado solo en el build de producción.

- [ ] **Step 4: Generar el proyecto Android**

Run:
```bash
cd frontend
npm run build:native
npx cap add android
```

Expected: se crea `frontend/android/` y `cap` reporta los plugins detectados
(deben salir los 7 de Capacitor más el de social-login). Si Gradle se queja del
SDK, crear `frontend/android/local.properties` con
`sdk.dir=C\:\\Users\\simon\\AppData\\Local\\Android\\Sdk` — ese archivo va
ignorado, es por máquina.

- [ ] **Step 5: Fijar las versiones del SDK**

En `frontend/android/variables.gradle`, confirmar o corregir:

```gradle
minSdkVersion = 24
compileSdkVersion = 36
targetSdkVersion = 36
```

- [ ] **Step 6: El manifest**

En `frontend/android/app/src/main/AndroidManifest.xml`:

En la etiqueta `<application ...>` añadir `android:allowBackup="false"` — el token
vive en SharedPreferences y no debe viajar a la copia de seguridad de Google.

Y antes de `<application>`, los permisos:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<!-- Sin MODIFY_AUDIO_SETTINGS, getUserMedia da NotAllowedError aunque el
     usuario acepte el permiso: el bridge de Capacitor concede el del WebView,
     pero el motor de audio necesita este otro. -->
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
```

`POST_NOTIFICATIONS` **no** va todavía: es de F-A2, y pedir un permiso que no se
usa es ruido en la ficha de Play.

- [ ] **Step 7: Ignorar lo generado por Gradle**

Crear `frontend/.gitignore` (o añadir si ya existe):

```
android/local.properties
android/.gradle/
android/build/
android/app/build/
android/capacitor-cordova-android-plugins/
.env.native.local
```

- [ ] **Step 8: Verificar que compila**

Run:
```bash
cd frontend && npm run cap:sync
cd android && ./gradlew assembleDebug
```
Expected: `BUILD SUCCESSFUL`, y el APK en
`frontend/android/app/build/outputs/apk/debug/app-debug.apk`.

- [ ] **Step 9: Gates y commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run test`

```bash
git add frontend/capacitor.config.ts frontend/package.json frontend/package-lock.json \
  frontend/vite.config.ts frontend/.gitignore frontend/.env.native frontend/android
git commit -m "feat(native): proyecto Capacitor 8 para Android — config, scripts y manifest (F-A1 §1, §4)"
```

---

### Task 8: El cascarón — splash, barra de estado, teclado, atrás, hápticos

**Files:**
- Create: `frontend/src/components/NativeChrome.tsx`
- Create: `frontend/src/styles/native.css`
- Modify: `frontend/src/App.tsx` (montar `NativeChrome`)
- Modify: `frontend/src/main.tsx` (importar el CSS)

**Interfaces:**
- Consume: `isNative`, `tap` (Tarea 2); `useTheme()` de
  `frontend/src/lib/preferences.ts:78`, que devuelve `[Theme, (t: Theme) => void]`
  con `Theme = "light" | "dark"`.
- Produce: `<NativeChrome />` — no renderiza nada, solo efectos.

- [ ] **Step 1: Implementar `NativeChrome`**

Crear `frontend/src/components/NativeChrome.tsx`:

```tsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { App as CapApp } from "@capacitor/app";
import { SplashScreen } from "@capacitor/splash-screen";
import { StatusBar, Style } from "@capacitor/status-bar";
import { isNative } from "../lib/native";
import { useTheme } from "../lib/preferences";

const PAPER = { light: "#F4EFE6", dark: "#16181C" } as const;

/** Renders nothing: it is the shell's side effects, gathered in one place. */
export default function NativeChrome() {
  const [theme] = useTheme();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isNative()) return;
    document.documentElement.classList.add("native");
    void SplashScreen.hide();
  }, []);

  useEffect(() => {
    if (!isNative()) return;
    // index.html's theme-color metas follow prefers-color-scheme, which stops
    // matching once the user picks a theme by hand. The bar follows the app's
    // choice (klara.theme), not the system's.
    void StatusBar.setBackgroundColor({ color: PAPER[theme] });
    void StatusBar.setStyle({ style: theme === "dark" ? Style.Dark : Style.Light });
  }, [theme]);

  useEffect(() => {
    if (!isNative()) return;
    const handle = CapApp.addListener("backButton", ({ canGoBack }) => {
      if (canGoBack) navigate(-1);
      else void CapApp.exitApp();
    });
    return () => {
      void handle.then((h) => h.remove());
    };
  }, [navigate]);

  return null;
}
```

- [ ] **Step 2: Montarlo**

`NativeChrome` usa `useNavigate`, así que va **dentro** del `BrowserRouter` — es
decir en `frontend/src/App.tsx`, no en `main.tsx`. Como primer hijo del layout
raíz:

```tsx
import NativeChrome from "./components/NativeChrome";
```
```tsx
<NativeChrome />
```

- [ ] **Step 3: El CSS del cascarón**

Crear `frontend/src/styles/native.css`:

```css
/* Only inside the shell: on the web these would break normal page behaviour. */
html.native,
html.native body {
  overscroll-behavior: none;
}
html.native {
  -webkit-tap-highlight-color: transparent;
}
html.native button,
html.native .k-btn,
html.native [role="button"] {
  user-select: none;
  -webkit-user-select: none;
}
```

E importarlo en `frontend/src/main.tsx`, **después** de `global.css` para que gane
en especificidad de orden:

```ts
import "./styles/native.css";
```

- [ ] **Step 4: El háptico al calificar**

Localizar los sitios donde se califica un repaso:

```bash
cd frontend && grep -rn "reviewCard\|reviewStudyCard" src --include=*.tsx | grep -v test
```

En cada handler de calificación, llamar `tap()` justo antes de mandar la
calificación:

```ts
import { tap } from "../lib/native";
```
```ts
tap();
await api.reviewCard(cardId, rating, elapsed);
```

`tap()` es no-op en web, así que no hace falta ningún condicional.

- [ ] **Step 5: Gates y commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run test`

```bash
git add frontend/src/components/NativeChrome.tsx frontend/src/styles/native.css \
  frontend/src/App.tsx frontend/src/main.tsx frontend/src/routes frontend/src/components
git commit -m "feat(native): el cascarón — splash, barra de estado, atrás y hápticos (F-A1 §4)"
```

---

### Task 9: Soltar el micrófono cuando el app se va a segundo plano

Android corta `getUserMedia` en segundo plano desde la 9. Hoy el WS, el worklet y
el MediaRecorder quedarían colgados. Y hay una carrera preexistente que el
listener de `pause` **empeora**: si el app se va al fondo mientras
`await startMicRecording()` espera el permiso, el teardown corre antes de que
exista el recorder, y al resolverse quedan micrófono, WS y worklet huérfanos.
`Speak.tsx:446` ya tiene el guard correcto; los otros tres consumidores no.

**Files:**
- Modify: `frontend/src/lib/useSentencePractice.ts:234, 334`
- Modify: `frontend/src/lib/useMicScorer.ts:123, 161`
- Modify: `frontend/src/components/StoryFinish.tsx:350, 421`

**Interfaces:**
- Consume: `isNative` (Tarea 2); `teardownStream` que ya existe en
  `useSentencePractice.ts:217`.
- Produce: sin API nueva.

- [ ] **Step 1: Guard de montaje tras el permiso**

En `useSentencePractice.ts`, junto a los otros refs:

```ts
const unmountedRef = useRef(false);
```

En el `useEffect` de desmontaje (línea 234), marcarlo:

```ts
useEffect(() => {
  return () => {
    unmountedRef.current = true;
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setMicAnalyser(null);
    teardownStream();
  };
}, [teardownStream]);
```

Y en la línea 334, replicar el guard que `Speak.tsx:446` ya tiene:

```ts
const rec = await startMicRecording();
if (unmountedRef.current) {
  rec.cancel();
  return;
}
recorderRef.current = rec;
```

Hacer lo mismo en `useMicScorer.ts:123` y en el quiz de `StoryFinish.tsx:350`,
con el ref de desmontaje que cada uno tenga; si no tienen, añádelo igual que
arriba y márcalo en su cleanup existente (`useMicScorer.ts:161`,
`StoryFinish.tsx:421`).

- [ ] **Step 2: Soltar en `pause`**

En `useSentencePractice.ts`, un efecto nuevo junto al de desmontaje:

```ts
useEffect(() => {
  if (!isNative()) return;
  const handle = CapApp.addListener("pause", () => {
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setMicAnalyser(null);
    teardownStream();
  });
  return () => {
    void handle.then((h) => h.remove());
  };
}, [teardownStream]);
```

Con `import { App as CapApp } from "@capacitor/app";` e
`import { isNative } from "./native";`.

`recorder.cancel()` ya libera las pistas del `MediaStream` vía el `cleanup()` de
`pronunciation.ts:243`, y `teardownStream()` cierra el WS y el worklet — no
dupliques nada de eso aquí.

- [ ] **Step 3: Verificar que el camino web no cambió**

Run: `cd frontend && npx vitest run src/lib/`
Expected: PASS. Los efectos nuevos salen por `isNative()` antes de tocar nada, así
que en vitest son no-ops.

- [ ] **Step 4: Gates y commit**

Run: `cd frontend && npm run typecheck && npm run i18n:check && npm run test`

```bash
git add frontend/src/lib/useSentencePractice.ts frontend/src/lib/useMicScorer.ts \
  frontend/src/components/StoryFinish.tsx
git commit -m "fix(native): soltar micrófono, WS y worklet en pause; guard tras el permiso (F-A1 §4)"
```

---

### Task 10: El gate en dispositivo (manual — es el gate de la fase)

No hay CI de Android (Actions apagadas a propósito). Este checklist **es** el
criterio de terminado de F-A1, según spec §10.

- [ ] **Step 1: Instalar en el teléfono**

```bash
export ANDROID_HOME="$HOME/AppData/Local/Android/Sdk"
export PATH="$ANDROID_HOME/platform-tools:$PATH"
adb devices                      # debe listar el teléfono
cd frontend && npm run cap:sync
cd android && ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

- [ ] **Step 2: Correr el checklist**

Crear `docs/superpowers/plans/2026-08-30-f-a1-smoke-android.md` con esta tabla y
llenarla mientras se prueba, al estilo de `2026-07-31-fase1-smoke-iphone.md`:

| # | Qué se prueba | Esperado |
|---|---|---|
| 1 | Abrir el app en frío | Splash sobre `#F4EFE6`, luego el shell. Sin barra de navegador. |
| 2 | Barra de estado | Del color del tema; cambiar el tema en Ajustes la cambia en vivo. |
| 3 | Edge-to-edge | El contenido no queda debajo de la barra de estado ni de la de gestos. |
| 4 | Login con contraseña | Entra. Cerrar y reabrir el app: la sesión sigue viva (token en Preferences). |
| 5 | Login con Google | Abre el selector de cuentas **nativo**, no una página web. Entra. |
| 6 | Teclado | Abrir un campo de texto no rompe el layout ni tapa el botón. |
| 7 | Grabar una frase | Pide permiso de micrófono; el streaming pinta palabras en vivo; sale la nota. |
| 8 | TTS | Se oye. Pedir dos audios seguidos no deja el primero sonando. |
| 9 | Segundo plano con el micro abierto | Grabar, irse al home, volver: el micro está libre, sin sesión colgada. |
| 10 | Botón atrás | Navega hacia atrás; en la raíz cierra el app. |
| 11 | Háptico | Calificar un repaso vibra corto. |
| 12 | Cerrar sesión | Vuelve al login. El token viejo da **401**. |

Para el #12, con el token que el app tenía guardado:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://klara.sdar.dev/api/v1/users/me \
  -H "Authorization: Bearer <token-viejo>"     # esperado: 401
```

- [ ] **Step 3: Commit del acta**

```bash
git add docs/superpowers/plans/2026-08-30-f-a1-smoke-android.md
git commit -m "docs(native): acta del smoke de F-A1 en Android"
```

---

## Fuera de scope de F-A1 (no lo hagas aquí)

- Notificaciones locales y share target → **F-A2**.
- Audio en segundo plano y Media Session → **F-A3**. El WebView de Android no
  implementa Media Session, así que el app pierde los controles de pantalla
  bloqueada que la PWA tenía. Es conocido y aceptado hasta F-A3.
- Keystore de release, Play, `POST_NOTIFICATIONS` → **F-A4**.
- iOS: nada. Pero nada de lo de arriba puede ser Android-only por construcción.
- El 429 del limitador de login en `Login.tsx` (hoy todo error no-400 cae en
  "credenciales inválidas"). Anotado en F-A0; sigue pendiente y **no** bloquea
  este gate.

## Hallazgos del inventario que NO se arreglan aquí

Salieron al trazar el frontend el 2026-08-30. Ninguno es de F-A1; se dejan
escritos para que no se pierdan:

1. **`Onboarding.tsx:68,98` guarda `password` y `passwordConfirm` en
   `localStorage`** como parte del draft. Sobrevive al cierre del navegador y es
   legible por cualquier script en la página. Merece issue propio.
2. **`Practice.tsx` no llama `practice.stopAudio()` al desmontar**, cosa que
   `Story.tsx:87` sí hace: salir de Práctica con el TTS sonando lo deja sonando.
3. **`client.ts` tenía `...init` después de `headers`**, lo que permitía que un
   llamador borrara los headers base. Hoy ningún llamador lo hace; la Tarea 3 lo
   invierte de paso.

---

## Self-review

**Cobertura de la spec:** §1 (repo y builds) → Tareas 2 y 7. §3 (las costuras,
más las tres que el inventario añadió) → Tareas 1, 3, 4, 5, 6. §4 (el cascarón) →
Tareas 7, 8, 9. §10 (gate de F-A1) → Tarea 10. §11 (tests del frontend: `apiBase`,
`deriveWsUrl`, token en el handshake, `speak()` en nativo, `native.ts` en web) →
Tareas 1, 2, 5, 6.

**Desviaciones deliberadas de la spec, todas argumentadas en su tarea:**
1. `VITE_API_BASE` en vez de `VITE_API_BASE_URL` — el segundo ya es el target del
   proxy de Vite y tiene forma de origen, no de base.
2. Seis costuras de mismo-origen, no tres: faltaban `Signup.tsx:33` y
   `Login.tsx:42`.
3. El botón de Google no solo "aparece" en nativo: cambia de flujo, porque Google
   bloquea el OAuth web dentro de un WebView.
4. La Tarea 9 añade el guard de montaje, que la spec no pedía, porque el listener
   de `pause` convierte una carrera latente en una fuga real.
5. Las variables del build nativo van en `.env.native` con `vite build --mode
   native`, no en la línea de comando como escribía la spec §1: `VAR=x cmd` no es
   sintaxis válida en Windows, y el archivo de modo evita añadir `cross-env`.

**Consistencia de tipos:** `apiBase(): string` y
`deriveWsUrl(base?: string, loc?: { protocol: string; host: string }): string`
(Tarea 1) se usan con esa firma en las Tareas 3, 5 y 6.
`authHeaders(): Promise<Record<string, string>>` (Tarea 2) se usa `await`-eada en
las Tareas 3 y 5. `getToken(): Promise<string | null>` (Tarea 2) se convierte a
`string | undefined` en la Tarea 6 con `?? undefined`, porque `openScoreStream`
toma `token?: string`. `tap(): void` (Tarea 2) se usa en la Tarea 8.
