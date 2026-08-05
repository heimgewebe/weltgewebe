import { describe, expect, it } from "vitest";
import { normalizeEdgeLifecycle } from "$lib/map/edgeLifecycle";
import {
  buildEdgeFeatures,
  buildThemedLineSegments,
} from "$lib/map/overlay/edges";
import type { Edge, MapEntityViewModel } from "$lib/map/types";
import { deriveEntityWeave } from "$lib/map/weaveModel";

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
    expect(feature.properties?.themeColors).toEqual([
      feature.properties?.themeColor,
    ]);
  });

  it("carries the full multi-theme target palette as a controlled braid", () => {
    const target = {
      type: "node" as const,
      id: "target",
      title: "Garten",
      kind: "Garten",
      tags: ["Natur", "Bildung", "Kunst"],
      created_at: new Date(createdAt).toISOString(),
      lat: 53.6,
      lon: 10,
      weave: deriveEntityWeave(
        {
          type: "node",
          id: "target",
          title: "Garten",
          kind: "Garten",
          tags: ["Natur", "Bildung", "Kunst"],
          created_at: new Date(createdAt).toISOString(),
          lat: 53.6,
          lon: 10,
        },
        [],
        createdAt,
      ),
    };
    const points = [
      {
        type: "garnrolle",
        id: "source",
        title: "Quelle",
        lat: 53.5,
        lon: 9.9,
      },
      target,
    ] as MapEntityViewModel[];

    const features = buildEdgeFeatures(
      [normalizeEdgeLifecycle(rawEdge)],
      points,
      true,
      createdAt,
    );

    expect(features.length).toBeGreaterThan(1);
    const palette = features[0].properties?.themeColors as string[];
    expect(palette.length).toBeGreaterThan(1);
    const strandColors = features.map(
      (feature) => feature.properties?.themeColor,
    );
    // Controlled braid: multiple strands, each colour drawn from the palette.
    // Distinct topic identities may still hash to the same paint colour.
    expect(new Set(strandColors).size).toBeGreaterThan(1);
    expect(new Set(strandColors).size).toBeLessThanOrEqual(palette.length);
    for (const feature of features) {
      expect(palette).toContain(feature.properties?.themeColor);
      expect(feature.properties?.themeColors).toEqual(palette);
      expect(feature.properties?.fadenType).toBe("legacy");
    }
  });

  it("builds equal multi-theme segments without a rainbow blend", () => {
    const segments = buildThemedLineSegments(
      [0, 0],
      [8, 0],
      ["#111111", "#222222"],
    );
    expect(segments).toHaveLength(4);
    expect(segments.map((segment) => segment.color)).toEqual([
      "#111111",
      "#222222",
      "#111111",
      "#222222",
    ]);
    expect(segments[0].coordinates[0]).toEqual([0, 0]);
    expect(segments.at(-1)?.coordinates[1]).toEqual([8, 0]);
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
