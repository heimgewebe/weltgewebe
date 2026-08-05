import { describe, expect, it } from "vitest";
import {
  hasRenderableMapPosition,
  isValidMapCoordinate,
} from "$lib/map/coordinates";

describe("isValidMapCoordinate", () => {
  it("accepts finite WGS84 positions", () => {
    expect(isValidMapCoordinate(10, 53.5)).toBe(true);
    expect(isValidMapCoordinate(-180, -90)).toBe(true);
    expect(isValidMapCoordinate(180, 90)).toBe(true);
  });

  it("rejects non-finite and out-of-range positions", () => {
    expect(isValidMapCoordinate(Number.NaN, 53)).toBe(false);
    expect(isValidMapCoordinate(10, Number.POSITIVE_INFINITY)).toBe(false);
    expect(isValidMapCoordinate(181, 53)).toBe(false);
    expect(isValidMapCoordinate(10, 91)).toBe(false);
    expect(isValidMapCoordinate(-181, 0)).toBe(false);
    expect(isValidMapCoordinate(0, -91)).toBe(false);
  });
});

describe("hasRenderableMapPosition", () => {
  it("requires a present entity with a valid coordinate pair", () => {
    expect(hasRenderableMapPosition(undefined)).toBe(false);
    expect(hasRenderableMapPosition(null)).toBe(false);
    expect(hasRenderableMapPosition({ lat: 53.5, lon: 10 })).toBe(true);
    expect(hasRenderableMapPosition({ lat: 53.5, lon: Number.NaN })).toBe(
      false,
    );
  });
});
