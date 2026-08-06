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
 * Spherical Web Mercator radius (EPSG:3857 convention). Geometry (chord,
 * normal, bulge, sampling) is computed in this projected plane — not in raw
 * lon/lat degrees and not in MapLibre CSS pixels.
 */
export const EDGE_CURVE_MERCATOR_RADIUS_M = 6378137;
/** Web Mercator latitude clamp (degrees); only internal projection. */
export const EDGE_CURVE_MERCATOR_MAX_LAT = 85.05112878;
/**
 * Projected chord length (metres) at which length scaling reaches full bulge.
 * Shorter paths scale down toward nearly straight.
 */
export const EDGE_CURVE_FULL_LENGTH_M = 12_000;
/** Absolute lateral bulge cap in projected Web-Mercator metres. */
export const EDGE_CURVE_MAX_BULGE_M = 5_000;
/** Max Bezier handle length as a fraction of projected chord (no loops). */
export const EDGE_CURVE_MAX_HANDLE_FRACTION = 0.32;
/**
 * Absolute Bezier handle cap in projected Web-Mercator metres. Prevents long
 * multi-source approaches from overshooting or looping at the target.
 */
export const EDGE_CURVE_MAX_HANDLE_M = 3_200;

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
/** Projected plane point (Web Mercator metres). */
export type ProjectedPoint = readonly [number, number];

/**
 * One coloured strand along the shared curve. Coordinates are a bounded
 * polyline on the canonical path (not a straight capsule pair).
 */
export type ThemedLineSegment = {
  coordinates: LngLatTuple[];
  color: string;
};

/**
 * Fixed multi-colour segment metadata in arc-progress space [0, 1].
 * Built once with the path; motion never recomputes colour seams.
 */
export type ThreadPathSegmentMeta = {
  readonly color: string;
  /** Arc progress at painted start (includes one-sided seam pullback). */
  readonly startProgress: number;
  /** Arc progress at painted end (nominal colour boundary). */
  readonly endProgress: number;
};

/**
 * Immutable canonical thread path. Built once per static feature or
 * ActiveMotion; frames only clip progress and wrap GeoJSON shells.
 *
 * Arc metrics (`cumulative`, `totalLength`) are Web-Mercator metres from
 * {@link projectedSamples}. GeoJSON {@link samples} keep exact source/target
 * lon/lat; progress/clipping/motion tip share this single prebuilt state.
 */
export type ThreadPathState = {
  /** GeoJSON polyline (exact delivered endpoints; intermediates may unwrap). */
  readonly samples: readonly LngLatTuple[];
  /**
   * Projected Web-Mercator samples aligned 1:1 with {@link samples}. Used for
   * cumulative arc length, progress, and tip interpolation — never recomputed
   * in RAF.
   */
  readonly projectedSamples: readonly ProjectedPoint[];
  /** Cumulative arc length along {@link projectedSamples} (metres). */
  readonly cumulative: readonly number[];
  /** Total path length in projected metres. */
  readonly totalLength: number;
  readonly segments: readonly ThreadPathSegmentMeta[];
  /** Monotonic build counter for cache instrumentation. */
  readonly buildSerial: number;
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
 * Shared approach corridor key. A real `faden_subject_id` groups antrag-related
 * threads into one corridor; otherwise each thread keeps a typed private
 * fallback. Never invents a subject relationship.
 */
export function threadCorridorKey(options: ThreadCurveOptions): string {
  const subject = options.subjectId?.trim();
  if (subject) return `subject:${subject}`;
  const thread = options.threadId?.trim();
  if (thread) return `thread:${thread}`;
  const faden = options.fadenType?.trim() || "legacy";
  return `thread:anon:${faden}`;
}

/** Shortest signed longitude delta in (-180, 180]. Avoids the 340° long way. */
export function shortestLongitudeDelta(fromLng: number, toLng: number): number {
  if (!Number.isFinite(fromLng) || !Number.isFinite(toLng)) return 0;
  let delta = toLng - fromLng;
  delta = ((((delta + 180) % 360) + 360) % 360) - 180;
  // Map exact -180 onto +180 so the unwrap side stays stable for 180° ties.
  return delta === -180 ? 180 : delta;
}

/** Project lon/lat into spherical Web Mercator metres (lat clamped internally). */
export function projectLngLatToMercator(
  lng: number,
  lat: number,
): [number, number] {
  const clampedLat = Math.max(
    -EDGE_CURVE_MERCATOR_MAX_LAT,
    Math.min(EDGE_CURVE_MERCATOR_MAX_LAT, lat),
  );
  const x = (lng * Math.PI * EDGE_CURVE_MERCATOR_RADIUS_M) / 180;
  const latRad = (clampedLat * Math.PI) / 180;
  const y =
    Math.log(Math.tan(Math.PI / 4 + latRad / 2)) * EDGE_CURVE_MERCATOR_RADIUS_M;
  return [x, y];
}

/** Inverse of {@link projectLngLatToMercator}. */
export function unprojectMercatorToLngLat(x: number, y: number): LngLatTuple {
  const lng = (x / EDGE_CURVE_MERCATOR_RADIUS_M) * (180 / Math.PI);
  const lat =
    (2 * Math.atan(Math.exp(y / EDGE_CURVE_MERCATOR_RADIUS_M)) - Math.PI / 2) *
    (180 / Math.PI);
  return [lng, lat];
}

/**
 * Projected chord using the shortest unwrapped longitude path. Endpoints stay
 * the caller's lon/lat; only the internal target longitude is unwrapped.
 */
export function projectedChord(
  source: LngLatTuple,
  target: LngLatTuple,
): {
  sourceXY: [number, number];
  targetXY: [number, number];
  dx: number;
  dy: number;
  length: number;
  unwrappedTargetLng: number;
} {
  const unwrappedTargetLng =
    source[0] + shortestLongitudeDelta(source[0], target[0]);
  const sourceXY = projectLngLatToMercator(source[0], source[1]);
  const targetXY = projectLngLatToMercator(unwrappedTargetLng, target[1]);
  const dx = targetXY[0] - sourceXY[0];
  const dy = targetXY[1] - sourceXY[1];
  const length = Math.hypot(dx, dy);
  return { sourceXY, targetXY, dx, dy, length, unwrappedTargetLng };
}

function cubicBezierPoint2(
  p0: ProjectedPoint,
  p1: ProjectedPoint,
  p2: ProjectedPoint,
  p3: ProjectedPoint,
  t: number,
): [number, number] {
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

/** Analytic derivative of {@link cubicBezierPoint2} at `t` (projected metres/unit-t). */
function cubicBezierTangent2(
  p0: ProjectedPoint,
  p1: ProjectedPoint,
  p2: ProjectedPoint,
  p3: ProjectedPoint,
  t: number,
): [number, number] {
  const u = 1 - t;
  return [
    3 * u * u * (p1[0] - p0[0]) +
      6 * u * t * (p2[0] - p1[0]) +
      3 * t * t * (p3[0] - p2[0]),
    3 * u * u * (p1[1] - p0[1]) +
      6 * u * t * (p2[1] - p1[1]) +
      3 * t * t * (p3[1] - p2[1]),
  ];
}

/**
 * Angle in degrees between two projected-plane vectors. A degenerate
 * (near-zero-length) tangent reports the maximum (180°) rather than silently
 * treating an ill-defined direction as flat — callers must not undersample a
 * near-singular point just because a vector happened to collapse to ~0.
 */
function angleBetweenDeg(
  a: readonly [number, number],
  b: readonly [number, number],
): number {
  const na = Math.hypot(a[0], a[1]);
  const nb = Math.hypot(b[0], b[1]);
  if (!(na > 1e-9) || !(nb > 1e-9)) return 180;
  const cos = Math.max(
    -1,
    Math.min(1, (a[0] * b[0] + a[1] * b[1]) / (na * nb)),
  );
  return (Math.acos(cos) * 180) / Math.PI;
}

/**
 * Map a projected sample back to lon/lat. Intermediate longitudes follow the
 * unwrapped short path (may leave [-180, 180] when the chord crosses the
 * antimeridian). Delivered endpoints are forced exact separately.
 *
 * Returns `null` when the projection is non-finite — never masks failure as
 * `[0, 0]` (null-island spike). Callers use safe linear unwrapped fallback.
 * MapLibre may still need a LineString split for world-wrapping display; this
 * path only guarantees finite, short-path-internal geometry without NaN/Infinity.
 */
export function projectedSampleToLngLat(
  x: number,
  y: number,
): LngLatTuple | null {
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    return null;
  }
  const lng = (x / EDGE_CURVE_MERCATOR_RADIUS_M) * (180 / Math.PI);
  const lat =
    (2 * Math.atan(Math.exp(y / EDGE_CURVE_MERCATOR_RADIUS_M)) - Math.PI / 2) *
    (180 / Math.PI);
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
    return null;
  }
  return [lng, lat];
}

/**
 * Linear unwrapped lon/lat interpolation on the short longitude path.
 * Safe finite fallback when unprojection fails — never null-island.
 */
export function interpolateLngLatUnwrapped(
  a: LngLatTuple,
  b: LngLatTuple,
  t: number,
): LngLatTuple {
  const bounded = clamp01(t);
  const dLng = shortestLongitudeDelta(a[0], b[0]);
  return [a[0] + dLng * bounded, a[1] + (b[1] - a[1]) * bounded];
}

/**
 * Deterministic target-local unit axis in projected metres from subject id and
 * target position only — independent of any source chord. Direction is outward
 * from the target toward the last Bezier handle (p2). The final approach unit
 * is the opposite; same subject + same target ⇒ same approach for all sources.
 */
export function threadTargetLocalCorridorAxis(
  target: LngLatTuple,
  subjectId: string,
): [number, number] {
  const subject = subjectId.trim();
  // Micro-degree quantisation so floating noise does not flip the axis.
  const lngKey = Math.round(target[0] * 1e6) / 1e6;
  const latKey = Math.round(target[1] * 1e6) / 1e6;
  const seed = `subject-corridor:${subject}@${lngKey},${latKey}`;
  const angle = hashUnit(seed) * Math.PI * 2;
  return [Math.cos(angle), Math.sin(angle)];
}

/** Clamp Bezier handle length: relative chord fraction and absolute metres. */
function clampHandleLength(chordLength: number, desired: number): number {
  if (!(chordLength > 0) || !Number.isFinite(chordLength)) return 0;
  if (!Number.isFinite(desired) || desired <= 0) return 0;
  return Math.min(
    desired,
    chordLength * EDGE_CURVE_MAX_HANDLE_FRACTION,
    EDGE_CURVE_MAX_HANDLE_M,
  );
}

/**
 * Deterministic cubic Bezier control points in lon/lat. Geometry is solved in
 * the projected plane; source/target endpoints stay exact. Same subject id
 * shares bend side and a target-local approach axis (independent of source);
 * mid tension and private mid handles may still differ. No waves, physics, or
 * per-frame RNG.
 */
export function threadCurveControlPoints(
  source: LngLatTuple,
  target: LngLatTuple,
  options: ThreadCurveOptions = {},
): { p0: LngLatTuple; p1: LngLatTuple; p2: LngLatTuple; p3: LngLatTuple } {
  const projected = threadCurveControlPointsProjected(source, target, options);
  const p1 =
    projectedSampleToLngLat(projected.p1[0], projected.p1[1]) ??
    interpolateLngLatUnwrapped(source, target, 0.25);
  const p2 =
    projectedSampleToLngLat(projected.p2[0], projected.p2[1]) ??
    interpolateLngLatUnwrapped(source, target, 0.75);
  return {
    p0: source,
    p1,
    p2,
    p3: target,
  };
}

/**
 * Projected-plane control points and the shared target approach unit vector.
 * Subject-bound stacks use a target-local corridor (subject + target only);
 * tests measure multi-source alignment here.
 */
export function threadCurveControlPointsProjected(
  source: LngLatTuple,
  target: LngLatTuple,
  options: ThreadCurveOptions = {},
): {
  p0: [number, number];
  p1: [number, number];
  p2: [number, number];
  p3: [number, number];
  /** Unit vector of the target-side approach (from p2 toward p3) in projected m. */
  targetApproach: [number, number];
  /**
   * Outward corridor axis from target toward p2 (unit). Subject-bound: pure
   * target-local; private fallback: chord-relative.
   */
  corridorAxis: [number, number];
  length: number;
} {
  const profile = threadCurveProfile(options.fadenType);
  const { sourceXY, targetXY, dx, dy, length } = projectedChord(source, target);

  if (!(length > 0) || !Number.isFinite(length)) {
    return {
      p0: sourceXY,
      p1: sourceXY,
      p2: targetXY,
      p3: targetXY,
      targetApproach: [1, 0],
      corridorAxis: [1, 0],
      length: 0,
    };
  }

  const alongX = dx / length;
  const alongY = dy / length;
  const corridor = threadCorridorKey(options);
  const subjectRaw = options.subjectId?.trim() ?? "";
  const subjectBound = subjectRaw.length > 0;
  const bendSide = hashUnit(`${corridor}:side`) < 0.5 ? -1 : 1;
  // Chord-normal for mid bulge / source handle (may differ per source).
  const perpX = -alongY * bendSide;
  const perpY = alongX * bendSide;

  // Micro variation from thread id. Subject-bound stacks share only the target
  // approach axis; mid arc may still use small per-thread micro.
  const variationSeed = options.threadId?.trim() || corridor;
  const micro = (hashUnit(`${variationSeed}:var`) - 0.5) * 2;
  const microScale = subjectBound ? 0.08 : 0.28;

  const lengthScale = smoothstep(0, EDGE_CURVE_FULL_LENGTH_M, length);
  const tensionScale = 1 - clamp01(profile.tension);
  let bulge = profile.maxBulgeFraction * length * tensionScale * lengthScale;
  bulge = Math.min(bulge, EDGE_CURVE_MAX_BULGE_M);
  // Corridor-bound types without a proven subject stay near-linear (private
  // fallback must not invent a full shared approach arc).
  if (profile.corridorBound && !subjectBound) {
    bulge *= 0.28;
  }
  bulge *= 1 + micro * microScale * 0.18;

  // Handle length: approach straightness + relative/absolute caps (no loops).
  // Subject-bound: keep target handles short and nearly uniform so mid-arc
  // type tension (bulge/p1) still differentiates without approach overshoot.
  const handleFraction = subjectBound
    ? 0.12 + 0.05 * clamp01(profile.approachStraightness)
    : 0.18 + 0.12 * clamp01(profile.approachStraightness);
  const baseHandle = clampHandleLength(length, length * handleFraction);
  const lateralAtHandle =
    0.28 + 0.4 * (1 - clamp01(profile.approachStraightness));
  const asym = clamp01(profile.asymmetry);

  // ── Target-side corridor axis ────────────────────────────────────────────
  // Subject-bound: deterministic target-local unit from subject + target only
  // (not from the source chord). Private fallback: chord-relative with micro.
  let axisX: number;
  let axisY: number;
  if (subjectBound) {
    const local = threadTargetLocalCorridorAxis(target, subjectRaw);
    axisX = local[0];
    axisY = local[1];
  } else {
    const corridorSkew = (hashUnit(`${corridor}:approach`) - 0.5) * 0.22 * 0.35;
    axisX = -alongX + perpX * corridorSkew;
    axisY = -alongY + perpY * corridorSkew;
    const axisLen = Math.hypot(axisX, axisY);
    if (axisLen > 0) {
      axisX /= axisLen;
      axisY /= axisLen;
    } else {
      axisX = -alongX;
      axisY = -alongY;
    }
    // Private only: blend toward reverse-chord if orientation would reverse.
    const alignment = axisX * -alongX + axisY * -alongY;
    if (alignment < 0.35) {
      axisX = -alongX * 0.85 + axisX * 0.15;
      axisY = -alongY * 0.85 + axisY * 0.15;
      const n = Math.hypot(axisX, axisY) || 1;
      axisX /= n;
      axisY /= n;
    }
  }

  // Source-side handle: type tension + micro (mid arcs may differ by source).
  const h1Lateral =
    bulge * lateralAtHandle * (1 - asym * 0.35) * (1 + micro * 0.08);
  const p1: [number, number] = [
    sourceXY[0] + alongX * baseHandle + perpX * h1Lateral,
    sourceXY[1] + alongY * baseHandle + perpY * h1Lateral,
  ];

  // Target-side handle: last control point on the corridor axis through target.
  // Direction is locked for subject stacks; length stays tightly bounded.
  const typeHandleScale = subjectBound
    ? 0.97 + 0.03 * (1 - clamp01(profile.tension))
    : 0.92 + 0.1 * (1 - clamp01(profile.tension)) + micro * 0.04;
  const sharedHandle = clampHandleLength(length, baseHandle * typeHandleScale);

  let p2: [number, number];
  if (subjectBound) {
    // Strictly on the target-local axis — no perpendicular material offset so
    // the normalised approach is identical for every source.
    p2 = [
      targetXY[0] + axisX * sharedHandle,
      targetXY[1] + axisY * sharedHandle,
    ];
  } else {
    // Private fallback: small material/asymmetry on the chord normal.
    const materialSeed = hashUnit(`${variationSeed}:material`);
    const materialOffset = (materialSeed - 0.5) * 2;
    const materialMetres =
      0.12 * Math.min(bulge, EDGE_CURVE_MAX_BULGE_M) * materialOffset;
    const residual = bulge * lateralAtHandle * asym * 0.12;
    p2 = [
      targetXY[0] +
        axisX * sharedHandle +
        perpX * materialMetres +
        perpX * residual,
      targetXY[1] +
        axisY * sharedHandle +
        perpY * materialMetres +
        perpY * residual,
    ];
  }

  // Target approach unit (p3 - p2). Subject-bound: exact -axis.
  let approachX = targetXY[0] - p2[0];
  let approachY = targetXY[1] - p2[1];
  const approachLen = Math.hypot(approachX, approachY);
  if (approachLen > 0) {
    approachX /= approachLen;
    approachY /= approachLen;
  } else {
    approachX = -axisX;
    approachY = -axisY;
  }

  return {
    p0: sourceXY,
    p1,
    p2,
    p3: targetXY,
    targetApproach: [approachX, approachY],
    corridorAxis: [axisX, axisY],
    length,
  };
}

/**
 * Unit target-side approach vector in projected metres (from last handle toward
 * the target). Same subject id → nearly identical vectors.
 */
export function threadTargetApproachVector(
  source: LngLatTuple,
  target: LngLatTuple,
  options: ThreadCurveOptions = {},
): [number, number] {
  return threadCurveControlPointsProjected(source, target, options)
    .targetApproach;
}

/**
 * Tangent-direction rotation (degrees) a sampled span may still cover before
 * it is bisected again. A plain chord-deviation/"flatness" test is not
 * enough here: a subject-bound target approach can have a last handle whose
 * direction is independent of the incoming chord (by design — see
 * {@link threadTargetLocalCorridorAxis}), which can fold the curve back on
 * itself right before the target. That fold can sit almost exactly on the
 * chord (near-zero perpendicular deviation) while still reversing direction
 * close to 180° — flatness alone would call that span "flat". Comparing the
 * analytic tangent at both ends of a span catches it regardless of position.
 */
export const EDGE_CURVE_TANGENT_ANGLE_TOLERANCE_DEG = 20;

/**
 * Below this projected span length (metres), a residual tangent-angle
 * violation is no longer worth another bisection: a direction change
 * confined to a sub-few-metre stretch cannot be told apart from a single
 * point at any map zoom that ever renders a Faden. Without this floor,
 * adaptive refinement would keep consuming the sample budget chasing an
 * extreme but literally invisible corridor fold (observed on long
 * subject-bound approaches) instead of leaving that budget for genuinely
 * visible curvature elsewhere on the same thread.
 */
export const EDGE_CURVE_MIN_VISIBLE_SEGMENT_M = 5;

/**
 * Deterministic, curvature-adaptive Bezier parameter breakpoints for the
 * canonical thread curve. Starts from `minSamples` uniform points (never
 * fewer, so short curves still round-cap cleanly on a dead-straight chord),
 * then greedily bisects the single span whose analytic tangent rotates the
 * most across it — skipping spans already shorter than
 * {@link EDGE_CURVE_MIN_VISIBLE_SEGMENT_M} — until every remaining span is
 * within {@link EDGE_CURVE_TANGENT_ANGLE_TOLERANCE_DEG} or the hard
 * `maxSamples` budget is spent. Pure function of the four control points:
 * deterministic, no RNG, no physics, no per-frame work — called once per
 * path build, same as the rest of this module. Bounded cost: at most
 * `maxSamples - minSamples` bisection rounds, each `O(current length)`
 * tangent evaluations.
 */
export function threadCurveAdaptiveBreakpoints(
  p0: ProjectedPoint,
  p1: ProjectedPoint,
  p2: ProjectedPoint,
  p3: ProjectedPoint,
  minSamples: number = EDGE_CURVE_MIN_SAMPLES,
  maxSamples: number = EDGE_CURVE_MAX_SAMPLES,
  angleToleranceDeg: number = EDGE_CURVE_TANGENT_ANGLE_TOLERANCE_DEG,
  minVisibleSegmentM: number = EDGE_CURVE_MIN_VISIBLE_SEGMENT_M,
): number[] {
  const bounded = Math.max(2, Math.min(minSamples, maxSamples));
  const ts: number[] = new Array(bounded);
  for (let index = 0; index < bounded; index += 1) {
    ts[index] = index / (bounded - 1);
  }
  const pointAt = (t: number) => cubicBezierPoint2(p0, p1, p2, p3, t);
  const tangentAt = (t: number) => cubicBezierTangent2(p0, p1, p2, p3, t);
  while (ts.length < maxSamples) {
    let worstIndex = -1;
    let worstAngle = angleToleranceDeg;
    for (let index = 0; index < ts.length - 1; index += 1) {
      const a = ts[index];
      const b = ts[index + 1];
      const pointA = pointAt(a);
      const pointB = pointAt(b);
      const spanLength = Math.hypot(
        pointB[0] - pointA[0],
        pointB[1] - pointA[1],
      );
      // Already indistinguishable from a point on any real map — leave it,
      // even if its residual tangent angle is large (see doc comment above).
      if (spanLength <= minVisibleSegmentM) continue;
      const angle = angleBetweenDeg(tangentAt(a), tangentAt(b));
      if (angle > worstAngle) {
        worstAngle = angle;
        worstIndex = index;
      }
    }
    if (worstIndex < 0) break;
    ts.splice(worstIndex + 1, 0, (ts[worstIndex] + ts[worstIndex + 1]) / 2);
  }
  return ts;
}

/**
 * Bounded sample count for the canonical thread curve. Curvature-adaptive
 * (see {@link threadCurveAdaptiveBreakpoints}): a near-straight chord stays
 * near {@link EDGE_CURVE_MIN_SAMPLES}, a sharply bent one grows toward
 * {@link EDGE_CURVE_MAX_SAMPLES} — never beyond it.
 */
export function threadCurveSampleCount(
  source: LngLatTuple,
  target: LngLatTuple,
  options: ThreadCurveOptions = {},
): number {
  const { length } = projectedChord(source, target);
  if (!(length > 0) || !Number.isFinite(length)) return 2;
  const { p0, p1, p2, p3 } = threadCurveControlPointsProjected(
    source,
    target,
    options,
  );
  return threadCurveAdaptiveBreakpoints(p0, p1, p2, p3).length;
}

/**
 * Sample the canonical thread curve in both lon/lat and projected metres.
 * First and last GeoJSON points are exactly source and target. Projected
 * samples share antimeridian unwrap continuity with the Bezier plane.
 */
export function sampleThreadCurveWithProjected(
  source: LngLatTuple,
  target: LngLatTuple,
  options: ThreadCurveOptions = {},
): {
  samples: LngLatTuple[];
  projected: [number, number][];
} {
  const chord = projectedChord(source, target);
  const { length, sourceXY, targetXY } = chord;
  if (!(length > 0) || !Number.isFinite(length)) {
    return {
      samples: [
        [source[0], source[1]],
        [target[0], target[1]],
      ],
      projected: [
        [sourceXY[0], sourceXY[1]],
        [targetXY[0], targetXY[1]],
      ],
    };
  }
  const { p0, p1, p2, p3 } = threadCurveControlPointsProjected(
    source,
    target,
    options,
  );
  // Same curvature-adaptive breakpoints threadCurveSampleCount reports —
  // computed directly from the control points already built above instead of
  // calling that helper again, so the control points are solved exactly once.
  const ts = threadCurveAdaptiveBreakpoints(p0, p1, p2, p3);
  const count = ts.length;
  const samples: LngLatTuple[] = new Array(count);
  const projected: [number, number][] = new Array(count);
  for (let index = 0; index < count; index += 1) {
    if (index === 0) {
      samples[index] = [source[0], source[1]];
      projected[index] = [p0[0], p0[1]];
      continue;
    }
    if (index === count - 1) {
      samples[index] = [target[0], target[1]];
      // Use exact projected target (unwrapped) for arc continuity.
      projected[index] = [p3[0], p3[1]];
      continue;
    }
    const t = ts[index];
    const [x, y] = cubicBezierPoint2(p0, p1, p2, p3, t);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      // Fail closed: linear in projected plane + unwrapped lon/lat.
      projected[index] = [
        p0[0] + (p3[0] - p0[0]) * t,
        p0[1] + (p3[1] - p0[1]) * t,
      ];
      samples[index] = interpolateLngLatUnwrapped(source, target, t);
      continue;
    }
    projected[index] = [x, y];
    const lngLat = projectedSampleToLngLat(x, y);
    samples[index] = lngLat ?? interpolateLngLatUnwrapped(source, target, t);
  }
  return { samples, projected };
}

/**
 * Sample the canonical thread curve. First and last points are exactly source
 * and target (no float drift on endpoints). Intermediates come from projected
 * Bezier sampling on the short unwrapped longitude path.
 */
export function sampleThreadCurve(
  source: LngLatTuple,
  target: LngLatTuple,
  options: ThreadCurveOptions = {},
): LngLatTuple[] {
  return sampleThreadCurveWithProjected(source, target, options).samples;
}

/**
 * Cumulative arc lengths in projected Web-Mercator metres along aligned
 * projected samples. Degree-space hypot is intentionally not used.
 */
export function projectedPolylineArcState(
  projected: readonly ProjectedPoint[],
): { cumulative: number[]; total: number } {
  const cumulative = new Array(projected.length);
  cumulative[0] = 0;
  for (let index = 1; index < projected.length; index += 1) {
    const prev = projected[index - 1];
    const curr = projected[index];
    const dx = curr[0] - prev[0];
    const dy = curr[1] - prev[1];
    const step =
      Number.isFinite(dx) && Number.isFinite(dy) ? Math.hypot(dx, dy) : 0;
    cumulative[index] = cumulative[index - 1] + step;
  }
  return { cumulative, total: cumulative[cumulative.length - 1] ?? 0 };
}

/**
 * Degree-space arc fallback only when projected samples are unavailable.
 * Prefer {@link projectedPolylineArcState} / prebuilt {@link ThreadPathState}.
 * Exposed so tests can detect accidental degree-space regression at high lat / N-S.
 */
export function degreeSpacePolylineArcState(points: readonly LngLatTuple[]): {
  cumulative: number[];
  total: number;
} {
  const cumulative = new Array(points.length);
  cumulative[0] = 0;
  for (let index = 1; index < points.length; index += 1) {
    const prev = points[index - 1];
    const curr = points[index];
    const dLng = shortestLongitudeDelta(prev[0], curr[0]);
    const dLat = curr[1] - prev[1];
    cumulative[index] = cumulative[index - 1] + Math.hypot(dLng, dLat);
  }
  return { cumulative, total: cumulative[cumulative.length - 1] ?? 0 };
}

function polylineArcStateFromLngLat(points: readonly LngLatTuple[]): {
  cumulative: number[];
  total: number;
  projected: [number, number][];
} {
  // Project with unwrap continuity from the first point so antimeridian paths
  // stay short-path; arc metrics stay in metres even without a prebuilt state.
  const projected: [number, number][] = new Array(points.length);
  let unwrapBaseLng = points[0]?.[0] ?? 0;
  for (let index = 0; index < points.length; index += 1) {
    const [lng, lat] = points[index];
    const unwrapped =
      index === 0
        ? lng
        : unwrapBaseLng + shortestLongitudeDelta(unwrapBaseLng, lng);
    unwrapBaseLng = unwrapped;
    projected[index] = projectLngLatToMercator(unwrapped, lat);
  }
  const { cumulative, total } = projectedPolylineArcState(projected);
  return { cumulative, total, projected };
}

type ArcProgressState = {
  cumulative: readonly number[];
  total: number;
  projected?: readonly ProjectedPoint[];
};

function interpolateProjected(
  a: ProjectedPoint,
  b: ProjectedPoint,
  t: number,
): [number, number] {
  const bounded = clamp01(t);
  return [a[0] + (b[0] - a[0]) * bounded, a[1] + (b[1] - a[1]) * bounded];
}

/**
 * Point at arc-length progress in [0, 1] on a sampled polyline.
 * When `arc` carries projected metres (from {@link ThreadPathState}), progress
 * and tip interpolation use that prebuilt state — no degree-space hypot.
 */
export function pointAtArcProgress(
  points: readonly LngLatTuple[],
  progress: number,
  arc?: ArcProgressState,
): LngLatTuple {
  if (points.length === 0) {
    // No geometry: explicit empty guard (not a null-island sample).
    return [Number.NaN, Number.NaN];
  }
  if (points.length === 1) return [points[0][0], points[0][1]];
  const bounded = clamp01(progress);
  if (bounded <= 0) return [points[0][0], points[0][1]];
  if (bounded >= 1) {
    const last = points[points.length - 1];
    return [last[0], last[1]];
  }
  const state: ArcProgressState = arc ?? polylineArcStateFromLngLat(points);
  const { cumulative, total } = state;
  if (!(total > 0)) return [points[0][0], points[0][1]];
  const targetDist = bounded * total;
  for (let index = 1; index < points.length; index += 1) {
    if (cumulative[index] + 1e-15 < targetDist) continue;
    const span = cumulative[index] - cumulative[index - 1];
    const local = span > 0 ? (targetDist - cumulative[index - 1]) / span : 0;
    const projected = state.projected;
    if (projected && projected.length === points.length) {
      const xy = interpolateProjected(
        projected[index - 1],
        projected[index],
        local,
      );
      const ll = projectedSampleToLngLat(xy[0], xy[1]);
      if (ll) return ll;
    }
    return interpolateLngLatUnwrapped(points[index - 1], points[index], local);
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
  arc?: ArcProgressState,
): LngLatTuple[] {
  const start = clamp01(startProgress);
  const end = clamp01(endProgress);
  if (!(start < end) || points.length === 0) return [];
  if (points.length === 1) return [[points[0][0], points[0][1]]];

  const state: ArcProgressState = arc ?? polylineArcStateFromLngLat(points);
  const { cumulative, total } = state;
  if (!(total > 0)) {
    return [
      [points[0][0], points[0][1]],
      [points[points.length - 1][0], points[points.length - 1][1]],
    ];
  }

  const startDist = start * total;
  const endDist = end * total;
  const result: LngLatTuple[] = [];
  result.push(pointAtArcProgress(points, start, state));

  for (let index = 1; index < points.length - 1; index += 1) {
    const d = cumulative[index];
    if (d > startDist + 1e-12 && d < endDist - 1e-12) {
      result.push([points[index][0], points[index][1]]);
    }
  }

  const tip = pointAtArcProgress(points, end, state);
  const last = result[result.length - 1];
  if (
    !last ||
    Math.hypot(shortestLongitudeDelta(last[0], tip[0]), tip[1] - last[1]) >
      1e-12 ||
    result.length === 1
  ) {
    result.push(tip);
  }
  return result;
}

/** Instrumentation: how many canonical path states were built. */
let threadPathBuildSerial = 0;

/** Test-only: reset path-build instrumentation counter. */
export function resetThreadPathBuildSerialForTests(): void {
  threadPathBuildSerial = 0;
}

/** Test-only: read path-build instrumentation counter. */
export function getThreadPathBuildSerialForTests(): number {
  return threadPathBuildSerial;
}

function themeSegmentMetas(colors: readonly string[]): ThreadPathSegmentMeta[] {
  const palette = colors.slice(0, MAX_X_CORE_THEMES);
  if (palette.length <= 1) {
    return [
      {
        color: palette[0] ?? "#76523d",
        startProgress: 0,
        endProgress: 1,
      },
    ];
  }
  const segmentCount = palette.length * 2;
  const seamOverlap = themeSegmentSeamOverlapProgress(segmentCount);
  const metas: ThreadPathSegmentMeta[] = [];
  for (let index = 0; index < segmentCount; index += 1) {
    const t0 = index / segmentCount;
    const t1 = (index + 1) / segmentCount;
    const start =
      index === 0 ? t0 : Math.max(0, Math.min(t1, t0 - seamOverlap));
    const end = t1;
    if (!(start < end)) continue;
    metas.push({
      color: palette[index % palette.length],
      startProgress: start,
      endProgress: end,
    });
  }
  return metas;
}

/**
 * Build the immutable canonical path once (samples, projected arc lengths,
 * colour seams). Static projection and motion share this pure builder and the
 * same identity. Progress/clip/tip all read this prebuilt metre-space state.
 */
export function buildThreadPathState(
  source: LngLatTuple,
  target: LngLatTuple,
  colors: readonly string[] = [],
  options: ThreadCurveOptions = {},
): ThreadPathState {
  threadPathBuildSerial += 1;
  const { samples, projected } = sampleThreadCurveWithProjected(
    source,
    target,
    options,
  );
  const { cumulative, total } = projectedPolylineArcState(projected);
  const segments = themeSegmentMetas(colors);
  return {
    samples,
    projectedSamples: projected,
    cumulative,
    totalLength: total,
    segments,
    buildSerial: threadPathBuildSerial,
  };
}

/**
 * Clip a prebuilt path to arc progress [0, progress]. Does not resample Bezier
 * controls, does not recompute seams — only extracts visible polylines from the
 * shared projected arc state.
 */
export function clipThreadPathByProgress(
  path: ThreadPathState,
  progress: number,
): ThemedLineSegment[] {
  const bounded = clamp01(progress);
  if (bounded <= 0) return [];
  const arc: ArcProgressState = {
    cumulative: path.cumulative,
    total: path.totalLength,
    projected: path.projectedSamples,
  };
  const clipped: ThemedLineSegment[] = [];
  for (const meta of path.segments) {
    // Segments are ordered by progress; stop once the tip has not reached this
    // segment's painted start (after seam pullback).
    if (bounded <= meta.startProgress) break;
    const start = meta.startProgress;
    const end = Math.min(bounded, meta.endProgress);
    if (!(start < end)) continue;
    const coordinates = subPolylineByArcProgress(path.samples, start, end, arc);
    if (coordinates.length < 2) continue;
    clipped.push({ coordinates, color: meta.color });
  }
  return clipped;
}

/**
 * Controlled multi-theme braid along the *actual curve length*. Segment colour
 * boundaries are fixed in arc-length progress space so motion clipping never
 * walks seams. Adjacent multi-colour segments overlap by
 * {@link themeSegmentSeamOverlapProgress} (fraction of local segment length).
 * Samples the curve exactly once.
 */
export function buildThemedLineSegments(
  source: LngLatTuple,
  target: LngLatTuple,
  colors: readonly string[],
  options: ThreadCurveOptions = {},
): ThemedLineSegment[] {
  const path = buildThreadPathState(source, target, colors, options);
  return clipThreadPathByProgress(path, 1);
}

/**
 * Same stable full-path arc-length segments as {@link buildThemedLineSegments},
 * clipped to draw progress in [0, 1]. Prefer caching {@link buildThreadPathState}
 * across frames; this helper still samples only once per call.
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
  const path = buildThreadPathState(source, target, colors, options);
  return clipThreadPathByProgress(path, bounded);
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
    // One pure path build per edge: samples + seams once, then feature shells.
    const pathState = buildThreadPathState(
      sourceLngLat,
      targetLngLat,
      palette,
      curveOptions,
    );
    const segments = themeColors
      ? clipThreadPathByProgress(pathState, 1)
      : [
          {
            coordinates: pathState.samples as LngLatTuple[],
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
