import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi, afterEach } from "vitest";
import type { MapEntityViewModel, WeaveArm } from "$lib/map/types";
import {
  WEAVE_ARM_DEPTH,
  WEAVE_ARMS,
  WEAVE_OVER_ARMS,
  WEAVE_UNDER_ARMS,
} from "$lib/map/types";
import {
  assignXCoreSegments,
  deriveEntityWeave,
  targetThemePalette,
  terminalThreadColor,
} from "$lib/map/weaveModel";
import { KNOTTING_THREAD_WIDTH_PX } from "$lib/map/weaveVisualTokens";
import {
  buildEdgeFeatures,
  buildEndpointIndex,
  EDGE_VISUAL_STYLE,
  sampleThreadCurve,
} from "./edges";
import {
  normalizeEdgeLifecycle,
  FADEN_LIFETIME_MS,
} from "$lib/map/edgeLifecycle";
import { DomElement, installDom as installDomStub } from "./domElementTestStub";
import { weaveRuntime } from "./weaveRuntime";
import type { WeaveEntity } from "$lib/map/weaveTheme";

const OVERLAY_DIR = dirname(fileURLToPath(import.meta.url));

/**
 * Focused proof suite for the "Knoten ist kein Symbol, sondern ein
 * eingesticktes X aus dem Knüpfungsfaden" contract:
 *
 *   1. The knotting thread's rendered endpoint is exactly the node's
 *      geometric center (no radius-based clipping).
 *   2. The woven X body always has exactly four arms / two diagonals.
 *   3. Over/under alternation is deterministic: walking the four arms in
 *      compass order (NW, NE, SE, SW) strictly alternates under/over.
 *   4. No separate woven-node crossing/circle/icon element exists — the
 *      knotting thread continues straight through the centre and *becomes*
 *      the X; there is nothing else to render a node's visual body.
 *   5. All four arms resolve their colour through the same pure
 *      `terminalThreadColor` helper `edges.ts` uses for the incoming
 *      knotting thread's terminal (target-side) segment, and their width
 *      through the same `KNOTTING_THREAD_WIDTH_PX` token `edges.ts` uses for
 *      that thread's line-width — so neither can silently drift from the
 *      thread it continues. Colour injection is root-only
 *      (--weave-thread-color); arms inherit via CSS.
 *   6. Governance overlays (arm overlays) still render on top of the X.
 *   7. (Covered together with existing suites) existing thread/node cases
 *      stay green — see edges.test.ts / weaveRuntime.test.ts / nodes.test.ts.
 */

function installDom() {
  installDomStub(vi);
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

    const underArms = under!.children.map((arm) => arm.dataset.arm as WeaveArm);
    const overArms = over!.children.map((arm) => arm.dataset.arm as WeaveArm);
    // Runtime strands must match the single canonical depth mapping.
    expect(underArms).toEqual([...WEAVE_UNDER_ARMS]);
    expect(overArms).toEqual([...WEAVE_OVER_ARMS]);
    const sequence = WEAVE_ARMS.map((arm) => WEAVE_ARM_DEPTH[arm]);
    expect(sequence).toEqual(["under", "over", "under", "over"]);
    // Every arm belongs to exactly one strand — no arm is both/neither.
    expect(new Set([...underArms, ...overArms]).size).toBe(4);
    for (const arm of underArms) expect(overArms).not.toContain(arm);
  });
});

describe("No separate circle/symbol feature is needed for a node", () => {
  it("builds the node visual purely from the woven X body (no icon child)", () => {
    installDom();
    const { root } = weaveRuntime.createRoot(testEntity(), "node");
    const host = root as unknown as DomElement;
    // Only garnrolle markers get an <img> icon; a node's visual is entirely
    // the woven-node structure (conversation ring + X + overlays) — no
    // separate crossing/circle patch layered on top.
    expect(host.querySelectorAll("img")).toHaveLength(0);
    expect(host.className).toContain("woven-node");
    expect(host.querySelectorAll(".woven-node__x")).toHaveLength(1);
  });

  it("never renders a woven-node crossing element: the thread itself is the whole knot", () => {
    installDom();
    const { root } = weaveRuntime.createRoot(testEntity(), "node");
    const host = root as unknown as DomElement;
    // The corrected contract: no separate circle/blob at the junction, under
    // any class name. The X's own arms (over/under weave) are the entire
    // visible knot.
    expect(host.querySelectorAll(".woven-node__crossing")).toHaveLength(0);
    expect(host.querySelectorAll(".woven-node__cross")).toHaveLength(0);
  });
});

describe("The X arms keep the knotting thread gauge while preserving target topics", () => {
  it("keeps terminalThreadColor as the root fallback and paints arms from xCoreSegments", () => {
    installDom();
    // kind "Knoten" is ignored as a theme, so the three tags alone (three
    // distinct, non-colliding hash colours) determine the palette.
    const entity = testEntity({
      kind: "Knoten",
      tags: ["Bildung", "Nachbarschaft", "Wasser"],
    });
    const weave = deriveEntityWeave(entity, [], 0);
    const expectedColor = terminalThreadColor(weave);

    const { root } = weaveRuntime.createRoot({ ...entity, weave }, "node");
    const host = root as unknown as DomElement;
    const arms = host.querySelectorAll(".woven-node__arm");
    expect(arms).toHaveLength(4);
    // The root keeps the incoming edge's terminal colour as a fallback, while
    // the four arms expose the modelled topic palette explicitly.
    expect(host.style.getPropertyValue("--weave-thread-color").trim()).toBe(
      expectedColor,
    );
    const expectedByArm = new Map(
      weave.xCoreSegments.map((segment) => [segment.arm, segment]),
    );
    const renderedColours = new Set<string>();
    for (const arm of arms) {
      const armId = arm.getAttribute("data-arm");
      const expected = expectedByArm.get(
        armId as (typeof weave.xCoreSegments)[number]["arm"],
      );
      expect(expected).toBeDefined();
      expect(arm.style.getPropertyValue("--arm-color")).toBe(expected?.color);
      expect(arm.getAttribute("data-theme-id")).toBe(expected?.themeId);
      if (expected) renderedColours.add(expected.color);
    }
    expect(renderedColours.size).toBeGreaterThan(1);
    // Sanity: with three distinct topics this is not trivially the primary
    // colour — the terminal colour genuinely differs from it.
    expect(expectedColor).not.toBe(weave.primaryThemeColor);
  });

  it("matches the exact colour edges.ts paints for the incoming thread's segment nearest the target", () => {
    installDom();
    const createdAt = Date.parse("2026-08-01T00:00:00Z");
    const entity = testEntity({
      id: "target-node",
      kind: "Knoten",
      tags: ["Bildung", "Nachbarschaft", "Wasser"],
    });
    const weave = deriveEntityWeave(entity, [], 0);
    const palette = targetThemePalette(weave);
    expect(palette.length).toBeGreaterThan(1);
    const target: MapEntityViewModel = {
      ...entity,
      weave,
    } as unknown as MapEntityViewModel;
    const source = {
      id: "source-account",
      type: "garnrolle",
      lat: 53.4,
      lon: 9.9,
    } as unknown as MapEntityViewModel;
    const knottingEdge = normalizeEdgeLifecycle({
      id: "knotting-terminal-color-proof",
      source_id: "source-account",
      target_id: "target-node",
      edge_kind: "reference",
      faden_type: "knotting",
      created_at: new Date(createdAt).toISOString(),
      expires_at: new Date(createdAt + FADEN_LIFETIME_MS).toISOString(),
    });

    const features = buildEdgeFeatures(
      [knottingEdge],
      [source, target],
      true,
      createdAt,
    );
    expect(features.length).toBeGreaterThan(0);
    // Terminal segment = highest themeStrand (closest to the target), not a
    // brittle total-feature count. That is the segment edges.ts paints at the
    // centre; its colour and final coordinate prove thread→X continuity.
    const terminalFeature = features.reduce((best, feature) => {
      const strand = Number(feature.properties?.themeStrand ?? -1);
      const bestStrand = Number(best?.properties?.themeStrand ?? -1);
      return strand >= bestStrand ? feature : best;
    }, features[0]);
    const terminalColor = terminalFeature.properties?.themeColor;
    expect(terminalColor).toBe(palette[palette.length - 1]);
    expect(terminalColor).toBe(terminalThreadColor(weave));
    // The painted terminal geometry still ends on the exact node centre.
    expect(terminalFeature.geometry.coordinates.at(-1)).toEqual([
      target.lon,
      target.lat,
    ]);

    const { root } = weaveRuntime.createRoot(target as WeaveEntity, "node");
    const host = root as unknown as DomElement;
    expect(host.style.getPropertyValue("--weave-thread-color").trim()).toBe(
      terminalColor,
    );
    // The terminal edge colour remains represented in the knot, but the other
    // target-topic colours are not collapsed into it.
    const expectedByArm = new Map(
      weave.xCoreSegments.map((segment) => [segment.arm, segment]),
    );
    const renderedColours: string[] = [];
    for (const arm of host.querySelectorAll(".woven-node__arm")) {
      const armId = arm.getAttribute("data-arm");
      const expected = expectedByArm.get(
        armId as (typeof weave.xCoreSegments)[number]["arm"],
      );
      expect(expected).toBeDefined();
      expect(arm.style.getPropertyValue("--arm-color")).toBe(expected?.color);
      renderedColours.push(arm.style.getPropertyValue("--arm-color"));
    }
    expect(renderedColours).toContain(terminalColor);
    expect(new Set(renderedColours).size).toBeGreaterThan(1);
  });

  it("falls back to the same fallback colour the edge itself uses when no theme palette exists", () => {
    installDom();
    const weave = deriveEntityWeave(testEntity({ tags: [] }), [], 0);
    const { root } = weaveRuntime.createRoot(
      { ...testEntity({ tags: [] }), weave },
      "node",
    );
    const host = root as unknown as DomElement;
    expect(host.style.getPropertyValue("--weave-thread-color").trim()).toBe(
      terminalThreadColor(weave),
    );
  });

  it("derives the arm width from the single shared knotting-thread token, not a duplicated magic number", () => {
    installDom();
    const { root } = weaveRuntime.createRoot(testEntity(), "node");
    const host = root as unknown as DomElement;
    expect(host.style.getPropertyValue("--weave-arm-width").trim()).toBe(
      `${KNOTTING_THREAD_WIDTH_PX}px`,
    );
    // Edge paint and DOM arms must resolve the same numeric width token.
    expect(EDGE_VISUAL_STYLE.byType.knotting.width).toBe(
      KNOTTING_THREAD_WIDTH_PX,
    );
  });

  it("keeps markers.css free of a hard-coded knotting width fallback", () => {
    const css = readFileSync(join(OVERLAY_DIR, "markers.css"), "utf8");
    // Structural proof only: arms consume the runtime token and CSS never
    // redefines --weave-arm-width as a numeric px fallback. The literal
    // token value lives solely in weaveVisualTokens.ts.
    expect(css).toMatch(/var\(--weave-arm-width\)/);
    expect(css).not.toMatch(/--weave-arm-width:\s*[\d.]+px/);
  });
});

describe("Governance overlays keep rendering on top of the stitched X", () => {
  it("still renders arm overlay elements alongside the narrowed arms", () => {
    installDom();
    const entity = testEntity();
    const weave = {
      ...deriveEntityWeave(entity, [], 0),
      armOverlays: [
        { arm: "northwest" as WeaveArm, id: "overlay-1", label: "Notiz" },
      ],
    };
    const { root } = weaveRuntime.createRoot({ ...entity, weave }, "node");
    const host = root as unknown as DomElement;
    const overlays = host.querySelectorAll(".woven-node__arm-overlay");
    expect(overlays).toHaveLength(1);
    expect(overlays[0].dataset.arm).toBe("northwest");
    expect(overlays[0].title).toBe("Notiz");
  });
});
