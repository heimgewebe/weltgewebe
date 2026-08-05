import { describe, expect, it } from "vitest";
import { areMapEdgesVisuallyEnabled } from "$lib/map/edgeVisibility";

describe("areMapEdgesVisuallyEnabled", () => {
  it("requires both edge and node visibility", () => {
    expect(areMapEdgesVisuallyEnabled(true, true)).toBe(true);
    expect(areMapEdgesVisuallyEnabled(true, false)).toBe(false);
    expect(areMapEdgesVisuallyEnabled(false, true)).toBe(false);
    expect(areMapEdgesVisuallyEnabled(false, false)).toBe(false);
  });
});
