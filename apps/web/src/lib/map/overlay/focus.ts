import type { Map as MapLibreMap, MapMouseEvent } from "maplibre-gl";
import { leaveToNavigation } from "$lib/stores/uiView";

export function setupFocusInteraction(
  map: MapLibreMap,
  getSystemState: () => string,
) {
  const handleClick = (e: MapMouseEvent) => {
    const markerClicked =
      e.originalEvent.target instanceof HTMLElement &&
      e.originalEvent.target.closest(".map-marker");

    // Exit focus if the user clicks the map but *not* on a marker.
    // We intentionally do not use `queryRenderedFeatures()` globally
    // here because a rich vector basemap might return features (like roads or parks)
    // everywhere, preventing the empty map click exit.
    if (!markerClicked) {
      if (getSystemState() === "fokus") {
        leaveToNavigation();
      }
      // Explicitly do not close 'komposition' on an empty map click to protect the workflow.
      // A workflow should only be aborted by intentional cancel actions (e.g. close panel).
    }
  };

  map.on("click", handleClick);

  return () => {
    map.off("click", handleClick);
  };
}
