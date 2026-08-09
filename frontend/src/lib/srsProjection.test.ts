import { describe, expect, it, vi } from "vitest";

vi.mock("../i18n", () => ({
  default: {
    t: (key: string, opts?: { count?: number }) => `${key.split(".").pop()}:${opts?.count ?? ""}`,
  },
}));

import { formatInterval } from "./srsProjection";

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
