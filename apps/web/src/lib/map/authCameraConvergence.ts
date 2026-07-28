import { get } from "svelte/store";
import { page } from "$app/stores";
import type { AuthStatus } from "$lib/auth/store";
import { authStore } from "$lib/auth/store";
import type { MapEntityViewModel } from "$lib/map/types";
import { parseMapUrlState } from "$lib/map/urlState";
import type { Map as MapLibreMap } from "maplibre-gl";

export interface AuthCameraConvergenceState {
  hasExplicitFocus: boolean;
  userMovedMap: boolean;
  alreadyApplied: boolean;
}

interface AuthStatusSource {
  subscribe(run: (status: AuthStatus) => void): () => void;
}

export interface AuthCameraConvergenceDependencies {
  store?: AuthStatusSource;
  hasExplicitFocus?: () => boolean;
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
  userMovedMap: () => boolean,
  dependencies: AuthCameraConvergenceDependencies = {},
): () => void {
  let alreadyApplied = false;
  const source = dependencies.store ?? authStore;
  const hasExplicitFocus =
    dependencies.hasExplicitFocus ??
    (() => Boolean(parseMapUrlState(get(page).url.searchParams).focus));
  return source.subscribe((status) => {
    if (
      !shouldApplyOwnGarnrolleCamera(
        {
          hasExplicitFocus: hasExplicitFocus(),
          userMovedMap: userMovedMap(),
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
}
