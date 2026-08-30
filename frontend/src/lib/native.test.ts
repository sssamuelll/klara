import { describe, expect, it } from "vitest";
import { authHeaders, clearToken, getToken, isNative, setToken, tap } from "./native";

// Vitest is not a native platform, so Capacitor.isNativePlatform() is really
// false here. That makes this the guard on the path that must never change:
// on the web there is no token, no header, and no haptic.
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
