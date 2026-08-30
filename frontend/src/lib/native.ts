import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";
import { Preferences } from "@capacitor/preferences";
import { Haptics, ImpactStyle } from "@capacitor/haptics";

const TOKEN_KEY = "klara.bearer";

/** The only place in the app allowed to ask whether we are inside the shell. */
export function isNative(): boolean {
  return Capacitor.isNativePlatform();
}

/**
 * Run `fn` when Android backgrounds the app. Returns an unsubscribe.
 * No-op on the web. Together with NativeChrome this is the only door to
 * @capacitor/app — the boundary exists so a plugin's import-time side
 * effects can never reach the web bundle.
 */
export function onAppPause(fn: () => void): () => void {
  if (!isNative()) return () => undefined;
  const handle = App.addListener("pause", fn);
  return () => {
    void handle.then((h) => h.remove()).catch(() => undefined);
  };
}

/**
 * Bearer token, in the app's private SharedPreferences (spec §3). Not Keystore:
 * Google retired EncryptedSharedPreferences in 2024, and the token is revocable
 * server-side, so a leak is killed from the box. Task 7 of this phase sets
 * android:allowBackup="false" so it never reaches Google's backup either.
 *
 * Every accessor is a no-op on the web on purpose: there the session is the
 * httponly cookie, and a token in localStorage would be strictly worse.
 *
 * The three accessors treat storage failure differently, on purpose:
 * read and clear swallow, write does not. See each one.
 */
export async function getToken(): Promise<string | null> {
  if (!isNative()) return null;
  try {
    const { value } = await Preferences.get({ key: TOKEN_KEY });
    return value ?? null;
  } catch {
    // Fail closed. No token means no header, which means a 401, which the
    // existing unauthorized listener already routes to the login screen.
    // Rejecting instead would blow up every call site with a storage error.
    return null;
  }
}

/**
 * Does NOT swallow: a token we failed to persist leaves the user looking
 * logged in now and logged out on the next launch. That has to be visible at
 * the login call site, not silent.
 */
export async function setToken(token: string): Promise<void> {
  if (!isNative()) return;
  await Preferences.set({ key: TOKEN_KEY, value: token });
}

export async function clearToken(): Promise<void> {
  if (!isNative()) return;
  try {
    await Preferences.remove({ key: TOKEN_KEY });
  } catch {
    // Swallows because logout() calls this from a `finally`: throwing here
    // would replace the real error from the logout round trip with this one.
  }
}

export async function authHeaders(): Promise<Record<string, string>> {
  const token = await getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Light tap when grading a review. No-op on the web, so callers need no branch. */
export function tap(): void {
  if (!isNative()) return;
  void Haptics.impact({ style: ImpactStyle.Light }).catch(() => undefined);
}
