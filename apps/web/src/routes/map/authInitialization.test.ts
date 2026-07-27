import { describe, expect, it } from "vitest";
import { shouldApplyOwnGarnrolleCamera } from "$lib/map/authCameraConvergence";

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
});
