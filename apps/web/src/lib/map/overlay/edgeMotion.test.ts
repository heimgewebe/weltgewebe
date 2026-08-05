import { describe, expect, it } from "vitest";
import type { Map as MapLibreMap } from "maplibre-gl";
import {
  EDGE_MOTION_DURATION_MS,
  EDGE_MOTION_HALO_LAYER,
  EDGE_MOTION_LAYER,
  EDGE_MOTION_LAYER_IDS,
  EDGE_MOTION_MAX_ACTIVE,
  EDGE_MOTION_SOURCE,
  EdgeMotionController,
  resolveEdgeMotionInput,
  type EdgeMotionInput,
  type EdgeMotionScheduler,
} from "$lib/map/overlay/edgeMotion";
import type { MapEdge, MapEntityViewModel } from "$lib/map/types";
import { normalizeEdgeLifecycle } from "$lib/map/edgeLifecycle";
import {
  buildEdgeFeatures,
  buildEdgeLayerSpecifications,
  buildProgressClippedThemeSegments,
  EDGE_THREAD_LAYER_IDS,
  EDGE_THREAD_VARIANTS,
  EDGE_VISUAL_STYLE,
  pointAtArcProgress,
  sampleThreadCurve,
} from "$lib/map/overlay/edges";
import { deriveEntityWeave, targetThemePalette } from "$lib/map/weaveModel";

class ManualScheduler implements EdgeMotionScheduler {
  time = 0;
  reduced = false;
  nextHandle = 1;
  callbacks = new Map<number, FrameRequestCallback>();

  now = () => this.time;
  prefersReducedMotion = () => this.reduced;
  requestFrame = (callback: FrameRequestCallback) => {
    const handle = this.nextHandle++;
    this.callbacks.set(handle, callback);
    return handle;
  };
  cancelFrame = (handle: number) => {
    this.callbacks.delete(handle);
  };

  advance(milliseconds: number) {
    this.time += milliseconds;
    const pending = Array.from(this.callbacks.values());
    this.callbacks.clear();
    for (const callback of pending) callback(this.time);
  }
}

class GeoJsonSourceStub {
  data: GeoJSON.FeatureCollection<GeoJSON.LineString> = {
    type: "FeatureCollection",
    features: [],
  };

  setData(data: GeoJSON.FeatureCollection<GeoJSON.LineString>) {
    this.data = data;
  }

  serialize() {
    return { type: "geojson", data: this.data };
  }
}

class MapStub {
  sources = new Map<string, GeoJsonSourceStub>();
  layers = new Map<string, Record<string, unknown>>();
  layerOrder: string[] = [];
  filters = new Map<string, unknown>();
  listeners = new Map<string, Set<() => void>>();

  constructor() {
    for (const layer of buildEdgeLayerSpecifications()) {
      this.addLayer(layer as unknown as Record<string, unknown>);
    }
    this.addLayer({ id: "labels", type: "symbol" });
  }

  on(event: string, listener: () => void) {
    const listeners = this.listeners.get(event) ?? new Set();
    listeners.add(listener);
    this.listeners.set(event, listeners);
    return this;
  }

  off(event: string, listener: () => void) {
    this.listeners.get(event)?.delete(listener);
    return this;
  }

  emit(event: string) {
    for (const listener of this.listeners.get(event) ?? []) listener();
  }

  addSource(id: string) {
    this.sources.set(id, new GeoJsonSourceStub());
  }

  getSource(id: string) {
    return this.sources.get(id);
  }

  removeSource(id: string) {
    this.sources.delete(id);
  }

  addLayer(layer: Record<string, unknown>, beforeId?: string) {
    const id = String(layer.id);
    this.layers.set(id, layer);
    if ("filter" in layer) this.filters.set(id, layer.filter ?? null);
    const oldIndex = this.layerOrder.indexOf(id);
    if (oldIndex >= 0) this.layerOrder.splice(oldIndex, 1);
    const beforeIndex = beforeId ? this.layerOrder.indexOf(beforeId) : -1;
    if (beforeIndex >= 0) this.layerOrder.splice(beforeIndex, 0, id);
    else this.layerOrder.push(id);
  }

  getLayer(id: string) {
    return this.layers.get(id);
  }

  removeLayer(id: string) {
    this.layers.delete(id);
    this.filters.delete(id);
    const index = this.layerOrder.indexOf(id);
    if (index >= 0) this.layerOrder.splice(index, 1);
  }

  getStyle() {
    return {
      version: 8 as const,
      sources: {},
      layers: this.layerOrder.map((id) => this.layers.get(id)!),
    };
  }

  getFilter(id: string) {
    return this.filters.get(id) ?? null;
  }

  setFilter(id: string, filter: unknown) {
    this.filters.set(id, filter ?? null);
  }
}

function createHarness(reduced = false) {
  const map = new MapStub();
  const scheduler = new ManualScheduler();
  scheduler.reduced = reduced;
  const controller = new EdgeMotionController(
    map as unknown as MapLibreMap,
    scheduler,
  );
  return { map, scheduler, controller };
}

const input: EdgeMotionInput = {
  id: "edge-1",
  source: [0, 0],
  target: [10, 20],
  kind: "reference",
};

function motionSource(map: MapStub) {
  return map.getSource(EDGE_MOTION_SOURCE)!;
}

const canonicalLayerSpecifications = new Map(
  buildEdgeLayerSpecifications().map((specification) => [
    specification.id,
    specification,
  ]),
);

function expectCanonicalFilters(map: MapStub, hiddenIds: string[]) {
  expect([...canonicalLayerSpecifications.keys()]).toEqual(
    EDGE_THREAD_LAYER_IDS,
  );
  const hideFilter = ["!", ["in", ["get", "id"], ["literal", hiddenIds]]];
  for (const layerId of EDGE_THREAD_LAYER_IDS) {
    const baseFilter =
      canonicalLayerSpecifications.get(layerId)?.filter ?? null;
    const expectedFilter =
      hiddenIds.length === 0
        ? baseFilter
        : baseFilter
          ? ["all", baseFilter, hideFilter]
          : hideFilter;
    expect(map.getFilter(layerId)).toEqual(expectedFilter);
  }
}

describe("resolveEdgeMotionInput", () => {
  it("resolves normal and Webgemeindezentrum endpoint ids", () => {
    const edge = {
      id: "edge-center",
      source_id: "account",
      target_id: "center-endpoint",
      edge_kind: "membership",
      lifecycle: { kind: "legacy" },
    } as MapEdge;
    const points = [
      {
        type: "garnrolle",
        id: "account",
        title: "Quelle",
        lat: 53.5,
        lon: 10,
        created_at: "2026-08-03T00:00:00Z",
      },
      {
        type: "webgemeindezentrum",
        id: "center",
        faden_endpoint_id: "center-endpoint",
        title: "Zentrum",
        lat: 53.6,
        lon: 10.2,
        summary: "",
        tags: [],
        created_at: "2026-08-03T00:00:00Z",
        updated_at: "2026-08-03T00:00:00Z",
        location_state: "desired",
        location_state_label: "Gewünscht",
        conversation_id: "conversation",
        location_label: "Ort",
        meeting_note: "",
        access_note: "",
        ortsweberei: {
          id: "ow",
          slug: "ow",
          name: "OW",
          gewebezelle_id: "ow.example",
        },
      },
    ] as MapEntityViewModel[];

    const resolved = resolveEdgeMotionInput(edge, points);
    expect(resolved).toMatchObject({
      id: "edge-center",
      source: [10, 53.5],
      target: [10.2, 53.6],
      kind: "membership",
      fadenType: "legacy",
    });
    expect(resolved?.themeColor).toMatch(/^#[0-9a-f]{6}$/i);
    expect(resolved?.themeColors?.length).toBeGreaterThan(0);
    expect(resolved?.themeColors?.[0]).toBe(resolved?.themeColor);
  });

  it("uses the projected multi-theme weave palette, not monochrome raw fallback", () => {
    const createdAt = "2026-08-03T00:00:00Z";
    const createdAtMs = Date.parse(createdAt);
    const edge = normalizeEdgeLifecycle({
      id: "edge-multi",
      source_id: "account",
      target_id: "node-1",
      edge_kind: "reference",
      faden_type: "knotting",
      created_at: createdAt,
    });
    const rawTarget = {
      type: "node" as const,
      id: "node-1",
      title: "Garten",
      kind: "Knoten",
      tags: ["Natur", "Bildung", "Kunst"],
      created_at: createdAt,
      lat: 53.6,
      lon: 10.2,
    };
    const projectedTarget = {
      ...rawTarget,
      weave: deriveEntityWeave(rawTarget, [], createdAtMs),
    };
    const source = {
      type: "garnrolle" as const,
      id: "account",
      title: "Quelle",
      lat: 53.5,
      lon: 10,
      created_at: createdAt,
    };
    const expectedPalette = targetThemePalette(projectedTarget.weave);
    expect(expectedPalette.length).toBeGreaterThan(1);

    const motionFromProjected = resolveEdgeMotionInput(edge, [
      source,
      projectedTarget,
    ] as MapEntityViewModel[]);
    expect(motionFromProjected?.themeColors).toEqual(expectedPalette);
    expect(motionFromProjected?.themeColor).toBe(expectedPalette[0]);

    // Raw markers without weave collapse to a single colour — the integration
    // path must never feed them into motion when projection is available.
    const motionFromRaw = resolveEdgeMotionInput(edge, [
      source,
      rawTarget,
    ] as MapEntityViewModel[]);
    expect(motionFromRaw?.themeColors).toHaveLength(1);
    expect(motionFromRaw?.themeColors).not.toEqual(expectedPalette);

    const staticFeatures = buildEdgeFeatures(
      [edge],
      [source, projectedTarget] as MapEntityViewModel[],
      true,
      createdAtMs,
    );
    const staticPalette = staticFeatures[0]?.properties?.themeColors as
      | string[]
      | undefined;
    expect(staticPalette).toEqual(expectedPalette);
    expect(motionFromProjected?.themeColors).toEqual(staticPalette);
  });
});

describe("EdgeMotionController", () => {
  it("grows once, hides only the matching static edge, then becomes idle", () => {
    const { map, scheduler, controller } = createHarness();
    controller.setVisibleEdgeIds(new Set([input.id]));
    controller.startCreate(input);

    expect(controller.inspect()).toMatchObject({
      activeCount: 1,
      framePending: true,
    });
    expectCanonicalFilters(map, [input.id]);

    scheduler.advance(EDGE_MOTION_DURATION_MS / 2);
    const halfway = motionSource(map).data.features[0];
    expect(halfway.properties?.progress).toBeCloseTo(0.5, 5);
    // Progress clips the stable curve at arc-length halfway (exact endpoints preserved).
    expect(halfway.geometry.coordinates[0]).toEqual([0, 0]);
    const expectedTip = pointAtArcProgress(
      sampleThreadCurve([0, 0], [10, 20], {
        fadenType: "legacy",
        threadId: input.id,
      }),
      0.5,
    );
    const tip = halfway.geometry.coordinates.at(-1)!;
    expect(tip[0]).toBeCloseTo(expectedTip[0], 8);
    expect(tip[1]).toBeCloseTo(expectedTip[1], 8);
    expect(halfway.geometry.coordinates.length).toBeGreaterThanOrEqual(2);

    scheduler.advance(EDGE_MOTION_DURATION_MS / 2);
    expect(controller.inspect()).toMatchObject({
      activeCount: 0,
      framePending: false,
    });
    expect(motionSource(map).data.features).toEqual([]);
    expectCanonicalFilters(map, []);
  });

  it("keeps multi-theme colours and typed structure during create and release", () => {
    const { map, scheduler, controller } = createHarness();
    const palette = ["#111111", "#222222", "#333333"];
    const typed: EdgeMotionInput = {
      id: "edge-multi",
      source: [0, 0],
      target: [12, 0],
      kind: "reference",
      fadenType: "proposal",
      themeColor: palette[0],
      themeColors: palette,
    };
    // All typed motion probes must remain visible while active.
    const allIds = new Set([
      typed.id,
      ...EDGE_THREAD_VARIANTS.map((variant) => `edge-${variant.fadenType}`),
    ]);
    controller.setVisibleEdgeIds(allIds);
    controller.startCreate(typed);
    scheduler.advance(EDGE_MOTION_DURATION_MS / 2);

    const creating = motionSource(map).data.features.filter(
      (feature) => feature.properties?.id === typed.id,
    );
    expect(creating.length).toBeGreaterThan(1);
    const createColors = [
      ...new Set(creating.map((feature) => feature.properties?.themeColor)),
    ];
    expect(createColors.length).toBeGreaterThan(1);
    expect(createColors.every((color) => palette.includes(String(color)))).toBe(
      true,
    );
    expect(
      creating.every((feature) => feature.properties?.fadenType === "proposal"),
    ).toBe(true);
    // Stable segment seams: first colour always starts at the source.
    expect(creating[0].geometry.coordinates[0]).toEqual([0, 0]);
    expect(creating[0].properties?.themeColor).toBe(palette[0]);

    // Typed motion layers exist with proposal structure (continuous body, highlight braid).
    const proposalMain = map.getLayer("edge-motion-layer-proposal") as
      | { paint?: Record<string, unknown> }
      | undefined;
    const proposalHighlight = map.getLayer(
      "edge-motion-highlight-layer-proposal",
    ) as { paint?: Record<string, unknown> } | undefined;
    expect(proposalMain?.paint?.["line-width"]).toBe(
      EDGE_VISUAL_STYLE.byType.proposal.width,
    );
    expect(proposalMain?.paint?.["line-dasharray"]).toBeUndefined();
    expect(proposalHighlight?.paint?.["line-dasharray"]).toEqual([
      ...EDGE_VISUAL_STYLE.byType.proposal.dashArray,
    ]);

    for (const fadenType of EDGE_THREAD_VARIANTS.map(
      (variant) => variant.fadenType,
    )) {
      const typeInput: EdgeMotionInput = {
        ...typed,
        id: `edge-${fadenType}`,
        fadenType: fadenType as EdgeMotionInput["fadenType"],
      };
      controller.startCreate(typeInput);
      // Progress is zero on the start frame; advance so segments become visible.
      scheduler.advance(EDGE_MOTION_DURATION_MS / 4);
      const features = motionSource(map).data.features.filter(
        (feature) => feature.properties?.id === typeInput.id,
      );
      expect(features.length).toBeGreaterThan(0);
      expect(
        features.every(
          (feature) => feature.properties?.fadenType === fadenType,
        ),
      ).toBe(true);
      const main = map.getLayer(
        fadenType === "legacy"
          ? EDGE_MOTION_LAYER
          : `edge-motion-layer-${fadenType}`,
      ) as { paint?: Record<string, unknown> } | undefined;
      const highlight = map.getLayer(
        fadenType === "legacy"
          ? "edge-motion-highlight-layer-legacy"
          : `edge-motion-highlight-layer-${fadenType}`,
      ) as { paint?: Record<string, unknown> } | undefined;
      const expected = EDGE_THREAD_VARIANTS.find(
        (variant) => variant.fadenType === fadenType,
      )!;
      expect(main?.paint?.["line-width"]).toBe(expected.width);
      expect(highlight?.paint?.["line-dasharray"]).toEqual([
        ...expected.dashArray,
      ]);
      if (expected.bodyContinuous) {
        expect(main?.paint?.["line-dasharray"]).toBeUndefined();
      } else {
        expect(main?.paint?.["line-dasharray"]).toEqual([
          ...expected.dashArray,
        ]);
      }
    }

    controller.cancel("edge-multi");
    for (const fadenType of EDGE_THREAD_VARIANTS.map(
      (variant) => variant.fadenType,
    )) {
      controller.cancel(`edge-${fadenType}`);
    }
    controller.setVisibleEdgeIds(new Set([typed.id]));
    controller.startRelease(typed);
    scheduler.advance(EDGE_MOTION_DURATION_MS / 3);
    const releasing = motionSource(map).data.features.filter(
      (feature) => feature.properties?.id === typed.id,
    );
    expect(releasing.length).toBeGreaterThan(1);
    expect(
      new Set(releasing.map((feature) => feature.properties?.themeColor)).size,
    ).toBeGreaterThan(1);
    expect(
      releasing.every(
        (feature) => feature.properties?.fadenType === "proposal",
      ),
    ).toBe(true);
  });

  it("clips progress on fixed colour seams rather than walking them", () => {
    const opts = { fadenType: "legacy", threadId: "edge-seams" };
    const full = buildProgressClippedThemeSegments(
      [0, 0],
      [8, 0],
      ["#aaaaaa", "#bbbbbb"],
      1,
      opts,
    );
    const half = buildProgressClippedThemeSegments(
      [0, 0],
      [8, 0],
      ["#aaaaaa", "#bbbbbb"],
      0.5,
      opts,
    );
    expect(full).toHaveLength(4);
    expect(half.length).toBeGreaterThan(0);
    expect(half.length).toBeLessThan(full.length);
    // First seam stays at the same absolute geometry for both progress values.
    expect(half[0].coordinates[0]).toEqual(full[0].coordinates[0]);
    expect(half[0].color).toBe(full[0].color);
    const lastHalf = half[half.length - 1];
    const tip = lastHalf.coordinates[lastHalf.coordinates.length - 1];
    const expectedTip = pointAtArcProgress(
      sampleThreadCurve([0, 0], [8, 0], opts),
      0.5,
    );
    expect(tip[0]).toBeCloseTo(expectedTip[0], 8);
    expect(tip[1]).toBeCloseTo(expectedTip[1], 8);
  });

  it("shares the exact static yarn style definition with motion layers", () => {
    const staticSpecs = buildEdgeLayerSpecifications();
    const { map, controller } = createHarness();
    // Ensure motion layers exist.
    controller.startCreate(input);

    for (const variant of EDGE_THREAD_VARIANTS) {
      const staticBodyId =
        variant.fadenType === "legacy"
          ? "edges-layer"
          : `edges-${variant.fadenType}-layer`;
      const staticHighlightId =
        variant.fadenType === "legacy"
          ? "edges-highlight-layer"
          : `edges-${variant.fadenType}-highlight-layer`;
      const motionBodyId =
        variant.fadenType === "legacy"
          ? EDGE_MOTION_LAYER
          : `edge-motion-layer-${variant.fadenType}`;
      const motionHighlightId =
        variant.fadenType === "legacy"
          ? "edge-motion-highlight-layer-legacy"
          : `edge-motion-highlight-layer-${variant.fadenType}`;
      const staticBody = staticSpecs.find((spec) => spec.id === staticBodyId);
      const staticHighlight = staticSpecs.find(
        (spec) => spec.id === staticHighlightId,
      );
      const motionBody = map.getLayer(motionBodyId) as
        | { paint?: Record<string, unknown> }
        | undefined;
      const motionHighlight = map.getLayer(motionHighlightId) as
        | { paint?: Record<string, unknown> }
        | undefined;

      expect(staticBody?.paint?.["line-width"]).toBe(variant.width);
      expect(motionBody?.paint?.["line-width"]).toBe(variant.width);
      // Highlight braid is shared; body continuity matches the variant profile.
      expect(staticHighlight?.paint?.["line-dasharray"]).toEqual([
        ...variant.dashArray,
      ]);
      expect(motionHighlight?.paint?.["line-dasharray"]).toEqual([
        ...variant.dashArray,
      ]);
      if (variant.bodyContinuous) {
        expect(staticBody?.paint?.["line-dasharray"]).toBeUndefined();
        expect(motionBody?.paint?.["line-dasharray"]).toBeUndefined();
      } else {
        expect(staticBody?.paint?.["line-dasharray"]).toEqual([
          ...variant.dashArray,
        ]);
        expect(motionBody?.paint?.["line-dasharray"]).toEqual([
          ...variant.dashArray,
        ]);
      }

      const typed =
        EDGE_VISUAL_STYLE.byType[
          variant.fadenType as keyof typeof EDGE_VISUAL_STYLE.byType
        ];
      expect(variant.width).toBe(typed?.width ?? EDGE_VISUAL_STYLE.bodyWidth);
      expect(variant.dashArray).toEqual(
        typed?.dashArray ?? EDGE_VISUAL_STYLE.dashArray,
      );
    }

    // Bounded yarn stack: three layers per type for static and motion alike.
    expect(EDGE_THREAD_LAYER_IDS).toHaveLength(EDGE_THREAD_VARIANTS.length * 3);
    expect(EDGE_MOTION_LAYER_IDS).toHaveLength(EDGE_THREAD_VARIANTS.length * 3);
    controller.destroy();
  });

  it("retracts along the same geometry and suppresses the static edge until data removal", () => {
    const { map, scheduler, controller } = createHarness();
    controller.setVisibleEdgeIds(new Set([input.id]));
    controller.startRelease(input);

    scheduler.advance(EDGE_MOTION_DURATION_MS / 2);
    const features = motionSource(map).data.features;
    expect(features.length).toBeGreaterThan(0);
    const expectedTip = pointAtArcProgress(
      sampleThreadCurve([0, 0], [10, 20], {
        fadenType: "legacy",
        threadId: input.id,
      }),
      0.5,
    );
    const lastFeature = features[features.length - 1];
    const tip =
      lastFeature.geometry.coordinates[
        lastFeature.geometry.coordinates.length - 1
      ];
    expect(tip[0]).toBeCloseTo(expectedTip[0], 8);
    expect(tip[1]).toBeCloseTo(expectedTip[1], 8);

    scheduler.advance(EDGE_MOTION_DURATION_MS / 2);
    expect(controller.inspect()).toMatchObject({
      activeCount: 0,
      framePending: false,
      suppressedIds: [input.id],
    });
    expectCanonicalFilters(map, [input.id]);

    controller.syncCanonicalEdges([]);
    expect(controller.inspect().suppressedIds).toEqual([]);
    expectCanonicalFilters(map, []);
  });

  it("jumps to the canonical end state under reduced motion without requesting a frame", () => {
    const { map, scheduler, controller } = createHarness(true);
    controller.startCreate(input);
    expect(controller.inspect()).toMatchObject({
      activeCount: 0,
      framePending: false,
      frameRequests: 0,
    });

    controller.startRelease(input);
    expect(controller.inspect()).toMatchObject({
      activeCount: 0,
      framePending: false,
      frameRequests: 0,
      suppressedIds: [input.id],
    });
    expect(scheduler.callbacks.size).toBe(0);
    expectCanonicalFilters(map, [input.id]);
  });

  it("reverses a rapid counter-event without a geometry jump", () => {
    const { scheduler, controller } = createHarness();
    controller.startCreate(input);
    scheduler.advance(EDGE_MOTION_DURATION_MS / 2);
    const before = controller.inspect().active[0].progress;

    controller.startRelease(input);
    const after = controller.inspect().active[0];
    expect(after.phase).toBe("releasing");
    expect(after.progress).toBeCloseTo(before, 8);

    scheduler.advance(EDGE_MOTION_DURATION_MS / 4);
    expect(controller.inspect().active[0].progress).toBeLessThan(before);
  });

  it("bounds concurrency, rehydrates after style replacement and cleans up fully", () => {
    const { map, controller } = createHarness();
    for (let index = 0; index < EDGE_MOTION_MAX_ACTIVE + 3; index += 1) {
      controller.startCreate({
        ...input,
        id: `edge-${index}`,
        target: [index + 1, index + 2],
      });
    }
    expect(controller.inspect().activeCount).toBe(EDGE_MOTION_MAX_ACTIVE);
    expect(EDGE_MOTION_LAYER_IDS.length).toBe(EDGE_THREAD_VARIANTS.length * 3);

    for (const layerId of EDGE_MOTION_LAYER_IDS) {
      map.removeLayer(layerId);
    }
    map.removeSource(EDGE_MOTION_SOURCE);
    map.emit("styledata");
    expect(map.getSource(EDGE_MOTION_SOURCE)).toBeDefined();
    for (const layerId of EDGE_MOTION_LAYER_IDS) {
      expect(map.getLayer(layerId)).toBeDefined();
    }
    expect(map.getLayer(EDGE_MOTION_LAYER)).toBeDefined();
    expect(map.getLayer(EDGE_MOTION_HALO_LAYER)).toBeDefined();
    const refreshesAfterRecovery = controller.inspect().styleRefreshes;
    map.emit("styledata");
    expect(controller.inspect().styleRefreshes).toBe(refreshesAfterRecovery);

    controller.destroy();
    expect(controller.inspect()).toMatchObject({
      activeCount: 0,
      framePending: false,
    });
    expect(map.getSource(EDGE_MOTION_SOURCE)).toBeUndefined();
    for (const layerId of EDGE_MOTION_LAYER_IDS) {
      expect(map.getLayer(layerId)).toBeUndefined();
    }
    expectCanonicalFilters(map, []);
    expect(map.listeners.get("styledata")?.size ?? 0).toBe(0);
  });
});
