import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./client";

function mockFetch() {
  const spy = vi.fn(async (_url: string, _init: RequestInit) =>
    new Response("{}", { status: 200, headers: { "content-type": "application/json" } }),
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => vi.unstubAllGlobals());

describe("reviewCard", () => {
  it("sends elapsed_seconds when provided", async () => {
    const fetchSpy = mockFetch();
    await api.reviewCard("card-1", "good", 7);
    const [, init] = fetchSpy.mock.calls[0];
    expect(JSON.parse(init.body as string)).toEqual({ rating: "good", elapsed_seconds: 7 });
  });

  it("omits elapsed_seconds when not provided", async () => {
    const fetchSpy = mockFetch();
    await api.reviewCard("card-1", "again");
    const [, init] = fetchSpy.mock.calls[0];
    expect(JSON.parse(init.body as string)).toEqual({ rating: "again" });
  });
});
