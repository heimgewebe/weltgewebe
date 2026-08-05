import { describe, expect, it } from "vitest";
import type { Map as MapLibreMap } from "maplibre-gl";
import {
  EDGE_MOTION_DURATION_MS,
  EDGE_MOTION_HALO_LAYER,
  EDGE_MOTION_LAYER,
  EDGE_MOTION_MAX_ACTIVE,
  EDGE_MOTION_SOURCE,
  EdgeMotionController,
  resolveEdgeMotionInput,
  type EdgeMotionInput,
  type EdgeMotionScheduler,
} from "$lib/map/overlay/edgeMotion";
import type { MapEdge, MapEntityViewModel } from "$lib/map/types";
import {
  buildEdgeLayerSpecifications,
  EDGE_THREAD_LAYER_IDS,
} from "$lib/map/overlay/edges";

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

    expect(resolveEdgeMotionInput(edge, points)).toEqual({
      id: "edge-center",
      source: [10, 53.5],
      target: [10.2, 53.6],
      kind: "membership",
    });
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
    expect(halfway.geometry.coordinates[1]).toEqual([5, 10]);

    scheduler.advance(EDGE_MOTION_DURATION_MS / 2);
    expect(controller.inspect()).toMatchObject({
      activeCount: 0,
      framePending: false,
    });
    expect(motionSource(map).data.features).toEqual([]);
    expectCanonicalFilters(map, []);
  });

  it("retracts along the same geometry and suppresses the static edge until data removal", () => {
    const { map, scheduler, controller } = createHarness();
    controller.setVisibleEdgeIds(new Set([input.id]));
    controller.startRelease(input);

    scheduler.advance(EDGE_MOTION_DURATION_MS / 2);
    expect(motionSource(map).data.features[0].geometry.coordinates[1]).toEqual([
      5, 10,
    ]);

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

    map.removeLayer(EDGE_MOTION_LAYER);
    map.removeLayer(EDGE_MOTION_HALO_LAYER);
    map.removeSource(EDGE_MOTION_SOURCE);
    map.emit("styledata");
    expect(map.getSource(EDGE_MOTION_SOURCE)).toBeDefined();
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
    expect(map.getLayer(EDGE_MOTION_LAYER)).toBeUndefined();
    expectCanonicalFilters(map, []);
    expect(map.listeners.get("styledata")?.size ?? 0).toBe(0);
  });
});
