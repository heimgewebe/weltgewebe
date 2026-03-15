import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
import type { Edge, RenderableMapPoint } from '../../../routes/map/types';
import { LAYERS } from './layers';

export function updateEdges(map: MapLibreMap, edges: Edge[], points: RenderableMapPoint[], showEdges: boolean) {
    if (!map) return;

    const shouldShow = showEdges && edges.length > 0;
    const sourceId = LAYERS.EDGES_SOURCE;
    const layerId = LAYERS.EDGES_LAYER;

    const source = map.getSource(sourceId) as GeoJSONSource | undefined;

    // Build GeoJSON features
    const features: GeoJSON.Feature<GeoJSON.LineString>[] = [];
    if (shouldShow) {
      // Create a map for faster lookup (optimization)
      const pointMap = new Map(points.map(p => [p.id, p]));

      for (const edge of edges) {
        const s = pointMap.get(edge.source_id);
        const t = pointMap.get(edge.target_id);

        if (s && t) {
          features.push({
            type: 'Feature',
            geometry: {
              type: 'LineString',
              coordinates: [
                [s.lon, s.lat],
                [t.lon, t.lat]
              ]
            },
            properties: {
              id: edge.id,
              kind: edge.edge_kind
            }
          });
        }
      }
    }

    const geoJsonData: GeoJSON.FeatureCollection<GeoJSON.LineString> = {
      type: 'FeatureCollection',
      features: features
    };

    if (source) {
      source.setData(geoJsonData);
    } else if (features.length > 0) {
      map.addSource(sourceId, {
        type: 'geojson',
        data: geoJsonData
      });

      map.addLayer({
        id: layerId,
        type: 'line',
        source: sourceId,
        layout: {
          'line-join': 'round',
          'line-cap': 'round'
        },
        paint: {
          'line-color': '#888',
          'line-width': 2,
          'line-dasharray': [2, 1]
        }
      });
    }
}
