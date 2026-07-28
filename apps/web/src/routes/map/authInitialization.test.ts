import { describe, expect, it } from "vitest";
import {
  installAuthCameraConvergence,
  shouldApplyOwnGarnrolleCamera,
} from "$lib/map/authCameraConvergence";

const authenticated = {
  state: "authenticated" as const,
  authenticated: true,
  account_id: "account-a",
  role: "weber" as const,
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

  it("does not override current URL focus", () => {
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

  it("consults live focus state and unsubscribes the auth source", () => {
    let emit!: (status: typeof authenticated) => void;
    let unsubscribed = false;
    let hasExplicitFocus = false;
    let jumpCount = 0;
    const map = {
      getZoom: () => 12,
      jumpTo: () => {
        jumpCount += 1;
      },
    };
    const markers = [
      {
        id: "account-a",
        type: "garnrolle",
        lat: 53.5604148,
        lon: 10.0629844,
      },
    ];
    const dispose = installAuthCameraConvergence(
      map as unknown as Parameters<typeof installAuthCameraConvergence>[0],
      markers as unknown as Parameters<typeof installAuthCameraConvergence>[1],
      () => false,
      {
        hasExplicitFocus: () => hasExplicitFocus,
        store: {
          subscribe: (run) => {
            emit = run as (status: typeof authenticated) => void;
            return () => {
              unsubscribed = true;
            };
          },
        },
      },
    );

    hasExplicitFocus = true;
    emit(authenticated);
    expect(jumpCount).toBe(0);
    dispose();
    expect(unsubscribed).toBe(true);
  });
});
