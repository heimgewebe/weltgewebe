export const MAP_MIN_ZOOM = 7;
export const GARNROLLE_FULL_SIZE_ZOOM = 13;
export const GARNROLLE_MIN_SCALE = 0.64;

/**
 * Keeps Garnrollen legible without letting them dominate a broad map view.
 * The smoothstep curve avoids visible size jumps while zooming.
 */
export function getGarnrolleMarkerScale(zoom: number): number {
  if (!Number.isFinite(zoom)) return 1;
  if (zoom <= MAP_MIN_ZOOM) return GARNROLLE_MIN_SCALE;
  if (zoom >= GARNROLLE_FULL_SIZE_ZOOM) return 1;

  const linearProgress =
    (zoom - MAP_MIN_ZOOM) / (GARNROLLE_FULL_SIZE_ZOOM - MAP_MIN_ZOOM);
  const smoothProgress =
    linearProgress * linearProgress * (3 - 2 * linearProgress);

  return GARNROLLE_MIN_SCALE + (1 - GARNROLLE_MIN_SCALE) * smoothProgress;
}
