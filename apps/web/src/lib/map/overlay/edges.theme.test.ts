import { describe, expect, it } from "vitest";
import { normalizeEdgeLifecycle } from "$lib/map/edgeLifecycle";
import { buildEdgeFeatures } from "$lib/map/overlay/edges";
import type { Edge, MapEntityViewModel } from "$lib/map/types";

const createdAt = Date.parse("2026-08-04T10:00:00Z");
const rawEdge: Edge = {
  id: "edge-theme",
  source_id: "source",
  target_id: "target",
  edge_kind: "reference",
  created_at: new Date(createdAt).toISOString(),
};

describe("edge theme fallback", () => {
  it("derives a node theme without requiring a preprojected weave", () => {
    const points = [
      {
        type: "garnrolle",
        id: "source",
        title: "Quelle",
        lat: 53.5,
        lon: 9.9,
      },
      {
        type: "node",
        id: "target",
        title: "Garten",
        kind: "Garten",
        tags: ["Natur"],
        created_at: new Date(createdAt).toISOString(),
        lat: 53.6,
        lon: 10,
      },
    ] as MapEntityViewModel[];

    const [feature] = buildEdgeFeatures(
      [normalizeEdgeLifecycle(rawEdge)],
      points,
      true,
      createdAt,
    );

    expect(feature.properties?.themeColor).toMatch(/^#[0-9a-f]{6}$/i);
  });

  it("keeps themeColor absent for Garnrollen", () => {
    const points = [
      {
        type: "node",
        id: "source",
        title: "Quelle",
        kind: "Quelle",
        tags: [],
        created_at: new Date(createdAt).toISOString(),
        lat: 53.5,
        lon: 9.9,
      },
      {
        type: "garnrolle",
        id: "target",
        title: "Ziel",
        lat: 53.6,
        lon: 10,
      },
    ] as MapEntityViewModel[];

    const [feature] = buildEdgeFeatures(
      [normalizeEdgeLifecycle(rawEdge)],
      points,
      true,
      createdAt,
    );

    expect(feature.properties).not.toHaveProperty("themeColor");
  });
});
