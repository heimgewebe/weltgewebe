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
  /** Yarn braid rhythm for untyped/legacy threads. */
  dashArray: [1.55, 0.72] as [number, number],
  byType: {
    // Soft conversational yarn: slightly thinner, open braid.
    conversation: { width: 2.2, dashArray: [1.55, 0.85] as [number, number] },
    // Proposal: broader strand with longer weave units.
    proposal: { width: 3.1, dashArray: [2.55, 0.38] as [number, number] },
    // Knotting: denser, almost continuous twist.
    knotting: { width: 2.85, dashArray: [2.95, 0.28] as [number, number] },
    // Votes: short outer stitches, never a solid road dash.
    vote: { width: 1.9, dashArray: [0.42, 0.9] as [number, number] },
  },
  // Back-compat aliases used by older call sites/tests.
  haloColor: "rgba(36, 22, 15, 0.42)",
  haloWidth: 2.9,
  haloBlur: 1.05,
  haloOpacityFactor: 0.58,
  mainColor: "#76523d",
  mainWidth: 2.35,
} as const;

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

export type ThemedLineSegment = {
  coordinates: [[number, number], [number, number]];
  color: string;
};

function interpolateLngLat(
  source: [number, number],
  target: [number, number],
  progress: number,
): [number, number] {
  const bounded = Math.max(0, Math.min(1, progress));
  return [
    source[0] + (target[0] - source[0]) * bounded,
    source[1] + (target[1] - source[1]) * bounded,
  ];
}

/**
 * Controlled multi-theme braid: the line is subdivided into a bounded number of
 * equal segments whose colours cycle through the target palette (max four).
 * One theme stays a single solid feature. No rainbow blend and no extra layers.
 * Segment boundaries are fixed along the full path so motion clipping never
 * walks colour seams frame-by-frame. Adjacent multi-colour segments overlap by
 * {@link themeSegmentSeamOverlapProgress} (fraction of local segment length,
 * trailing/start side only) to close proven WebGL hairline joins under round
 * line-caps without growing colour bands with full path length.
 */
export function buildThemedLineSegments(
  source: [number, number],
  target: [number, number],
  colors: readonly string[],
): ThemedLineSegment[] {
  const palette = colors.slice(0, MAX_X_CORE_THEMES);
  if (palette.length <= 1) {
    return [
      {
        coordinates: [source, target],
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
    segments.push({
      coordinates: [
        interpolateLngLat(source, target, start),
        interpolateLngLat(source, target, end),
      ],
      color: palette[index % palette.length],
    });
  }
  return segments;
}

/**
 * Same stable full-path segments as {@link buildThemedLineSegments}, clipped to
 * the draw progress in [0, 1] measured from source toward target. Colour
 * boundaries stay fixed; only the visible length changes.
 */
export function buildProgressClippedThemeSegments(
  source: [number, number],
  target: [number, number],
  colors: readonly string[],
  progress: number,
): ThemedLineSegment[] {
  const bounded = Math.max(0, Math.min(1, progress));
  if (bounded <= 0) return [];
  const full = buildThemedLineSegments(source, target, colors);
  if (bounded >= 1) return full;

  const palette = colors.slice(0, MAX_X_CORE_THEMES);
  if (palette.length <= 1) {
    return [
      {
        coordinates: [source, interpolateLngLat(source, target, bounded)],
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
    // One-sided backward overlap closes the prior join; never draw past
    // `bounded` and never extend the nominal end into the next colour.
    const start =
      index === 0 ? t0 : Math.max(0, Math.min(t1, t0 - seamOverlap));
    const end = Math.min(bounded, t1);
    if (!(start < end)) continue;
    clipped.push({
      coordinates: [
        interpolateLngLat(source, target, start),
        interpolateLngLat(source, target, end),
      ],
      color: full[index].color,
    });
  }
  return clipped;
}

/** Structural paint values shared by static threads and edge motion. */
export function edgeThreadVisual(fadenType: string | undefined): {
  width: number;
  dashArray: [number, number];
} {
  if (fadenType && fadenType in EDGE_VISUAL_STYLE.byType) {
    const style =
      EDGE_VISUAL_STYLE.byType[
        fadenType as keyof typeof EDGE_VISUAL_STYLE.byType
      ];
    return {
      width: style.width,
      dashArray: [...style.dashArray] as [number, number],
    };
  }
  return {
    width: EDGE_VISUAL_STYLE.bodyWidth,
    dashArray: [...EDGE_VISUAL_STYLE.dashArray] as [number, number],
  };
}

/**
 * Canonical thread variants used by both static projection and motion overlay.
 * Layer ids remain source-specific; structure (type, width, dash) is shared so
 * the two paths cannot drift.
 */
export const EDGE_THREAD_VARIANTS = EDGE_LAYER_VARIANTS.map((variant) => ({
  fadenType: variant.fadenType,
  width: variant.width,
  dashArray: [...variant.dashArray] as [number, number],
  fallbackColor: variant.fallbackColor,
})) as ReadonlyArray<{
  fadenType: (typeof EDGE_LAYER_VARIANTS)[number]["fadenType"];
  width: number;
  dashArray: [number, number];
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

    const themeColors = targetThemeColors(target);
    const palette = themeColors ?? [];
    const segments = themeColors
      ? buildThemedLineSegments(
          [source.lon, source.lat],
          [target.lon, target.lat],
          themeColors,
        )
      : [
          {
            coordinates: [
              [source.lon, source.lat],
              [target.lon, target.lat],
            ] as [[number, number], [number, number]],
            color: undefined as string | undefined,
          },
        ];

    for (let strand = 0; strand < segments.length; strand += 1) {
      const segment = segments[strand];
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
      paint: {
        "line-color": EDGE_VISUAL_STYLE.shadowColor,
        "line-width": bodyWidth + EDGE_VISUAL_STYLE.shadowWidthExtra,
        "line-blur": EDGE_VISUAL_STYLE.shadowBlur,
        "line-opacity": shadowOpacity,
        "line-dasharray": dashArray,
      },
    };
    const bodyLayer: LineLayerSpecification = {
      id: variant.layerId,
      type: "line",
      source: sourceId,
      filter,
      layout: commonLayout,
      paint: {
        "line-color": [
          "coalesce",
          ["get", "themeColor"],
          variant.fallbackColor,
        ],
        "line-width": bodyWidth,
        "line-opacity": opacity,
        "line-dasharray": dashArray,
      },
    };
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
