import { beforeEach, describe, expect, it, vi } from "vitest";

// The native branch of native.ts never runs under vitest, so the only way to
// pin the credential format and the storage-failure contract is to stand in for
// the two plugins. What is under test is OUR logic — the "Bearer " prefix, the
// fail-closed read, the swallowed clear — not the plugins'.
const h = vi.hoisted(() => ({
  store: new Map<string, string>(),
  failOn: "" as "" | "get" | "set" | "remove",
}));

vi.mock("@capacitor/core", () => ({
  Capacitor: { isNativePlatform: () => true },
}));

vi.mock("@capacitor/preferences", () => ({
  Preferences: {
    get: async ({ key }: { key: string }) => {
      if (h.failOn === "get") throw new Error("almacenamiento caído");
      return { value: h.store.get(key) ?? null };
    },
    set: async ({ key, value }: { key: string; value: string }) => {
      if (h.failOn === "set") throw new Error("almacenamiento caído");
      h.store.set(key, value);
    },
    remove: async ({ key }: { key: string }) => {
      if (h.failOn === "remove") throw new Error("almacenamiento caído");
      h.store.delete(key);
    },
  },
}));

vi.mock("@capacitor/haptics", () => ({
  Haptics: { impact: vi.fn(async () => undefined) },
  ImpactStyle: { Light: "LIGHT" },
}));

const { authHeaders, clearToken, getToken, setToken, tap } = await import("./native");

beforeEach(() => {
  h.store.clear();
  h.failOn = "";
});

describe("native.ts en el cascarón", () => {
  it("guarda, lee y borra el token", async () => {
    await setToken("tok-abc");
    expect(await getToken()).toBe("tok-abc");
    await clearToken();
    expect(await getToken()).toBeNull();
  });

  it("el header es exactamente `Bearer <token>`", async () => {
    await setToken("tok-abc");
    expect(await authHeaders()).toEqual({ Authorization: "Bearer tok-abc" });
  });

  it("sin token guardado no hay header", async () => {
    expect(await authHeaders()).toEqual({});
  });

  it("tap() no lanza", () => {
    expect(tap()).toBeUndefined();
  });
});

describe("fallos del almacenamiento", () => {
  it("si la lectura falla, getToken devuelve null en vez de lanzar", async () => {
    await setToken("tok-abc");
    h.failOn = "get";
    expect(await getToken()).toBeNull();
  });

  it("si la lectura falla, authHeaders no lanza y va sin header", async () => {
    await setToken("tok-abc");
    h.failOn = "get";
    // Fail closed: no header means a 401, which routes to the login screen.
    // Rejecting here would blow up every call site instead.
    expect(await authHeaders()).toEqual({});
  });

  it("si el borrado falla, clearToken no lanza", async () => {
    await setToken("tok-abc");
    h.failOn = "remove";
    // clearToken runs inside logout()'s `finally`; a throw here would mask the
    // real error from the logout round trip.
    await expect(clearToken()).resolves.toBeUndefined();
  });

  it("si la escritura falla, setToken SÍ lanza", async () => {
    h.failOn = "set";
    // Deliberate asymmetry: a token we failed to persist means the user looks
    // logged in and is logged out on the next launch. That has to be visible.
    await expect(setToken("tok-abc")).rejects.toThrow();
  });
});
