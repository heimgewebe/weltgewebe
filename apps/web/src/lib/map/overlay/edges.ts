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

export const EDGE_VISUAL_STYLE = {
  haloColor: "#f5eadb",
  haloWidth: 5,
  haloBlur: 0.7,
  haloOpacityFactor: 0.72,
  mainColor: "#76523d",
  mainWidth: 2.25,
  dashArray: [1.4, 0.7] as [number, number],
  byType: {
    conversation: { width: 2.15, dashArray: [1.4, 0.7] },
    proposal: { width: 3.05, dashArray: [2.4, 0.28] },
    knotting: { width: 2.75, dashArray: [3.2, 0.2] },
    vote: { width: 1.85, dashArray: [0.35, 0.82] },
  },
} as const;

const EDGE_LAYER_VARIANTS = [
  {
    fadenType: "legacy",
    layerId: LAYERS.EDGES_LAYER,
    haloLayerId: LAYERS.EDGES_HALO_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.mainColor,
    width: EDGE_VISUAL_STYLE.mainWidth,
    dashArray: EDGE_VISUAL_STYLE.dashArray,
  },
  {
    fadenType: "conversation",
    layerId: LAYERS.EDGES_CONVERSATION_LAYER,
    haloLayerId: LAYERS.EDGES_CONVERSATION_HALO_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.mainColor,
    ...EDGE_VISUAL_STYLE.byType.conversation,
  },
  {
    fadenType: "proposal",
    layerId: LAYERS.EDGES_PROPOSAL_LAYER,
    haloLayerId: LAYERS.EDGES_PROPOSAL_HALO_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.mainColor,
    ...EDGE_VISUAL_STYLE.byType.proposal,
  },
  {
    fadenType: "knotting",
    layerId: LAYERS.EDGES_KNOTTING_LAYER,
    haloLayerId: LAYERS.EDGES_KNOTTING_HALO_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.mainColor,
    ...EDGE_VISUAL_STYLE.byType.knotting,
  },
  {
    fadenType: "vote",
    layerId: LAYERS.EDGES_VOTE_LAYER,
    haloLayerId: LAYERS.EDGES_VOTE_HALO_LAYER,
    fallbackColor: EDGE_VISUAL_STYLE.mainColor,
    ...EDGE_VISUAL_STYLE.byType.vote,
  },
] as const;

/**
 * Every layer a complete typed Faden style owns, derived from the variants
 * themselves so a new thread type cannot be forgotten here. Halo before line,
 * matching the render order.
 */
export const EDGE_THREAD_LAYER_IDS: readonly string[] =
  EDGE_LAYER_VARIANTS.flatMap((variant) => [
    variant.haloLayerId,
    variant.layerId,
  ]);

/** Minimal surface a style-readiness check needs; keeps it unit-testable. */
export type EdgeStyleProbe = {
  getSource: (id: string) => unknown;
  getLayer: (id: string) => unknown;
};

/**
 * The edge style counts as fully rehydrated only when the shared source and
 * *every* canonical halo and line layer exist. Checking the source plus two
 * legacy layers would call a half-restored style ready and silently drop the
 * typed threads after a style switch.
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

/**
 * Controlled multi-theme braid: the line is subdivided into a bounded number of
 * equal segments whose colours cycle through the target palette (max four).
 * One theme stays a single solid feature. No rainbow blend and no extra layers.
 */
export function buildThemedLineSegments(
  source: [number, number],
  target: [number, number],
  colors: readonly string[],
): Array<{ coordinates: [[number, number], [number, number]]; color: string }> {
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
  const segments: Array<{
    coordinates: [[number, number], [number, number]];
    color: string;
  }> = [];
  for (let index = 0; index < segmentCount; index += 1) {
    const t0 = index / segmentCount;
    const t1 = (index + 1) / segmentCount;
    segments.push({
      coordinates: [
        [
          source[0] + (target[0] - source[0]) * t0,
          source[1] + (target[1] - source[1]) * t0,
        ],
        [
          source[0] + (target[0] - source[0]) * t1,
          source[1] + (target[1] - source[1]) * t1,
        ],
      ],
      color: palette[index % palette.length],
    });
  }
  return segments;
}

export function buildEdgeFeatures(
  edges: MapEdge[],
  points: MapEntityViewModel[],
  showEdges: boolean,
  nowMs: number,
): GeoJSON.Feature<GeoJSON.LineString>[] {
  if (!showEdges || edges.length === 0) return [];

  const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
  const pointMap = new Map<string, MapEntityViewModel>();
  for (const point of points) {
    pointMap.set(point.id, point);
    if (point.type === "webgemeindezentrum") {
      pointMap.set(point.faden_endpoint_id, point);
    }
  }

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
  const haloOpacity: ExpressionSpecification = [
    "*",
    opacity,
    EDGE_VISUAL_STYLE.haloOpacityFactor,
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
    const haloLayer: LineLayerSpecification = {
      id: variant.haloLayerId,
      type: "line",
      source: sourceId,
      filter,
      layout: commonLayout,
      paint: {
        "line-color": EDGE_VISUAL_STYLE.haloColor,
        "line-width": variant.width + 2.75,
        "line-blur": EDGE_VISUAL_STYLE.haloBlur,
        "line-opacity": haloOpacity,
        "line-dasharray": dashArray,
      },
    };
    const mainLayer: LineLayerSpecification = {
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
        "line-width": variant.width,
        "line-opacity": opacity,
        "line-dasharray": dashArray,
      },
    };
    return [haloLayer, mainLayer];
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

  for (let index = 0; index < specifications.length; index += 2) {
    const haloLayer = specifications[index];
    const mainLayer = specifications[index + 1];
    const hasHalo = Boolean(map.getLayer(haloLayer.id));
    const hasMain = Boolean(map.getLayer(mainLayer.id));

    if (!hasHalo) {
      map.addLayer(haloLayer, hasMain ? mainLayer.id : firstSymbolId);
    }
    if (!hasMain) {
      map.addLayer(mainLayer, firstSymbolId);
    }
  }
}
