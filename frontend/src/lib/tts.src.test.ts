import { afterEach, describe, expect, it, vi } from "vitest";

// El audio del catálogo (kana, pares mínimos) suena por speak() con `src`: el
// mismo elemento desbloqueado y el mismo respaldo que el TTS en vivo.
vi.mock("./native", () => ({
  isNative: () => false,
  getToken: async () => null,
  setToken: async () => undefined,
  clearToken: async () => undefined,
  authHeaders: async () => ({}),
  tap: () => undefined,
}));

class FakeAudio {
  static creados: FakeAudio[] = [];
  src = "";
  preload = "";
  preservesPitch = true;
  playbackRate = 1;
  currentTime = 0;
  duration = Number.NaN;
  constructor() {
    FakeAudio.creados.push(this);
  }
  addEventListener() {}
  load() {}
  pause() {}
  play() {
    return Promise.resolve();
  }
}
vi.stubGlobal("Audio", FakeAudio);

const { speak, stop } = await import("./tts");
const ultimo = () => FakeAudio.creados[FakeAudio.creados.length - 1];
const tic = () => new Promise((r) => setTimeout(r, 0));

afterEach(() => stop());

describe("speak con un archivo", () => {
  it("reproduce el archivo y no pide TTS", async () => {
    speak("あ", "ja", { src: "/api/v1/audio/ja/a.mp3" });
    await tic();
    expect(ultimo().src).toBe("/api/v1/audio/ja/a.mp3");
  });

  it("sin src sigue pidiendo TTS", async () => {
    speak("Hallo", "de");
    await tic();
    expect(ultimo().src).toContain("/tts?text=Hallo");
  });
});
