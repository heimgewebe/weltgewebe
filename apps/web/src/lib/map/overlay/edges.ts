import type {
  ExpressionSpecification,
  GeoJSONSource,
  LineLayerSpecification,
  Map as MapLibreMap,
} from "maplibre-gl";
import { edgeOpacityAt } from "$lib/map/edgeLifecycle";
import type { MapEdge, MapEntityViewModel } from "$lib/map/types";
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
    conversation: { color: "#76523d", width: 2.15, dashArray: [1.4, 0.7] },
    proposal: { color: "#68402f", width: 3.05, dashArray: [2.4, 0.28] },
    knotting: { color: "#7b4f30", width: 2.75, dashArray: [3.2, 0.2] },
    vote: { color: "#5f463d", width: 1.85, dashArray: [0.35, 0.82] },
  },
} as const;

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
    if (!source || !target) continue;

    features.push({
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [source.lon, source.lat],
          [target.lon, target.lat],
        ],
      },
      properties: {
        id: edge.id,
        kind: edge.edge_kind,
        fadenType: edge.faden_type ?? "legacy",
        fadenSubjectId: edge.faden_subject_id ?? null,
        opacity,
      },
    });
  }

  return features;
}

export function updateEdges(
  map: MapLibreMap,
  edges: MapEdge[],
  points: MapEntityViewModel[],
  showEdges: boolean,
  nowMs = Date.now(),
) {
  const sourceId = LAYERS.EDGES_SOURCE;
  const layerId = LAYERS.EDGES_LAYER;
  const haloLayerId = LAYERS.EDGES_HALO_LAYER;
  const source = map.getSource(sourceId) as GeoJSONSource | undefined;
  const features = buildEdgeFeatures(edges, points, showEdges, nowMs);
  const geoJsonData: GeoJSON.FeatureCollection<GeoJSON.LineString> = {
    type: "FeatureCollection",
    features,
  };

  if (source) {
    source.setData(geoJsonData);
    ensureEdgeLayers(map, sourceId, layerId, haloLayerId);
  } else if (features.length > 0) {
    map.addSource(sourceId, { type: "geojson", data: geoJsonData });
    ensureEdgeLayers(map, sourceId, layerId, haloLayerId);
  }
}

function ensureEdgeLayers(
  map: MapLibreMap,
  sourceId: string,
  layerId: string,
  haloLayerId: string,
) {
  const firstSymbolId = map
    .getStyle()
    ?.layers?.find((layer) => layer.type === "symbol")?.id;
  const hasHalo = Boolean(map.getLayer(haloLayerId));
  const hasMain = Boolean(map.getLayer(layerId));

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
  const fadenType: ExpressionSpecification = [
    "coalesce",
    ["get", "fadenType"],
    "legacy",
  ];
  const mainColor: ExpressionSpecification = [
    "match",
    fadenType,
    "conversation",
    EDGE_VISUAL_STYLE.byType.conversation.color,
    "proposal",
    EDGE_VISUAL_STYLE.byType.proposal.color,
    "knotting",
    EDGE_VISUAL_STYLE.byType.knotting.color,
    "vote",
    EDGE_VISUAL_STYLE.byType.vote.color,
    EDGE_VISUAL_STYLE.mainColor,
  ];
  const mainWidth: ExpressionSpecification = [
    "match",
    fadenType,
    "conversation",
    EDGE_VISUAL_STYLE.byType.conversation.width,
    "proposal",
    EDGE_VISUAL_STYLE.byType.proposal.width,
    "knotting",
    EDGE_VISUAL_STYLE.byType.knotting.width,
    "vote",
    EDGE_VISUAL_STYLE.byType.vote.width,
    EDGE_VISUAL_STYLE.mainWidth,
  ];
  const dashArray: ExpressionSpecification = [
    "match",
    fadenType,
    "conversation",
    ["literal", EDGE_VISUAL_STYLE.byType.conversation.dashArray],
    "proposal",
    ["literal", EDGE_VISUAL_STYLE.byType.proposal.dashArray],
    "knotting",
    ["literal", EDGE_VISUAL_STYLE.byType.knotting.dashArray],
    "vote",
    ["literal", EDGE_VISUAL_STYLE.byType.vote.dashArray],
    ["literal", EDGE_VISUAL_STYLE.dashArray],
  ];
  const haloWidth: ExpressionSpecification = ["+", mainWidth, 2.75];
  const commonLayout: LineLayerSpecification["layout"] = {
    "line-join": "round",
    "line-cap": "round",
  };
  const haloLayer: LineLayerSpecification = {
    id: haloLayerId,
    type: "line",
    source: sourceId,
    layout: commonLayout,
    paint: {
      "line-color": EDGE_VISUAL_STYLE.haloColor,
      "line-width": haloWidth,
      "line-blur": EDGE_VISUAL_STYLE.haloBlur,
      "line-opacity": haloOpacity,
      "line-dasharray": dashArray,
    },
  };
  const mainLayer: LineLayerSpecification = {
    id: layerId,
    type: "line",
    source: sourceId,
    layout: commonLayout,
    paint: {
      "line-color": mainColor,
      "line-width": mainWidth,
      "line-opacity": opacity,
      "line-dasharray": dashArray,
    },
  };

  if (!hasHalo && !hasMain) {
    map.addLayer(haloLayer, firstSymbolId);
    map.addLayer(mainLayer, firstSymbolId);
  } else if (!hasHalo && hasMain) {
    map.addLayer(haloLayer, layerId);
  } else if (hasHalo && !hasMain) {
    map.addLayer(mainLayer, firstSymbolId);
  }
}
