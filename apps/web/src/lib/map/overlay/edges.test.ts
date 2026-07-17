import { describe, expect, it } from "vitest";
import {
  FADEN_LIFETIME_MS,
  normalizeEdgeLifecycle,
} from "$lib/map/edgeLifecycle";
import { buildEdgeFeatures } from "$lib/map/overlay/edges";
import type { Edge, MapEntityViewModel } from "$lib/map/types";

const createdAt = Date.parse("2026-07-17T10:00:00Z");
const points = [
  { id: "source", lat: 53.5, lon: 9.9 },
  { id: "target", lat: 53.6, lon: 10.0 },
] as MapEntityViewModel[];
const rawEdge: Edge = {
  id: "edge-1",
  source_id: "source",
  target_id: "target",
  edge_kind: "reference",
  created_at: new Date(createdAt).toISOString(),
  expires_at: new Date(createdAt + FADEN_LIFETIME_MS).toISOString(),
};
const edge = normalizeEdgeLifecycle(rawEdge);

describe("buildEdgeFeatures", () => {
  it("binds continuous opacity to the feature", () => {
    const features = buildEdgeFeatures(
      [edge],
      points,
      true,
      createdAt + FADEN_LIFETIME_MS / 2,
    );
    expect(features).toHaveLength(1);
    expect(features[0].properties?.opacity).toBe(0.5);
  });

  it("omits expired, hidden, and unresolved edges", () => {
    expect(
      buildEdgeFeatures([edge], points, true, createdAt + FADEN_LIFETIME_MS),
    ).toEqual([]);
    expect(buildEdgeFeatures([edge], points, false, createdAt)).toEqual([]);
    expect(
      buildEdgeFeatures([edge], points.slice(0, 1), true, createdAt),
    ).toEqual([]);
  });
});
