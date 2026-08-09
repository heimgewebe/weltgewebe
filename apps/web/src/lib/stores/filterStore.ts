import { derived, writable } from "svelte/store";
import type { KnottingTopic } from "$lib/knottingTopics";
import {
  countActiveMapContentFilters,
  createEmptyMapContentFilters,
  type MapContentFilters,
} from "$lib/map/contentFilters";

export const isFilterOpen = writable<boolean>(false);
export const mapContentFilters = writable<MapContentFilters>(
  createEmptyMapContentFilters(),
);
export const activeFilterCount = derived(
  mapContentFilters,
  countActiveMapContentFilters,
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

export function toggleFilterType(type: string) {
  mapContentFilters.update((filters) => {
    const contentTypes = new Set(filters.contentTypes);
    if (contentTypes.has(type)) {
      contentTypes.delete(type);
    } else {
      contentTypes.add(type);
    }
    return { ...filters, contentTypes };
  });
}

export function toggleFilterTopic(topic: KnottingTopic) {
  mapContentFilters.update((filters) => {
    const topics = new Set(filters.topics);
    if (topics.has(topic)) {
      topics.delete(topic);
    } else {
      topics.add(topic);
    }
    return { ...filters, topics };
  });
}

export function clearTopicFilters() {
  mapContentFilters.update((filters) => ({ ...filters, topics: new Set() }));
}

export function clearFilters() {
  mapContentFilters.set(createEmptyMapContentFilters());
}
