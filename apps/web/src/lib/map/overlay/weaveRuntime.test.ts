import { afterEach, describe, expect, it, vi } from "vitest";
import type {
  MapEntityWeave,
  WeaveArm,
  WeaveProposalArc,
} from "$lib/map/types";
import {
  MAX_VISIBLE_ARM_OVERLAYS,
  MAX_VISIBLE_PROPOSAL_ARCS,
  MAX_VISIBLE_VOTE_STITCHES,
  maxWeaveDomNodeBudget,
} from "$lib/map/weaveModel";
import {
  applyWeaveDynamicProperties,
  countRenderedWeaveDomNodes,
  weaveRenderSignature,
  weaveRuntime,
} from "./weaveRuntime";

/**
 * Minimal element tree that supports the createElement/text/attribute path
 * used by weaveRuntime. Vitest runs in the node environment; this host is
 * intentionally close to jsdom semantics for descendant counting and attribute
 * safety without adding a new runtime dependency.
 */
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
  };
  dataset: Record<string, string> = {};
  children: DomElement[] = [];
  attributes = new Map<string, string>();

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

function maximalWeave(): MapEntityWeave {
  const arms: WeaveArm[] = ["northwest", "northeast", "southeast", "southwest"];
  const xCoreSegments = arms.map((arm, index) => ({
    arm,
    themeId: `theme-${index}`,
    label: `Theme ${index}`,
    color: `#${(index + 1).toString(16).repeat(6).slice(0, 6)}`,
  }));
  const armOverlays = arms
    .slice(0, MAX_VISIBLE_ARM_OVERLAYS)
    .map((arm, index) => ({
      arm,
      id: `overlay-${index}`,
      label: index === 0 ? 'Notiz "A" & <B>' : `Overlay ${index}`,
    }));
  const proposalArcs: WeaveProposalArc[] = Array.from(
    { length: MAX_VISIBLE_PROPOSAL_ARCS },
    (_, index) => ({
      subjectId:
        index === MAX_VISIBLE_PROPOSAL_ARCS - 1
          ? "__proposal-overflow__"
          : `proposal-${index}`,
      proposalThreadCount: 1,
      conversationThreadCount: 0,
      voteThreadCount: MAX_VISIBLE_VOTE_STITCHES + 3,
      bundledSubjectCount: index === MAX_VISIBLE_PROPOSAL_ARCS - 1 ? 4 : 1,
      latestActivityAtMs: 1000 - index,
      opacity: 0.8,
      color: "#5f7a55",
      startDeg: index * 40,
      spanDeg: 32,
    }),
  );
  return {
    zoneOrder: ["knotting", "conversation", "proposal", "vote"],
    themeSegments: xCoreSegments.map((segment) => ({
      id: segment.themeId,
      label: segment.label,
      color: segment.color,
      arm: segment.arm,
    })),
    xCoreSegments,
    armOverlays,
    primaryThemeColor: "#5f7a55",
    coreDensity: 1,
    conversationRingThickness: 1,
    knottingThreadCount: 4,
    conversationThreadCount: 20,
    conversationOpacity: 0.9,
    proposalArcs,
    proposalCount: MAX_VISIBLE_PROPOSAL_ARCS + 3,
    proposalOverflowCount: 4,
    voteThreadCount: proposalArcs.reduce(
      (sum, arc) => sum + arc.voteThreadCount,
      0,
    ),
    totalActiveThreadCount: 99,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("weaveRuntime DOM safety and budget", () => {
  it("renders arm overlay ids/labels through attribute APIs without injection", () => {
    installDom();
    const weave = maximalWeave();
    const { root } = weaveRuntime.createRoot(
      {
        type: "node",
        id: "n1",
        title: "Safe",
        kind: "Garten",
        tags: ["Natur"],
        created_at: "2026-08-01T00:00:00Z",
        lat: 53.5,
        lon: 10,
        weave,
      },
      "node",
    );
    const host = root as unknown as DomElement;
    const overlay = host.querySelectorAll(".woven-node__arm-overlay")[0];
    expect(overlay.title).toBe('Notiz "A" & <B>');
    expect(overlay.getAttribute("data-overlay-id")).toBe("overlay-0");
    // No attribute-string concatenation path for title.
    expect(overlay.getAttribute("title")).toBeNull();
    const serializedAttrs = [...overlay.attributes.entries()]
      .map(([name, value]) => `${name}=${value}`)
      .join("|");
    expect(serializedAttrs).not.toMatch(/onerror|javascript:|<script/i);
  });

  it("counts a maximal real weave against the documented DOM budget", () => {
    installDom();
    const weave = maximalWeave();
    const rendered = countRenderedWeaveDomNodes(weave);
    const budget = maxWeaveDomNodeBudget();
    expect(rendered).toBeLessThanOrEqual(budget);
    // conversation + x + 2 strands + 4 arms + 4 overlays
    // + 8 proposals + 8 vote siblings + overflow = 29
    expect(rendered).toBe(
      1 +
        1 +
        2 +
        4 +
        MAX_VISIBLE_ARM_OVERLAYS +
        MAX_VISIBLE_PROPOSAL_ARCS +
        MAX_VISIBLE_PROPOSAL_ARCS +
        1,
    );
    expect(budget).toBe(rendered);
    expect(weave.xCoreSegments).toHaveLength(4);
    expect(weave.armOverlays).toHaveLength(MAX_VISIBLE_ARM_OVERLAYS);
    expect(weave.proposalArcs).toHaveLength(MAX_VISIBLE_PROPOSAL_ARCS);
    expect(weave.proposalOverflowCount).toBeGreaterThan(0);
    expect(
      weave.proposalArcs.every(
        (arc) => arc.voteThreadCount > MAX_VISIBLE_VOTE_STITCHES,
      ),
    ).toBe(true);
  });

  it("includes overlay labels in the structural signature", () => {
    const base = maximalWeave();
    const renamed: MapEntityWeave = {
      ...base,
      armOverlays: base.armOverlays.map((overlay, index) =>
        index === 0 ? { ...overlay, label: "Geändert" } : overlay,
      ),
    };
    expect(weaveRenderSignature(renamed)).not.toBe(weaveRenderSignature(base));
  });

  it("applies conversation thickness and opacity as dynamic CSS properties", () => {
    installDom();
    const weave = {
      ...maximalWeave(),
      conversationOpacity: 0.42,
      conversationRingThickness: 1.75,
      proposalArcs: [
        {
          ...maximalWeave().proposalArcs[0],
          opacity: 0.33,
        },
      ],
    };
    const { root } = weaveRuntime.createRoot(
      {
        type: "node",
        id: "n-dyn",
        title: "Dyn",
        kind: "Garten",
        tags: ["Natur"],
        created_at: "2026-08-01T00:00:00Z",
        lat: 53.5,
        lon: 10,
        weave,
      },
      "node",
    );
    const host = root as unknown as DomElement;
    expect(host.style.props.get("--weave-conversation-opacity")).toBe("0.42");
    expect(host.style.props.get("--weave-conversation-thickness")).toBe("1.75");

    const aged = {
      ...weave,
      conversationOpacity: 0.11,
      conversationRingThickness: 0.5,
      proposalArcs: [{ ...weave.proposalArcs[0], opacity: 0.2 }],
    };
    applyWeaveDynamicProperties(root as HTMLElement, aged);
    expect(host.style.props.get("--weave-conversation-opacity")).toBe("0.11");
    expect(host.style.props.get("--weave-conversation-thickness")).toBe("0.5");
    const slot = host.querySelectorAll("[data-proposal-slot]")[0];
    expect(slot.style.opacity).toBe("0.2");
  });
});
