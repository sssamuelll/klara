import { afterEach, describe, expect, it, vi } from "vitest";
import { api, mergeHeaders } from "./client";

function mockFetch(status = 200, body: string | null = "{}") {
  const spy = vi.fn(
    async (_url: string, _init?: RequestInit) =>
      // 204 must carry a null body: the Response constructor rejects any body
      // on a null-body status, even the empty string.
      new Response(status === 204 ? null : body, {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => vi.unstubAllGlobals());

// The web path is the one that must not change. isNative() is false under
// vitest, so these assert that the bearer transport did not move the cookie
// transport's routes, credentials or headers.
describe("transporte en web", () => {
  it("el login va a /auth/jwt/login y no manda Authorization", async () => {
    const spy = mockFetch();
    await api.login("a@b.com", "secreta");
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/v1/auth/jwt/login");
    // Read through Headers: request() now hands fetch a Headers instance, and
    // a plain property access on one is always undefined — an assert that can
    // never fail is worse than no assert.
    expect(new Headers(init?.headers).get("Authorization")).toBeNull();
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
    expect(new Headers(init?.headers).get("Authorization")).toBeNull();
  });

  it("manda los headers base", async () => {
    const spy = mockFetch(200, '{"id":"u1"}');
    await api.getMe();
    const headers = new Headers(spy.mock.calls[0][1]?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Accept-Language")).toBeTruthy();
  });
});

// No caller passes init.headers today, so none of this is reachable yet — which
// is exactly why it needs a test: the day one does, silently dropping the
// Authorization would look like a random logout, not like a bug here.
describe("mergeHeaders", () => {
  it("conserva los base cuando el init no trae nada", () => {
    const h = mergeHeaders(undefined, {});
    expect(h.get("Content-Type")).toBe("application/json");
  });

  it("el init puede sobrescribir un header base", () => {
    const h = mergeHeaders({ "Content-Type": "text/plain" }, {});
    expect(h.get("Content-Type")).toBe("text/plain");
  });

  it("el Authorization gana aunque el init traiga uno", () => {
    const h = mergeHeaders({ Authorization: "Bearer del-llamador" }, {
      Authorization: "Bearer de-la-sesion",
    });
    expect(h.get("Authorization")).toBe("Bearer de-la-sesion");
  });

  it("el Authorization gana aunque el init lo escriba en otro casing", () => {
    const h = mergeHeaders({ authorization: "Bearer del-llamador" }, {
      Authorization: "Bearer de-la-sesion",
    });
    expect(h.get("authorization")).toBe("Bearer de-la-sesion");
    expect([...h].filter(([k]) => k.toLowerCase() === "authorization")).toHaveLength(1);
  });

  it("acepta un objeto Headers como init", () => {
    const h = mergeHeaders(new Headers({ "X-Prueba": "1" }), {});
    expect(h.get("X-Prueba")).toBe("1");
    expect(h.get("Content-Type")).toBe("application/json");
  });

  it("acepta un arreglo de tuplas como init", () => {
    const h = mergeHeaders([["X-Prueba", "1"]], {});
    expect(h.get("X-Prueba")).toBe("1");
    expect(h.get("Content-Type")).toBe("application/json");
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
