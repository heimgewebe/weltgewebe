import { afterEach, describe, expect, it, vi } from "vitest";
import type { Map as MapLibreMap } from "maplibre-gl";
import type {
  MapEntityNode,
  MapEntityWeave,
  MapEntityWebgemeindezentrum,
} from "$lib/map/types";
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

  toggle(value: string, force?: boolean) {
    const enabled = force ?? !this.values.has(value);
    if (enabled) this.values.add(value);
    else this.values.delete(value);
    return enabled;
  }
}

class FakeStyle {
  [key: string]: string | ((name: string, value: string) => void);

  setProperty(name: string, value: string) {
    this[name] = value;
  }
}

class FakeElement {
  classList = new FakeClassList();
  dataset: Record<string, string> = {};
  title = "";
  textContent = "";
  innerHTML = "";
  type = "";
  src = "";
  alt = "";
  draggable = false;
  children: FakeElement[] = [];
  attributes = new Map<string, string>();
  style = new FakeStyle();
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

  getAttribute(name: string) {
    return this.attributes.get(name) ?? null;
  }

  hasAttribute(name: string) {
    return this.attributes.has(name);
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

function makeWeave(overrides: Partial<MapEntityWeave> = {}): MapEntityWeave {
  return {
    zoneOrder: ["knotting", "conversation", "proposal", "vote"],
    themeSegments: [
      {
        id: "natur",
        label: "Natur",
        color: "#5f7a55",
        startDeg: 0,
        spanDeg: 360,
      },
    ],
    primaryThemeColor: "#5f7a55",
    coreDensity: 0.55,
    knottingThreadCount: 1,
    conversationThreadCount: 1,
    conversationOpacity: 0.8,
    proposalArcs: [],
    proposalCount: 0,
    proposalOverflowCount: 0,
    voteThreadCount: 0,
    totalActiveThreadCount: 2,
    ...overrides,
  };
}

function makeNode(
  id: string,
  overrides: Partial<MapEntityNode> = {},
): MapEntityNode {
  return {
    type: "node",
    id,
    title: `Node ${id}`,
    kind: "Werkstatt",
    tags: [],
    created_at: "2025-01-01T00:00:00Z",
    lat: 53.5,
    lon: 10,
    weave: makeWeave(),
    ...overrides,
  };
}

function makeCenter(
  id = "webgemeindezentrum-hammer-park",
): MapEntityWebgemeindezentrum {
  return {
    type: "webgemeindezentrum",
    id,
    title: "Webgemeindezentrum Hammer Park",
    lat: 53.5585,
    lon: 10.058,
    summary: "Hier kann die Ortsweberei tatsächlich zusammenkommen.",
    tags: ["Webgemeindezentrum", "Ortsweberei Hamm"],
    created_at: "2026-08-02T10:08:00.000Z",
    updated_at: "2026-08-02T10:08:00.000Z",
    location_state: "desired",
    location_state_label: "Gewünschter Treffort",
    faden_endpoint_id: "22222222-2222-5222-8222-222222222222",
    conversation_id: "33333333-3333-5333-8333-333333333333",
    location_label: "Hammer Park – gewünschter Treffpunkt auf der Grünfläche",
    meeting_note: "Hier kann die Ortsweberei tatsächlich zusammenkommen.",
    access_note: "Nutzung und Barrierefreiheit sind noch nicht bestätigt.",
    weave: makeWeave(),
    ortsweberei: {
      id: "ortsweberei-hamm",
      slug: "hamm",
      name: "Ortsweberei Hamm",
      gewebezelle_id: "hamm.weltgewebe.net",
    },
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

describe("NodesOverlay selection lifecycle", () => {
  it("applies a selected state as a round-halo hook without recreating markers", () => {
    const overlay = makeOverlay();
    overlay.update([makeNode("a"), makeNode("b")], true);
    const markerA = overlay.getActiveMarker("a");

    overlay.updateSelection("a");
    expect(markerA?.element.classList.contains("is-selected")).toBe(true);
    expect(markerA?.element.dataset.selected).toBe("true");
    expect(markerA?.element.getAttribute("aria-current")).toBe("true");
    expect(
      markerA?.element.children[0].classList.contains("marker-node__visual"),
    ).toBe(true);
    expect(
      markerA?.element.children[1].classList.contains("map-marker__halo"),
    ).toBe(true);

    overlay.updateSelection("b");
    expect(markerA?.element.classList.contains("is-selected")).toBe(false);
    expect(markerA?.element.dataset.selected).toBeUndefined();
    expect(markerA?.element.hasAttribute("aria-current")).toBe(false);
    expect(overlay.getActiveMarker("a")?.marker).toBe(markerA?.marker);
    expect(overlay.getActiveMarker("b")?.element.dataset.selected).toBe("true");
  });

  it("restores selection when a filtered marker is recreated", () => {
    const overlay = makeOverlay();
    overlay.updateSelection("a");
    overlay.update([makeNode("a")], true);
    expect(overlay.getActiveMarker("a")?.element.dataset.selected).toBe("true");

    overlay.update([], true);
    overlay.update([makeNode("a")], true);
    expect(overlay.getActiveMarker("a")?.element.dataset.selected).toBe("true");
  });
});

describe("NodesOverlay woven node marker", () => {
  it("renders the core, conversation ring and separate proposal-bound vote wreaths", () => {
    const overlay = makeOverlay();
    overlay.update(
      [
        makeNode("woven", {
          weave: makeWeave({
            proposalCount: 2,
            voteThreadCount: 3,
            proposalArcs: [
              {
                subjectId: "proposal-a",
                proposalThreadCount: 1,
                conversationThreadCount: 1,
                voteThreadCount: 2,
                bundledSubjectCount: 1,
                latestActivityAtMs: 10,
                opacity: 0.9,
                color: "#5f7a55",
                startDeg: 20,
                spanDeg: 120,
              },
              {
                subjectId: "proposal-b",
                proposalThreadCount: 1,
                conversationThreadCount: 0,
                voteThreadCount: 1,
                bundledSubjectCount: 1,
                latestActivityAtMs: 9,
                opacity: 0.8,
                color: "#5f7a55",
                startDeg: 190,
                spanDeg: 120,
              },
            ],
          }),
        }),
      ],
      true,
    );

    const marker = overlay.getActiveMarker("woven");
    const root = marker?.element.children[0].children[0] as
      | HTMLElement
      | undefined;
    expect(root?.classList.contains("woven-node")).toBe(true);
    expect(root?.dataset.zoneOrder).toBe("knotting,conversation,proposal,vote");
    expect(root?.innerHTML).toContain('data-zone="knotting"');
    expect(root?.innerHTML).toContain('data-zone="conversation"');
    expect(root?.innerHTML.match(/data-zone="proposal"/g)).toHaveLength(2);
    expect(root?.innerHTML.match(/data-zone="vote"/g)).toHaveLength(2);
  });

  it("updates the woven body without recreating the stable map marker", () => {
    const overlay = makeOverlay();
    overlay.update([makeNode("a")], true);
    const before = overlay.getActiveMarker("a");
    const rootBefore = before?.element.children[0].children[0] as
      | HTMLElement
      | undefined;

    overlay.update(
      [
        makeNode("a", {
          weave: makeWeave({
            proposalCount: 1,
            proposalArcs: [
              {
                subjectId: "proposal-a",
                proposalThreadCount: 1,
                conversationThreadCount: 0,
                voteThreadCount: 0,
                bundledSubjectCount: 1,
                latestActivityAtMs: 10,
                opacity: 1,
                color: "#5f7a55",
                startDeg: 55,
                spanDeg: 250,
              },
            ],
          }),
        }),
      ],
      true,
    );

    const after = overlay.getActiveMarker("a");
    expect(after?.marker).toBe(before?.marker);
    expect(after?.element.children[0].children[0]).toBe(rootBefore);
    expect(rootBefore?.dataset.proposalCount).toBe("1");
    expect(rootBefore?.innerHTML.match(/data-zone="proposal"/g)).toHaveLength(
      1,
    );
  });
});

describe("NodesOverlay Webgemeindezentrum marker", () => {
  it("renders a distinct desired-location marker without pretending confirmation", () => {
    const overlay = makeOverlay();
    overlay.update([makeCenter()], true);

    const element = overlay.getActiveMarker(
      "webgemeindezentrum-hammer-park",
    )?.element;
    expect(element?.classList.contains("marker-webgemeindezentrum")).toBe(true);
    expect(element?.dataset.markerCategory).toBe("webgemeindezentrum");
    expect(element?.dataset.locationState).toBe("desired");
    expect(element?.dataset.testid).toBe(
      "marker-webgemeindezentrum-webgemeindezentrum-hammer-park",
    );
    expect(element?.children[0].children[0].textContent).toBe("");
    expect(
      element?.children[0].children[0].classList.contains(
        "marker-webgemeindezentrum__icon",
      ),
    ).toBe(true);
    expect(
      (element?.children[0] as HTMLElement | undefined)?.style.borderStyle,
    ).toBe("dashed");
  });

  it("updates desired to confirmed styling without recreating the stable marker", () => {
    const overlay = makeOverlay();
    overlay.update([makeCenter()], true);
    const before = overlay.getActiveMarker("webgemeindezentrum-hammer-park");

    overlay.update(
      [
        {
          ...makeCenter(),
          location_state: "confirmed",
          location_state_label: "Bestätigter Treffort",
        },
      ],
      true,
    );

    const after = overlay.getActiveMarker("webgemeindezentrum-hammer-park");
    expect(after?.marker).toBe(before?.marker);
    expect(after?.element.dataset.locationState).toBe("confirmed");
    expect(
      (after?.element.children[0] as HTMLElement | undefined)?.style
        .borderStyle,
    ).toBe("");
  });

  it("recreates a marker when a stable id changes semantic category", () => {
    const overlay = makeOverlay();
    overlay.update([makeNode("shared")], true);
    const first = overlay.getActiveMarker("shared")
      ?.marker as unknown as FakeMarker;

    overlay.update([makeCenter("shared")], true);

    expect(first.removed).toBe(true);
    expect(
      overlay
        .getActiveMarker("shared")
        ?.element.classList.contains("marker-webgemeindezentrum"),
    ).toBe(true);
  });
});
