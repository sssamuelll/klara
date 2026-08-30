import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

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
// vitest, so these assert that adding the bearer transport left the cookie
// transport byte-for-byte where it was.
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

  it("un init.headers propio no borra los headers base", async () => {
    const spy = mockFetch(200, '{"id":"u1"}');
    await api.getMe();
    const [, init] = spy.mock.calls[0];
    const headers = init?.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["Accept-Language"]).toBeTruthy();
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
