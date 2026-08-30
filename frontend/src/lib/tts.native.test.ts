import { afterEach, describe, expect, it, vi } from "vitest";
import { ttsSourceForTest } from "./tts";

afterEach(() => vi.unstubAllGlobals());

// isNative() is really false here, so this pins the web path: the <audio>
// element keeps pointing straight at the URL and the cookie rides along. No
// fetch, no blob, nothing to revoke.
describe("origen del audio de TTS en web", () => {
  it("devuelve la URL directa y no hace fetch", async () => {
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    const src = await ttsSourceForTest("Hallo", "de", "narration");
    expect(src).toBe("/api/v1/tts?text=Hallo&lang=de&mode=narration");
    expect(spy).not.toHaveBeenCalled();
  });
});
