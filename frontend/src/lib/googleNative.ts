import { SocialLogin } from "@capgo/capacitor-social-login";
import { api } from "../api/client";
import { setToken } from "./native";

const WEB_CLIENT_ID = import.meta.env.VITE_GOOGLE_WEB_CLIENT_ID as string | undefined;

/** The build has no Google client id, so the button cannot work at all. */
export class GoogleNotConfigured extends Error {}

/** The account picker was dismissed. Not an error to show the user. */
export class GoogleCancelled extends Error {}

let initialized = false;

async function ensureInit(): Promise<void> {
  if (initialized) return;
  if (!WEB_CLIENT_ID) {
    throw new GoogleNotConfigured("VITE_GOOGLE_WEB_CLIENT_ID no está definida");
  }
  // The WEB client id on purpose, not the Android one. Credential Manager mints
  // an ID token whose `aud` is this value, and that is what the backend's
  // /auth/google/native verifies (spec §2.2). The Android OAuth client exists
  // only so Google authorises this package + signing key; it never appears here.
  await SocialLogin.initialize({ google: { webClientId: WEB_CLIENT_ID } });
  initialized = true;
}

/** Credential Manager → ID token → our endpoint → stored bearer. */
export async function signInWithGoogleNative(): Promise<void> {
  await ensureInit();

  let result;
  try {
    ({ result } = await SocialLogin.login({
      provider: "google",
      // Credential Manager defaults to only offering accounts that already
      // authorised this app, which on a first install is none — the picker
      // then opens empty and the button looks broken.
      options: { filterByAuthorizedAccounts: false },
    }));
  } catch (err) {
    if ((err as { code?: string })?.code === "USER_CANCELLED") {
      throw new GoogleCancelled("el usuario cerró el selector de cuentas");
    }
    throw err;
  }

  const idToken = "idToken" in result ? result.idToken : null;
  if (!idToken) throw new Error("Google no devolvió idToken");

  await setToken(await api.googleNative(idToken));
}
