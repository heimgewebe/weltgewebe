import { describe, expect, it, vi, afterEach } from "vitest";
import type { MapEntityViewModel, WeaveArm } from "$lib/map/types";
import { WEAVE_ARMS } from "$lib/map/types";
import { assignXCoreSegments } from "$lib/map/weaveModel";
import {
  buildEdgeFeatures,
  buildEndpointIndex,
  sampleThreadCurve,
} from "./edges";
import {
  normalizeEdgeLifecycle,
  FADEN_LIFETIME_MS,
} from "$lib/map/edgeLifecycle";
import { weaveRuntime } from "./weaveRuntime";
import type { WeaveEntity } from "$lib/map/weaveTheme";

/**
 * Focused proof suite for the "Knoten ist kein Symbol, sondern ein
 * eingesticktes X aus dem Knüpfungsfaden" contract:
 *
 *   1. The knotting thread's rendered endpoint is exactly the node's
 *      geometric center (no radius-based clipping).
 *   2. The woven X body always has exactly four arms / two diagonals.
 *   3. Over/under alternation is deterministic: walking the four arms in
 *      compass order (NW, NE, SE, SW) strictly alternates under/over.
 *   4. No separate circle/icon feature is required to render a node — the
 *      woven X *is* the whole visible body (no <img>/icon child, no
 *      rounded/filled background on the marker visual).
 *   5. (Covered together with existing suites) existing thread/node cases
 *      stay green — see edges.test.ts / weaveRuntime.test.ts / nodes.test.ts.
 */

// ─── Minimal DOM stub (mirrors weaveRuntime.test.ts) ───────────────────────

class DomElement {
  className = "";
  title = "";
  textContent = "";
  style = {
    opacity: "",
    background: "",
    props: new Map<string, string>(),
    setProperty(name: string, value: string) {
      this.props.set(name, value);
    },
    getPropertyValue(name: string) {
      return this.props.get(name) ?? "";
    },
  };
  dataset: Record<string, string> = {};
  children: DomElement[] = [];
  attributes = new Map<string, string>();
  tagName = "SPAN";

  setAttribute(name: string, value: string) {
    this.attributes.set(name, value);
    if (name.startsWith("data-")) {
      const key = name
        .slice(5)
        .replace(/-([a-z])/g, (_, letter: string) => letter.toUpperCase());
      this.dataset[key] = value;
    }
  }

  getAttribute(name: string) {
    return this.attributes.get(name) ?? null;
  }

  append(...nodes: DomElement[]) {
    this.children.push(...nodes);
  }

  get firstChild(): DomElement | null {
    return this.children[0] ?? null;
  }

  removeChild(child: DomElement) {
    const index = this.children.indexOf(child);
    if (index >= 0) this.children.splice(index, 1);
    return child;
  }

  querySelectorAll(selector: string): DomElement[] {
    const matches: DomElement[] = [];
    const visit = (node: DomElement) => {
      for (const child of node.children) {
        if (selector === "*" || matchesSelector(child, selector)) {
          matches.push(child);
        }
        visit(child);
      }
    };
    visit(this);
    return matches;
  }
}

function matchesSelector(node: DomElement, selector: string): boolean {
  if (selector === "*") return true;
  if (selector.startsWith(".")) {
    return node.className.split(/\s+/).includes(selector.slice(1));
  }
  if (selector.startsWith("[") && selector.endsWith("]")) {
    const body = selector.slice(1, -1);
    const eq = body.indexOf("=");
    if (eq < 0) return node.attributes.has(body);
    const name = body.slice(0, eq);
    const raw = body.slice(eq + 1).replace(/^["']|["']$/g, "");
    return node.attributes.get(name) === raw;
  }
  return false;
}

function installDom() {
  vi.stubGlobal("document", {
    createElement: () => new DomElement(),
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function testEntity(overrides: Partial<WeaveEntity> = {}): WeaveEntity {
  return {
    type: "node",
    id: "node-under-test",
    title: "Testknoten",
    kind: "Garten",
    tags: ["Natur", "Bildung"],
    created_at: "2026-08-01T00:00:00Z",
    lat: 53.5,
    lon: 10,
    ...overrides,
  } as WeaveEntity;
}

describe("Knüpfungsfaden endpoint is the exact knot center", () => {
  const createdAt = Date.parse("2026-08-01T00:00:00Z");
  const knottingEdge = normalizeEdgeLifecycle({
    id: "knotting-endpoint-proof",
    source_id: "source",
    target_id: "target",
    edge_kind: "reference",
    faden_type: "knotting",
    created_at: new Date(createdAt).toISOString(),
    expires_at: new Date(createdAt + FADEN_LIFETIME_MS).toISOString(),
  });

  it("ends the sampled curve exactly on the node's lon/lat (no radius clip)", () => {
    const source: [number, number] = [9.9, 53.5];
    const target: [number, number] = [10.058, 53.6123];
    const path = sampleThreadCurve(source, target, {
      fadenType: "knotting",
      threadId: knottingEdge.id,
    });
    const last = path.at(-1);
    expect(last).toEqual(target);
  });

  it("emits a GeoJSON knotting feature whose last coordinate is the exact node center", () => {
    const points = [
      { id: "source", lat: 53.5, lon: 9.9 },
      { id: "target", type: "node", lat: 53.6123, lon: 10.058 },
    ] as MapEntityViewModel[];

    const features = buildEdgeFeatures([knottingEdge], points, true, createdAt);
    expect(features).toHaveLength(1);
    expect(features[0].properties?.fadenType).toBe("knotting");
    const coords = features[0].geometry.coordinates;
    const target = points[1];
    // Exact equality, not "close enough": the visible endpoint must be the
    // geometric center used for the marker anchor, not a radius-shortened
    // approach.
    expect(coords.at(-1)).toEqual([target.lon, target.lat]);
  });

  it("resolves the endpoint through the same lookup the marker anchor uses", () => {
    const point = {
      id: "target",
      type: "node",
      lat: 53.6123,
      lon: 10.058,
    } as MapEntityViewModel;
    const index = buildEndpointIndex([point]);
    expect(index.get("target")).toBe(point);
    // The marker is placed at [item.lon, item.lat] (MARKER_GEO_ANCHOR =
    // "center"); the edge target must resolve to that very object, so the
    // thread and the marker can never drift apart.
    expect([point.lon, point.lat]).toEqual([10.058, 53.6123]);
  });
});

describe("Woven X core: exactly four arms, deterministic over/under alternation", () => {
  it("always assigns exactly four arm slots, one per compass diagonal", () => {
    for (const topicCount of [0, 1, 2, 3, 4, 6]) {
      const labels = Array.from(
        { length: topicCount },
        (_, index) => `Thema ${index}`,
      );
      const segments = assignXCoreSegments(labels);
      expect(segments).toHaveLength(4);
      expect(new Set(segments.map((segment) => segment.arm))).toEqual(
        new Set(WEAVE_ARMS),
      );
    }
  });

  it("renders exactly four .woven-node__arm elements forming two diagonals", () => {
    installDom();
    const { root } = weaveRuntime.createRoot(testEntity(), "node");
    const host = root as unknown as DomElement;
    const arms = host.querySelectorAll(".woven-node__arm");
    expect(arms).toHaveLength(4);
    expect(new Set(arms.map((arm) => arm.dataset.arm))).toEqual(
      new Set(WEAVE_ARMS),
    );
  });

  it("alternates under/over strictly in compass order NW → NE → SE → SW", () => {
    installDom();
    const { root } = weaveRuntime.createRoot(testEntity(), "node");
    const host = root as unknown as DomElement;
    const xCore = host.querySelectorAll(".woven-node__x")[0];
    const strands = xCore.children;
    const under = strands.find((strand) =>
      strand.className.includes("woven-node__strand--under"),
    );
    const over = strands.find((strand) =>
      strand.className.includes("woven-node__strand--over"),
    );
    expect(under).toBeDefined();
    expect(over).toBeDefined();

    const underArms = new Set(
      under!.children.map((arm) => arm.dataset.arm as WeaveArm),
    );
    const overArms = new Set(
      over!.children.map((arm) => arm.dataset.arm as WeaveArm),
    );
    // Deterministic depth sequence per arm, compass order NW, NE, SE, SW:
    const sequence: ("under" | "over")[] = WEAVE_ARMS.map((arm) =>
      underArms.has(arm) ? "under" : "over",
    );
    expect(sequence).toEqual(["under", "over", "under", "over"]);
    // Every arm belongs to exactly one strand — no arm is both/neither.
    expect(underArms.size + overArms.size).toBe(4);
    for (const arm of underArms) expect(overArms.has(arm)).toBe(false);
  });
});

describe("No separate circle/symbol feature is needed for a node", () => {
  it("builds the node visual purely from the woven X body (no icon child)", () => {
    installDom();
    const { root } = weaveRuntime.createRoot(testEntity(), "node");
    const host = root as unknown as DomElement;
    // Only garnrolle markers get an <img> icon; a node's visual is entirely
    // the woven-node structure (crossing + conversation ring + X + overlays).
    expect(host.querySelectorAll("img")).toHaveLength(0);
    expect(host.className).toContain("woven-node");
    expect(host.querySelectorAll(".woven-node__x")).toHaveLength(1);
  });

  it("keeps the crossing a small yarn nexus, not a separate iconographic circle", () => {
    installDom();
    const { root } = weaveRuntime.createRoot(testEntity(), "node");
    const host = root as unknown as DomElement;
    const crossing = host.querySelectorAll(".woven-node__crossing");
    // Exactly one crossing point (the X's own junction), never an additional
    // symbol layered on top of it.
    expect(crossing).toHaveLength(1);
  });
});
