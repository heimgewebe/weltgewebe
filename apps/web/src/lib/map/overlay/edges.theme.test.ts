import { describe, expect, it } from "vitest";
import { normalizeEdgeLifecycle } from "$lib/map/edgeLifecycle";
import {
  buildEdgeFeatures,
  buildThemedLineSegments,
  buildThreadPathState,
  clipThreadPathByProgress,
  pointAtArcProgress,
  projectLngLatToMercator,
  shortestLongitudeDelta,
  themeSegmentSeamOverlapProgress,
  THEME_SEGMENT_SEAM_OVERLAP,
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

const curveOpts = {
  fadenType: "out",
  threadId: "edge-theme",
} as const;

/** Projected Web-Mercator length (metres) with short-path unwrap continuity. */
function projectedPolylineLength(points: readonly [number, number][]): number {
  if (points.length < 2) return 0;
  let total = 0;
  let unwrapLng = points[0][0];
  let prevXY = projectLngLatToMercator(unwrapLng, points[0][1]);
  for (let index = 1; index < points.length; index += 1) {
    unwrapLng = unwrapLng + shortestLongitudeDelta(unwrapLng, points[index][0]);
    const currXY = projectLngLatToMercator(unwrapLng, points[index][1]);
    total += Math.hypot(currXY[0] - prevXY[0], currXY[1] - prevXY[1]);
    prevXY = currXY;
  }
  return total;
}

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
    // Curved mono-theme path keeps exact endpoints.
    expect(feature.geometry.coordinates[0]).toEqual([9.9, 53.5]);
    expect(feature.geometry.coordinates.at(-1)).toEqual([10, 53.6]);
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
      expect(feature.properties?.fadenType).toBe("out");
      expect(feature.geometry.coordinates.length).toBeGreaterThanOrEqual(2);
    }
    expect(features[0].geometry.coordinates[0]).toEqual([9.9, 53.5]);
    expect(features.at(-1)?.geometry.coordinates.at(-1)).toEqual([10, 53.6]);
  });

  it("builds equal multi-theme segments without a rainbow blend", () => {
    const segments = buildThemedLineSegments(
      [0, 0],
      [8, 0],
      ["#111111", "#222222"],
      curveOpts,
    );
    expect(segments).toHaveLength(4);
    expect(segments.map((segment) => segment.color)).toEqual([
      "#111111",
      "#222222",
      "#111111",
      "#222222",
    ]);
    expect(segments[0].coordinates[0]).toEqual([0, 0]);
    expect(segments.at(-1)?.coordinates.at(-1)).toEqual([8, 0]);
  });

  it("applies stable geometric seam overlap only between multi-colour joins", () => {
    const single = buildThemedLineSegments(
      [0, 0],
      [10, 0],
      ["#111111"],
      curveOpts,
    );
    expect(single).toHaveLength(1);
    expect(single[0].coordinates[0]).toEqual([0, 0]);
    expect(single[0].coordinates.at(-1)).toEqual([10, 0]);

    const path = buildThreadPathState(
      [0, 0],
      [10, 0],
      ["#111111", "#222222"],
      curveOpts,
    );
    const multi = clipThreadPathByProgress(path, 1);
    expect(multi).toHaveLength(4);
    // Adjacent multi-colour strands MUST overlap in arc-progress space.
    // Removing the seam pullback (startProgress === previous endProgress) fails this.
    for (let index = 1; index < path.segments.length; index += 1) {
      const prev = path.segments[index - 1];
      const curr = path.segments[index];
      expect(curr.startProgress).toBeLessThan(prev.endProgress);
      expect(prev.endProgress - curr.startProgress).toBeCloseTo(
        themeSegmentSeamOverlapProgress(path.segments.length),
        10,
      );
    }
    const fullLen = path.totalLength;
    const segmentCount = 4;
    const nominal = fullLen / segmentCount;
    const seam = themeSegmentSeamOverlapProgress(segmentCount) * fullLen;
    for (let index = 1; index < multi.length; index += 1) {
      const prevLen = projectedPolylineLength(multi[index - 1].coordinates);
      const currLen = projectedPolylineLength(multi[index].coordinates);
      expect(currLen).toBeGreaterThan(nominal * 0.5);
      expect(prevLen).toBeGreaterThan(nominal * 0.5);
      expect(currLen).toBeLessThanOrEqual(nominal + seam + 1e-6);
    }
    expect(multi[0].coordinates[0]).toEqual([0, 0]);
    expect(multi.at(-1)?.coordinates.at(-1)).toEqual([10, 0]);
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
        const segments = buildThemedLineSegments(
          source,
          target,
          colors,
          curveOpts,
        );
        const segmentCount = colors.length * 2;
        expect(segments).toHaveLength(segmentCount);

        const pathState = buildThreadPathState(
          source,
          target,
          colors,
          curveOpts,
        );
        const pathLength = pathState.totalLength;
        const segmentLength = pathLength / segmentCount;
        const maxOverlap =
          themeSegmentSeamOverlapProgress(segmentCount) * pathLength;
        // Overlap must track segment length: 1.2% of segment, never 1.2% of path.
        expect(maxOverlap).toBeCloseTo(
          THEME_SEGMENT_SEAM_OVERLAP * segmentLength,
          10,
        );
        expect(maxOverlap).toBeLessThan(
          THEME_SEGMENT_SEAM_OVERLAP * pathLength * 0.5,
        );

        expect(segments[0].coordinates[0]).toEqual(source);
        expect(segments.at(-1)?.coordinates.at(-1)).toEqual(target);

        for (let index = 0; index < segments.length; index += 1) {
          const painted = projectedPolylineLength(segments[index].coordinates);
          expect(painted).toBeGreaterThan(0);
          // One-sided: at most segment length + local overlap.
          expect(painted).toBeLessThanOrEqual(
            segmentLength + maxOverlap + 1e-6,
          );
          expect(painted).toBeLessThanOrEqual(segmentLength * 1.25 + 1e-6);
        }

        // Progress clip: tip is exactly pointAtArcProgress; no segment past tip.
        for (const progress of [0.01, 0.25, 0.5, 0.75, 0.99, 1]) {
          const clipped = clipThreadPathByProgress(pathState, progress);
          for (const segment of clipped) {
            expect(
              projectedPolylineLength(segment.coordinates),
            ).toBeGreaterThan(0);
            expect(segment.coordinates.length).toBeGreaterThanOrEqual(2);
          }
          if (progress >= 1) {
            expect(clipped).toHaveLength(segmentCount);
          }
          if (progress < 1 && progress > 0) {
            expect(clipped.length).toBeGreaterThan(0);
            expect(clipped.length).toBeLessThanOrEqual(segmentCount);
            const tip = clipped[clipped.length - 1].coordinates.at(-1)!;
            const expectedTip = pointAtArcProgress(
              pathState.samples,
              progress,
              {
                cumulative: pathState.cumulative,
                total: pathState.totalLength,
                projected: pathState.projectedSamples,
              },
            );
            expect(tip[0]).toBeCloseTo(expectedTip[0], 10);
            expect(tip[1]).toBeCloseTo(expectedTip[1], 10);
            // No painted end may exceed the motion tip progress.
            for (const meta of pathState.segments) {
              if (meta.startProgress >= progress) continue;
              const paintedEnd = Math.min(progress, meta.endProgress);
              expect(paintedEnd).toBeLessThanOrEqual(progress + 1e-12);
            }
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
