import { afterEach, describe, expect, it, vi } from "vitest";
import type { MapEntityWeave, WeaveProposalArc } from "$lib/map/types";
import { WEAVE_ARMS } from "$lib/map/types";
import {
  MAX_VISIBLE_ARM_OVERLAYS,
  MAX_VISIBLE_PROPOSAL_ARCS,
  MAX_VISIBLE_VOTE_STITCHES,
  maxWeaveDomNodeBudget,
} from "$lib/map/weaveModel";
import { DomElement, installDom as installDomStub } from "./domElementTestStub";
import {
  applyWeaveDynamicProperties,
  countRenderedWeaveDomNodes,
  weaveRenderSignature,
  weaveRuntime,
} from "./weaveRuntime";

function installDom() {
  installDomStub(vi);
}

function maximalWeave(): MapEntityWeave {
  const xCoreSegments = WEAVE_ARMS.map((arm, index) => ({
    arm,
    themeId: `theme-${index}`,
    label: `Theme ${index}`,
    color: `#${(index + 1).toString(16).repeat(6).slice(0, 6)}`,
  }));
  const armOverlays = WEAVE_ARMS.slice(0, MAX_VISIBLE_ARM_OVERLAYS).map(
    (arm, index) => ({
      arm,
      id: `overlay-${index}`,
      label: index === 0 ? 'Notiz "A" & <B>' : `Overlay ${index}`,
    }),
  );
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
    conversationRingScale: 1.25,
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

  it("keeps the modelled topic palette on the four stitched arms", () => {
    installDom();
    const weave = maximalWeave();
    const { root } = weaveRuntime.createRoot(
      {
        type: "node",
        id: "n-palette",
        title: "Palette",
        kind: "Knoten",
        tags: ["A", "B", "C", "D"],
        created_at: "2026-08-01T00:00:00Z",
        lat: 53.5,
        lon: 10,
        weave,
      },
      "node",
    );
    const host = root as unknown as DomElement;
    const expectedByArm = new Map(
      weave.xCoreSegments.map((segment) => [segment.arm, segment]),
    );
    const arms = host.querySelectorAll(".woven-node__arm");
    expect(arms).toHaveLength(4);
    expect(
      new Set(arms.map((arm) => arm.style.props.get("--arm-color"))).size,
    ).toBe(4);
    for (const arm of arms) {
      const armId = arm.getAttribute("data-arm");
      const expected = expectedByArm.get(
        armId as (typeof weave.xCoreSegments)[number]["arm"],
      );
      expect(expected).toBeDefined();
      expect(arm.style.props.get("--arm-color")).toBe(expected?.color);
      expect(arm.getAttribute("data-theme-id")).toBe(expected?.themeId);
    }
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

  it("updates conversation count and ring geometry without rebuilding the weave body", () => {
    installDom();
    const weave = {
      ...maximalWeave(),
      conversationOpacity: 0.42,
      conversationRingThickness: 1.75,
      conversationRingScale: 1.12,
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
    expect(host.style.props.get("--weave-conversation-scale")).toBe("1.12");
    expect(host.dataset.conversationThreads).toBe("20");

    const conversationBefore = host.querySelectorAll(
      ".woven-node__conversation",
    )[0];
    const previousSignature = weaveRenderSignature(weave);
    const resized = {
      ...weave,
      conversationThreadCount: 12,
      conversationOpacity: 0.77,
      conversationRingThickness: 0.8,
      conversationRingScale: 1.16,
    };
    const nextSignature = weaveRuntime.syncRoot(
      root,
      {
        type: "node",
        id: "n-dyn",
        title: "Dyn",
        kind: "Garten",
        tags: ["Natur"],
        created_at: "2026-08-01T00:00:00Z",
        lat: 53.5,
        lon: 10,
        weave: resized,
      },
      previousSignature,
    );
    expect(nextSignature).toBe(previousSignature);
    expect(host.querySelectorAll(".woven-node__conversation")[0]).toBe(
      conversationBefore,
    );
    expect(host.dataset.conversationThreads).toBe("12");
    expect(host.style.props.get("--weave-conversation-scale")).toBe("1.16");

    const aged = {
      ...weave,
      conversationOpacity: 0.11,
      conversationRingThickness: 0.5,
      conversationRingScale: 0.84,
      proposalArcs: [{ ...weave.proposalArcs[0], opacity: 0.2 }],
    };
    applyWeaveDynamicProperties(root as HTMLElement, aged);
    expect(host.style.props.get("--weave-conversation-opacity")).toBe("0.11");
    expect(host.style.props.get("--weave-conversation-thickness")).toBe("0.5");
    expect(host.style.props.get("--weave-conversation-scale")).toBe("0.84");
    const slot = host.querySelectorAll("[data-proposal-slot]")[0];
    expect(slot.style.opacity).toBe("0.2");

    applyWeaveDynamicProperties(root as HTMLElement, {
      ...aged,
      conversationThreadCount: 0,
      conversationOpacity: 0,
      conversationRingThickness: 0,
      conversationRingScale: 0,
    });
    expect(host.dataset.conversationThreads).toBe("0");
    expect(conversationBefore.className).toContain("is-empty");
  });
});
