import { derived, writable } from "svelte/store";
import type { KnottingTopic } from "$lib/knottingTopics";

export interface MapFilterState {
  contentTypes: Set<string>;
  topics: Set<KnottingTopic>;
}

function emptyFilterState(): MapFilterState {
  return {
    contentTypes: new Set(),
    topics: new Set(),
  };
}

export const isFilterOpen = writable<boolean>(false);
export const filterState = writable<MapFilterState>(emptyFilterState());
export const activeFilterCount = derived(
  filterState,
  ({ contentTypes, topics }) => contentTypes.size + topics.size,
);

export function toggleFilter() {
  isFilterOpen.update((v) => !v);
}

/**
 * Opens the filter overlay unconditionally. Used by URL deep-link addressing,
 * which must never toggle (a toggle could close an already-open overlay).
 */
export function openFilter() {
  isFilterOpen.set(true);
}

export function closeFilter() {
  isFilterOpen.set(false);
}

export function toggleContentType(type: string) {
  filterState.update((state) => {
    const contentTypes = new Set(state.contentTypes);
    if (contentTypes.has(type)) {
      contentTypes.delete(type);
    } else {
      contentTypes.add(type);
    }
    return { ...state, contentTypes };
  });
}

export function toggleTopic(topic: KnottingTopic) {
  filterState.update((state) => {
    const topics = new Set(state.topics);
    if (topics.has(topic)) {
      topics.delete(topic);
    } else {
      topics.add(topic);
    }
    return { ...state, topics };
  });
}

export function clearFilters() {
  filterState.set(emptyFilterState());
}
