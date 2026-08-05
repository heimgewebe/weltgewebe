import { describe, expect, it } from "vitest";
import {
  FADEN_LIFETIME_MS,
  normalizeEdgeLifecycle,
} from "$lib/map/edgeLifecycle";
import {
  EDGE_CURVE_MAX_SAMPLES,
  EDGE_THREAD_LAYER_IDS,
  EDGE_THREAD_VARIANTS,
  EDGE_VISUAL_STYLE,
  buildEdgeFeatures,
  buildEdgeLayerSpecifications,
  buildEndpointIndex,
  buildProgressClippedThemeSegments,
  buildThemedLineSegments,
  hasCompleteEdgeThreadStyle,
  sampleThreadCurve,
  threadCorridorKey,
  threadCurveControlPoints,
  threadCurveProfile,
  threadCurveSampleCount,
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

  it("bends to a stable side from thread identity", () => {
    const left = threadCurveControlPoints(source, target, {
      fadenType: "conversation",
      threadId: "edge-a",
    });
    const again = threadCurveControlPoints(source, target, {
      fadenType: "conversation",
      threadId: "edge-a",
    });
    expect(left.p1[1] - source[1]).toBeCloseTo(again.p1[1] - source[1], 12);
    // Control points leave the chord (natural mid arc, not a technical line).
    const midY = (source[1] + target[1]) / 2;
    const chordYAtHalf = source[1] + 0.5 * (target[1] - source[1]);
    const sampleMid = sampleThreadCurve(source, target, {
      fadenType: "conversation",
      threadId: "edge-a",
    });
    const midPoint = sampleMid[Math.floor(sampleMid.length / 2)];
    expect(Math.abs(midPoint[1] - chordYAtHalf)).toBeGreaterThan(1e-6);
    expect(midY).toBeDefined();
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
    const shortMid = shortPath[Math.floor(shortPath.length / 2)];
    const longMid = longPath[Math.floor(longPath.length / 2)];
    const shortChord = [
      (source[0] + nearTarget[0]) / 2,
      (source[1] + nearTarget[1]) / 2,
    ];
    const longChord = [
      (source[0] + target[0]) / 2,
      (source[1] + target[1]) / 2,
    ];
    const shortDeflect = Math.hypot(
      shortMid[0] - shortChord[0],
      shortMid[1] - shortChord[1],
    );
    const longDeflect = Math.hypot(
      longMid[0] - longChord[0],
      longMid[1] - longChord[1],
    );
    // Absolute short deflection stays tiny relative to a full soft conversation arc.
    expect(shortDeflect).toBeLessThan(longDeflect * 0.15);
    expect(shortDeflect).toBeLessThan(0.0005);
  });

  it("applies distinct tension profiles per Fadenart", () => {
    const midDeflection = (fadenType: string) => {
      const path = sampleThreadCurve(source, target, {
        fadenType,
        threadId: "edge-profile",
        subjectId: "shared-subject",
      });
      const mid = path[Math.floor(path.length / 2)];
      const chord = [(source[0] + target[0]) / 2, (source[1] + target[1]) / 2];
      return Math.hypot(mid[0] - chord[0], mid[1] - chord[1]);
    };
    const knot = midDeflection("knotting");
    const talk = midDeflection("conversation");
    const proposal = midDeflection("proposal");
    const vote = midDeflection("vote");
    // Knotting taut; conversation soft/wide; vote no independent large curve.
    expect(talk).toBeGreaterThan(knot);
    expect(talk).toBeGreaterThan(proposal);
    expect(proposal).toBeGreaterThan(vote);
    expect(threadCurveProfile("knotting").tension).toBeGreaterThan(
      threadCurveProfile("conversation").tension,
    );
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
    // Interior strands are polylines on the curve, not two-point capsules.
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
    const full = buildProgressClippedThemeSegments(
      source,
      target,
      ["#aaaaaa"],
      1,
      opts,
    );
    const half = buildProgressClippedThemeSegments(
      source,
      target,
      ["#aaaaaa"],
      0.5,
      opts,
    );
    expect(full[0].coordinates).toEqual(staticPath);
    expect(half[0].coordinates[0]).toEqual(source);
    expect(half[0].coordinates.at(-1)).not.toEqual(target);
    // Half tip lies on the same static path (prefix of full curve).
    const tip = half[0].coordinates.at(-1)!;
    const onPath = staticPath.some(
      (point) => Math.hypot(point[0] - tip[0], point[1] - tip[1]) < 1e-9,
    );
    // Tip is interpolated; verify it sits between consecutive full-path points
    // by checking distance to the polyline is tiny via nearest segment.
    let minDist = Number.POSITIVE_INFINITY;
    for (let index = 1; index < staticPath.length; index += 1) {
      const a = staticPath[index - 1];
      const b = staticPath[index];
      const abx = b[0] - a[0];
      const aby = b[1] - a[1];
      const apx = tip[0] - a[0];
      const apy = tip[1] - a[1];
      const ab2 = abx * abx + aby * aby;
      const t =
        ab2 > 0 ? Math.max(0, Math.min(1, (apx * abx + apy * aby) / ab2)) : 0;
      const px = a[0] + abx * t;
      const py = a[1] + aby * t;
      minDist = Math.min(minDist, Math.hypot(tip[0] - px, tip[1] - py));
    }
    expect(minDist).toBeLessThan(1e-9);
    expect(onPath || minDist < 1e-9).toBe(true);
  });

  it("binds proposal-related threads to a shared subject corridor with safe fallback", () => {
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

    const proposal = threadCurveControlPoints(source, target, {
      fadenType: "proposal",
      threadId: "proposal-1",
      subjectId: subject,
    });
    const vote = threadCurveControlPoints(source, target, {
      fadenType: "vote",
      threadId: "vote-1",
      subjectId: subject,
    });
    // Same corridor bend side: lateral offset signs match.
    const propLat = proposal.p1[0] - source[0];
    const voteLat = vote.p1[0] - source[0];
    // Along-chord component dominates; compare perpendicular component via p1 offset side.
    const dx = target[0] - source[0];
    const dy = target[1] - source[1];
    const len = Math.hypot(dx, dy);
    const alongX = dx / len;
    const alongY = dy / len;
    const propPerp =
      (proposal.p1[0] - source[0]) * -alongY +
      (proposal.p1[1] - source[1]) * alongX;
    const votePerp =
      (vote.p1[0] - source[0]) * -alongY + (vote.p1[1] - source[1]) * alongX;
    expect(Math.sign(propPerp)).toBe(Math.sign(votePerp));
    expect(propLat).toBeDefined();
    expect(voteLat).toBeDefined();

    const unboundVote = sampleThreadCurve(source, target, {
      fadenType: "vote",
      threadId: "vote-unbound",
      subjectId: null,
    });
    const boundVote = sampleThreadCurve(source, target, {
      fadenType: "vote",
      threadId: "vote-bound",
      subjectId: subject,
    });
    const midDeflect = (path: [number, number][]) => {
      const mid = path[Math.floor(path.length / 2)];
      const chord = [(source[0] + target[0]) / 2, (source[1] + target[1]) / 2];
      return Math.hypot(mid[0] - chord[0], mid[1] - chord[1]);
    };
    // Unbound vote stays safer/smaller without inventing a corridor partner.
    expect(midDeflect(unboundVote)).toBeLessThanOrEqual(
      midDeflect(boundVote) * 1.05,
    );
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
