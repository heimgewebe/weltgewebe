import { describe, expect, it } from "vitest";
import {
  GARNROLLE_FULL_SIZE_ZOOM,
  GARNROLLE_MIN_SCALE,
  MAP_MIN_ZOOM,
  getGarnrolleMarkerScale,
} from "./markerScale";

describe("getGarnrolleMarkerScale", () => {
  it("uses the compact size at and below the broadest map view", () => {
    expect(getGarnrolleMarkerScale(MAP_MIN_ZOOM)).toBe(GARNROLLE_MIN_SCALE);
    expect(getGarnrolleMarkerScale(MAP_MIN_ZOOM - 5)).toBe(GARNROLLE_MIN_SCALE);
  });

  it("restores the full size at local zoom levels", () => {
    expect(getGarnrolleMarkerScale(GARNROLLE_FULL_SIZE_ZOOM)).toBe(1);
    expect(getGarnrolleMarkerScale(GARNROLLE_FULL_SIZE_ZOOM + 5)).toBe(1);
  });

  it("scales smoothly and monotonically between both limits", () => {
    const low = getGarnrolleMarkerScale(8);
    const middle = getGarnrolleMarkerScale(10);
    const high = getGarnrolleMarkerScale(12);

    expect(low).toBeGreaterThan(GARNROLLE_MIN_SCALE);
    expect(middle).toBeCloseTo(0.82, 5);
    expect(high).toBeGreaterThan(middle);
    expect(low).toBeLessThan(middle);
    expect(high).toBeLessThan(1);
  });

  it("fails safe to the normal size for a non-finite zoom", () => {
    expect(getGarnrolleMarkerScale(Number.NaN)).toBe(1);
    expect(getGarnrolleMarkerScale(Number.POSITIVE_INFINITY)).toBe(1);
  });
});
