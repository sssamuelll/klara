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
 * server-side, so a leak is killed from the box. The manifest sets
 * android:allowBackup="false" so it never reaches Google's backup either.
 *
 * Every accessor is a no-op on the web on purpose: there the session is the
 * httponly cookie, and a token in localStorage would be strictly worse.
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

/** Light tap when grading a review. No-op on the web, so callers need no branch. */
export function tap(): void {
  if (!isNative()) return;
  void Haptics.impact({ style: ImpactStyle.Light }).catch(() => undefined);
}
