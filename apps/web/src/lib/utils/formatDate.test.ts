import { describe, it, expect } from "vitest";
import { formatDate } from "./formatDate";

describe("formatDate", () => {
  it("returns the fallback for nullish input", () => {
    expect(formatDate(undefined)).toBe("Unbekannt");
    expect(formatDate(null)).toBe("Unbekannt");
    expect(formatDate("")).toBe("Unbekannt");
  });

  it("formats a valid ISO date in de-DE / UTC", () => {
    expect(formatDate("2026-05-26T00:00:00Z")).toBe("26.05.2026");
  });

  it("formats a date without time component", () => {
    expect(formatDate("2026-01-02")).toBe("02.01.2026");
  });

  it("returns the fallback for malformed input", () => {
    expect(formatDate("not-a-date")).toBe("Unbekannt");
  });

  it("uses a caller-supplied formatter when provided", () => {
    const formatter = new Intl.DateTimeFormat("en-US", {
      timeZone: "UTC",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
    expect(formatDate("2026-05-26T00:00:00Z", formatter)).toBe("May 26, 2026");
  });
});
