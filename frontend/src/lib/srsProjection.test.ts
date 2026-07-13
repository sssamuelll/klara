import { describe, expect, it, vi } from "vitest";

vi.mock("../i18n", () => ({
  default: {
    t: (key: string, opts?: { count?: number }) => `${key.split(".").pop()}:${opts?.count ?? ""}`,
  },
}));

import { projectIntervals, formatInterval } from "./srsProjection";

describe("projectIntervals", () => {
  it("uses fixed learning steps for a new card (ease is ignored)", () => {
    const p = projectIntervals({ state: "new", interval_days: 0, ease: 2.5 });
    expect(p.again).toBeCloseTo(0.0069, 4);
    expect(p.hard).toBeCloseTo(0.04, 4);
    expect(p.good).toBe(1);
    expect(p.easy).toBe(4);
  });

  it("scales off the current interval and ease for a reviewing card", () => {
    const p = projectIntervals({ state: "reviewing", interval_days: 10, ease: 2.5 });
    expect(p.again).toBeCloseTo(0.0069, 4);
    expect(p.hard).toBeCloseTo(12, 2); // 10 * 1.2
    expect(p.good).toBeCloseTo(25, 2); // 10 * 2.5
    expect(p.easy).toBeCloseTo(32.5, 2); // 10 * 2.5 * 1.3
  });

  it("floors the reviewing base interval at 1 day", () => {
    const p = projectIntervals({ state: "reviewing", interval_days: 0, ease: 2.0 });
    expect(p.good).toBeCloseTo(2, 2); // max(0,1) * 2.0
  });
});

describe("formatInterval", () => {
  it("labels sub-hour, sub-day, day, week, month buckets", () => {
    expect(formatInterval(0.0069)).toContain("minutes"); // ~10 min
    expect(formatInterval(0.04)).toContain("hours"); // ~1 h
    expect(formatInterval(1)).toContain("day"); // 1 día
    expect(formatInterval(4)).toContain("days"); // 4 días
    expect(formatInterval(14)).toContain("weeks"); // 2 sem
    expect(formatInterval(60)).toContain("months"); // 2 mes
  });

  it("uses the singular month key for a single month, not months", () => {
    const label = formatInterval(30); // round(30 / 30) = 1
    expect(label).toContain("month");
    expect(label).not.toContain("months");
  });
});
