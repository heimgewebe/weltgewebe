import { describe, expect, it } from "vitest";
import {
  FADEN_LIFETIME_MS,
  normalizeEdgeLifecycle,
} from "$lib/map/edgeLifecycle";
import {
  EDGE_THREAD_LAYER_IDS,
  buildEdgeFeatures,
  buildEdgeLayerSpecifications,
  hasCompleteEdgeThreadStyle,
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
    expect(features[0].geometry.coordinates).toEqual([
      [9.9, 53.5],
      [10.058, 53.5585],
    ]);
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
          themeSegments: [],
          primaryThemeColor: "#5f7a55",
          coreDensity: 0.5,
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
    // Halo plus line for legacy and the four typed thread kinds.
    expect(EDGE_THREAD_LAYER_IDS).toHaveLength(10);
  });

  it("accepts the complete set of source and thread layers", () => {
    expect(hasCompleteEdgeThreadStyle(probe(EDGE_THREAD_LAYER_IDS))).toBe(true);
  });

  it("rejects a style that is missing the last typed layer", () => {
    expect(
      hasCompleteEdgeThreadStyle(probe(EDGE_THREAD_LAYER_IDS.slice(0, -1))),
    ).toBe(false);
  });

  it("rejects the old partial check of source plus the two legacy layers", () => {
    expect(
      hasCompleteEdgeThreadStyle(
        probe([LAYERS.EDGES_HALO_LAYER, LAYERS.EDGES_LAYER]),
      ),
    ).toBe(false);
  });

  it("rejects a missing edge source and an absent map", () => {
    expect(
      hasCompleteEdgeThreadStyle(probe(EDGE_THREAD_LAYER_IDS, "other-source")),
    ).toBe(false);
    expect(hasCompleteEdgeThreadStyle(null)).toBe(false);
  });
});
