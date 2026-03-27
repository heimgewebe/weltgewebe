import type { Map as MapLibreMap, GeoJSONSource } from "maplibre-gl";
import type { RenderableMapPoint } from "$lib/map/types";
import { LAYERS } from "./layers";

export function updateActivity(map: MapLibreMap, points: RenderableMapPoint[]) {
  if (!map) return;

  const sourceId = LAYERS.ACTIVITY_SOURCE;
  const layerId = LAYERS.ACTIVITY_LAYER;

  const source = map.getSource(sourceId) as GeoJSONSource | undefined;

  const features: GeoJSON.Feature<GeoJSON.Point>[] = points.map((p) => ({
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [p.lon, p.lat],
    },
    properties: {
      id: p.id,
      kind: p.kind || "node",
    },
  }));

  const geoJsonData: GeoJSON.FeatureCollection<GeoJSON.Point> = {
    type: "FeatureCollection",
    features: features,
  };

  if (source) {
    source.setData(geoJsonData);
  } else {
    map.addSource(sourceId, {
      type: "geojson",
      data: geoJsonData,
    });
  }

  ensureActivityLayer(map, sourceId, layerId);
}

function ensureActivityLayer(
  map: MapLibreMap,
  sourceId: string,
  layerId: string,
) {
  const hasLayer = !!map.getLayer(layerId);

  if (hasLayer) return;

  const layers = map.getStyle()?.layers;
  let beforeId: string | undefined;
  if (layers) {
    // Priority: place heatmap below edge layers to ensure edges are visible over density
    for (const layer of layers) {
      if (
        layer.id === LAYERS.EDGES_HALO_LAYER ||
        layer.id === LAYERS.EDGES_LAYER
      ) {
        beforeId = layer.id;
        break;
      } else if (!beforeId && layer.type === "symbol") {
        // Fallback: place below the first symbol layer (e.g., place labels)
        beforeId = layer.id;
      }
    }
  }

  // Activity density is rendered as a heatmap
  map.addLayer(
    {
      id: layerId,
      type: "heatmap",
      source: sourceId,
      maxzoom: 17,
      paint: {
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 0, 1, 17, 3],
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0,
          "rgba(33,102,172,0)",
          0.2,
          "rgba(103,169,207,0.5)",
          0.4,
          "rgba(209,229,240,0.6)",
          0.6,
          "rgba(253,219,199,0.7)",
          0.8,
          "rgba(239,138,98,0.8)",
          1,
          "rgba(178,24,43,0.9)",
        ],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 0, 5, 17, 40],
        "heatmap-opacity": [
          "interpolate",
          ["linear"],
          ["zoom"],
          12,
          0.8,
          16,
          0.6,
          17,
          0,
        ],
      },
    },
    beforeId,
  );
}
