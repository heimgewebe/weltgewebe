import type * as maplibregl from "maplibre-gl";
import { getContext, setContext } from "svelte";
import { writable, type Writable } from "svelte/store";

export const MAP_CONTEXT_KEY = Symbol("maplibre-context");

export type MapContextValue = {
  map: Writable<maplibregl.Map | null>;
  maplibre: typeof import("maplibre-gl") | null;
};

export function initMapContext(): MapContextValue {
  const value: MapContextValue = {
    map: writable<maplibregl.Map | null>(null),
    maplibre: null,
  };

  setContext(MAP_CONTEXT_KEY, value);
  return value;
}

export function useMapContext(): MapContextValue {
  const context = getContext<MapContextValue | undefined>(MAP_CONTEXT_KEY);

  if (!context) {
    throw new Error(
      "MapLibre components must be used inside a <MapLibre> container.",
    );
  }

  return context;
}
