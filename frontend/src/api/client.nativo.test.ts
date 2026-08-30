import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Stands in for lib/native so the shell branch of client.ts becomes executable.
// What is under test is client.ts's transport choice and header emission — the
// storage itself is native.ts's job and has its own tests.
const h = vi.hoisted(() => ({
  token: null as string | null,
  saved: [] as string[],
  cleared: 0,
}));

vi.mock("../lib/native", () => ({
  isNative: () => true,
  getToken: async () => h.token,
  setToken: async (t: string) => {
    h.saved.push(t);
    h.token = t;
  },
  clearToken: async () => {
    h.cleared += 1;
    h.token = null;
  },
  authHeaders: async () => (h.token ? { Authorization: `Bearer ${h.token}` } : {}),
  tap: () => undefined,
}));

const { api } = await import("./client");

function mockFetch(status = 200, body: string | null = "{}") {
  const spy = vi.fn(
    async (_url: string, _init?: RequestInit) =>
      new Response(status === 204 ? null : body, {
        status,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

beforeEach(() => {
  h.token = null;
  h.saved = [];
  h.cleared = 0;
});
afterEach(() => vi.unstubAllGlobals());

describe("transporte en el cascarón", () => {
  it("el login va a /auth/bearer/login y guarda el token que devuelve", async () => {
    const spy = mockFetch(200, '{"access_token":"tok-1","token_type":"bearer"}');
    await api.login("a@b.com", "secreta");
    expect(spy.mock.calls[0][0]).toBe("/api/v1/auth/bearer/login");
    expect(h.saved).toEqual(["tok-1"]);
  });

  it("un login fallido no guarda nada", async () => {
    mockFetch(400, '{"detail":"LOGIN_BAD_CREDENTIALS"}');
    await expect(api.login("a@b.com", "mala")).rejects.toThrow();
    expect(h.saved).toEqual([]);
  });

  it("request() emite el Authorization cuando hay token", async () => {
    h.token = "tok-1";
    const spy = mockFetch(200, '{"id":"u1"}');
    await api.getMe();
    const [, init] = spy.mock.calls[0];
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer tok-1");
  });

  it("el export del taller, que no pasa por request(), también lo emite", async () => {
    h.token = "tok-1";
    const spy = mockFetch(200, "a\tb\n");
    await api.exportTaller();
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/v1/taller/export");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer tok-1");
  });

  // The three FormData uploads bypass request() too. They are the ones a
  // dropped header would hurt most: recording a sentence and getting a 401 in
  // the middle of a study session reads as "the mic broke".
  it.each([
    [
      "scorePronunciation",
      "/api/v1/pronunciation/score",
      () => api.scorePronunciation(new Blob(["x"]), "Hallo", "de"),
    ],
    [
      "resolveMC",
      "/api/v1/stories/s1/quiz/resolve-mc",
      () => api.resolveMC("s1", new Blob(["x"]), ["a", "b"], "de"),
    ],
    [
      "speakTurn",
      "/api/v1/speak/turn",
      () =>
        api.speakTurn(new Blob(["x"]), {
          language: "de",
          focusSound: "r",
          focusExamples: [],
          history: [],
        }),
    ],
  ])("%s emite el Authorization y no fija Content-Type", async (_n, url, call) => {
    h.token = "tok-1";
    const spy = mockFetch(200, "{}");
    await call();
    const [calledUrl, init] = spy.mock.calls[0];
    expect(calledUrl).toBe(url);
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer tok-1");
    // FormData must set its own boundary; a manual Content-Type breaks the body.
    expect(headers.get("Content-Type")).toBeNull();
  });

  it("el logout va a /auth/bearer/logout y borra el token", async () => {
    h.token = "tok-1";
    const spy = mockFetch(204, null);
    await api.logout();
    expect(spy.mock.calls[0][0]).toBe("/api/v1/auth/bearer/logout");
    expect(h.cleared).toBe(1);
  });

  it("si el logout falla en la red, el token igual se borra", async () => {
    h.token = "tok-1";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("sin red");
      }),
    );
    await expect(api.logout()).rejects.toThrow("sin red");
    expect(h.cleared).toBe(1);
  });
});
