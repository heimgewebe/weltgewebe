import type {
  MapEdge,
  MapEntityViewModel,
  MapEntityWeave,
} from "$lib/map/types";
import { WEAVE_OVER_ARMS, WEAVE_UNDER_ARMS } from "$lib/map/types";
import type { WeaveEntity } from "$lib/map/weaveTheme";
import {
  deriveEntityWeave,
  MAX_VISIBLE_VOTE_STITCHES,
  projectEntityWeaves,
  terminalThreadColor,
  voteStitchConicGradient,
} from "$lib/map/weaveModel";
import {
  CONVERSATION_RING_BASE_DIAMETER_PERCENT,
  CONVERSATION_THREAD_WIDTH_PX,
  KNOTTING_THREAD_WIDTH_PX,
} from "$lib/map/weaveVisualTokens";

export type WeaveRootState = {
  root: HTMLElement;
  signature: string;
};

export type WeaveRuntime = {
  label: (item: MapEntityViewModel) => string;
  createRoot: (
    item: WeaveEntity,
    markerCategory: "node" | "webgemeindezentrum",
  ) => WeaveRootState;
  syncRoot: (
    root: HTMLElement,
    item: WeaveEntity,
    previousSignature: string | null,
  ) => string;
};

function entityWeave(item: WeaveEntity): MapEntityWeave {
  return item.weave ?? deriveEntityWeave(item, [], 0);
}

export function projectMarkersForWeave(
  points: MapEntityViewModel[],
  weaveEdges: MapEdge[],
  nowMs: number,
): MapEntityViewModel[] {
  return projectEntityWeaves(points, weaveEdges, nowMs);
}

export type ProjectedMapMarkerViews = {
  visible: MapEntityViewModel[];
  motion: MapEntityViewModel[];
};

/**
 * Build the expensive full weave projection once, then select the filtered
 * marker view from those already-projected entities. The filter evaluator
 * preserves scene order, so the no-filter path can reuse the array itself and
 * a filtered path can retain the same projected object identities.
 */
export function projectMapMarkerViewsForWeave(
  points: MapEntityViewModel[],
  visiblePoints: MapEntityViewModel[],
  edges: MapEdge[],
  nowMs: number,
): ProjectedMapMarkerViews {
  const motion = projectMarkersForWeave(points, edges, nowMs);
  const allVisible =
    points.length === visiblePoints.length &&
    points.every((point, index) => point.id === visiblePoints[index]?.id);
  if (allVisible) return { visible: motion, motion };

  const visibleIds = new Set(visiblePoints.map((point) => point.id));
  return {
    visible: motion.filter((point) => visibleIds.has(point.id)),
    motion,
  };
}

/**
 * Structural signature: only values whose change actually rebuilds the woven
 * DOM. Ageing conversation and proposal threads change their opacity on every
 * projection step; treating that as structure would tear down and rebuild every
 * marker body once a minute. Opacity is applied separately to the elements that
 * already exist — see {@link applyWeaveDynamicProperties}.
 *
 * Arm overlays include label (and every other DOM-relevant field) so a stable
 * overlay id with a changed title still rebuilds.
 */
export function weaveRenderSignature(weave: MapEntityWeave): string {
  let signature = `${weave.primaryThemeColor}|${weave.coreDensity}|${weave.knottingThreadCount}|${weave.proposalCount}|${weave.proposalOverflowCount}|${weave.voteThreadCount}|${weave.armOverlays.length}`;
  for (const { id, color, arm, label } of weave.themeSegments) {
    signature += `|${id}:${color}:${arm ?? "-"}:${label}`;
  }
  for (const { arm, themeId, color, label } of weave.xCoreSegments) {
    signature += `|x:${arm}:${themeId}:${color}:${label}`;
  }
  for (const overlay of weave.armOverlays) {
    signature += `|o:${overlay.arm}:${overlay.id}:${overlay.label}`;
  }
  for (const {
    subjectId,
    color,
    startDeg,
    spanDeg,
    voteThreadCount,
    proposalThreadCount,
    bundledSubjectCount,
  } of weave.proposalArcs) {
    signature += `|${subjectId}:${color}:${startDeg}:${spanDeg}:${voteThreadCount}:${proposalThreadCount}:${bundledSubjectCount}`;
  }
  return signature;
}

/**
 * DOM-preserving dynamic CSS state written onto an already-rendered weave body.
 * Covers conversation opacity and ring diameter geometry, plus per-slot
 * proposal/vote opacities — not a structural rebuild. The yarn gauge is static.
 */
export function conversationRingInsetPercent(scale: number): number {
  if (!Number.isFinite(scale) || scale <= 0) return 50;
  return 50 - (CONVERSATION_RING_BASE_DIAMETER_PERCENT * scale) / 2;
}

export function applyWeaveDynamicProperties(
  root: HTMLElement,
  weave: MapEntityWeave,
) {
  root.dataset.conversationThreads = String(weave.conversationThreadCount);
  root.style.setProperty(
    "--weave-conversation-opacity",
    String(weave.conversationOpacity),
  );
  root.style.setProperty(
    "--weave-conversation-scale",
    String(weave.conversationRingScale),
  );
  root.style.setProperty(
    "--weave-conversation-inset",
    `${conversationRingInsetPercent(weave.conversationRingScale)}%`,
  );
  const conversation = root.querySelectorAll<HTMLElement>(
    ".woven-node__conversation",
  )[0];
  if (conversation)
    conversation.className = `woven-node__conversation${weave.conversationThreadCount ? "" : " is-empty"}`;
  if (!weave.proposalArcs.length) return;
  // One query for the whole body: an arc and its vote stitches share a slot.
  for (const element of root.querySelectorAll<HTMLElement>(
    "[data-proposal-slot]",
  )) {
    const arc = weave.proposalArcs[Number(element.dataset.proposalSlot) - 1];
    if (arc) element.style.opacity = String(arc.opacity);
  }
}

function createSpan(
  className: string,
  attributes: Record<string, string> = {},
): HTMLElement {
  const element = document.createElement("span");
  element.className = className;
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "title") {
      element.title = value;
    } else {
      element.setAttribute(name, value);
    }
  }
  return element;
}

function renderWeave(root: HTMLElement, weave: MapEntityWeave) {
  Object.assign(root.dataset, {
    zoneOrder: "knotting,conversation,proposal,vote",
    knottingThreads: String(weave.knottingThreadCount),
    proposalCount: String(weave.proposalCount),
    voteThreads: String(weave.voteThreadCount),
    xGeometry: "diagonal",
    armOverlayCount: String(weave.armOverlays.length),
  });
  root.style.setProperty("--weave-primary", weave.primaryThemeColor);
  root.style.setProperty("--weave-core-density", String(weave.coreDensity));
  root.style.setProperty(
    "--weave-conversation-width",
    `${CONVERSATION_THREAD_WIDTH_PX}px`,
  );
  // The incoming knotting thread and all four stitched arms are one physical
  // yarn, so width has exactly one source of truth. Colour is different: the
  // incoming edge may braid several topic colours, and the X must keep that
  // palette visible instead of collapsing to the terminal colour. The root
  // terminal colour remains a safe fallback; each arm receives its modelled
  // topic colour below.
  const threadColor = terminalThreadColor(weave);
  root.style.setProperty("--weave-thread-color", threadColor);
  root.style.setProperty("--weave-arm-width", `${KNOTTING_THREAD_WIDTH_PX}px`);
  const coreSegmentByArm = new Map(
    weave.xCoreSegments.map((segment) => [segment.arm, segment]),
  );

  // Clear previous structure without parsing untrusted HTML.
  while (root.firstChild) root.removeChild(root.firstChild);

  const conversation = createSpan("woven-node__conversation", {
    "data-zone": "conversation",
  });

  // No separate crossing/knot element: the X's own visual body (arms +
  // over/under weave in markers.css) is the entire visible knot — there is
  // no additional circle/patch layered on top of it.
  const xCore = createSpan("woven-node__x", {
    "data-zone": "knotting",
    "data-x-geometry": "diagonal",
  });
  const strandUnder = createSpan(
    "woven-node__strand woven-node__strand--under",
    {
      "data-strand": "a",
    },
  );
  for (const arm of WEAVE_UNDER_ARMS) {
    const armElement = createSpan("woven-node__arm", { "data-arm": arm });
    const segment = coreSegmentByArm.get(arm);
    armElement.style.setProperty("--arm-color", segment?.color ?? threadColor);
    if (segment) armElement.setAttribute("data-theme-id", segment.themeId);
    strandUnder.append(armElement);
  }
  const strandOver = createSpan("woven-node__strand woven-node__strand--over", {
    "data-strand": "b",
  });
  for (const arm of WEAVE_OVER_ARMS) {
    const armElement = createSpan("woven-node__arm", { "data-arm": arm });
    const segment = coreSegmentByArm.get(arm);
    armElement.style.setProperty("--arm-color", segment?.color ?? threadColor);
    if (segment) armElement.setAttribute("data-theme-id", segment.themeId);
    strandOver.append(armElement);
  }
  xCore.append(strandUnder, strandOver);
  for (const overlay of weave.armOverlays) {
    const overlayEl = createSpan("woven-node__arm-overlay", {
      "data-arm": overlay.arm,
      "data-overlay-id": overlay.id,
      title: overlay.label,
    });
    xCore.append(overlayEl);
  }

  root.append(conversation, xCore);

  for (let index = 0; index < weave.proposalArcs.length; index += 1) {
    const arc = weave.proposalArcs[index];
    const slot = String(index + 1);
    // Dynamic CSS stays out of the markup: applyWeaveDynamicProperties owns it,
    // so a purely temporal change never has to touch this tree.
    const arcStyleVars = {
      "--arc-start": `${arc.startDeg}deg`,
      "--arc-span": `${arc.spanDeg}deg`,
      "--arc-color": arc.color,
    } as const;
    const proposal = createSpan("woven-node__proposal-arc", {
      "data-zone": "proposal",
      "data-proposal-slot": slot,
      "data-vote-threads": String(arc.voteThreadCount),
    });
    for (const [name, value] of Object.entries(arcStyleVars)) {
      proposal.style.setProperty(name, value);
    }
    root.append(proposal);

    if (arc.voteThreadCount) {
      const votes = createSpan("woven-node__vote-stitches", {
        "data-zone": "vote",
        "data-proposal-slot": slot,
        "data-vote-total": String(arc.voteThreadCount),
        "data-vote-visible": String(
          Math.min(MAX_VISIBLE_VOTE_STITCHES, arc.voteThreadCount),
        ),
      });
      for (const [name, value] of Object.entries(arcStyleVars)) {
        votes.style.setProperty(name, value);
      }
      votes.style.background = voteStitchConicGradient(
        arc.spanDeg,
        arc.voteThreadCount,
      );
      root.append(votes);
    }
  }

  if (weave.proposalOverflowCount) {
    const overflow = createSpan("woven-node__overflow");
    overflow.textContent = `+${weave.proposalOverflowCount}`;
    root.append(overflow);
  }
}

/**
 * Count element nodes that {@link renderWeave} emits for one body. Used by the
 * deterministic per-marker DOM budget test.
 */
export function countRenderedWeaveDomNodes(weave: MapEntityWeave): number {
  const host = document.createElement("span");
  renderWeave(host, weave);
  return host.querySelectorAll("*").length;
}

function accessibleMarkerLabel(item: MapEntityViewModel): string {
  if (item.type === "garnrolle") return item.title;
  const weave = entityWeave(item);
  return `${item.title}. Knüpfkern ${weave.knottingThreadCount}. Gesprächsring ${weave.conversationThreadCount}. Anträge ${weave.proposalCount}. Stimmen ${weave.voteThreadCount}.`;
}

export const weaveRuntime: WeaveRuntime = {
  label: accessibleMarkerLabel,
  createRoot(item, markerCategory) {
    const weave = entityWeave(item);
    const root = document.createElement("span");
    root.className = `woven-node woven-node--${markerCategory}`;
    root.setAttribute("aria-hidden", "true");
    renderWeave(root, weave);
    applyWeaveDynamicProperties(root, weave);
    return { root, signature: weaveRenderSignature(weave) };
  },
  syncRoot(root, item, previousSignature) {
    const weave = entityWeave(item);
    const signature = weaveRenderSignature(weave);
    if (signature !== previousSignature) renderWeave(root, weave);
    applyWeaveDynamicProperties(root, weave);
    return signature;
  },
};
