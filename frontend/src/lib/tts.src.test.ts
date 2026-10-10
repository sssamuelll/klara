import { afterEach, describe, expect, it, vi } from "vitest";

// El audio del catálogo (kana, pares mínimos) suena por speak() con `src`: el
// mismo elemento desbloqueado y el mismo respaldo que el TTS en vivo.
const h = vi.hoisted(() => ({ nativo: false }));
vi.mock("./native", () => ({
  isNative: () => h.nativo,
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
  defaultPlaybackRate = 1;
  currentTime = 0;
  duration = Number.NaN;
  oyentes: Record<string, (() => void)[]> = {};
  constructor() {
    FakeAudio.creados.push(this);
  }
  addEventListener(tipo: string, fn: () => void) {
    (this.oyentes[tipo] ??= []).push(fn);
  }
  emitir(tipo: string) {
    for (const fn of this.oyentes[tipo] ?? []) fn();
  }
  // Como el navegador (verificado en Chromium): load() devuelve playbackRate a defaultPlaybackRate.
  load() {
    this.playbackRate = this.defaultPlaybackRate;
  }
  pause() {}
  play() {
    return Promise.resolve();
  }
}
vi.stubGlobal("Audio", FakeAudio);

// Web Speech: el respaldo cuando el archivo no carga.
class FakeUtterance {
  lang = "";
  voice: unknown = null;
  rate = 1;
  onend: unknown = null;
  onerror: unknown = null;
  constructor(public text: string) {}
}
const dichas: FakeUtterance[] = [];
vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
vi.stubGlobal("window", {
  speechSynthesis: { speak: (u: FakeUtterance) => dichas.push(u), cancel: () => undefined, getVoices: () => [] },
});

const { speak, stop } = await import("./tts");
const ultimo = () => FakeAudio.creados[FakeAudio.creados.length - 1];
const tic = () => new Promise((r) => setTimeout(r, 0));

afterEach(() => {
  stop();
  dichas.length = 0;
});

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

  it("la velocidad sobrevive a load(): también va en defaultPlaybackRate", async () => {
    speak("あ", "ja", { src: "/api/v1/audio/ja/a.mp3", rate: 0.75 });
    await tic();
    expect([ultimo().defaultPlaybackRate, ultimo().playbackRate]).toEqual([0.75, 0.75]);
  });

  it("si el archivo no carga, lo dice Web Speech una sola vez, en ja-JP", async () => {
    speak("あ", "ja", { src: "/api/v1/audio/ja/a.mp3" });
    await tic();
    ultimo().emitir("error");
    ultimo().emitir("error");
    expect(dichas.map((u) => [u.text, u.lang])).toEqual([["あ", "ja-JP"]]);
  });

  it("en el cascarón el src ya llega absoluto: no se baja con fetch", async () => {
    h.nativo = true;
    const espia = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("no debía llamarse"));
    try {
      speak("あ", "ja", { src: "https://api.klara.app/api/v1/audio/ja/a.mp3" });
      await tic();
      expect(espia).not.toHaveBeenCalled();
      expect(ultimo().src).toBe("https://api.klara.app/api/v1/audio/ja/a.mp3");
    } finally {
      espia.mockRestore();
      h.nativo = false;
    }
  });
});
