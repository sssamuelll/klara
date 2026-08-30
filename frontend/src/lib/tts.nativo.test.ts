import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Stands in for lib/native so the shell branch becomes executable. What is
// under test is that the token travels as a header and that each call revokes
// the blob the previous one made — a leak here is a few hundred KB per spoken
// sentence, which on a study session is real memory.
const h = vi.hoisted(() => ({ token: "tok-1" as string | null }));

vi.mock("./native", () => ({
  isNative: () => true,
  getToken: async () => h.token,
  setToken: async () => undefined,
  clearToken: async () => undefined,
  authHeaders: async () => (h.token ? { Authorization: `Bearer ${h.token}` } : {}),
  tap: () => undefined,
}));

const { ttsSourceForTest, TtsSuperseded } = await import("./tts");

const created: string[] = [];
const revoked: string[] = [];

beforeEach(() => {
  h.token = "tok-1";
  created.length = 0;
  revoked.length = 0;
  let n = 0;
  vi.stubGlobal("URL", {
    createObjectURL: () => {
      const url = `blob:fake/${++n}`;
      created.push(url);
      return url;
    },
    revokeObjectURL: (u: string) => {
      revoked.push(u);
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

function mockFetch(status = 200) {
  const spy = vi.fn(
    async (_url: string, _init?: RequestInit) =>
      new Response(status === 200 ? "audio-bytes" : null, { status }),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

describe("origen del audio de TTS en el cascarón", () => {
  it("baja el audio con el header y devuelve un blob", async () => {
    const spy = mockFetch();
    const src = await ttsSourceForTest("Hallo", "de", "narration");
    const [url, init] = spy.mock.calls[0];
    expect(url).toBe("/api/v1/tts?text=Hallo&lang=de&mode=narration");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer tok-1");
    expect(src).toBe(created[0]);
  });

  it("revoca el blob anterior en cada llamada", async () => {
    mockFetch();
    // Measured as a delta, not as an absolute: the module keeps the last blob
    // url across calls by design, so an earlier test in this file can leave one
    // pending. Asserting the whole `revoked` array would make this test depend
    // on the order the file happens to run in.
    const first = await ttsSourceForTest("uno", "de", "narration");
    const yaRevocados = revoked.length;
    const second = await ttsSourceForTest("dos", "de", "narration");
    expect(revoked.slice(yaRevocados)).toEqual([first]);
    expect(second).not.toBe(first);
  });

  it("si la descarga falla, lanza y no deja un blob colgando", async () => {
    mockFetch(500);
    await expect(ttsSourceForTest("Hallo", "de", "narration")).rejects.toThrow();
    expect(created).toEqual([]);
  });
});

describe("dos speak() encabalgados", () => {
  it("la llamada vieja no revoca el blob de la nueva", async () => {
    mockFetch();
    // The new call already won and its blob is the one playing.
    const deLaNueva = await ttsSourceForTest("nueva", "de", "narration");
    const revocadosAntes = revoked.length;

    // The old call finishes its download afterwards and finds itself stale.
    // It must drop only what it made: revoking the current one would kill the
    // audio that is playing right now.
    await expect(
      ttsSourceForTest("vieja", "de", "narration", () => true),
    ).rejects.toBeInstanceOf(TtsSuperseded);

    const revocadosDespues = revoked.slice(revocadosAntes);
    expect(revocadosDespues).toHaveLength(1);
    expect(revocadosDespues[0]).not.toBe(deLaNueva);
    expect(revoked).not.toContain(deLaNueva);
  });

  it("una llamada vigente sí revoca la anterior", async () => {
    mockFetch();
    const primera = await ttsSourceForTest("uno", "de", "narration", () => false);
    const revocadosAntes = revoked.length;
    await ttsSourceForTest("dos", "de", "narration", () => false);
    expect(revoked.slice(revocadosAntes)).toEqual([primera]);
  });
});
