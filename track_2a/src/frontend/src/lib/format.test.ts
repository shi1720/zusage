import { describe, expect, it } from "vitest";

import { avg, cn, daysSince, daysUntil, initials, scoreColor, timeAgo } from "./format";

const NOW = new Date("2026-10-02T12:00:00Z");

describe("dates", () => {
  it("counts whole days and never goes negative", () => {
    expect(daysSince("2026-09-26T12:00:00Z", NOW)).toBe(6);
    expect(daysSince("2026-10-03T12:00:00Z", NOW)).toBe(0);
    expect(daysUntil("2026-10-05T10:00:00Z", NOW)).toBe(3);
  });

  it("formats relative time in the user's language", () => {
    expect(timeAgo("2026-09-29T12:00:00Z", "en-GB", NOW)).toBe("3 days ago");
    expect(timeAgo("2026-09-29T12:00:00Z", "de-CH", NOW)).toBe("vor 3 Tagen");
  });
});

describe("helpers", () => {
  it("maps rubric scores onto the four-step ramp", () => {
    expect(scoreColor(1)).toContain("score-1");
    expect(scoreColor(2.2)).toContain("score-2");
    expect(scoreColor(3)).toContain("score-3");
    expect(scoreColor(4)).toContain("score-4");
    expect(scoreColor(null)).toContain("line");
  });

  it("joins class names and initials", () => {
    expect(cn("a", false, "b", null)).toBe("a b");
    expect(initials("Frau Meier")).toBe("FM");
    expect(avg([2, 4])).toBe(3);
    expect(avg([])).toBeNull();
  });
});
