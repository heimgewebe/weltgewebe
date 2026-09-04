import type { Map as MapLibreMap, MapMouseEvent } from "maplibre-gl";
import { leaveToNavigation } from "$lib/stores/uiView";

type DomainFeatureHitTest = (point: MapMouseEvent["point"]) => boolean;

export function setupFocusInteraction(
  map: MapLibreMap,
  getSystemState: () => string,
  isDomainFeatureAtPoint: DomainFeatureHitTest = () => false,
) {
  const handleClick = (e: MapMouseEvent) => {
    const domMarkerClicked =
      e.originalEvent.target instanceof HTMLElement &&
      e.originalEvent.target.closest(".map-marker");
    const domainFeatureClicked = isDomainFeatureAtPoint(e.point);

    // Exit focus if the user clicks the map but *not* on a domain entity.
    // DOM markers remain directly detectable. Dense native MapLibre entities
    // use the injected, layer-bounded hit test so we still avoid a global
    // `queryRenderedFeatures()` call against arbitrary basemap features.
    if (!domMarkerClicked && !domainFeatureClicked) {
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
