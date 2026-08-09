import { describe, expect, it } from "vitest";
import {
  MAP_MARKER_MAX_SCALE,
  MAP_MARKER_MIN_SCALE,
  MAP_MARKER_REFERENCE_ZOOM,
  MAP_MAX_ZOOM,
  MAP_MIN_ZOOM,
  getGarnrolleMarkerScale,
  getMapMarkerScale,
} from "./markerScale";

describe("getMapMarkerScale", () => {
  it("clamps to the damped far and near limits", () => {
    expect(getMapMarkerScale(MAP_MIN_ZOOM)).toBe(MAP_MARKER_MIN_SCALE);
    expect(getMapMarkerScale(MAP_MIN_ZOOM - 5)).toBe(MAP_MARKER_MIN_SCALE);
    expect(getMapMarkerScale(MAP_MAX_ZOOM)).toBe(MAP_MARKER_MAX_SCALE);
    expect(getMapMarkerScale(MAP_MAX_ZOOM + 5)).toBe(MAP_MARKER_MAX_SCALE);
  });

  it("uses natural artwork size at the compact/detail reference zoom", () => {
    expect(getMapMarkerScale(MAP_MARKER_REFERENCE_ZOOM)).toBe(1);
    expect(getMapMarkerScale(13)).toBeCloseTo(0.994, 3);
  });

  it("is continuous and monotonic throughout the supported zoom range", () => {
    const zooms = Array.from(
      { length: (MAP_MAX_ZOOM - MAP_MIN_ZOOM) * 4 + 1 },
      (_, index) => MAP_MIN_ZOOM + index / 4,
    );
    const scales = zooms.map(getMapMarkerScale);

    for (let index = 1; index < scales.length; index += 1) {
      expect(scales[index]).toBeGreaterThanOrEqual(scales[index - 1]);
    }
    expect(scales.every(Number.isFinite)).toBe(true);
    expect(scales[0]).toBe(MAP_MARKER_MIN_SCALE);
    expect(scales.at(-1)).toBe(MAP_MARKER_MAX_SCALE);
  });

  it("fails safe to natural artwork size for non-finite zooms", () => {
    expect(getMapMarkerScale(Number.NaN)).toBe(1);
    expect(getMapMarkerScale(Number.POSITIVE_INFINITY)).toBe(1);
    expect(getMapMarkerScale(Number.NEGATIVE_INFINITY)).toBe(1);
  });

  it("keeps the former Garnrolle export as an exact compatibility alias", () => {
    expect(getGarnrolleMarkerScale).toBe(getMapMarkerScale);
  });
});
