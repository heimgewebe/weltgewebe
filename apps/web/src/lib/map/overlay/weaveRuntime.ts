import type {
  MapEdge,
  MapEntityViewModel,
  MapEntityWeave,
  WeaveArm,
  WeaveXCoreSegment,
} from "$lib/map/types";
import type { WeaveEntity } from "$lib/map/weaveTheme";
import {
  deriveEntityWeave,
  MAX_VISIBLE_VOTE_STITCHES,
  projectEntityWeaves,
  voteStitchConicGradient,
} from "$lib/map/weaveModel";

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
  let signature = `${weave.primaryThemeColor}|${weave.coreDensity}|${weave.conversationRingThickness}|${weave.knottingThreadCount}|${weave.conversationThreadCount}|${weave.proposalCount}|${weave.proposalOverflowCount}|${weave.voteThreadCount}|${weave.armOverlays.length}`;
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
    conversationThreadCount,
    bundledSubjectCount,
  } of weave.proposalArcs) {
    signature += `|${subjectId}:${color}:${startDeg}:${spanDeg}:${voteThreadCount}:${proposalThreadCount}:${conversationThreadCount}:${bundledSubjectCount}`;
  }
  return signature;
}

/**
 * DOM-preserving dynamic CSS state written onto an already-rendered weave body.
 * Covers conversation opacity, conversation-ring thickness, and per-slot
 * proposal/vote opacities — not a structural rebuild.
 */
export function applyWeaveDynamicProperties(
  root: HTMLElement,
  weave: MapEntityWeave,
) {
  root.style.setProperty(
    "--weave-conversation-opacity",
    String(weave.conversationOpacity),
  );
  root.style.setProperty(
    "--weave-conversation-thickness",
    String(weave.conversationRingThickness),
  );
  if (!weave.proposalArcs.length) return;
  // One query for the whole body: an arc and its vote stitches share a slot.
  for (const element of root.querySelectorAll<HTMLElement>(
    "[data-proposal-slot]",
  )) {
    const arc = weave.proposalArcs[Number(element.dataset.proposalSlot) - 1];
    if (arc) element.style.opacity = String(arc.opacity);
  }
}

function armColor(arms: readonly WeaveXCoreSegment[], arm: WeaveArm): string {
  return arms.find((segment) => segment.arm === arm)?.color ?? "#76523d";
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
    conversationThreads: String(weave.conversationThreadCount),
    proposalCount: String(weave.proposalCount),
    voteThreads: String(weave.voteThreadCount),
    xGeometry: "diagonal",
    armOverlayCount: String(weave.armOverlays.length),
  });
  root.style.setProperty("--weave-primary", weave.primaryThemeColor);
  root.style.setProperty("--weave-core-density", String(weave.coreDensity));
  root.style.setProperty(
    "--weave-conversation-thickness",
    String(weave.conversationRingThickness),
  );
  for (const segment of weave.xCoreSegments) {
    root.style.setProperty(`--weave-arm-${segment.arm}`, segment.color);
  }

  // Clear previous structure without parsing untrusted HTML.
  while (root.firstChild) root.removeChild(root.firstChild);

  const arms = weave.xCoreSegments;
  const crossing = createSpan("woven-node__crossing", {
    "data-zone": "crossing",
  });
  const conversationClass = weave.conversationThreadCount
    ? "woven-node__conversation"
    : "woven-node__conversation is-empty";
  const conversation = createSpan(conversationClass, {
    "data-zone": "conversation",
  });

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
  for (const arm of ["northwest", "southeast"] as const) {
    const armEl = createSpan("woven-node__arm", { "data-arm": arm });
    armEl.style.setProperty("--arm-color", armColor(arms, arm));
    strandUnder.append(armEl);
  }
  const strandOver = createSpan("woven-node__strand woven-node__strand--over", {
    "data-strand": "b",
  });
  for (const arm of ["northeast", "southwest"] as const) {
    const armEl = createSpan("woven-node__arm", { "data-arm": arm });
    armEl.style.setProperty("--arm-color", armColor(arms, arm));
    strandOver.append(armEl);
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

  root.append(crossing, conversation, xCore);

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
