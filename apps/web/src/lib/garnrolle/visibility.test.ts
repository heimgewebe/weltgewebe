import { describe, expect, it } from "vitest";
import type { Account } from "$lib/map/types";
import {
  deriveGarnrolleMapState,
  describeGarnrolleVisibility,
  findOwnGarnrolle,
} from "./visibility";

const baseAccount: Account = {
  id: "account-1",
  type: "garnrolle",
  title: "Test Garnrolle",
  created_at: "2026-07-10T00:00:00Z",
  tags: [],
};

describe("garnrolle visibility helpers", () => {
  it("treats missing public position as not on the map", () => {
    expect(deriveGarnrolleMapState(baseAccount)).toBe("not_on_map");
    expect(describeGarnrolleVisibility(baseAccount).canZoomToMap).toBe(false);
  });

  it("treats radius zero as exact visibility", () => {
    const account: Account = {
      ...baseAccount,
      public_pos: { lat: 53.56, lon: 10.06 },
      radius_m: 0,
    };
    expect(deriveGarnrolleMapState(account)).toBe("exact");
    expect(describeGarnrolleVisibility(account).label).toBe("Exakt sichtbar");
  });

  it("treats positive radius as radius visibility", () => {
    const account: Account = {
      ...baseAccount,
      public_pos: { lat: 53.56, lon: 10.06 },
      radius_m: 250,
    };
    expect(deriveGarnrolleMapState(account)).toBe("radius");
    expect(describeGarnrolleVisibility(account).description).toContain("250 m");
  });

  it("finds the authenticated account's Garnrolle when present", () => {
    expect(findOwnGarnrolle([baseAccount], "account-1")?.id).toBe("account-1");
    expect(findOwnGarnrolle([baseAccount], "missing")).toBeNull();
  });
});
