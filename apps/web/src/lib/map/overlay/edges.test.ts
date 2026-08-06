import { describe, expect, it } from "vitest";
import {
  FADEN_LIFETIME_MS,
  normalizeEdgeLifecycle,
} from "$lib/map/edgeLifecycle";
import {
  EDGE_CURVE_MAX_HANDLE_FRACTION,
  EDGE_CURVE_MAX_HANDLE_M,
  EDGE_CURVE_MAX_SAMPLES,
  EDGE_CURVE_MERCATOR_RADIUS_M,
  EDGE_THREAD_LAYER_IDS,
  EDGE_THREAD_VARIANTS,
  EDGE_VISUAL_STYLE,
  buildEdgeFeatures,
  buildEdgeLayerSpecifications,
  buildEndpointIndex,
  buildProgressClippedThemeSegments,
  buildThemedLineSegments,
  buildThreadPathState,
  clipThreadPathByProgress,
  degreeSpacePolylineArcState,
  getThreadPathBuildSerialForTests,
  hasCompleteEdgeThreadStyle,
  pointAtArcProgress,
  projectedChord,
  projectedSampleToLngLat,
  projectLngLatToMercator,
  resetThreadPathBuildSerialForTests,
  sampleThreadCurve,
  shortestLongitudeDelta,
  threadCorridorKey,
  threadCurveControlPoints,
  threadCurveControlPointsProjected,
  threadCurveProfile,
  threadCurveSampleCount,
  threadTargetApproachVector,
  threadTargetLocalCorridorAxis,
  updateEdges,
} from "$lib/map/overlay/edges";
import { LAYERS } from "$lib/map/overlay/layers";
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
    expect(features[0].properties).not.toHaveProperty("themeColor");
  });

  it("indexes Faden endpoints by id and faden_endpoint_id for center attachment", () => {
    const centerEndpointId = "22222222-2222-5222-8222-222222222222";
    const center = {
      type: "webgemeindezentrum",
      id: "webgemeindezentrum-hammer-park",
      faden_endpoint_id: centerEndpointId,
      lat: 53.5585,
      lon: 10.058,
    } as MapEntityViewModel;
    const index = buildEndpointIndex([points[0], center]);
    expect(index.get("source")?.lon).toBe(9.9);
    expect(index.get(centerEndpointId)?.id).toBe(
      "webgemeindezentrum-hammer-park",
    );
    expect(index.get("webgemeindezentrum-hammer-park")?.lat).toBe(53.5585);
  });

  it("resolves a Webgemeindezentrum through its strict Faden UUID alias", () => {
    const centerEndpointId = "22222222-2222-5222-8222-222222222222";
    const center = {
      type: "webgemeindezentrum",
      id: "webgemeindezentrum-hammer-park",
      faden_endpoint_id: centerEndpointId,
      conversation_id: "33333333-3333-5333-8333-333333333333",
      title: "Webgemeindezentrum Hammer Park",
      lat: 53.5585,
      lon: 10.058,
      summary: "Treffpunkt",
      tags: [],
      created_at: new Date(createdAt).toISOString(),
      updated_at: new Date(createdAt).toISOString(),
      location_state: "desired",
      location_state_label: "Gewünschter Treffort",
      location_label: "Hammer Park",
      meeting_note: "Treffpunkt",
      access_note: "Noch zu bestätigen",
      ortsweberei: {
        id: "ortsweberei-hamm",
        slug: "hamm",
        name: "Ortsweberei Hamm",
        gewebezelle_id: "hamm.weltgewebe.net",
      },
    } as MapEntityViewModel;
    const centerEdge = normalizeEdgeLifecycle({
      ...rawEdge,
      id: "edge-center",
      target_id: centerEndpointId,
    });

    const features = buildEdgeFeatures(
      [centerEdge],
      [points[0], center],
      true,
      createdAt,
    );

    expect(features).toHaveLength(1);
    const coords = features[0].geometry.coordinates;
    expect(coords[0]).toEqual([9.9, 53.5]);
    expect(coords.at(-1)).toEqual([10.058, 53.5585]);
    expect(coords.length).toBeGreaterThanOrEqual(2);
    expect(coords.length).toBeLessThanOrEqual(EDGE_CURVE_MAX_SAMPLES);
  });

  it("projects the canonical Faden type and subject without vote content", () => {
    const typed = normalizeEdgeLifecycle({
      ...rawEdge,
      faden_type: "vote",
      faden_subject_id: "11111111-1111-5111-8111-111111111111",
    });
    const themedPoints = [
      points[0],
      {
        ...points[1],
        type: "node",
        weave: {
          zoneOrder: ["knotting", "conversation", "proposal", "vote"],
          themeSegments: [
            {
              id: "natur",
              label: "Natur",
              color: "#5f7a55",
              arm: "northwest",
            },
          ],
          xCoreSegments: [
            {
              arm: "northwest",
              themeId: "natur",
              label: "Natur",
              color: "#5f7a55",
            },
            {
              arm: "northeast",
              themeId: "natur",
              label: "Natur",
              color: "#5f7a55",
            },
            {
              arm: "southeast",
              themeId: "natur",
              label: "Natur",
              color: "#5f7a55",
            },
            {
              arm: "southwest",
              themeId: "natur",
              label: "Natur",
              color: "#5f7a55",
            },
          ],
          armOverlays: [],
          primaryThemeColor: "#5f7a55",
          coreDensity: 0.5,
          conversationRingThickness: 0,
          knottingThreadCount: 0,
          conversationThreadCount: 0,
          conversationOpacity: 0,
          proposalArcs: [],
          proposalCount: 0,
          proposalOverflowCount: 0,
          voteThreadCount: 0,
          totalActiveThreadCount: 0,
        },
      },
    ] as MapEntityViewModel[];
    const features = buildEdgeFeatures([typed], themedPoints, true, createdAt);
    expect(features[0].properties).toMatchObject({
      fadenType: "vote",
      fadenSubjectId: "11111111-1111-5111-8111-111111111111",
      themeColor: "#5f7a55",
    });
    expect(features[0].properties).not.toHaveProperty("choice");
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

  it("defensively drops edges with non-finite or out-of-range endpoints", () => {
    const invalidPoints = [
      { id: "source", lat: Number.NaN, lon: 9.9 },
      { id: "target", lat: 53.6, lon: 10.0 },
    ] as MapEntityViewModel[];
    const outOfRange = [
      { id: "source", lat: 53.5, lon: 9.9 },
      { id: "target", lat: 91, lon: 10.0 },
    ] as MapEntityViewModel[];

    expect(buildEdgeFeatures([edge], invalidPoints, true, createdAt)).toEqual(
      [],
    );
    expect(buildEdgeFeatures([edge], outOfRange, true, createdAt)).toEqual([]);
  });
});

describe("updateEdges source readiness", () => {
  it("installs the empty GeoJSON source and every canonical layer", () => {
    const sources = new Map<string, { data: unknown }>();
    const layers = new Map<string, unknown>();
    const map = {
      getSource: (id: string) => sources.get(id),
      addSource: (id: string, spec: { data: unknown }) => {
        sources.set(id, { data: spec.data });
      },
      getLayer: (id: string) => layers.get(id),
      addLayer: (layer: { id: string }) => {
        layers.set(layer.id, layer);
      },
      getStyle: () => ({ layers: [{ id: "labels", type: "symbol" }] }),
    };

    updateEdges(map as never, [], points, true, createdAt);

    expect(sources.has(LAYERS.EDGES_SOURCE)).toBe(true);
    expect(
      (sources.get(LAYERS.EDGES_SOURCE)?.data as GeoJSON.FeatureCollection)
        .features,
    ).toEqual([]);
    for (const layerId of EDGE_THREAD_LAYER_IDS) {
      expect(layers.has(layerId)).toBe(true);
    }
    expect(hasCompleteEdgeThreadStyle(map)).toBe(true);
  });
});

describe("hasCompleteEdgeThreadStyle", () => {
  function probe(
    layerIds: readonly string[],
    sourceId: string = LAYERS.EDGES_SOURCE,
  ) {
    const layers = new Set(layerIds);
    return {
      getSource: (id: string) => (id === sourceId ? {} : undefined),
      getLayer: (id: string) => (layers.has(id) ? {} : undefined),
    };
  }

  it("derives the canonical list from the layer specifications themselves", () => {
    expect(EDGE_THREAD_LAYER_IDS).toEqual(
      buildEdgeLayerSpecifications().map((specification) => specification.id),
    );
    // Shadow + body + highlight for legacy and the four typed thread kinds.
    expect(EDGE_THREAD_LAYER_IDS).toHaveLength(15);
  });

  it("accepts the complete set of source and thread layers", () => {
    expect(hasCompleteEdgeThreadStyle(probe(EDGE_THREAD_LAYER_IDS))).toBe(true);
  });

  it("rejects a style that is missing the last typed layer", () => {
    expect(
      hasCompleteEdgeThreadStyle(probe(EDGE_THREAD_LAYER_IDS.slice(0, -1))),
    ).toBe(false);
  });

  it("rejects the old partial check of source plus two legacy layers", () => {
    expect(
      hasCompleteEdgeThreadStyle(
        probe([
          LAYERS.EDGES_SHADOW_LAYER,
          LAYERS.EDGES_LAYER,
          LAYERS.EDGES_HIGHLIGHT_LAYER,
        ]),
      ),
    ).toBe(false);
  });

  it("keeps shadow/body/highlight triples with continuous body and highlight rhythm", () => {
    const specs = buildEdgeLayerSpecifications();
    expect(specs).toHaveLength(15);
    for (let index = 0; index < specs.length; index += 3) {
      const shadow = specs[index];
      const body = specs[index + 1];
      const highlight = specs[index + 2];
      expect(shadow.id).toContain("shadow");
      expect(highlight.id).toContain("highlight");
      expect(shadow.paint?.["line-width"]).toBeGreaterThan(
        Number(body.paint?.["line-width"]),
      );
      expect(Number(highlight.paint?.["line-width"])).toBeLessThan(
        Number(body.paint?.["line-width"]),
      );
      // Highlight always carries the braid/fiber dash rhythm.
      expect(highlight.paint?.["line-dasharray"]).toBeDefined();
      const variant = EDGE_THREAD_VARIANTS[index / 3];
      if (variant.shadowContinuous) {
        expect(shadow.paint?.["line-dasharray"]).toBeUndefined();
      }
      if (variant.bodyContinuous) {
        expect(body.paint?.["line-dasharray"]).toBeUndefined();
      } else {
        // Vote stays stitch-like on the body with continuous shadow link.
        expect(body.paint?.["line-dasharray"]).toEqual([...variant.dashArray]);
        expect(shadow.paint?.["line-dasharray"]).toBeUndefined();
      }
    }
  });

  it("rejects a missing edge source and an absent map", () => {
    expect(
      hasCompleteEdgeThreadStyle(probe(EDGE_THREAD_LAYER_IDS, "other-source")),
    ).toBe(false);
    expect(hasCompleteEdgeThreadStyle(null)).toBe(false);
  });
});

describe("natural thread curves", () => {
  const source: [number, number] = [9.9, 53.5];
  const target: [number, number] = [10.1, 53.65];

  function projectedMidDeflection(
    path: readonly [number, number][],
    from: [number, number],
    to: [number, number],
  ): number {
    const mid = path[Math.floor(path.length / 2)];
    const { sourceXY, targetXY } = projectedChord(from, to);
    const midXY = projectLngLatToMercator(mid[0], mid[1]);
    const chordMid: [number, number] = [
      (sourceXY[0] + targetXY[0]) / 2,
      (sourceXY[1] + targetXY[1]) / 2,
    ];
    return Math.hypot(midXY[0] - chordMid[0], midXY[1] - chordMid[1]);
  }

  it("keeps exact endpoints on every sampled curve", () => {
    for (const fadenType of [
      "knotting",
      "conversation",
      "proposal",
      "vote",
      "legacy",
    ] as const) {
      const path = sampleThreadCurve(source, target, {
        fadenType,
        threadId: `edge-${fadenType}`,
        subjectId: fadenType === "vote" ? "subject-1" : null,
      });
      expect(path[0]).toEqual(source);
      expect(path.at(-1)).toEqual(target);
      for (const point of path) {
        expect(Number.isFinite(point[0])).toBe(true);
        expect(Number.isFinite(point[1])).toBe(true);
      }
    }
  });

  it("is deterministic for the same identity", () => {
    const opts = {
      fadenType: "conversation",
      threadId: "edge-stable",
      subjectId: null,
    };
    const a = sampleThreadCurve(source, target, opts);
    const b = sampleThreadCurve(source, target, opts);
    expect(a).toEqual(b);
    const c = threadCurveControlPoints(source, target, opts);
    const d = threadCurveControlPoints(source, target, opts);
    expect(c).toEqual(d);
  });

  it("enforces real lateral deflection for soft conversation profiles", () => {
    const path = sampleThreadCurve(source, target, {
      fadenType: "conversation",
      threadId: "edge-soft",
    });
    expect(path.length).toBeGreaterThanOrEqual(4);
    expect(path.length).toBeLessThanOrEqual(EDGE_CURVE_MAX_SAMPLES);
    const deflection = projectedMidDeflection(path, source, target);
    // Soft profile must leave the projected chord by a meaningful margin.
    expect(deflection).toBeGreaterThan(80);
    const again = threadCurveControlPointsProjected(source, target, {
      fadenType: "conversation",
      threadId: "edge-soft",
    });
    const once = threadCurveControlPointsProjected(source, target, {
      fadenType: "conversation",
      threadId: "edge-soft",
    });
    expect(again.p1[0]).toBeCloseTo(once.p1[0], 10);
    expect(again.p1[1]).toBeCloseTo(once.p1[1], 10);
  });

  it("keeps short paths nearly straight", () => {
    const nearTarget: [number, number] = [9.901, 53.5005];
    const shortPath = sampleThreadCurve(source, nearTarget, {
      fadenType: "conversation",
      threadId: "edge-short",
    });
    const longPath = sampleThreadCurve(source, target, {
      fadenType: "conversation",
      threadId: "edge-short",
    });
    const shortDeflect = projectedMidDeflection(shortPath, source, nearTarget);
    const longDeflect = projectedMidDeflection(longPath, source, target);
    expect(shortDeflect).toBeLessThan(longDeflect * 0.15);
    expect(shortDeflect).toBeLessThan(25);
  });

  it("applies distinct tension profiles per Fadenart", () => {
    /**
     * Lateral offset of the projected Bezier at t=0.5 from the projected chord.
     * Private (no subject): mid-arc profiles must differ by type tension.
     * Subject-bound multi-source approach is covered separately.
     */
    const midDeflection = (fadenType: string, subjectId: string | null) => {
      const { p0, p1, p2, p3, length } = threadCurveControlPointsProjected(
        source,
        target,
        {
          fadenType,
          threadId: `edge-profile-${fadenType}`,
          subjectId,
        },
      );
      // Cubic Bezier at t=0.5: 1/8*(p0+p3)+3/8*(p1+p2)
      const midX = 0.125 * (p0[0] + p3[0]) + 0.375 * (p1[0] + p2[0]);
      const midY = 0.125 * (p0[1] + p3[1]) + 0.375 * (p1[1] + p2[1]);
      const chordMidX = (p0[0] + p3[0]) / 2;
      const chordMidY = (p0[1] + p3[1]) / 2;
      expect(length).toBeGreaterThan(0);
      return Math.hypot(midX - chordMidX, midY - chordMidY);
    };
    const knot = midDeflection("knotting", null);
    const talk = midDeflection("conversation", null);
    const proposal = midDeflection("proposal", null);
    const vote = midDeflection("vote", null);
    // Knotting taut; conversation soft/wide; vote no independent large curve.
    expect(talk).toBeGreaterThan(knot);
    expect(talk).toBeGreaterThan(proposal);
    expect(talk).toBeGreaterThan(vote);
    // Proposal mid arc must clearly exceed vote's near-linear stitch — not a
    // weak half-margin that would still pass if the profiles collapsed.
    expect(proposal).toBeGreaterThan(vote);
    expect(proposal / vote).toBeGreaterThan(1.35);
    expect(threadCurveProfile("proposal").tension).toBeLessThan(
      threadCurveProfile("vote").tension,
    );
    expect(threadCurveProfile("knotting").tension).toBeGreaterThan(
      threadCurveProfile("conversation").tension,
    );
    expect(threadCurveProfile("vote").maxBulgeFraction).toBeLessThan(
      threadCurveProfile("proposal").maxBulgeFraction,
    );
    // Subject-bound: mid deflection is not required to rank like private
    // profiles (shared target axis dominates); multi-source tests lock approach.
    expect(EDGE_VISUAL_STYLE.byType.knotting.width).toBeGreaterThan(
      EDGE_VISUAL_STYLE.byType.conversation.width,
    );
    expect(EDGE_VISUAL_STYLE.byType.proposal.width).toBeGreaterThan(
      EDGE_VISUAL_STYLE.byType.vote.width,
    );
  });

  it("bounds sample count by EDGE_CURVE_MAX_SAMPLES", () => {
    const far: [number, number] = [12, 55];
    const count = threadCurveSampleCount(source, far, {
      fadenType: "conversation",
      threadId: "edge-long",
    });
    expect(count).toBeLessThanOrEqual(EDGE_CURVE_MAX_SAMPLES);
    expect(
      sampleThreadCurve(source, far, {
        fadenType: "conversation",
        threadId: "edge-long",
      }).length,
    ).toBe(count);
  });

  it("segments multi-colour strands by curve arc length with stable endpoints", () => {
    const colors = ["#111111", "#222222"];
    const segments = buildThemedLineSegments(source, target, colors, {
      fadenType: "proposal",
      threadId: "edge-theme",
    });
    expect(segments).toHaveLength(4);
    expect(segments[0].coordinates[0]).toEqual(source);
    expect(segments.at(-1)?.coordinates.at(-1)).toEqual(target);
    for (const segment of segments) {
      expect(segment.coordinates.length).toBeGreaterThanOrEqual(2);
      expect(segment.coordinates.length).toBeLessThanOrEqual(
        EDGE_CURVE_MAX_SAMPLES,
      );
    }
  });

  it("shares static and motion curve geometry for the same identity", () => {
    const opts = {
      fadenType: "proposal",
      threadId: "edge-shared",
      subjectId: "subject-42",
    };
    const staticPath = sampleThreadCurve(source, target, opts);
    const pathState = buildThreadPathState(source, target, ["#aaaaaa"], opts);
    expect(pathState.samples).toEqual(staticPath);
    const full = clipThreadPathByProgress(pathState, 1);
    const half = clipThreadPathByProgress(pathState, 0.5);
    expect(full[0].coordinates).toEqual(staticPath);
    expect(half[0].coordinates[0]).toEqual(source);
    const tip = half[0].coordinates.at(-1)!;
    const expectedTip = pointAtArcProgress(staticPath, 0.5, {
      cumulative: pathState.cumulative,
      total: pathState.totalLength,
      projected: pathState.projectedSamples,
    });
    expect(tip[0]).toBeCloseTo(expectedTip[0], 10);
    expect(tip[1]).toBeCloseTo(expectedTip[1], 10);
  });

  it("binds antrag-related threads to a shared target approach corridor", () => {
    const subject = "11111111-1111-5111-8111-111111111111";
    expect(threadCorridorKey({ threadId: "vote-1", subjectId: subject })).toBe(
      `subject:${subject}`,
    );
    expect(
      threadCorridorKey({ threadId: "proposal-1", subjectId: subject }),
    ).toBe(`subject:${subject}`);
    // Fallback never invents a subject relationship.
    expect(threadCorridorKey({ threadId: "vote-2", subjectId: null })).toBe(
      "thread:vote-2",
    );
    expect(
      threadCorridorKey({
        threadId: undefined,
        subjectId: null,
        fadenType: "vote",
      }),
    ).toBe("thread:anon:vote");

    const proposalApproach = threadTargetApproachVector(source, target, {
      fadenType: "proposal",
      threadId: "proposal-1",
      subjectId: subject,
    });
    const voteApproach = threadTargetApproachVector(source, target, {
      fadenType: "vote",
      threadId: "vote-1",
      subjectId: subject,
    });
    const talkApproach = threadTargetApproachVector(source, target, {
      fadenType: "conversation",
      threadId: "talk-1",
      subjectId: subject,
    });
    // Target-side approach axes align (dot product near 1) — not only bend sign.
    const dot = (a: [number, number], b: [number, number]) =>
      a[0] * b[0] + a[1] * b[1];
    expect(dot(proposalApproach, voteApproach)).toBeGreaterThan(0.999);
    expect(dot(proposalApproach, talkApproach)).toBeGreaterThan(0.999);

    // Without a subject id the corridor key stays private per thread — never
    // invents a shared relationship between unrelated votes.
    expect(
      threadCorridorKey({ threadId: "vote-private-a", subjectId: null }),
    ).not.toBe(
      threadCorridorKey({ threadId: "vote-private-b", subjectId: null }),
    );

    // Corridor-bound types declare the contract; without subject they stay private.
    expect(threadCurveProfile("vote").corridorBound).toBe(true);
    expect(threadCurveProfile("proposal").corridorBound).toBe(true);
    expect(threadCurveProfile("vote").maxBulgeFraction).toBeLessThan(
      threadCurveProfile("conversation").maxBulgeFraction,
    );
  });

  it("shares a true multi-source target-local approach for one subject", () => {
    const subject = "22222222-2222-5222-8222-222222222222";
    const sharedTarget: [number, number] = [10.05, 53.55];
    // Three strongly different sources: W, N, and far SE of the target.
    const sources: Array<[number, number]> = [
      [8.5, 53.55],
      [10.05, 54.4],
      [12.2, 52.1],
    ];
    const types = ["proposal", "vote", "conversation"] as const;
    const approaches = sources.map((src, index) =>
      threadTargetApproachVector(src, sharedTarget, {
        fadenType: types[index],
        threadId: `multi-src-${index}`,
        subjectId: subject,
      }),
    );
    const axis = threadTargetLocalCorridorAxis(sharedTarget, subject);
    const expectedApproach: [number, number] = [-axis[0], -axis[1]];
    const dot = (a: [number, number], b: [number, number]) =>
      a[0] * b[0] + a[1] * b[1];
    for (let i = 0; i < approaches.length; i += 1) {
      expect(dot(approaches[i], expectedApproach)).toBeGreaterThan(0.999);
      for (let j = i + 1; j < approaches.length; j += 1) {
        expect(dot(approaches[i], approaches[j])).toBeGreaterThan(0.999);
      }
    }

    for (let i = 0; i < sources.length; i += 1) {
      const path = sampleThreadCurve(sources[i], sharedTarget, {
        fadenType: types[i],
        threadId: `multi-src-${i}`,
        subjectId: subject,
      });
      expect(path[0]).toEqual(sources[i]);
      expect(path.at(-1)).toEqual(sharedTarget);
      for (const point of path) {
        expect(Number.isFinite(point[0])).toBe(true);
        expect(Number.isFinite(point[1])).toBe(true);
        // Never spike to null island unless that is a real endpoint.
        if (
          Math.abs(sources[i][0]) > 1 ||
          Math.abs(sources[i][1]) > 1 ||
          Math.abs(sharedTarget[0]) > 1 ||
          Math.abs(sharedTarget[1]) > 1
        ) {
          expect(point[0] === 0 && point[1] === 0).toBe(false);
        }
      }

      // Last control point lies on the target-local corridor axis.
      const ctrl = threadCurveControlPointsProjected(sources[i], sharedTarget, {
        fadenType: types[i],
        threadId: `multi-src-${i}`,
        subjectId: subject,
      });
      const { targetXY } = projectedChord(sources[i], sharedTarget);
      const outX = ctrl.p2[0] - targetXY[0];
      const outY = ctrl.p2[1] - targetXY[1];
      const outLen = Math.hypot(outX, outY);
      expect(outLen).toBeGreaterThan(0);
      expect(outLen).toBeLessThanOrEqual(
        Math.min(
          ctrl.length * EDGE_CURVE_MAX_HANDLE_FRACTION + 1e-6,
          EDGE_CURVE_MAX_HANDLE_M + 1e-6,
        ),
      );
      const outUnit: [number, number] = [outX / outLen, outY / outLen];
      expect(dot(outUnit, axis)).toBeGreaterThan(0.999);

      // Monotone approach in the last quarter: distance to target non-increasing.
      const lastQuarterFrom = Math.floor(path.length * 0.75);
      let prevDist = Number.POSITIVE_INFINITY;
      for (let s = lastQuarterFrom; s < path.length; s += 1) {
        const xy = projectLngLatToMercator(path[s][0], path[s][1]);
        const txy = projectLngLatToMercator(sharedTarget[0], sharedTarget[1]);
        const dist = Math.hypot(xy[0] - txy[0], xy[1] - txy[1]);
        expect(dist).toBeLessThanOrEqual(prevDist + 1e-6);
        prevDist = dist;
      }

      // No self-loop: consecutive sample direction never reverses more than 120°.
      for (let s = 2; s < path.length; s += 1) {
        const a = projectLngLatToMercator(path[s - 2][0], path[s - 2][1]);
        const b = projectLngLatToMercator(path[s - 1][0], path[s - 1][1]);
        const c = projectLngLatToMercator(path[s][0], path[s][1]);
        const v1x = b[0] - a[0];
        const v1y = b[1] - a[1];
        const v2x = c[0] - b[0];
        const v2y = c[1] - b[1];
        const n1 = Math.hypot(v1x, v1y);
        const n2 = Math.hypot(v2x, v2y);
        if (n1 < 1e-9 || n2 < 1e-9) continue;
        const turn = (v1x * v2x + v1y * v2y) / (n1 * n2);
        expect(turn).toBeGreaterThan(-0.5);
      }
    }

    // Mid arcs may still differ by type/source; only the final approach is locked.
    const midDefl = sources.map((src, index) => {
      const { p0, p1, p2, p3 } = threadCurveControlPointsProjected(
        src,
        sharedTarget,
        {
          fadenType: types[index],
          threadId: `multi-src-${index}`,
          subjectId: subject,
        },
      );
      const midX = 0.125 * (p0[0] + p3[0]) + 0.375 * (p1[0] + p2[0]);
      const midY = 0.125 * (p0[1] + p3[1]) + 0.375 * (p1[1] + p2[1]);
      return Math.hypot(midX - (p0[0] + p3[0]) / 2, midY - (p0[1] + p3[1]) / 2);
    });
    expect(midDefl[2]).toBeGreaterThan(midDefl[1]);
  });

  it("projects geometry in Web Mercator with stable EW length across latitudes", () => {
    const midSource: [number, number] = [10, 45];
    const midTarget: [number, number] = [10.2, 45];
    const highSource: [number, number] = [10, 70];
    const highTarget: [number, number] = [10.2, 70];
    const midLen = projectedChord(midSource, midTarget).length;
    const highLen = projectedChord(highSource, highTarget).length;
    // Same lon delta → same mercator-x chord at any latitude.
    expect(midLen).toBeCloseTo(highLen, 6);
    expect(midLen).toBeGreaterThan(0);

    const ns = projectedChord([10, 45], [10, 45.2]).length;
    // EW and NS with equal degree span differ in projected metres — geometry
    // uses that projected chord so map-space tension stays comparable.
    expect(Math.abs(midLen - ns)).toBeGreaterThan(1);

    const path = sampleThreadCurve(midSource, midTarget, {
      fadenType: "conversation",
      threadId: "proj-ew",
    });
    expect(path[0]).toEqual(midSource);
    expect(path.at(-1)).toEqual(midTarget);
  });

  it("measures arc progress in projected metres, not degree-space hypot", () => {
    // High-latitude diagonal: degree hypot weights Δlng/Δlat equally; Mercator
    // does not — a degree-space regression is detectable on total and tip.
    const highSource: [number, number] = [10, 68];
    const highTarget: [number, number] = [14, 72];
    const highPath = buildThreadPathState(highSource, highTarget, [], {
      fadenType: "conversation",
      threadId: "arc-high-lat",
    });
    const highDegree = degreeSpacePolylineArcState(highPath.samples);
    // Metres vs degrees: multi-order-of-magnitude gap (regression detector).
    expect(highPath.totalLength).toBeGreaterThan(highDegree.total * 1000);
    const highTip = pointAtArcProgress(highPath.samples, 0.5, {
      cumulative: highPath.cumulative,
      total: highPath.totalLength,
      projected: highPath.projectedSamples,
    });
    const highDegreeTip = pointAtArcProgress(highPath.samples, 0.5, {
      cumulative: highDegree.cumulative,
      total: highDegree.total,
    });
    // Degree-space progress misplaces the tip on a high-lat diagonal curve.
    expect(
      Math.hypot(highTip[0] - highDegreeTip[0], highTip[1] - highDegreeTip[1]),
    ).toBeGreaterThan(1e-4);

    // Pure N-S: projected Y stretch ≠ degree Δlat; totalLength is metres.
    const nsSource: [number, number] = [10, 45];
    const nsTarget: [number, number] = [10, 50];
    const nsPath = buildThreadPathState(nsSource, nsTarget, [], {
      fadenType: "conversation",
      threadId: "arc-ns",
    });
    const nsDegree = degreeSpacePolylineArcState(nsPath.samples);
    expect(nsPath.totalLength).toBeGreaterThan(nsDegree.total * 1000);
    expect(nsPath.projectedSamples.length).toBe(nsPath.samples.length);
    expect(nsPath.cumulative[0]).toBe(0);
    expect(nsPath.cumulative[nsPath.cumulative.length - 1]).toBe(
      nsPath.totalLength,
    );
    // Path state total is in metres (order of hundreds of km for 5° latitude).
    expect(nsPath.totalLength).toBeGreaterThan(100_000);
    // N-S midpoint progress differs once Mercator Y is nonlinear in lat.
    const nsTip = pointAtArcProgress(nsPath.samples, 0.5, {
      cumulative: nsPath.cumulative,
      total: nsPath.totalLength,
      projected: nsPath.projectedSamples,
    });
    const nsDegreeTip = pointAtArcProgress(nsPath.samples, 0.5, {
      cumulative: nsDegree.cumulative,
      total: nsDegree.total,
    });
    expect(Math.abs(nsTip[1] - nsDegreeTip[1])).toBeGreaterThan(1e-5);
  });

  it("never masks invalid projection as null-island [0,0]", () => {
    expect(projectedSampleToLngLat(Number.NaN, 0)).toBeNull();
    expect(projectedSampleToLngLat(0, Number.NaN)).toBeNull();
    expect(projectedSampleToLngLat(Number.POSITIVE_INFINITY, 0)).toBeNull();
    expect(projectedSampleToLngLat(0, Number.NEGATIVE_INFINITY)).toBeNull();
    // Finite projection still works.
    const origin = projectedSampleToLngLat(0, 0);
    expect(origin).not.toBeNull();
    expect(origin![0]).toBeCloseTo(0, 10);
    expect(origin![1]).toBeCloseTo(0, 10);
    // Sampled paths never inject a [0,0] spike on non-zero endpoints.
    const path = sampleThreadCurve([9, 53], [11, 54], {
      fadenType: "proposal",
      threadId: "finite-fallback",
    });
    for (const point of path) {
      expect(Number.isFinite(point[0])).toBe(true);
      expect(Number.isFinite(point[1])).toBe(true);
      expect(point[0] === 0 && point[1] === 0).toBe(false);
    }
  });

  it("uses the short unwrapped antimeridian path without NaN samples", () => {
    const west: [number, number] = [170, 10];
    const east: [number, number] = [-170, 10];
    expect(shortestLongitudeDelta(170, -170)).toBe(20);
    expect(Math.abs(shortestLongitudeDelta(170, -170))).toBeLessThan(180);
    const chord = projectedChord(west, east);
    // Unwrapped target at 190° — short 20° hop, not the 340° long way.
    expect(chord.unwrappedTargetLng).toBeCloseTo(190, 10);
    // Naive lon subtraction without unwrap would span 340°.
    const naiveDx =
      projectLngLatToMercator(-170, 10)[0] -
      projectLngLatToMercator(170, 10)[0];
    const naiveLong = Math.hypot(naiveDx, 0);
    expect(chord.length).toBeLessThan(naiveLong * 0.2);
    expect(chord.length).toBeCloseTo(
      Math.abs((20 * Math.PI * EDGE_CURVE_MERCATOR_RADIUS_M) / 180),
      0,
    );

    const path = sampleThreadCurve(west, east, {
      fadenType: "conversation",
      threadId: "anti-1",
    });
    expect(path[0]).toEqual(west);
    expect(path.at(-1)).toEqual(east);
    for (const point of path) {
      expect(Number.isFinite(point[0])).toBe(true);
      expect(Number.isFinite(point[1])).toBe(true);
    }
    // Intermediate samples follow the unwrapped short corridor (lng ≥ 170).
    for (let index = 1; index < path.length - 1; index += 1) {
      expect(path[index][0]).toBeGreaterThan(169);
    }
  });

  it("builds a path state once and clips progress without rebuilding", () => {
    resetThreadPathBuildSerialForTests();
    const before = getThreadPathBuildSerialForTests();
    const path = buildThreadPathState(source, target, ["#111111", "#222222"], {
      fadenType: "proposal",
      threadId: "cache-1",
    });
    expect(getThreadPathBuildSerialForTests()).toBe(before + 1);
    const a = clipThreadPathByProgress(path, 0.25);
    const b = clipThreadPathByProgress(path, 0.5);
    const c = clipThreadPathByProgress(path, 0.9);
    expect(getThreadPathBuildSerialForTests()).toBe(before + 1);
    expect(a.length).toBeGreaterThan(0);
    expect(b.length).toBeGreaterThanOrEqual(a.length);
    expect(c.length).toBeGreaterThanOrEqual(b.length);
    const tip = c[c.length - 1].coordinates.at(-1)!;
    const expected = pointAtArcProgress(path.samples, 0.9, {
      cumulative: path.cumulative,
      total: path.totalLength,
      projected: path.projectedSamples,
    });
    expect(tip[0]).toBeCloseTo(expected[0], 10);
    expect(tip[1]).toBeCloseTo(expected[1], 10);
  });

  it("projects continuous body/shadow layers vs highlight braid rhythm", () => {
    for (const variant of EDGE_THREAD_VARIANTS) {
      if (variant.fadenType === "vote") {
        expect(variant.bodyContinuous).toBe(false);
        expect(variant.shadowContinuous).toBe(true);
      } else {
        expect(variant.bodyContinuous).toBe(true);
        expect(variant.shadowContinuous).toBe(true);
      }
      expect(variant.dashArray[0]).toBeGreaterThan(0);
    }
  });

  it("keeps multi-colour strand colours stable under partial progress", () => {
    const colors = ["#111111", "#222222", "#333333"];
    const full = buildThemedLineSegments(source, target, colors, {
      fadenType: "knotting",
      threadId: "edge-multi",
    });
    const half = buildProgressClippedThemeSegments(
      source,
      target,
      colors,
      0.5,
      { fadenType: "knotting", threadId: "edge-multi" },
    );
    expect(half.length).toBeGreaterThan(0);
    expect(half.length).toBeLessThanOrEqual(full.length);
    expect(half[0].color).toBe(full[0].color);
    expect(half[0].coordinates[0]).toEqual(full[0].coordinates[0]);
  });
});
