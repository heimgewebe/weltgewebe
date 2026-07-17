import { writable } from "svelte/store";

export type MapFan = "tools" | "governance";

export const expandedMapFan = writable<MapFan | null>(null);

export function toggleMapFan(fan: MapFan): void {
  expandedMapFan.update((current) => (current === fan ? null : fan));
}

export function closeMapFan(fan?: MapFan): void {
  expandedMapFan.update((current) =>
    !fan || current === fan ? null : current,
  );
}
