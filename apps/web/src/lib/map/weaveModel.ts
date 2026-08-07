import { edgeOpacityAt } from "$lib/map/edgeLifecycle";
import type {
  MapEdge,
  MapEntityViewModel,
  MapEntityWeave,
  WeaveArm,
  WeaveArmOverlay,
  WeaveProposalArc,
  WeaveThemeSegment,
  WeaveXCoreSegment,
} from "$lib/map/types";
import { WEAVE_ARMS } from "$lib/map/types";
import {
  WEAVE_FALLBACK_COLOR,
  weaveTopicColor,
  weaveTopicDisplayLabel,
  weaveTopicIdentity,
  weaveTopics,
  type WeaveEntity,
} from "$lib/map/weaveTheme";

export const WEAVE_ZONE_ORDER: MapEntityWeave["zoneOrder"] = [
  "knotting",
  "conversation",
  "proposal",
  "vote",
];
export const MAX_VISIBLE_PROPOSAL_ARCS = 8;
/** Visual X core uses at most four primary colour regions. */
export const MAX_X_CORE_THEMES = 4;
/**
 * Cap on visible arm overlays. The public map projection does not yet expose
 * node-attached content, so the projection is always empty (truth boundary).
 */
export const MAX_VISIBLE_ARM_OVERLAYS = 4;
/** Visible vote stitches per proposal arc; the model keeps the full count. */
export const MAX_VISIBLE_VOTE_STITCHES = 12;
/**
 * Conversation count at which log1p thickness reaches the fixed maximum.
 * Higher counts stay capped — no unbounded ring growth.
 */
export const CONVERSATION_THICKNESS_SATURATION_COUNT = 20;

type Group = {
  subjectId: string;
  proposals: number;
  conversations: number;
  votes: number;
  bundled: number;
  latestMs: number;
  opacity: number;
};

/**
 * Diagonal strand pairing:
 * - strand A (under): northwest ↔ southeast
 * - strand B (over):  northeast ↔ southwest
 *
 * One theme colours the whole X; two themes each take one strand; three leave
 * the remaining arm on strand A with the first theme; four map 1:1; more than
 * four keep full identities in themeSegments while only the first four paint.
 */
export function assignXCoreSegments(
  topicLabels: readonly string[],
): WeaveXCoreSegment[] {
  const visual: Omit<WeaveXCoreSegment, "arm">[] = [];
  const seen = new Set<string>();
  for (const label of topicLabels) {
    const themeId = weaveTopicIdentity(label);
    if (!themeId || seen.has(themeId)) continue;
    seen.add(themeId);
    visual.push({
      themeId,
      label: weaveTopicDisplayLabel(label),
      color: weaveTopicColor(label),
    });
    if (visual.length === MAX_X_CORE_THEMES) break;
  }
  const fallback = {
    themeId: weaveTopicIdentity("Gemeingut"),
    label: "Gemeingut",
    color: WEAVE_FALLBACK_COLOR,
  };
  const themes = visual.length ? visual : [fallback];

  if (themes.length === 1) {
    return WEAVE_ARMS.map((arm) => ({ arm, ...themes[0] }));
  }
  if (themes.length === 2) {
    return [
      { arm: "northwest", ...themes[0] },
      { arm: "southeast", ...themes[0] },
      { arm: "northeast", ...themes[1] },
      { arm: "southwest", ...themes[1] },
    ];
  }
  if (themes.length === 3) {
    return [
      { arm: "northwest", ...themes[0] },
      { arm: "northeast", ...themes[1] },
      { arm: "southeast", ...themes[2] },
      { arm: "southwest", ...themes[0] },
    ];
  }
  return [
    { arm: "northwest", ...themes[0] },
    { arm: "northeast", ...themes[1] },
    { arm: "southeast", ...themes[2] },
    { arm: "southwest", ...themes[3] },
  ];
}

export function deriveWeaveThemeSegments(
  entity: WeaveEntity,
): WeaveThemeSegment[] {
  const labels = weaveTopics(entity);
  const xCore = assignXCoreSegments(labels);
  const primaryArmByTheme = new Map<string, WeaveArm>();
  for (const segment of xCore) {
    if (!primaryArmByTheme.has(segment.themeId)) {
      primaryArmByTheme.set(segment.themeId, segment.arm);
    }
  }
  // Identity and colour come from the complete topic text. Only `label` is a
  // display value and may therefore be shortened at the very end.
  return labels.map((label) => {
    const id = weaveTopicIdentity(label);
    return {
      id,
      label: weaveTopicDisplayLabel(label),
      color: weaveTopicColor(label),
      arm: primaryArmByTheme.get(id) ?? null,
    };
  });
}

/**
 * log1p saturation into [0, 1]. Zero conversations stay invisible; growth is
 * smooth and hard-capped at CONVERSATION_THICKNESS_SATURATION_COUNT.
 */
export function conversationRingThickness(count: number): number {
  if (!Number.isFinite(count) || count <= 0) return 0;
  const ratio =
    Math.log1p(count) / Math.log1p(CONVERSATION_THICKNESS_SATURATION_COUNT);
  return Math.min(1, Math.max(0, ratio));
}

/**
 * Truth boundary: the public node/map projection does not yet carry a bounded
 * list of content pieces attached to a node. Prepare the type and a hard cap,
 * return empty, and never invent overlay counts for the renderer.
 */
export function deriveArmOverlays(entity: WeaveEntity): WeaveArmOverlay[] {
  void entity;
  return [];
}

function newGroup(subjectId: string): Group {
  return {
    subjectId,
    proposals: 0,
    conversations: 0,
    votes: 0,
    bundled: 1,
    latestMs: 0,
    opacity: 0,
  };
}

function proposalArcs(groups: Group[], color: string): WeaveProposalArc[] {
  if (!groups.length) return [];
  const gapDeg =
    groups.length === 1 ? 0 : Math.max(3, 7 - groups.length * 0.45);
  const coverageDeg =
    groups.length === 1 ? 250 : Math.min(344, 226 + groups.length * 18);
  const spanDeg =
    (coverageDeg - gapDeg * Math.max(0, groups.length - 1)) / groups.length;
  const startDeg = (360 - coverageDeg) / 2;
  return groups.map((group, index) => ({
    subjectId: group.subjectId,
    proposalThreadCount: group.proposals,
    conversationThreadCount: group.conversations,
    voteThreadCount: group.votes,
    bundledSubjectCount: group.bundled,
    latestActivityAtMs: group.latestMs,
    opacity: group.opacity,
    color,
    startDeg: startDeg + index * (spanDeg + gapDeg),
    spanDeg,
  }));
}

function mergeGroups(groups: Group[]): Group {
  const merged = newGroup("__proposal-overflow__");
  merged.bundled = 0;
  for (const group of groups) {
    merged.proposals += group.proposals;
    merged.conversations += group.conversations;
    merged.votes += group.votes;
    merged.bundled += group.bundled;
    merged.latestMs = Math.max(merged.latestMs, group.latestMs);
    merged.opacity = Math.max(merged.opacity, group.opacity);
  }
  return merged;
}

export function deriveEntityWeave(
  entity: WeaveEntity,
  edges: MapEdge[],
  nowMs: number,
): MapEntityWeave {
  const topicLabels = weaveTopics(entity);
  const themeSegments = deriveWeaveThemeSegments(entity);
  const xCoreSegments = assignXCoreSegments(topicLabels);
  const armOverlays = deriveArmOverlays(entity).slice(
    0,
    MAX_VISIBLE_ARM_OVERLAYS,
  );
  const primaryThemeColor =
    xCoreSegments[0]?.color ?? themeSegments[0]?.color ?? WEAVE_FALLBACK_COLOR;
  const endpointId =
    entity.type === "webgemeindezentrum" ? entity.faden_endpoint_id : entity.id;
  const groups = new Map<string, Group>();
  let knottingThreadCount = 0;
  let conversationThreadCount = 0;
  let conversationOpacity = 0;
  let totalActiveThreadCount = 0;

  for (const edge of edges) {
    if (
      !edge.faden_type ||
      (edge.target_id !== entity.id && edge.target_id !== endpointId)
    ) {
      continue;
    }
    const opacity = edgeOpacityAt(edge, nowMs);
    if (opacity <= 0) continue;

    if (edge.faden_type === "knotting") {
      knottingThreadCount += 1;
      totalActiveThreadCount += 1;
      continue;
    }

    if (edge.faden_type === "conversation") {
      conversationThreadCount += 1;
      conversationOpacity = Math.max(conversationOpacity, opacity);
      totalActiveThreadCount += 1;
    }

    const subjectId = edge.faden_subject_id;
    if (!subjectId) continue;
    const group = groups.get(subjectId) ?? newGroup(subjectId);
    if (edge.faden_type === "proposal") {
      group.proposals += 1;
      totalActiveThreadCount += 1;
    } else if (edge.faden_type === "vote") {
      group.votes += 1;
    } else if (edge.faden_type === "conversation") {
      group.conversations += 1;
    } else {
      continue;
    }
    const activityAtMs =
      edge.lifecycle.kind === "faden" ? edge.lifecycle.createdAtMs : 0;
    group.latestMs = Math.max(group.latestMs, activityAtMs);
    group.opacity = Math.max(group.opacity, opacity);
    groups.set(subjectId, group);
  }

  const sorted = [...groups.values()]
    .filter((group) => group.proposals > 0)
    .sort(
      (left, right) =>
        right.latestMs - left.latestMs ||
        left.subjectId.localeCompare(right.subjectId),
    );
  const voteThreadCount = sorted.reduce(
    (count, group) => count + group.votes,
    0,
  );
  totalActiveThreadCount += voteThreadCount;
  const proposalCount = sorted.length;
  const proposalOverflowCount = Math.max(
    0,
    proposalCount - MAX_VISIBLE_PROPOSAL_ARCS + 1,
  );
  const visible = proposalOverflowCount
    ? [
        ...sorted.slice(0, MAX_VISIBLE_PROPOSAL_ARCS - 1),
        mergeGroups(sorted.slice(MAX_VISIBLE_PROPOSAL_ARCS - 1)),
      ]
    : sorted;

  return {
    zoneOrder: WEAVE_ZONE_ORDER,
    themeSegments,
    xCoreSegments,
    armOverlays,
    primaryThemeColor,
    coreDensity: Math.min(
      1,
      0.42 +
        Math.log2(knottingThreadCount + 1) * 0.14 +
        Math.min(MAX_X_CORE_THEMES, themeSegments.length) * 0.045,
    ),
    conversationRingThickness: conversationRingThickness(
      conversationThreadCount,
    ),
    knottingThreadCount,
    conversationThreadCount,
    conversationOpacity,
    proposalArcs: proposalArcs(visible, primaryThemeColor),
    proposalCount,
    proposalOverflowCount,
    voteThreadCount,
    totalActiveThreadCount,
  };
}

export function projectEntityWeaves(
  entities: MapEntityViewModel[],
  edges: MapEdge[],
  nowMs: number,
): MapEntityViewModel[] {
  const edgesByTarget = new Map<string, MapEdge[]>();
  for (const edge of edges) {
    if (!edge.faden_type) continue;
    const bucket = edgesByTarget.get(edge.target_id);
    if (bucket) bucket.push(edge);
    else edgesByTarget.set(edge.target_id, [edge]);
  }

  return entities.map((entity) => {
    if (entity.type === "garnrolle") return entity;
    const directEdges = edgesByTarget.get(entity.id) ?? [];
    const relatedEdges =
      entity.type === "webgemeindezentrum" &&
      entity.faden_endpoint_id !== entity.id
        ? directEdges.concat(edgesByTarget.get(entity.faden_endpoint_id) ?? [])
        : directEdges;
    return {
      ...entity,
      weave: deriveEntityWeave(entity, relatedEdges, nowMs),
    };
  });
}

/** Ordered, de-duplicated target theme palette for edge paint (max four). */
export function targetThemePalette(
  entity:
    | Pick<MapEntityWeave, "themeSegments" | "primaryThemeColor">
    | null
    | undefined,
): string[] {
  if (!entity) return [WEAVE_FALLBACK_COLOR];
  const colors: string[] = [];
  const seen = new Set<string>();
  for (const segment of entity.themeSegments) {
    if (seen.has(segment.id)) continue;
    seen.add(segment.id);
    colors.push(segment.color);
    if (colors.length === MAX_X_CORE_THEMES) break;
  }
  return colors.length
    ? colors
    : [entity.primaryThemeColor || WEAVE_FALLBACK_COLOR];
}

/**
 * The exact visible colour of the incoming knotting thread's last painted
 * segment before it reaches the node centre. `edges.ts` braids a target's
 * {@link targetThemePalette} across the thread in `palette.length * 2`
 * segments cycling through the palette, so the final segment — the one
 * touching the centre — always lands on the palette's last colour. The
 * stitched X is the same thread continuing past that point, so every arm
 * must resolve its colour through this one helper rather than an independent
 * per-arm topic palette; that is what keeps the thread and the X from ever
 * picking two different colours for the same node. Falls back to the same
 * {@link WEAVE_FALLBACK_COLOR} the edge itself falls back to when no theme
 * palette exists.
 */
export function terminalThreadColor(
  entity:
    | Pick<MapEntityWeave, "themeSegments" | "primaryThemeColor">
    | null
    | undefined,
): string {
  const palette = targetThemePalette(entity);
  return palette[palette.length - 1] ?? WEAVE_FALLBACK_COLOR;
}

export function voteStitchConicGradient(
  spanDeg: number,
  voteCount: number,
  color = "#f6ead7",
): string {
  if (!voteCount || !spanDeg) return "transparent";
  const count = Math.min(MAX_VISIBLE_VOTE_STITCHES, voteCount);
  const step = spanDeg / (count + 1);
  const width = Math.max(0.8, Math.min(2.1, step * 0.34));
  const stops: string[] = [];
  let lastEnd = 0;
  for (let index = 1; index <= count; index += 1) {
    const center = step * index;
    const start = center - width / 2;
    const end = center + width / 2;
    stops.push(
      `transparent ${lastEnd}deg ${start}deg`,
      `${color} ${start}deg ${end}deg`,
    );
    lastEnd = end;
  }
  stops.push(`transparent ${lastEnd}deg 360deg`);
  return `conic-gradient(${stops.join(",")})`;
}

/**
 * Upper bound on DOM element nodes for one maximally complex woven body.
 * Used by the deterministic budget test; keep in sync with {@link renderWeave}.
 */
export function maxWeaveDomNodeBudget(): number {
  // conversation ring + x root + 2 strands + 4 arms
  // + max arm overlays + 8 proposal arcs + 8 vote siblings + overflow badge
  return (
    1 +
    1 +
    2 +
    4 +
    MAX_VISIBLE_ARM_OVERLAYS +
    MAX_VISIBLE_PROPOSAL_ARCS +
    MAX_VISIBLE_PROPOSAL_ARCS +
    1
  );
}
