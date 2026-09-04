import { afterEach, describe, expect, it, vi } from "vitest";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { MapEdge, MapEntityViewModel } from "$lib/map/types";
import { NodesOverlay, type MarkerConstructor } from "./nodes";
import { deriveWeaveEdges } from "$lib/stores/mapView";
import { weaveRuntime } from "./weaveRuntime";

class FakeClassList {
  private values = new Set<string>();

  add(value: string) {
    this.values.add(value);
  }

  remove(value: string) {
    this.values.delete(value);
  }

  toggle(value: string, force?: boolean) {
    const enabled = force ?? !this.values.has(value);
    if (enabled) this.values.add(value);
    else this.values.delete(value);
    return enabled;
  }
}

class FakeElement {
  classList = new FakeClassList();
  dataset: Record<string, string> = {};
  title = "";
  type = "";
  className = "";
  src = "";
  alt = "";
  draggable = false;
  children: FakeElement[] = [];
  private attributes = new Map<string, string>();

  setAttribute(name: string, value: string) {
    this.attributes.set(name, value);
  }

  getAttribute(name: string) {
    return this.attributes.get(name) ?? null;
  }

  removeAttribute(name: string) {
    this.attributes.delete(name);
  }

  append(...children: FakeElement[]) {
    this.children.push(...children);
  }
}

class FakeMarker {
  private lng = 0;
  private lat = 0;

  constructor(
    public options: { element?: FakeElement; anchor?: string } = {},
  ) {}

  setLngLat([lng, lat]: [number, number]) {
    this.lng = lng;
    this.lat = lat;
    return this;
  }

  addTo() {
    return this;
  }

  getLngLat() {
    return { lng: this.lng, lat: this.lat };
  }

  remove() {}
}

function relation(id: string, sourceId: string, targetId: string): MapEdge {
  return {
    id,
    source_id: sourceId,
    target_id: targetId,
    edge_kind: "reference",
  } as MapEdge;
}

function account(id: string, lon: number, lat: number): MapEntityViewModel {
  return {
    type: "garnrolle",
    id,
    title: `Garnrolle ${id}`,
    lon,
    lat,
    created_at: "2026-09-04T00:00:00Z",
  };
}

function installFakeDocument() {
  vi.stubGlobal("document", {
    createElement: () => new FakeElement(),
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("NodesOverlay visibility and zoom ownership", () => {
  it("keeps relations for visible weave targets when source markers are filtered out", () => {
    const centerEndpoint = "22222222-2222-5222-8222-222222222222";
    const points = [
      { type: "node", id: "source" },
      {
        type: "webgemeindezentrum",
        id: "center",
        faden_endpoint_id: centerEndpoint,
      },
    ] as MapEntityViewModel[];
    const edges = [
      relation("visible-source", "source", centerEndpoint),
      relation("filtered-source", "missing", centerEndpoint),
      relation("hidden-target", "source", "missing"),
    ];
    const visibleEdgeIds = deriveWeaveEdges(edges, points).map(
      (edge) => edge.id,
    );

    expect(visibleEdgeIds).toEqual(["visible-source", "filtered-source"]);
  });

  it("owns and releases its MapLibre zoom listener", () => {
    const on = vi.fn();
    const off = vi.fn();
    const map = {
      getZoom: () => 12,
      on,
      off,
    } as unknown as MapLibreMap;
    const MarkerClass = class {} as unknown as MarkerConstructor;

    const overlay = new NodesOverlay(map, MarkerClass, weaveRuntime);
    expect(on).toHaveBeenCalledWith("zoom", expect.any(Function));

    overlay.destroy();
    expect(off).toHaveBeenCalledWith("zoom", expect.any(Function));
  });

  it("bounds moveend work to spatial candidates for a 10k point dataset", () => {
    installFakeDocument();
    const contains = vi.fn(
      ([lon, lat]: [number, number]) =>
        lon >= 9.9 && lon <= 10.1 && lat >= 53.4 && lat <= 53.6,
    );
    const bounds = {
      getWest: () => 9.9,
      getEast: () => 10.1,
      getSouth: () => 53.4,
      getNorth: () => 53.6,
      contains,
    };
    const on = vi.fn();
    const off = vi.fn();
    const map = {
      getBounds: () => bounds,
      on,
      off,
    } as unknown as MapLibreMap;
    const overlay = new NodesOverlay(
      map,
      FakeMarker as unknown as MarkerConstructor,
      weaveRuntime,
    );
    const points = Array.from({ length: 10_000 }, (_, index) =>
      account(
        `grid-${index}`,
        -170 + (index % 100) * 3.4,
        -80 + Math.floor(index / 100) * 1.6,
      ),
    );
    points.push(
      account("inside", 10, 53.5),
      account("search-pinned", 40, 0),
      account("selected-pinned", 50, 0),
    );

    overlay.update(points, true);
    expect(overlay.getActiveMarker("inside")).toBeDefined();
    expect(overlay.getActiveMarker("search-pinned")).toBeUndefined();
    expect(contains.mock.calls.length).toBeLessThan(100);

    const moveEnd = on.mock.calls.find((call) => call[0] === "moveend")?.[1] as
      | (() => void)
      | undefined;
    expect(moveEnd).toBeTypeOf("function");
    contains.mockClear();
    moveEnd?.();
    expect(contains.mock.calls.length).toBeLessThan(100);

    overlay.updateSearchMatches(new Set(["search-pinned"]));
    expect(
      overlay.getActiveMarker("search-pinned")?.element.dataset.searchMatch,
    ).toBe("true");

    overlay.updateSelection("selected-pinned");
    expect(
      overlay.getActiveMarker("selected-pinned")?.element.dataset.selected,
    ).toBe("true");

    overlay.destroy();
  });

  it("queries both sides of an antimeridian-crossing viewport", () => {
    installFakeDocument();
    const contains = vi.fn(
      ([lon, lat]: [number, number]) =>
        (lon >= 179 || lon <= -179) && lat >= -10 && lat <= 10,
    );
    const bounds = {
      getWest: () => 179,
      getEast: () => -179,
      getSouth: () => -10,
      getNorth: () => 10,
      contains,
    };
    const map = {
      getBounds: () => bounds,
      on: vi.fn(),
      off: vi.fn(),
    } as unknown as MapLibreMap;
    const overlay = new NodesOverlay(
      map,
      FakeMarker as unknown as MarkerConstructor,
      weaveRuntime,
    );
    const points = Array.from({ length: 101 }, (_, index) =>
      account(`middle-${index}`, 0, 0),
    );
    points.push(
      account("east-edge", 179.5, 0),
      account("west-edge", -179.5, 0),
    );

    overlay.update(points, true);

    expect(overlay.getActiveMarker("middle-0")).toBeUndefined();
    expect(overlay.getActiveMarker("east-edge")).toBeDefined();
    expect(overlay.getActiveMarker("west-edge")).toBeDefined();
    overlay.destroy();
  });
});
