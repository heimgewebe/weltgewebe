import { describe, expect, it } from "vitest";
import {
  constrainCodePointInput,
  countUnicodeCodePoints,
} from "./codePointInput";

describe("code-point-aware input limits", () => {
  it("counts supplementary-plane characters as one Unicode codepoint each", () => {
    const whales = "🐋".repeat(500);

    expect(whales).toHaveLength(1_000);
    expect(countUnicodeCodePoints(whales)).toBe(500);
    expect(constrainCodePointInput("", whales, 500)).toBe(whales);
  });

  it("limits new input without splitting a supplementary-plane character", () => {
    const nextValue = `${"a".repeat(499)}🐋🐋`;
    const constrained = constrainCodePointInput("", nextValue, 500);

    expect(constrained).toBe(`${"a".repeat(499)}🐋`);
    expect(countUnicodeCodePoints(constrained)).toBe(500);
  });

  it("does not silently truncate loaded legacy values above the limit", () => {
    const loadedLegacyValue = "🐋".repeat(501);
    const shortenedValue = "🐋".repeat(500);

    expect(
      constrainCodePointInput(loadedLegacyValue, `${loadedLegacyValue}🐋`, 500),
    ).toBe(loadedLegacyValue);
    expect(
      constrainCodePointInput(loadedLegacyValue, shortenedValue, 500),
    ).toBe(shortenedValue);
  });
});
