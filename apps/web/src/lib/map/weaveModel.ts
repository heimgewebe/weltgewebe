import { edgeOpacityAt } from "$lib/map/edgeLifecycle";
import type {
  MapEdge,
  MapEntityViewModel,
  MapEntityWeave,
  WeaveProposalArc,
  WeaveThemeSegment,
} from "$lib/map/types";
import {
  WEAVE_FALLBACK_COLOR,
  weaveTopicColor,
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

type Group = {
  subjectId: string;
  proposals: number;
  conversations: number;
  votes: number;
  bundled: number;
  latestMs: number;
  opacity: number;
};

export function deriveWeaveThemeSegments(
  entity: WeaveEntity,
): WeaveThemeSegment[] {
  const labels = weaveTopics(entity);
  const spanDeg = 360 / labels.length;
  return labels.map((label, index) => ({
    id: label,
    label,
    color: weaveTopicColor(label),
    startDeg: index * spanDeg,
    spanDeg,
  }));
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
  const themeSegments = deriveWeaveThemeSegments(entity);
  const primaryThemeColor = themeSegments[0]?.color ?? WEAVE_FALLBACK_COLOR;
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
    primaryThemeColor,
    coreDensity: Math.min(
      1,
      0.42 +
        Math.log2(knottingThreadCount + 1) * 0.14 +
        themeSegments.length * 0.045,
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

export function themeConicGradient(segments: WeaveThemeSegment[]): string {
  return segments.length
    ? `conic-gradient(${segments
        .map(
          ({ color, startDeg, spanDeg }) =>
            `${color} ${startDeg}deg ${startDeg + spanDeg}deg`,
        )
        .join(",")})`
    : WEAVE_FALLBACK_COLOR;
}

export function voteStitchConicGradient(
  spanDeg: number,
  voteCount: number,
  color = "#f6ead7",
): string {
  if (!voteCount || !spanDeg) return "transparent";
  const count = Math.min(14, voteCount);
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
