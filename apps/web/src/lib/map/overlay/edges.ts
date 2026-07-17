import type {
  ExpressionSpecification,
  GeoJSONSource,
  LineLayerSpecification,
  Map as MapLibreMap,
} from "maplibre-gl";
import { edgeOpacityAt } from "$lib/map/edgeLifecycle";
import type { Edge, MapEntityViewModel } from "$lib/map/types";
import { LAYERS } from "./layers";

export function buildEdgeFeatures(
  edges: Edge[],
  points: MapEntityViewModel[],
  showEdges: boolean,
  nowMs: number,
): GeoJSON.Feature<GeoJSON.LineString>[] {
  if (!showEdges || edges.length === 0) return [];

  const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
  const pointMap = new Map(points.map((point) => [point.id, point]));

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
        opacity,
      },
    });
  }

  return features;
}

export function updateEdges(
  map: MapLibreMap,
  edges: Edge[],
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
  const haloOpacity: ExpressionSpecification = ["*", opacity, 0.8];
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
      "line-color": "#ffffff",
      "line-width": 4,
      "line-opacity": haloOpacity,
      "line-dasharray": [2, 1],
    },
  };
  const mainLayer: LineLayerSpecification = {
    id: layerId,
    type: "line",
    source: sourceId,
    layout: commonLayout,
    paint: {
      "line-color": "#888",
      "line-width": 2,
      "line-opacity": opacity,
      "line-dasharray": [2, 1],
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
