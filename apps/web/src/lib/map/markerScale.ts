export const MAP_MIN_ZOOM = 7;
export const MAP_MARKER_REFERENCE_ZOOM = 13.5;
export const MAP_MAX_ZOOM = 18;
export const MAP_MARKER_MIN_SCALE = 0.62;
export const MAP_MARKER_MAX_SCALE = 1.3;

function smoothstep(progress: number): number {
  return progress * progress * (3 - 2 * progress);
}

/**
 * One damped world-scale contract for nodes, Webgemeindezentren and Garnrollen.
 * Both halves meet at scale 1 with a flat tangent, avoiding a visible step at
 * the compact/detail boundary while still allowing modest growth nearby.
 */
export function getMapMarkerScale(zoom: number): number {
  if (!Number.isFinite(zoom)) return 1;
  if (zoom <= MAP_MIN_ZOOM) return MAP_MARKER_MIN_SCALE;
  if (zoom >= MAP_MAX_ZOOM) return MAP_MARKER_MAX_SCALE;

  if (zoom < MAP_MARKER_REFERENCE_ZOOM) {
    const progress =
      (zoom - MAP_MIN_ZOOM) / (MAP_MARKER_REFERENCE_ZOOM - MAP_MIN_ZOOM);
    return (
      MAP_MARKER_MIN_SCALE + (1 - MAP_MARKER_MIN_SCALE) * smoothstep(progress)
    );
  }

  const progress =
    (zoom - MAP_MARKER_REFERENCE_ZOOM) /
    (MAP_MAX_ZOOM - MAP_MARKER_REFERENCE_ZOOM);
  return 1 + (MAP_MARKER_MAX_SCALE - 1) * smoothstep(progress);
}

/** @deprecated Use the shared map-object scale contract. */
export const GARNROLLE_FULL_SIZE_ZOOM = MAP_MARKER_REFERENCE_ZOOM;
/** @deprecated Use the shared map-object scale contract. */
export const GARNROLLE_MIN_SCALE = MAP_MARKER_MIN_SCALE;
/** @deprecated Use the shared map-object scale contract. */
export const getGarnrolleMarkerScale = getMapMarkerScale;
