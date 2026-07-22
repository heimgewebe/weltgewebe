import { afterEach, describe, expect, it, vi } from "vitest";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { MapEntityViewModel } from "$lib/map/types";
import {
  NodesOverlay,
  diffSearchMatchIds,
  type MarkerConstructor,
} from "./nodes";

class FakeClassList {
  private values = new Set<string>();

  setFromClassName(className: string) {
    this.values = new Set(className.split(/\s+/).filter(Boolean));
  }

  contains(value: string) {
    return this.values.has(value);
  }

  add(value: string) {
    this.values.add(value);
  }

  remove(value: string) {
    this.values.delete(value);
  }
}

class FakeElement {
  classList = new FakeClassList();
  dataset: Record<string, string> = {};
  title = "";
  type = "";
  src = "";
  alt = "";
  draggable = false;
  children: FakeElement[] = [];
  attributes = new Map<string, string>();
  private _className = "";

  set className(value: string) {
    this._className = value;
    this.classList.setFromClassName(value);
  }

  get className() {
    return this._className;
  }

  setAttribute(name: string, value: string) {
    this.attributes.set(name, value);
  }

  append(child: FakeElement) {
    this.children.push(child);
  }
}

class FakeMarker {
  private lng = 0;
  private lat = 0;
  removed = false;

  constructor(public options: { element?: FakeElement } = {}) {}

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

  remove() {
    this.removed = true;
  }
}

function makeNode(id: string): MapEntityViewModel {
  return {
    type: "node",
    id,
    title: `Node ${id}`,
    kind: "Werkstatt",
    tags: [],
    created_at: "2025-01-01T00:00:00Z",
    lat: 53.5,
    lon: 10,
  };
}

function makeOverlay() {
  vi.stubGlobal("document", {
    createElement: () => new FakeElement(),
  });
  return new NodesOverlay(
    {} as MapLibreMap,
    FakeMarker as unknown as MarkerConstructor,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("diffSearchMatchIds", () => {
  it("returns only the changed search-match ids", () => {
    expect(
      diffSearchMatchIds(new Set(["keep", "remove"]), new Set(["keep", "add"])),
    ).toEqual({
      added: ["add"],
      removed: ["remove"],
    });
  });

  it("returns an empty delta for unchanged matches", () => {
    expect(
      diffSearchMatchIds(new Set(["a", "b"]), new Set(["a", "b"])),
    ).toEqual({
      added: [],
      removed: [],
    });
  });
});

describe("NodesOverlay search-highlight lifecycle", () => {
  it("applies stored search state to a marker created later", () => {
    const overlay = makeOverlay();
    overlay.updateSearchMatches(new Set(["a"]));
    overlay.update([makeNode("a")], true);

    expect(overlay.getActiveMarker("a")?.element.dataset.searchMatch).toBe(
      "true",
    );
  });

  it("updates A to B and then clears the highlight without a full marker update", () => {
    const overlay = makeOverlay();
    overlay.update([makeNode("a"), makeNode("b")], true);

    overlay.updateSearchMatches(new Set(["a"]));
    expect(overlay.getActiveMarker("a")?.element.dataset.searchMatch).toBe(
      "true",
    );
    expect(
      overlay.getActiveMarker("b")?.element.dataset.searchMatch,
    ).toBeUndefined();

    overlay.updateSearchMatches(new Set(["b"]));
    expect(
      overlay.getActiveMarker("a")?.element.dataset.searchMatch,
    ).toBeUndefined();
    expect(overlay.getActiveMarker("b")?.element.dataset.searchMatch).toBe(
      "true",
    );

    overlay.updateSearchMatches(new Set());
    expect(
      overlay.getActiveMarker("b")?.element.dataset.searchMatch,
    ).toBeUndefined();
  });

  it("restores the highlight after marker removal and recreation", () => {
    const overlay = makeOverlay();
    overlay.updateSearchMatches(new Set(["a"]));
    overlay.update([makeNode("a")], true);
    overlay.update([], true);
    expect(overlay.getActiveMarker("a")).toBeUndefined();

    overlay.update([makeNode("a")], true);
    expect(overlay.getActiveMarker("a")?.element.dataset.searchMatch).toBe(
      "true",
    );
  });

  it("preserves search state across showNodes false to true", () => {
    const overlay = makeOverlay();
    overlay.updateSearchMatches(new Set(["a"]));
    overlay.update([makeNode("a")], true);
    overlay.update([makeNode("a")], false);
    expect(overlay.getActiveMarker("a")).toBeUndefined();

    overlay.update([makeNode("a")], true);
    expect(overlay.getActiveMarker("a")?.element.dataset.searchMatch).toBe(
      "true",
    );
  });
});
