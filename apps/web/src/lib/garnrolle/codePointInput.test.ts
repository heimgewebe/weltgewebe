import { describe, expect, it } from "vitest";
import { countUnicodeCodePoints } from "./codePointInput";

describe("code-point-aware input limits", () => {
  it("counts supplementary-plane characters as one Unicode codepoint each", () => {
    const whales = "🐋".repeat(500);

    expect(whales).toHaveLength(1_000);
    expect(countUnicodeCodePoints(whales)).toBe(500);
  });

  it("counts the server-normalized value without mutating the input", () => {
    const rawValue = `  ${"🐋".repeat(500)}  `;

    expect(countUnicodeCodePoints(rawValue.trim())).toBe(500);
    expect(rawValue).toBe(`  ${"🐋".repeat(500)}  `);
  });
});
