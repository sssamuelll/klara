import { describe, expect, it } from "vitest";
import { createLevelClassifier, type MicLevel } from "./silenceDetector";

const dbfs = (db: number): number => Math.pow(10, db / 20);

/** 60fps. Feeds `ms` worth of frames at a steady rms/peak, returns the verdict. */
function feed(
  c: { push: (rms: number, peak: number, dt: number) => MicLevel },
  ms: number,
  rms: number,
  peak = rms * 3,
): MicLevel {
  const dt = 1000 / 60;
  let level: MicLevel = "silent";
  for (let t = 0; t < ms; t += dt) level = c.push(rms, peak, dt);
  return level;
}

describe("createLevelClassifier", () => {
  it("stays silent through room tone", () => {
    const c = createLevelClassifier();
    expect(feed(c, 3000, dbfs(-60))).toBe("silent");
  });

  it("calls soft speech quiet", () => {
    const c = createLevelClassifier();
    expect(feed(c, 1000, dbfs(-42))).toBe("quiet");
  });

  it("calls normal speech ok", () => {
    const c = createLevelClassifier();
    expect(feed(c, 1000, dbfs(-20))).toBe("ok");
  });

  it("calls a clipped frame loud, even at a low rms", () => {
    const c = createLevelClassifier();
    expect(c.push(dbfs(-30), 1.0, 16)).toBe("loud");
  });

  // The reason peak-hold freezes below the floor: a pause between words is
  // not evidence that the speaker is too quiet.
  it("holds the verdict through a pause instead of flashing quiet", () => {
    const c = createLevelClassifier();
    expect(feed(c, 1000, dbfs(-20))).toBe("ok");
    expect(feed(c, 3000, dbfs(-60))).toBe("ok");
  });

  it("follows the level down when the speaker drops to a whisper", () => {
    const c = createLevelClassifier();
    expect(feed(c, 1000, dbfs(-20))).toBe("ok");
    expect(feed(c, 2500, dbfs(-42))).toBe("quiet");
  });

  it("releases loud once the clipping stops", () => {
    const c = createLevelClassifier();
    expect(c.push(dbfs(-20), 1.0, 16)).toBe("loud");
    expect(feed(c, 500, dbfs(-20))).toBe("loud");
    expect(feed(c, 1500, dbfs(-20))).toBe("ok");
  });

  it("honours overridden thresholds", () => {
    const c = createLevelClassifier({ quietDbfs: -60 });
    expect(feed(c, 1000, dbfs(-42))).toBe("ok");
  });
});
