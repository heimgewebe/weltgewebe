import type { Map as MapLibreMap, GeoJSONSource } from "maplibre-gl";
import type { Edge, MapEntityViewModel } from "$lib/map/types";
import { LAYERS } from "./layers";

export function updateEdges(
  map: MapLibreMap,
  edges: Edge[],
  points: MapEntityViewModel[],
  showEdges: boolean,
) {
  if (!map) return;

  const shouldShow = showEdges && edges.length > 0;
  const sourceId = LAYERS.EDGES_SOURCE;
  const layerId = LAYERS.EDGES_LAYER;
  const haloLayerId = LAYERS.EDGES_HALO_LAYER;

  const source = map.getSource(sourceId) as GeoJSONSource | undefined;

  // Build GeoJSON features
  const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
  if (shouldShow) {
    // Create a map for faster lookup (optimization)
    const pointMap = new Map(points.map((p) => [p.id, p]));

    for (const edge of edges) {
      const s = pointMap.get(edge.source_id);
      const t = pointMap.get(edge.target_id);

      if (s && t) {
        features.push({
          type: "Feature",
          geometry: {
            type: "LineString",
            coordinates: [
              [s.lon, s.lat],
              [t.lon, t.lat],
            ],
          },
          properties: {
            id: edge.id,
            kind: edge.edge_kind,
          },
        });
      }
    }
  }

  const geoJsonData: GeoJSON.FeatureCollection<GeoJSON.LineString> = {
    type: "FeatureCollection",
    features: features,
  };

  if (source) {
    source.setData(geoJsonData);
    ensureEdgeLayers(map, sourceId, layerId, haloLayerId);
  } else if (features.length > 0) {
    map.addSource(sourceId, {
      type: "geojson",
      data: geoJsonData,
    });
    ensureEdgeLayers(map, sourceId, layerId, haloLayerId);
  }
}

function ensureEdgeLayers(
  map: MapLibreMap,
  sourceId: string,
  layerId: string,
  haloLayerId: string,
) {
  // Insert edges below basemap symbols (labels, POIs) so they stay readable.
  const layers = map.getStyle()?.layers;
  let firstSymbolId: string | undefined;
  if (layers) {
    for (const layer of layers) {
      if (layer.type === "symbol") {
        firstSymbolId = layer.id;
        break;
      }
    }
  }

  const hasHalo = !!map.getLayer(haloLayerId);
  const hasMain = !!map.getLayer(layerId);

  // Common styling constants to prevent duplication drift
  const EDGE_DASHARRAY = [2, 1] as [number, number];
  const EDGE_JOIN = "round";
  const EDGE_CAP = "round";

  if (!hasHalo && !hasMain) {
    // Both missing: Insert halo first, then main (main ends up above halo)
    map.addLayer(
      {
        id: haloLayerId,
        type: "line",
        source: sourceId,
        layout: {
          "line-join": EDGE_JOIN,
          "line-cap": EDGE_CAP,
        },
        paint: {
          "line-color": "#ffffff",
          "line-width": 4,
          "line-opacity": 0.8,
          "line-dasharray": EDGE_DASHARRAY,
        },
      },
      firstSymbolId,
    );

    map.addLayer(
      {
        id: layerId,
        type: "line",
        source: sourceId,
        layout: {
          "line-join": EDGE_JOIN,
          "line-cap": EDGE_CAP,
        },
        paint: {
          "line-color": "#888",
          "line-width": 2,
          "line-dasharray": EDGE_DASHARRAY,
        },
      },
      firstSymbolId,
    );
  } else if (!hasHalo && hasMain) {
    // Only halo missing: Insert halo explicitly BEFORE the main layer so it sits beneath it
    map.addLayer(
      {
        id: haloLayerId,
        type: "line",
        source: sourceId,
        layout: {
          "line-join": EDGE_JOIN,
          "line-cap": EDGE_CAP,
        },
        paint: {
          "line-color": "#ffffff",
          "line-width": 4,
          "line-opacity": 0.8,
          "line-dasharray": EDGE_DASHARRAY,
        },
      },
      layerId,
    );
  } else if (hasHalo && !hasMain) {
    // Only main missing: Insert main explicitly AFTER the halo, or before firstSymbolId
    // Adding it before firstSymbolId is safe here, as halo is also before firstSymbolId.
    map.addLayer(
      {
        id: layerId,
        type: "line",
        source: sourceId,
        layout: {
          "line-join": EDGE_JOIN,
          "line-cap": EDGE_CAP,
        },
        paint: {
          "line-color": "#888",
          "line-width": 2,
          "line-dasharray": EDGE_DASHARRAY,
        },
      },
      firstSymbolId,
    );
  }
}
