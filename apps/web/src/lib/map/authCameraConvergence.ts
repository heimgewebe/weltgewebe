import type { AuthStatus } from "$lib/auth/store";
import { authStore } from "$lib/auth/store";
import type { MapEntityViewModel } from "$lib/map/types";
import type { Map as MapLibreMap } from "maplibre-gl";

export interface AuthCameraConvergenceState {
  hasExplicitFocus: boolean;
  userMovedMap: boolean;
  alreadyApplied: boolean;
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

export function installAuthCameraConvergence(
  map: MapLibreMap,
  markers: MapEntityViewModel[],
): () => void {
  let userMovedMap = false;
  let alreadyApplied = false;
  const markUserMove = (event: { originalEvent?: unknown }) => {
    if (event.originalEvent) userMovedMap = true;
  };
  map.on("movestart", markUserMove);
  const unsubscribe = authStore.subscribe((status) => {
    if (
      !shouldApplyOwnGarnrolleCamera(
        {
          hasExplicitFocus: false,
          userMovedMap,
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
  return () => {
    unsubscribe();
    map.off("movestart", markUserMove);
  };
}
