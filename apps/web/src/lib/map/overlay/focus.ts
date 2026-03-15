import type { Map as MapLibreMap } from 'maplibre-gl';
import { leaveToNavigation } from '$lib/stores/uiView';

export function setupFocusInteraction(map: MapLibreMap, getSystemState: () => string) {
  const handleClick = (e: any) => {
    const features = map?.queryRenderedFeatures(e.point);
    const markerClicked = e.originalEvent.target instanceof HTMLElement && e.originalEvent.target.closest('.map-marker');

    if (!features?.length && !markerClicked) {
       if (getSystemState() === 'fokus') {
           leaveToNavigation();
       }
       // Explicitly do not close 'komposition' on an empty map click to protect the workflow.
       // A workflow should only be aborted by intentional cancel actions (e.g. close panel).
    }
  };

  map.on('click', handleClick);

  return () => {
    map.off('click', handleClick);
  };
}
