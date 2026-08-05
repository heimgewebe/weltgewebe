import type {
  ExpressionSpecification,
  GeoJSONSource,
  LineLayerSpecification,
  Map as MapLibreMap,
} from "maplibre-gl";
import { isValidMapCoordinate } from "$lib/map/coordinates";
import { edgeOpacityAt } from "$lib/map/edgeLifecycle";
import type { MapEdge, MapEntityViewModel } from "$lib/map/types";
import { MAX_X_CORE_THEMES, targetThemePalette } from "$lib/map/weaveModel";
import { primaryWeaveColor } from "$lib/map/weaveTheme";
import { LAYERS } from "./layers";

/**
 * Canonical yarn material language for static Fäden and edge motion.
 * Three bounded MapLibre layers per type: shadow underlay, coloured body,
 * fine light/fiber accent. Width and braid/dash rhythms distinguish types —
 * not road-marking or pearl optics.
 *
 * Shadow/body stay largely continuous for knotting/conversation/proposal;
 * the braid/fiber rhythm lives primarily on the narrow highlight. Vote body
 * may stay stitch-like; its shadow remains continuous for a fine connective
 * underlay.
 */
export const EDGE_VISUAL_STYLE = {
  shadowColor: "rgba(36, 22, 15, 0.42)",
  shadowWidthExtra: 2.9,
  shadowBlur: 1.05,
  shadowOpacityFactor: 0.58,
  bodyColor: "#76523d",
  bodyWidth: 2.35,
  highlightColor: "rgba(250, 239, 218, 0.48)",
  highlightWidthFactor: 0.3,
  highlightOpacityFactor: 0.62,
  /** Yarn braid rhythm for untyped/legacy highlight (body continuous). */
  dashArray: [1.55, 0.72] as [number, number],
  byType: {
    // Soft conversational yarn: thinner body; open braid on highlight.
    conversation: {
      width: 2.2,
      dashArray: [1.55, 0.85] as [number, number],
      bodyContinuous: true,
      shadowContinuous: true,
    },
    // Proposal: broader strand; longer weave units on highlight.
    proposal: {
      width: 3.1,
      dashArray: [2.55, 0.38] as [number, number],
      bodyContinuous: true,
      shadowContinuous: true,
    },
    // Knotting: denser, almost continuous twist on highlight only.
    knotting: {
      width: 2.85,
      dashArray: [2.95, 0.28] as [number, number],
      bodyContinuous: true,
      shadowContinuous: true,
    },
    // Votes: short outer stitches on body+highlight; continuous shadow link.
    vote: {
      width: 1.9,
      dashArray: [0.42, 0.9] as [number, number],
      bodyContinuous: false,
      shadowContinuous: true,
    },
  },
  // Back-compat aliases used by older call sites/tests.
  haloColor: "rgba(36, 22, 15, 0.42)",
  haloWidth: 2.9,
  haloBlur: 1.05,
  haloOpacityFactor: 0.58,
  mainColor: "#76523d",
  mainWidth: 2.35,
} as const;

/** Hard cap on sampled curve points (no unbounded polylines). */
export const EDGE_CURVE_MAX_SAMPLES = 24;
/** Minimum samples so short curves still round-cap cleanly. */
export const EDGE_CURVE_MIN_SAMPLES = 4;
/**
 * Chord length (degrees) at which length scaling reaches full bulge.
 * Shorter paths scale down toward nearly straight.
 */
export const EDGE_CURVE_FULL_LENGTH_DEG = 0.12;
/** Absolute lateral bulge cap in degrees (screen-distance stand-in). */
export const EDGE_CURVE_MAX_BULGE_DEG = 0.045;

/**
 * Tension / material profile per Fadenart. Geometry only — paint width lives
 * in {@link EDGE_VISUAL_STYLE}. Higher tension → straighter mid arc.
 */
export type ThreadCurveProfile = {
  /** 0 = soft wide arc, 1 = taut nearly straight. */
  tension: number;
  /** Max lateral bulge as fraction of chord before length/tension scaling. */
  maxBulgeFraction: number;
  /** 0 = symmetric; positive biases the mid arc slightly toward the target. */
  asymmetry: number;
  /** 0.5–1: how tightly exit/entry hug the chord direction. */
  approachStraightness: number;
  /**
   * When true, large independent curves are suppressed without a shared
   * subject corridor (`faden_subject_id`).
   */
  corridorBound: boolean;
};

export const THREAD_CURVE_PROFILES: Record<string, ThreadCurveProfile> = {
  // Knüpffaden: taut, lightly curved, sturdy.
  knotting: {
    tension: 0.84,
    maxBulgeFraction: 0.075,
    asymmetry: 0.06,
    approachStraightness: 0.9,
    corridorBound: false,
  },
  // Gespräch: soft, wide, lightly asymmetric.
  conversation: {
    tension: 0.42,
    maxBulgeFraction: 0.2,
    asymmetry: 0.24,
    approachStraightness: 0.72,
    corridorBound: false,
  },
  // Antrag: calm, medium tension.
  proposal: {
    tension: 0.64,
    maxBulgeFraction: 0.12,
    asymmetry: 0.1,
    approachStraightness: 0.82,
    corridorBound: true,
  },
  // Stimme: no independent large curve; shares proposal corridor when bound.
  vote: {
    tension: 0.9,
    maxBulgeFraction: 0.045,
    asymmetry: 0.05,
    approachStraightness: 0.93,
    corridorBound: true,
  },
  legacy: {
    tension: 0.66,
    maxBulgeFraction: 0.11,
    asymmetry: 0.1,
    approachStraightness: 0.8,
    corridorBound: false,
  },
};

export type ThreadCurveOptions = {
  fadenType?: string;
  /** Stable thread identity (edge id) for micro-variation. */
  threadId?: string;
  /**
   * Shared approach corridor key from `faden_subject_id` (proposal/vote).
   * Absent → safe per-thread fallback, never invents a relationship.
   */
  subjectId?: string | null;
};

/**
 * Multi-colour WebGL line segments share exact endpoints. Round caps leave a
 * proven hairline seam between adjacent coloured features. Each interior join
 * therefore extends by this fraction of the *local segment length* on the
 * trailing (start) side only — a stable geometric overlap, not a share of the
 * full path and not a walking gradient. Scaling to segment length keeps the
 * visible colour band stable across short/long geometries and multi-colour
 * braids; one-sided extension avoids double-sided order dominance.
 */
export const THEME_SEGMENT_SEAM_OVERLAP = 0.012;

/**
 * Absolute progress-space overlap for one multi-colour braid with
 * `segmentCount` equal segments. Always a fraction of the local segment
 * length, never of the full path; zero for single-segment / mono-colour.
 */
export function themeSegmentSeamOverlapProgress(segmentCount: number): number {
  if (!Number.isFinite(segmentCount) || segmentCount < 2) return 0;
  const segmentLength = 1 / segmentCount;
  // Hard cap: never more than a quarter of the segment so start stays strictly
  // before end even if THEME_SEGMENT_SEAM_OVERLAP is raised aggressively.
  return Math.min(
    THEME_SEGMENT_SEAM_OVERLAP * segmentLength,
    segmentLength * 0.25,
  );
}

const EDGE_LAYER_VARIANTS = [
  {
    fadenType: "legacy",
    shadowLayerId: LAYERS.EDGES_SHADOW_LAYER,
    layerId: LAYERS.EDGES_LAYER,
    highlightLayerId: LAYERS.EDGES_HIGHLIGHT_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.bodyColor,
    width: EDGE_VISUAL_STYLE.bodyWidth,
    dashArray: EDGE_VISUAL_STYLE.dashArray,
    bodyContinuous: true,
    shadowContinuous: true,
  },
  {
    fadenType: "conversation",
    shadowLayerId: LAYERS.EDGES_CONVERSATION_SHADOW_LAYER,
    layerId: LAYERS.EDGES_CONVERSATION_LAYER,
    highlightLayerId: LAYERS.EDGES_CONVERSATION_HIGHLIGHT_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.bodyColor,
    ...EDGE_VISUAL_STYLE.byType.conversation,
  },
  {
    fadenType: "proposal",
    shadowLayerId: LAYERS.EDGES_PROPOSAL_SHADOW_LAYER,
    layerId: LAYERS.EDGES_PROPOSAL_LAYER,
    highlightLayerId: LAYERS.EDGES_PROPOSAL_HIGHLIGHT_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.bodyColor,
    ...EDGE_VISUAL_STYLE.byType.proposal,
  },
  {
    fadenType: "knotting",
    shadowLayerId: LAYERS.EDGES_KNOTTING_SHADOW_LAYER,
    layerId: LAYERS.EDGES_KNOTTING_LAYER,
    highlightLayerId: LAYERS.EDGES_KNOTTING_HIGHLIGHT_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.bodyColor,
    ...EDGE_VISUAL_STYLE.byType.knotting,
  },
  {
    fadenType: "vote",
    shadowLayerId: LAYERS.EDGES_VOTE_SHADOW_LAYER,
    layerId: LAYERS.EDGES_VOTE_LAYER,
    highlightLayerId: LAYERS.EDGES_VOTE_HIGHLIGHT_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.bodyColor,
    ...EDGE_VISUAL_STYLE.byType.vote,
  },
] as const;

/**
 * Every layer a complete typed Faden style owns, derived from the variants
 * themselves so a new thread type cannot be forgotten here. Shadow → body →
 * highlight, matching the yarn render order.
 */
export const EDGE_THREAD_LAYER_IDS: readonly string[] =
  EDGE_LAYER_VARIANTS.flatMap((variant) => [
    variant.shadowLayerId,
    variant.layerId,
    variant.highlightLayerId,
  ]);

/** Minimal surface a style-readiness check needs; keeps it unit-testable. */
export type EdgeStyleProbe = {
  getSource: (id: string) => unknown;
  getLayer: (id: string) => unknown;
};

/**
 * The edge style counts as fully rehydrated only when the shared source and
 * *every* canonical yarn layer exists. Checking the source plus two legacy
 * layers would call a half-restored style ready and silently drop typed threads.
 */
export function hasCompleteEdgeThreadStyle(
  map: EdgeStyleProbe | null | undefined,
): boolean {
  if (!map || !map.getSource(LAYERS.EDGES_SOURCE)) return false;
  return EDGE_THREAD_LAYER_IDS.every((layerId) =>
    Boolean(map.getLayer(layerId)),
  );
}

function targetThemeColors(point: MapEntityViewModel): string[] | undefined {
  if (point.type !== "node" && point.type !== "webgemeindezentrum") {
    return undefined;
  }
  if (point.weave) {
    return targetThemePalette(point.weave);
  }
  return [primaryWeaveColor(point)];
}

export type LngLatTuple = [number, number];

/**
 * One coloured strand along the shared curve. Coordinates are a bounded
 * polyline on the canonical path (not a straight capsule pair).
 */
export type ThemedLineSegment = {
  coordinates: LngLatTuple[];
  color: string;
};

// ─── Deterministic thread curve geometry ────────────────────────────────────

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

/** Smoothstep from 0→1 over [edge0, edge1]. */
function smoothstep(edge0: number, edge1: number, x: number): number {
  if (edge1 <= edge0) return x >= edge1 ? 1 : 0;
  const t = clamp01((x - edge0) / (edge1 - edge0));
  return t * t * (3 - 2 * t);
}

/** FNV-1a style hash → unit interval in [0, 1). Deterministic, no RNG. */
export function hashUnit(input: string): number {
  let hash = 2166136261;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967296;
}

export function threadCurveProfile(
  fadenType: string | undefined,
): ThreadCurveProfile {
  if (fadenType && fadenType in THREAD_CURVE_PROFILES) {
    return THREAD_CURVE_PROFILES[fadenType];
  }
  return THREAD_CURVE_PROFILES.legacy;
}

/**
 * Shared approach corridor key. Proposal/vote with a real `faden_subject_id`
 * share bend side and base arc; otherwise each thread keeps a private fallback.
 */
export function threadCorridorKey(options: ThreadCurveOptions): string {
  const subject = options.subjectId?.trim();
  if (subject) return `subject:${subject}`;
  const thread = options.threadId?.trim();
  if (thread) return `thread:${thread}`;
  return "thread:anon";
}

function chordLength(source: LngLatTuple, target: LngLatTuple): number {
  const dx = target[0] - source[0];
  const dy = target[1] - source[1];
  return Math.hypot(dx, dy);
}

function cubicBezierPoint(
  p0: LngLatTuple,
  p1: LngLatTuple,
  p2: LngLatTuple,
  p3: LngLatTuple,
  t: number,
): LngLatTuple {
  const u = 1 - t;
  const tt = t * t;
  const uu = u * u;
  const uuu = uu * u;
  const ttt = tt * t;
  return [
    uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0],
    uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1],
  ];
}

/**
 * Deterministic cubic Bezier control points for one thread. Source and target
 * stay exact endpoints. Exit/entry hug the chord; one wide natural mid arc;
 * short paths nearly straight; bend side stable from corridor identity.
 * No waves, no physics, no per-frame randomness.
 */
export function threadCurveControlPoints(
  source: LngLatTuple,
  target: LngLatTuple,
  options: ThreadCurveOptions = {},
): { p0: LngLatTuple; p1: LngLatTuple; p2: LngLatTuple; p3: LngLatTuple } {
  const profile = threadCurveProfile(options.fadenType);
  const dx = target[0] - source[0];
  const dy = target[1] - source[1];
  const length = Math.hypot(dx, dy);

  if (!(length > 0) || !Number.isFinite(length)) {
    return { p0: source, p1: source, p2: target, p3: target };
  }

  const alongX = dx / length;
  const alongY = dy / length;
  // Perpendicular (left of direction). Bend side flips this unit.
  const corridor = threadCorridorKey(options);
  const bendSide = hashUnit(`${corridor}:side`) < 0.5 ? -1 : 1;
  const perpX = -alongY * bendSide;
  const perpY = alongX * bendSide;

  // Micro-variation from thread id so stacked subject threads share corridor
  // but do not become identical capsule copies.
  const variationSeed = options.threadId?.trim() || corridor;
  const micro = (hashUnit(`${variationSeed}:var`) - 0.5) * 2;
  const microScale = options.subjectId?.trim() ? 0.1 : 0.28;

  // Short paths almost straight; longer paths approach full profile bulge.
  const lengthScale = smoothstep(0, EDGE_CURVE_FULL_LENGTH_DEG, length);
  const tensionScale = 1 - clamp01(profile.tension);
  let bulge = profile.maxBulgeFraction * length * tensionScale * lengthScale;
  bulge = Math.min(bulge, EDGE_CURVE_MAX_BULGE_DEG);
  // Corridor-bound types without a proven subject stay near-linear.
  if (profile.corridorBound && !options.subjectId?.trim()) {
    bulge *= 0.45;
  }
  bulge *= 1 + micro * microScale * 0.2;

  // Handle placement: closer to ends + lower lateral → nearly straight exit/entry.
  const handleT = 0.2 + 0.12 * clamp01(profile.approachStraightness); // ~0.20–0.32 along chord
  const lateralAtHandle =
    0.32 + 0.45 * (1 - clamp01(profile.approachStraightness));
  const asym = clamp01(profile.asymmetry);
  const h1 = bulge * lateralAtHandle * (1 - asym * 0.35) * (1 + micro * 0.08);
  const h2 = bulge * lateralAtHandle * (1 + asym * 0.45) * (1 - micro * 0.06);

  const p1: LngLatTuple = [
    source[0] + alongX * length * handleT + perpX * h1,
    source[1] + alongY * length * handleT + perpY * h1,
  ];
  const p2: LngLatTuple = [
    target[0] - alongX * length * handleT + perpX * h2,
    target[1] - alongY * length * handleT + perpY * h2,
  ];

  return { p0: source, p1, p2, p3: target };
}

/**
 * Bounded sample count from chord length and profile softness. Never exceeds
 * {@link EDGE_CURVE_MAX_SAMPLES}; never recalculates per animation frame beyond
 * progress clipping of this fixed polyline.
 */
export function threadCurveSampleCount(
  source: LngLatTuple,
  target: LngLatTuple,
  options: ThreadCurveOptions = {},
): number {
  const length = chordLength(source, target);
  if (!(length > 0) || !Number.isFinite(length)) return 2;
  const profile = threadCurveProfile(options.fadenType);
  const softness = 1 - clamp01(profile.tension);
  const density =
    EDGE_CURVE_MIN_SAMPLES +
    Math.ceil((length / EDGE_CURVE_FULL_LENGTH_DEG) * 10) +
    Math.ceil(softness * 6);
  return Math.max(
    EDGE_CURVE_MIN_SAMPLES,
    Math.min(EDGE_CURVE_MAX_SAMPLES, density),
  );
}

/**
 * Sample the canonical thread curve. First and last points are exactly source
 * and target (no float drift on endpoints).
 */
export function sampleThreadCurve(
  source: LngLatTuple,
  target: LngLatTuple,
  options: ThreadCurveOptions = {},
): LngLatTuple[] {
  const length = chordLength(source, target);
  if (!(length > 0) || !Number.isFinite(length)) {
    return [source, target];
  }
  const { p0, p1, p2, p3 } = threadCurveControlPoints(source, target, options);
  const count = threadCurveSampleCount(source, target, options);
  const points: LngLatTuple[] = new Array(count);
  for (let index = 0; index < count; index += 1) {
    if (index === 0) {
      points[index] = [source[0], source[1]];
      continue;
    }
    if (index === count - 1) {
      points[index] = [target[0], target[1]];
      continue;
    }
    const t = index / (count - 1);
    points[index] = cubicBezierPoint(p0, p1, p2, p3, t);
  }
  return points;
}

function polylineArcState(points: readonly LngLatTuple[]): {
  cumulative: number[];
  total: number;
} {
  const cumulative = new Array(points.length);
  cumulative[0] = 0;
  for (let index = 1; index < points.length; index += 1) {
    const prev = points[index - 1];
    const curr = points[index];
    cumulative[index] =
      cumulative[index - 1] + Math.hypot(curr[0] - prev[0], curr[1] - prev[1]);
  }
  return { cumulative, total: cumulative[cumulative.length - 1] ?? 0 };
}

function interpolateAlongSegment(
  a: LngLatTuple,
  b: LngLatTuple,
  t: number,
): LngLatTuple {
  const bounded = clamp01(t);
  return [a[0] + (b[0] - a[0]) * bounded, a[1] + (b[1] - a[1]) * bounded];
}

/** Point at arc-length progress in [0, 1] on a sampled polyline. */
export function pointAtArcProgress(
  points: readonly LngLatTuple[],
  progress: number,
): LngLatTuple {
  if (points.length === 0) return [0, 0];
  if (points.length === 1) return points[0];
  const bounded = clamp01(progress);
  if (bounded <= 0) return [points[0][0], points[0][1]];
  if (bounded >= 1) {
    const last = points[points.length - 1];
    return [last[0], last[1]];
  }
  const { cumulative, total } = polylineArcState(points);
  if (!(total > 0)) return [points[0][0], points[0][1]];
  const target = bounded * total;
  for (let index = 1; index < points.length; index += 1) {
    if (cumulative[index] + 1e-15 < target) continue;
    const span = cumulative[index] - cumulative[index - 1];
    const local = span > 0 ? (target - cumulative[index - 1]) / span : 0;
    return interpolateAlongSegment(points[index - 1], points[index], local);
  }
  const last = points[points.length - 1];
  return [last[0], last[1]];
}

/**
 * Extract the sub-polyline covering arc progress [start, end] on the shared
 * sample. Endpoints are interpolated exactly; interior samples retained.
 */
export function subPolylineByArcProgress(
  points: readonly LngLatTuple[],
  startProgress: number,
  endProgress: number,
): LngLatTuple[] {
  const start = clamp01(startProgress);
  const end = clamp01(endProgress);
  if (!(start < end) || points.length === 0) return [];
  if (points.length === 1) return [[points[0][0], points[0][1]]];

  const { cumulative, total } = polylineArcState(points);
  if (!(total > 0)) {
    return [
      [points[0][0], points[0][1]],
      [points[points.length - 1][0], points[points.length - 1][1]],
    ];
  }

  const startDist = start * total;
  const endDist = end * total;
  const result: LngLatTuple[] = [];
  result.push(pointAtArcProgress(points, start));

  for (let index = 1; index < points.length - 1; index += 1) {
    const d = cumulative[index];
    if (d > startDist + 1e-12 && d < endDist - 1e-12) {
      result.push([points[index][0], points[index][1]]);
    }
  }

  const tip = pointAtArcProgress(points, end);
  const last = result[result.length - 1];
  if (
    !last ||
    Math.hypot(tip[0] - last[0], tip[1] - last[1]) > 1e-12 ||
    result.length === 1
  ) {
    result.push(tip);
  }
  return result;
}

/**
 * Controlled multi-theme braid along the *actual curve length*. Segment colour
 * boundaries are fixed in arc-length progress space so motion clipping never
 * walks seams. Adjacent multi-colour segments overlap by
 * {@link themeSegmentSeamOverlapProgress} (fraction of local segment length).
 */
export function buildThemedLineSegments(
  source: LngLatTuple,
  target: LngLatTuple,
  colors: readonly string[],
  options: ThreadCurveOptions = {},
): ThemedLineSegment[] {
  const palette = colors.slice(0, MAX_X_CORE_THEMES);
  const path = sampleThreadCurve(source, target, options);

  if (palette.length <= 1) {
    return [
      {
        coordinates: path,
        color: palette[0] ?? "#76523d",
      },
    ];
  }

  // Two segments per colour so the repeating weave reads along the whole edge.
  const segmentCount = palette.length * 2;
  const seamOverlap = themeSegmentSeamOverlapProgress(segmentCount);
  const segments: ThemedLineSegment[] = [];
  for (let index = 0; index < segmentCount; index += 1) {
    const t0 = index / segmentCount;
    const t1 = (index + 1) / segmentCount;
    // One-sided: pull the start of each non-first segment back over the prior
    // join only. Nominal ends stay exact so later paint order does not get a
    // second, full-path-scaled invasion into the next colour.
    const start =
      index === 0 ? t0 : Math.max(0, Math.min(t1, t0 - seamOverlap));
    const end = t1;
    if (!(start < end)) continue;
    const coordinates = subPolylineByArcProgress(path, start, end);
    if (coordinates.length < 2) continue;
    segments.push({
      coordinates,
      color: palette[index % palette.length],
    });
  }
  return segments;
}

/**
 * Same stable full-path arc-length segments as {@link buildThemedLineSegments},
 * clipped to draw progress in [0, 1] measured from source toward target along
 * the curve. Colour boundaries stay fixed; only the visible length changes.
 */
export function buildProgressClippedThemeSegments(
  source: LngLatTuple,
  target: LngLatTuple,
  colors: readonly string[],
  progress: number,
  options: ThreadCurveOptions = {},
): ThemedLineSegment[] {
  const bounded = clamp01(progress);
  if (bounded <= 0) return [];
  const full = buildThemedLineSegments(source, target, colors, options);
  if (bounded >= 1) return full;

  const palette = colors.slice(0, MAX_X_CORE_THEMES);
  const path = sampleThreadCurve(source, target, options);

  if (palette.length <= 1) {
    return [
      {
        coordinates: subPolylineByArcProgress(path, 0, bounded),
        color: full[0]?.color ?? palette[0] ?? "#76523d",
      },
    ];
  }

  const segmentCount = full.length;
  const seamOverlap = themeSegmentSeamOverlapProgress(segmentCount);
  const clipped: ThemedLineSegment[] = [];
  for (let index = 0; index < segmentCount; index += 1) {
    const t0 = index / segmentCount;
    const t1 = (index + 1) / segmentCount;
    if (bounded <= t0) break;
    const start =
      index === 0 ? t0 : Math.max(0, Math.min(t1, t0 - seamOverlap));
    const end = Math.min(bounded, t1);
    if (!(start < end)) continue;
    const coordinates = subPolylineByArcProgress(path, start, end);
    if (coordinates.length < 2) continue;
    clipped.push({
      coordinates,
      color: full[index].color,
    });
  }
  return clipped;
}

/** Structural paint values shared by static threads and edge motion. */
export function edgeThreadVisual(fadenType: string | undefined): {
  width: number;
  dashArray: [number, number];
  bodyContinuous: boolean;
  shadowContinuous: boolean;
} {
  if (fadenType && fadenType in EDGE_VISUAL_STYLE.byType) {
    const style =
      EDGE_VISUAL_STYLE.byType[
        fadenType as keyof typeof EDGE_VISUAL_STYLE.byType
      ];
    return {
      width: style.width,
      dashArray: [...style.dashArray] as [number, number],
      bodyContinuous: style.bodyContinuous,
      shadowContinuous: style.shadowContinuous,
    };
  }
  return {
    width: EDGE_VISUAL_STYLE.bodyWidth,
    dashArray: [...EDGE_VISUAL_STYLE.dashArray] as [number, number],
    bodyContinuous: true,
    shadowContinuous: true,
  };
}

/**
 * Canonical thread variants used by both static projection and motion overlay.
 * Layer ids remain source-specific; structure (type, width, dash, continuity)
 * is shared so the two paths cannot drift.
 */
export const EDGE_THREAD_VARIANTS = EDGE_LAYER_VARIANTS.map((variant) => ({
  fadenType: variant.fadenType,
  width: variant.width,
  dashArray: [...variant.dashArray] as [number, number],
  bodyContinuous: variant.bodyContinuous,
  shadowContinuous: variant.shadowContinuous,
  fallbackColor: variant.fallbackColor,
})) as ReadonlyArray<{
  fadenType: (typeof EDGE_LAYER_VARIANTS)[number]["fadenType"];
  width: number;
  dashArray: [number, number];
  bodyContinuous: boolean;
  shadowContinuous: boolean;
  fallbackColor: string;
}>;

/**
 * Resolve endpoints for line geometry. Coordinates are the entity lat/lon
 * which, with center-anchored markers, is the visible knot/spool midpoint.
 * Webgemeindezentren remain addressable via `faden_endpoint_id`.
 */
export function buildEndpointIndex(
  points: readonly MapEntityViewModel[],
): Map<string, MapEntityViewModel> {
  const pointMap = new Map<string, MapEntityViewModel>();
  for (const point of points) {
    pointMap.set(point.id, point);
    if (point.type === "webgemeindezentrum") {
      pointMap.set(point.faden_endpoint_id, point);
    }
  }
  return pointMap;
}

function curveOptionsForEdge(edge: MapEdge): ThreadCurveOptions {
  return {
    fadenType: edge.faden_type ?? "legacy",
    threadId: edge.id,
    subjectId: edge.faden_subject_id ?? null,
  };
}

export function buildEdgeFeatures(
  edges: MapEdge[],
  points: MapEntityViewModel[],
  showEdges: boolean,
  nowMs: number,
): GeoJSON.Feature<GeoJSON.LineString>[] {
  if (!showEdges || edges.length === 0) return [];

  const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
  const pointMap = buildEndpointIndex(points);

  for (const edge of edges) {
    const opacity = edgeOpacityAt(edge, nowMs);
    if (opacity <= 0) continue;

    const source = pointMap.get(edge.source_id);
    const target = pointMap.get(edge.target_id);
    // Missing or geographically invalid endpoints must never produce a line;
    // MapLibre would still draw NaN/out-of-range coordinates as garbage.
    if (!source || !target) continue;
    if (
      !isValidMapCoordinate(source.lon, source.lat) ||
      !isValidMapCoordinate(target.lon, target.lat)
    ) {
      continue;
    }

    const sourceLngLat: LngLatTuple = [source.lon, source.lat];
    const targetLngLat: LngLatTuple = [target.lon, target.lat];
    const curveOptions = curveOptionsForEdge(edge);
    const themeColors = targetThemeColors(target);
    const palette = themeColors ?? [];
    const segments = themeColors
      ? buildThemedLineSegments(
          sourceLngLat,
          targetLngLat,
          themeColors,
          curveOptions,
        )
      : [
          {
            coordinates: sampleThreadCurve(
              sourceLngLat,
              targetLngLat,
              curveOptions,
            ),
            color: undefined as string | undefined,
          },
        ];

    for (let strand = 0; strand < segments.length; strand += 1) {
      const segment = segments[strand];
      if (segment.coordinates.length < 2) continue;
      features.push({
        type: "Feature",
        geometry: {
          type: "LineString",
          coordinates: segment.coordinates,
        },
        properties: {
          id: edge.id,
          kind: edge.edge_kind,
          fadenType: edge.faden_type ?? "legacy",
          fadenSubjectId: edge.faden_subject_id ?? null,
          ...(segment.color ? { themeColor: segment.color } : {}),
          ...(palette.length ? { themeColors: palette } : {}),
          themeStrand: strand,
          themeStrandCount: segments.length,
          opacity,
        },
      });
    }
  }

  return features;
}

function applyDashPaint(
  paint: LineLayerSpecification["paint"],
  continuous: boolean,
  dashArray: [number, number],
): LineLayerSpecification["paint"] {
  if (continuous || !paint) return paint;
  return { ...paint, "line-dasharray": dashArray };
}

export function buildEdgeLayerSpecifications(
  sourceId: string = LAYERS.EDGES_SOURCE,
): LineLayerSpecification[] {
  const opacity: ExpressionSpecification = [
    "coalesce",
    ["to-number", ["get", "opacity"]],
    0,
  ];
  const shadowOpacity: ExpressionSpecification = [
    "*",
    opacity,
    EDGE_VISUAL_STYLE.shadowOpacityFactor,
  ];
  const highlightOpacity: ExpressionSpecification = [
    "*",
    opacity,
    EDGE_VISUAL_STYLE.highlightOpacityFactor,
  ];
  const commonLayout: LineLayerSpecification["layout"] = {
    "line-join": "round",
    "line-cap": "round",
  };

  return EDGE_LAYER_VARIANTS.flatMap((variant) => {
    const filter = [
      "==",
      ["get", "fadenType"],
      variant.fadenType,
    ] as LineLayerSpecification["filter"];
    const dashArray = [...variant.dashArray] as [number, number];
    const bodyWidth = variant.width;
    const shadowLayer: LineLayerSpecification = {
      id: variant.shadowLayerId,
      type: "line",
      source: sourceId,
      filter,
      layout: commonLayout,
      paint: applyDashPaint(
        {
          "line-color": EDGE_VISUAL_STYLE.shadowColor,
          "line-width": bodyWidth + EDGE_VISUAL_STYLE.shadowWidthExtra,
          "line-blur": EDGE_VISUAL_STYLE.shadowBlur,
          "line-opacity": shadowOpacity,
        },
        variant.shadowContinuous,
        dashArray,
      ),
    };
    const bodyLayer: LineLayerSpecification = {
      id: variant.layerId,
      type: "line",
      source: sourceId,
      filter,
      layout: commonLayout,
      paint: applyDashPaint(
        {
          "line-color": [
            "coalesce",
            ["get", "themeColor"],
            variant.fallbackColor,
          ],
          "line-width": bodyWidth,
          "line-opacity": opacity,
        },
        variant.bodyContinuous,
        dashArray,
      ),
    };
    // Highlight always carries the braid/fiber rhythm.
    const highlightLayer: LineLayerSpecification = {
      id: variant.highlightLayerId,
      type: "line",
      source: sourceId,
      filter,
      layout: commonLayout,
      paint: {
        "line-color": EDGE_VISUAL_STYLE.highlightColor,
        "line-width": Math.max(
          0.55,
          bodyWidth * EDGE_VISUAL_STYLE.highlightWidthFactor,
        ),
        "line-opacity": highlightOpacity,
        "line-dasharray": dashArray,
      },
    };
    return [shadowLayer, bodyLayer, highlightLayer];
  });
}

export function updateEdges(
  map: MapLibreMap,
  edges: MapEdge[],
  points: MapEntityViewModel[],
  showEdges: boolean,
  nowMs = Date.now(),
) {
  const sourceId = LAYERS.EDGES_SOURCE;
  const source = map.getSource(sourceId) as GeoJSONSource | undefined;
  const features = buildEdgeFeatures(edges, points, showEdges, nowMs);
  const geoJsonData: GeoJSON.FeatureCollection<GeoJSON.LineString> = {
    type: "FeatureCollection",
    features,
  };

  // Always install the canonical source and every typed layer, even with an
  // empty FeatureCollection. Otherwise a style switch while no lines are
  // visible never rehydrates the full layer set and hasCompleteEdgeThreadStyle
  // keeps scheduling forever.
  if (source) {
    source.setData(geoJsonData);
  } else {
    map.addSource(sourceId, { type: "geojson", data: geoJsonData });
  }
  ensureEdgeLayers(map, sourceId);
}

function ensureEdgeLayers(map: MapLibreMap, sourceId: string) {
  const firstSymbolId = map
    .getStyle()
    ?.layers?.find((layer) => layer.type === "symbol")?.id;
  const specifications = buildEdgeLayerSpecifications(sourceId);

  // Install in order: shadow → body → highlight per type.
  for (let index = 0; index < specifications.length; index += 3) {
    const shadowLayer = specifications[index];
    const bodyLayer = specifications[index + 1];
    const highlightLayer = specifications[index + 2];
    const hasShadow = Boolean(map.getLayer(shadowLayer.id));
    const hasBody = Boolean(map.getLayer(bodyLayer.id));
    const hasHighlight = Boolean(map.getLayer(highlightLayer.id));

    if (!hasShadow) {
      const before = hasBody
        ? bodyLayer.id
        : hasHighlight
          ? highlightLayer.id
          : firstSymbolId;
      map.addLayer(shadowLayer, before);
    }
    if (!hasBody) {
      const before = hasHighlight ? highlightLayer.id : firstSymbolId;
      map.addLayer(bodyLayer, before);
    }
    if (!hasHighlight) {
      map.addLayer(highlightLayer, firstSymbolId);
    }
  }
}
