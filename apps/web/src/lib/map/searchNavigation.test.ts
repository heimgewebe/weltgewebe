import { describe, expect, it } from "vitest";
import type { AuthStatus } from "$lib/auth/store";
import type { MapEntityViewModel } from "$lib/map/types";
import {
  deriveSearchDirectionIndicators,
  MAP_CONTENT_FIT_MAX_ZOOM,
  resolveInitialMapCamera,
} from "./searchNavigation";

const markers: MapEntityViewModel[] = [
  {
    type: "garnrolle",
    id: "own",
    title: "Eigene Garnrolle",
    lat: 53.56,
    lon: 10.06,
    created_at: "2026-01-01T00:00:00Z",
    tags: [],
  },
  {
    type: "node",
    id: "focus-node",
    title: "Fokus-Knoten",
    kind: "Ort",
    lat: 54,
    lon: 11,
    created_at: "2026-01-01T00:00:00Z",
    tags: [],
  },
];

const authenticated: AuthStatus = {
  state: "authenticated",
  authenticated: true,
  account_id: "own",
  role: "weber",
};

const guest: AuthStatus = {
  state: "unauthenticated",
  authenticated: false,
  role: "gast",
};

const completeScene = { loadState: "ok" } as const;

describe("resolveInitialMapCamera", () => {
  it("centers on the own positioned Garnrolle", () => {
    expect(
      resolveInitialMapCamera(
        markers,
        authenticated,
        null,
        [10, 53],
        12,
        completeScene,
      ),
    ).toEqual({
      kind: "point",
      center: [10.06, 53.56],
      zoom: 14,
      source: "own-garnrolle",
    });
  });

  it("lets an explicit focus override the own Garnrolle", () => {
    expect(
      resolveInitialMapCamera(
        markers,
        authenticated,
        { type: "node", id: "focus-node" },
        [10, 53],
        12,
        completeScene,
      ),
    ).toEqual({
      kind: "point",
      center: [11, 54],
      zoom: 14,
      source: "focus",
    });
  });

  it("fits renderable content for guests instead of choosing a place fallback", () => {
    expect(
      resolveInitialMapCamera(
        markers,
        guest,
        null,
        [10, 53],
        12,
        completeScene,
      ),
    ).toEqual({
      kind: "bounds",
      bounds: [
        [10.06, 53.56],
        [11, 54],
      ],
      maxZoom: MAP_CONTENT_FIT_MAX_ZOOM,
      source: "content",
    });
  });

  it("uses the configured basemap fallback only for an empty scene", () => {
    expect(
      resolveInitialMapCamera([], guest, null, [10, 53], 7, completeScene),
    ).toEqual({
      kind: "point",
      center: [10, 53],
      zoom: 7,
      source: "fallback",
    });
  });

  it("uses a bounded content zoom for a scene with one renderable point", () => {
    expect(
      resolveInitialMapCamera(
        [markers[0]],
        guest,
        null,
        [10, 53],
        7,
        completeScene,
      ),
    ).toEqual({
      kind: "point",
      center: [10.06, 53.56],
      zoom: MAP_CONTENT_FIT_MAX_ZOOM,
      source: "content",
    });
  });

  it.each(["partial", "failed"] as const)(
    "uses the configured fallback instead of fragmentary content when loading is %s",
    (loadState) => {
      expect(
        resolveInitialMapCamera(markers, guest, null, [10, 53], 7, {
          loadState,
        }),
      ).toEqual({
        kind: "point",
        center: [10, 53],
        zoom: 7,
        source: "fallback",
      });
    },
  );

  it("preserves explicit focus and own-Garnrolle precedence for degraded data", () => {
    expect(
      resolveInitialMapCamera(
        markers,
        guest,
        { type: "node", id: "focus-node" },
        [10, 53],
        7,
        { loadState: "partial" },
      ),
    ).toEqual({
      kind: "point",
      center: [11, 54],
      zoom: 14,
      source: "focus",
    });
    expect(
      resolveInitialMapCamera(markers, authenticated, null, [10, 53], 7, {
        loadState: "failed",
      }),
    ).toEqual({
      kind: "point",
      center: [10.06, 53.56],
      zoom: 14,
      source: "own-garnrolle",
    });
  });

  it("ignores focus targets with invalid coordinates", () => {
    const invalidFocus = [
      {
        type: "node",
        id: "focus-node",
        title: "Ungültig",
        kind: "Ort",
        lat: Number.NaN,
        lon: 11,
        created_at: "2026-01-01T00:00:00Z",
        tags: [],
      },
    ] as MapEntityViewModel[];
    expect(
      resolveInitialMapCamera(
        invalidFocus,
        guest,
        { type: "node", id: "focus-node" },
        [10, 53],
        12,
        completeScene,
      ),
    ).toEqual({
      kind: "point",
      center: [10, 53],
      zoom: 12,
      source: "fallback",
    });
  });
});

describe("deriveSearchDirectionIndicators", () => {
  const bounds = { left: 30, top: 30, right: 370, bottom: 270 };

  it("omits visible matches and places outer matches on the correct edges", () => {
    const indicators = deriveSearchDirectionIndicators(
      [
        { item: markers[0], point: { x: 200, y: 150 } },
        { item: markers[1], point: { x: 900, y: 150 } },
      ],
      bounds,
    );

    expect(indicators).toHaveLength(1);
    expect(indicators[0].item.id).toBe("focus-node");
    expect(indicators[0].side).toBe("right");
    expect(indicators[0].x).toBeCloseTo(370);
    expect(indicators[0].y).toBeCloseTo(150);
    expect(indicators[0].angle).toBeCloseTo(0);
  });

  it("spreads multiple indicators on the same edge", () => {
    const indicators = deriveSearchDirectionIndicators(
      [
        { item: markers[0], point: { x: 900, y: 145 } },
        { item: markers[1], point: { x: 900, y: 150 } },
      ],
      bounds,
    );

    expect(indicators).toHaveLength(2);
    expect(indicators.every((indicator) => indicator.side === "right")).toBe(
      true,
    );
    const positions = indicators
      .map((indicator) => indicator.y)
      .sort((a, b) => a - b);
    expect(positions[1] - positions[0]).toBeGreaterThan(0);
  });

  it("fails closed for unusable viewport bounds", () => {
    expect(
      deriveSearchDirectionIndicators(
        [{ item: markers[0], point: { x: 900, y: 150 } }],
        { left: 100, top: 100, right: 50, bottom: 50 },
      ),
    ).toEqual([]);
  });
});
