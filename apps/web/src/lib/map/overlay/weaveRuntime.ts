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
 * already exist — see {@link applyWeaveOpacity}.
 */
export function weaveRenderSignature(weave: MapEntityWeave): string {
  let signature = `${weave.primaryThemeColor}|${weave.coreDensity}|${weave.conversationRingThickness}|${weave.knottingThreadCount}|${weave.conversationThreadCount}|${weave.proposalCount}|${weave.proposalOverflowCount}|${weave.voteThreadCount}|${weave.armOverlays.length}`;
  for (const { id, color, arm } of weave.themeSegments) {
    signature += `|${id}:${color}:${arm ?? "-"}`;
  }
  for (const { arm, themeId, color } of weave.xCoreSegments) {
    signature += `|x:${arm}:${themeId}:${color}`;
  }
  for (const overlay of weave.armOverlays) {
    signature += `|o:${overlay.arm}:${overlay.id}`;
  }
  for (const {
    subjectId,
    color,
    startDeg,
    spanDeg,
    voteThreadCount,
  } of weave.proposalArcs) {
    signature += `|${subjectId}:${color}:${startDeg}:${spanDeg}:${voteThreadCount}`;
  }
  return signature;
}

/**
 * Time-dependent opacity, written onto the existing nodes. The conversation
 * ring reads a CSS variable; every proposal arc and its vote stitches are
 * addressed through their shared `data-proposal-slot`.
 */
export function applyWeaveOpacity(root: HTMLElement, weave: MapEntityWeave) {
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

  const arms = weave.xCoreSegments;
  const armMarkup = (arm: WeaveArm) =>
    `<span class="woven-node__arm" data-arm="${arm}" style="--arm-color:${armColor(arms, arm)}"></span>`;
  const overlays = weave.armOverlays
    .map(
      (overlay) =>
        `<span class="woven-node__arm-overlay" data-arm="${overlay.arm}" data-overlay-id="${overlay.id}" title="${overlay.label}"></span>`,
    )
    .join("");
  // Layer order inside the body: crossing → conversation → X (under then over)
  // → arm overlays → proposals → vote siblings → overflow badge.
  const xCore = `<span class="woven-node__x" data-zone="knotting" data-x-geometry="diagonal"><span class="woven-node__strand woven-node__strand--under" data-strand="a">${armMarkup("northwest")}${armMarkup("southeast")}</span><span class="woven-node__strand woven-node__strand--over" data-strand="b">${armMarkup("northeast")}${armMarkup("southwest")}</span>${overlays}</span>`;
  const proposals = weave.proposalArcs
    .map((arc, index) => {
      const slot = String(index + 1);
      // Opacity stays out of the markup: applyWeaveOpacity owns it, so a purely
      // temporal change never has to touch this string.
      const arcStyle = `--arc-start:${arc.startDeg}deg;--arc-span:${arc.spanDeg}deg;--arc-color:${arc.color}`;
      const proposal = `<span class="woven-node__proposal-arc" data-zone="proposal" data-proposal-slot="${slot}" data-vote-threads="${arc.voteThreadCount}" style="${arcStyle}"></span>`;
      const votes = arc.voteThreadCount
        ? `<span class="woven-node__vote-stitches" data-zone="vote" data-proposal-slot="${slot}" data-vote-total="${arc.voteThreadCount}" data-vote-visible="${Math.min(MAX_VISIBLE_VOTE_STITCHES, arc.voteThreadCount)}" style="${arcStyle};background:${voteStitchConicGradient(arc.spanDeg, arc.voteThreadCount)}"></span>`
        : "";
      return proposal + votes;
    })
    .join("");
  root.innerHTML = `<span class="woven-node__crossing" data-zone="crossing"></span><span class="woven-node__conversation${weave.conversationThreadCount ? "" : " is-empty"}" data-zone="conversation"></span>${xCore}${proposals}${weave.proposalOverflowCount ? `<span class="woven-node__overflow">+${weave.proposalOverflowCount}</span>` : ""}`;
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
    applyWeaveOpacity(root, weave);
    return { root, signature: weaveRenderSignature(weave) };
  },
  syncRoot(root, item, previousSignature) {
    const weave = entityWeave(item);
    const signature = weaveRenderSignature(weave);
    if (signature !== previousSignature) renderWeave(root, weave);
    applyWeaveOpacity(root, weave);
    return signature;
  },
};
