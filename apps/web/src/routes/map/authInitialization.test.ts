import { describe, expect, it } from "vitest";
import {
  hasMapCameraChanged,
  shouldApplyOwnGarnrolleCamera,
} from "$lib/map/authCameraConvergence";

const authenticated = {
  state: "authenticated" as const,
  authenticated: true,
  account_id: "account-a",
  role: "weber",
};

describe("delayed map auth convergence", () => {
  it("applies own-Garnrolle camera once after delayed authentication", () => {
    expect(
      shouldApplyOwnGarnrolleCamera(
        {
          hasExplicitFocus: false,
          userMovedMap: false,
          alreadyApplied: false,
        },
        authenticated,
      ),
    ).toBe(true);
  });

  it("does not override explicit URL focus", () => {
    expect(
      shouldApplyOwnGarnrolleCamera(
        {
          hasExplicitFocus: true,
          userMovedMap: false,
          alreadyApplied: false,
        },
        authenticated,
      ),
    ).toBe(false);
  });

  it("does not recenter after person moved the map", () => {
    expect(
      shouldApplyOwnGarnrolleCamera(
        {
          hasExplicitFocus: false,
          userMovedMap: true,
          alreadyApplied: false,
        },
        authenticated,
      ),
    ).toBe(false);
  });

  it("never applies delayed camera twice", () => {
    expect(
      shouldApplyOwnGarnrolleCamera(
        {
          hasExplicitFocus: false,
          userMovedMap: false,
          alreadyApplied: true,
        },
        authenticated,
      ),
    ).toBe(false);
  });

  it("detects camera movement that happened before auth became ready", () => {
    const map = {
      getCenter: () => ({ lng: 10.071, lat: 53.571 }),
      getZoom: () => 13,
    };
    expect(hasMapCameraChanged(map, [10.058, 53.5585], 12)).toBe(true);
  });

  it("keeps an untouched initial camera eligible", () => {
    const map = {
      getCenter: () => ({ lng: 10.058, lat: 53.5585 }),
      getZoom: () => 12,
    };
    expect(hasMapCameraChanged(map, [10.058, 53.5585], 12)).toBe(false);
  });
});
