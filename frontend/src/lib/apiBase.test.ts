import { afterEach, describe, expect, it, vi } from "vitest";
import { apiBase, deriveWsUrl } from "./apiBase";

afterEach(() => vi.unstubAllEnvs());

describe("apiBase", () => {
  it("es relativa cuando VITE_API_BASE no está definida", () => {
    vi.stubEnv("VITE_API_BASE", "");
    expect(apiBase()).toBe("/api/v1");
  });

  it("usa VITE_API_BASE cuando está definida", () => {
    vi.stubEnv("VITE_API_BASE", "https://klara.sdar.dev/api/v1");
    expect(apiBase()).toBe("https://klara.sdar.dev/api/v1");
  });

  it("le quita la barra final", () => {
    vi.stubEnv("VITE_API_BASE", "https://klara.sdar.dev/api/v1/");
    expect(apiBase()).toBe("https://klara.sdar.dev/api/v1");
  });
});

describe("deriveWsUrl", () => {
  it("usa wss en https y ws en http cuando la base es relativa", () => {
    expect(deriveWsUrl("/api/v1", { protocol: "https:", host: "klara.example" })).toBe(
      "wss://klara.example/api/v1/pronunciation/stream",
    );
    expect(deriveWsUrl("/api/v1", { protocol: "http:", host: "localhost:5273" })).toBe(
      "ws://localhost:5273/api/v1/pronunciation/stream",
    );
  });

  it("deriva de la base absoluta e ignora la ubicación", () => {
    expect(
      deriveWsUrl("https://klara.sdar.dev/api/v1", {
        protocol: "http:",
        host: "localhost:5273",
      }),
    ).toBe("wss://klara.sdar.dev/api/v1/pronunciation/stream");
  });

  it("usa ws: cuando la base absoluta es http", () => {
    expect(
      deriveWsUrl("http://192.168.1.10:8000/api/v1", { protocol: "http:", host: "x" }),
    ).toBe("ws://192.168.1.10:8000/api/v1/pronunciation/stream");
  });
});
