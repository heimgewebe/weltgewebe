import type { AuthStatus } from "$lib/auth/store";
import { authStore } from "$lib/auth/store";
import type { MapEntityViewModel } from "$lib/map/types";
import type { Map as MapLibreMap } from "maplibre-gl";

export interface AuthCameraConvergenceState {
  hasExplicitFocus: boolean;
  userMovedMap: boolean;
  alreadyApplied: boolean;
}

interface CameraReader {
  getCenter(): { lng: number; lat: number };
  getZoom(): number;
}

export function shouldApplyOwnGarnrolleCamera(
  state: AuthCameraConvergenceState,
  auth: AuthStatus,
): boolean {
  return (
    !state.hasExplicitFocus &&
    !state.userMovedMap &&
    !state.alreadyApplied &&
    auth.state === "authenticated" &&
    auth.authenticated &&
    typeof auth.account_id === "string"
  );
}

/**
 * Compare against the camera used at map construction so movement that happens
 * before the delayed auth module loads still blocks a later recenter.
 */
export function hasMapCameraChanged(
  map: CameraReader,
  initialCenter: [number, number],
  initialZoom: number,
): boolean {
  const center = map.getCenter();
  const epsilon = 1e-7;
  return (
    Math.abs(center.lng - initialCenter[0]) > epsilon ||
    Math.abs(center.lat - initialCenter[1]) > epsilon ||
    Math.abs(map.getZoom() - initialZoom) > epsilon
  );
}

export function installAuthCameraConvergence(
  map: MapLibreMap,
  markers: MapEntityViewModel[],
  initialCenter: [number, number],
  initialZoom: number,
): () => void {
  let alreadyApplied = false;
  const unsubscribe = authStore.subscribe((status) => {
    if (
      !shouldApplyOwnGarnrolleCamera(
        {
          hasExplicitFocus: false,
          userMovedMap: hasMapCameraChanged(map, initialCenter, initialZoom),
          alreadyApplied,
        },
        status,
      )
    ) {
      return;
    }
    const own = markers.find(
      (marker) =>
        marker.type === "garnrolle" &&
        marker.id === status.account_id &&
        Number.isFinite(marker.lat) &&
        marker.lat >= -90 &&
        marker.lat <= 90 &&
        Number.isFinite(marker.lon) &&
        marker.lon >= -180 &&
        marker.lon <= 180,
    );
    if (!own) return;
    alreadyApplied = true;
    map.jumpTo({
      center: [own.lon, own.lat],
      zoom: Math.max(map.getZoom(), 14),
    });
  });
  return unsubscribe;
}
