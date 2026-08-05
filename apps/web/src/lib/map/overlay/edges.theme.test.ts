import { describe, expect, it } from "vitest";
import { normalizeEdgeLifecycle } from "$lib/map/edgeLifecycle";
import {
  buildEdgeFeatures,
  buildProgressClippedThemeSegments,
  buildThemedLineSegments,
  THEME_SEGMENT_SEAM_OVERLAP,
  themeSegmentSeamOverlapProgress,
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

  it("applies stable geometric seam overlap only between multi-colour joins", () => {
    const single = buildThemedLineSegments([0, 0], [10, 0], ["#111111"]);
    expect(single).toHaveLength(1);
    expect(single[0].coordinates).toEqual([
      [0, 0],
      [10, 0],
    ]);

    const multi = buildThemedLineSegments(
      [0, 0],
      [10, 0],
      ["#111111", "#222222"],
    );
    expect(multi).toHaveLength(4);
    // Adjacent segments must overlap so WebGL round-caps leave no hairline gap.
    expect(multi[0].coordinates[1][0]).toBeGreaterThan(
      multi[1].coordinates[0][0],
    );
    expect(multi[1].coordinates[1][0]).toBeGreaterThan(
      multi[2].coordinates[0][0],
    );
    // Endpoints of the full path remain exact; only interior joins overlap.
    expect(multi[0].coordinates[0]).toEqual([0, 0]);
    expect(multi.at(-1)?.coordinates[1]).toEqual([10, 0]);
  });

  it("bounds seam overlap to a fraction of local segment length, not full path", () => {
    const palettes = [
      ["#111111", "#222222"],
      ["#111111", "#222222", "#333333", "#444444"],
    ] as const;
    const geometries: Array<[[number, number], [number, number]]> = [
      [
        [0, 0],
        [1, 0],
      ],
      [
        [0, 0],
        [100, 0],
      ],
    ];

    for (const colors of palettes) {
      for (const [source, target] of geometries) {
        const pathLength = target[0] - source[0];
        const segments = buildThemedLineSegments(source, target, colors);
        // Two braid units per colour (matches buildThemedLineSegments).
        const segmentCount = colors.length * 2;
        expect(segments).toHaveLength(segmentCount);

        const segmentLength = pathLength / segmentCount;
        const maxOverlap =
          themeSegmentSeamOverlapProgress(segmentCount) * pathLength;
        // Overlap must track segment length: 1.2% of segment, never 1.2% of path.
        expect(maxOverlap).toBeCloseTo(
          THEME_SEGMENT_SEAM_OVERLAP * segmentLength,
          10,
        );
        // Distinct from the old full-path formula for multi-segment braids.
        expect(maxOverlap).toBeLessThan(
          THEME_SEGMENT_SEAM_OVERLAP * pathLength * 0.5,
        );

        expect(segments[0].coordinates[0]).toEqual(source);
        expect(segments.at(-1)?.coordinates[1]).toEqual(target);

        for (let index = 0; index < segments.length; index += 1) {
          const [start, end] = segments[index].coordinates;
          // No inverted or zero-length progress geometry.
          expect(end[0]).toBeGreaterThan(start[0]);
          expect(start[0]).toBeGreaterThanOrEqual(source[0] - 1e-12);
          expect(end[0]).toBeLessThanOrEqual(target[0] + 1e-12);

          const painted = end[0] - start[0];
          // One-sided: at most segment length + local overlap.
          expect(painted).toBeLessThanOrEqual(
            segmentLength + maxOverlap + 1e-9,
          );
          // Never flood more than ~half a neighbour (hard cap is 0.25).
          expect(painted).toBeLessThanOrEqual(segmentLength * 1.25 + 1e-9);

          if (index > 0) {
            const prevEnd = segments[index - 1].coordinates[1][0];
            const currStart = start[0];
            const overlap = prevEnd - currStart;
            expect(overlap).toBeGreaterThan(0);
            expect(overlap).toBeLessThanOrEqual(maxOverlap + 1e-9);
          }

          // Nominal end stays exact (one-sided start pullback only).
          const nominalEnd =
            source[0] + ((index + 1) / segmentCount) * pathLength;
          expect(end[0]).toBeCloseTo(nominalEnd, 10);
        }

        // Progress clip must not invent negative/overflowing ranges.
        for (const progress of [0.01, 0.25, 0.5, 0.75, 0.99, 1]) {
          const clipped = buildProgressClippedThemeSegments(
            source,
            target,
            colors,
            progress,
          );
          const tip = source[0] + progress * pathLength;
          for (const segment of clipped) {
            const [start, end] = segment.coordinates;
            expect(end[0]).toBeGreaterThan(start[0]);
            expect(end[0]).toBeLessThanOrEqual(tip + 1e-9);
            expect(start[0]).toBeGreaterThanOrEqual(source[0] - 1e-12);
          }
          if (progress >= 1) {
            expect(clipped).toHaveLength(segmentCount);
          }
        }
      }
    }
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
